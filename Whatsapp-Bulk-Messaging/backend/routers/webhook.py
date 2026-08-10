import logging
import mimetypes
from pathlib import Path
from fastapi import APIRouter, Request, Response, HTTPException
from database import db_cursor, now, get_setting
import config
import whatsapp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("")
def verify_webhook(request: Request):
    """Meta's webhook verification handshake."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    expected = get_setting("whatsapp_verify_token") or config.WHATSAPP_VERIFY_TOKEN
    if mode == "subscribe" and token == expected:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(403, "Verification failed")


@router.post("")
async def receive_webhook(request: Request):
    payload = await request.json()
    event = whatsapp.parse_incoming(payload)
    if not event:
        return {"status": "ignored"}

    if event["kind"] == "message":
        _handle_incoming_message(event)
    elif event["kind"] == "status":
        _handle_status_update(event)

    return {"status": "ok"}


def _get_or_create_contact(cur, phone: str) -> int:
    row = cur.execute("SELECT id FROM contacts WHERE phone=?", (phone,)).fetchone()
    if row:
        return row["id"]
    ts = now()
    cur.execute("INSERT INTO contacts (phone, created_at, updated_at) VALUES (?,?,?)", (phone, ts, ts))
    return cur.lastrowid


def _download_and_store_media(media_id: str, mime_type: str | None, filename: str | None):
    """Resolves a WhatsApp media ID to a CDN URL, downloads the bytes, and saves them
    under config.MEDIA_DIR so the frontend can display/link to them directly.
    Returns (media_url, mime_type) — media_url is a local "/media/..." path, or
    (None, None) if the download failed for any reason (network issue, expired token,
    etc.) — callers fall back to showing the text placeholder in that case."""
    try:
        info = whatsapp.get_media_info(media_id)
        content, content_type = whatsapp.download_media_bytes(info["url"])
        real_mime = content_type or info.get("mime_type") or mime_type or "application/octet-stream"

        ext = Path(filename).suffix if filename else ""
        if not ext:
            ext = mimetypes.guess_extension(real_mime.split(";")[0].strip()) or ""
        safe_name = f"{media_id}{ext}"

        (config.MEDIA_DIR / safe_name).write_bytes(content)
        return f"/media/{safe_name}", real_mime
    except Exception as e:
        logger.error("Failed to download media %s: %s", media_id, e)
        return None, None


def _handle_incoming_message(event: dict) -> None:
    media_url, media_mime_type = (None, None)
    if event.get("media_id"):
        media_url, media_mime_type = _download_and_store_media(
            event["media_id"], event.get("mime_type"), event.get("filename")
        )

    with db_cursor() as cur:
        contact_id = _get_or_create_contact(cur, event["phone"])
        cur.execute("""
            INSERT INTO messages (contact_id, direction, wa_message_id, body, message_type,
                                  media_url, media_mime_type, reaction_emoji, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (contact_id, "in", event["wa_message_id"], event["text"], event["msg_type"],
              media_url, media_mime_type, event.get("reaction_emoji"), "received", now()))

        # If this contact is a recipient of any campaign, mark them as replied
        cur.execute("""
            UPDATE campaign_recipients SET status='replied', replied_at=?
            WHERE contact_id=? AND status IN ('sent','delivered','read')
        """, (now(), contact_id))

    try:
        whatsapp.mark_as_read(event["wa_message_id"])
    except Exception:
        pass


def _handle_status_update(event: dict) -> None:
    wa_id = event["wa_message_id"]
    status = event["status"]  # sent/delivered/read/failed
    ts_field = {"delivered": "delivered_at", "read": "read_at", "sent": "sent_at"}.get(status)

    with db_cursor() as cur:
        # Update the message log
        cur.execute("UPDATE messages SET status=? WHERE wa_message_id=?", (status, wa_id))

        # Update the campaign recipient row, but never downgrade replied -> read/delivered
        row = cur.execute("SELECT id, status FROM campaign_recipients WHERE wa_message_id=?", (wa_id,)).fetchone()
        if row and row["status"] != "replied":
            if ts_field:
                cur.execute(f"UPDATE campaign_recipients SET status=?, {ts_field}=? WHERE id=?",
                            (status, now(), row["id"]))
            else:
                failed_reason = None
                if status == "failed" and event.get("errors"):
                    failed_reason = str(event["errors"][0])[:500]
                cur.execute("UPDATE campaign_recipients SET status=?, failed_reason=? WHERE id=?",
                            (status, failed_reason, row["id"]))
