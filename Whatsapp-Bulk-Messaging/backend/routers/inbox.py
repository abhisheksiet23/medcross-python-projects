import logging
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from database import db_cursor, now
import config
import whatsapp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inbox", tags=["inbox"])


@router.get("/conversations")
def list_conversations(q: str | None = None):
    """One row per contact that has at least one message, most recent first."""
    where = ""
    params: list = []
    if q:
        where = "WHERE c.name LIKE ? OR c.phone LIKE ?"
        params = [f"%{q}%", f"%{q}%"]

    with db_cursor() as cur:
        rows = cur.execute(f"""
            SELECT c.id AS contact_id, c.name, c.phone,
                   m.body AS last_message, m.direction AS last_direction, m.created_at AS last_at,
                   m.message_type AS last_message_type,
                   (SELECT COUNT(*) FROM messages m2
                      WHERE m2.contact_id = c.id AND m2.direction='in' AND m2.status != 'read') AS unread_count
            FROM contacts c
            JOIN messages m ON m.id = (
                SELECT id FROM messages WHERE contact_id = c.id ORDER BY created_at DESC LIMIT 1
            )
            {where}
            ORDER BY m.created_at DESC
        """, params).fetchall()
        return [dict(r) for r in rows]


@router.get("/conversations/{contact_id}")
def get_thread(contact_id: int):
    with db_cursor() as cur:
        contact = cur.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        if not contact:
            raise HTTPException(404, "Contact not found")
        messages = cur.execute(
            "SELECT * FROM messages WHERE contact_id=? ORDER BY created_at ASC", (contact_id,)
        ).fetchall()
        # mark incoming messages as read
        cur.execute("UPDATE messages SET status='read' WHERE contact_id=? AND direction='in'", (contact_id,))
        return {"contact": dict(contact), "messages": [dict(m) for m in messages]}


class ReplyIn(BaseModel):
    text: str


@router.post("/conversations/{contact_id}/reply")
def send_reply(contact_id: int, body: ReplyIn):
    with db_cursor() as cur:
        contact = cur.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        if not contact:
            raise HTTPException(404, "Contact not found")

    error_detail = None
    try:
        resp = whatsapp.send_message(contact["phone"], body.text)
        wa_id = (resp.get("messages") or [{}])[0].get("id")
        status = "sent"
    except Exception as e:
        wa_id = None
        status = "failed"
        error_detail = str(e)[:500]

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO messages (contact_id, direction, wa_message_id, body, message_type, status, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (contact_id, "out", wa_id, body.text, "text", status, now()))

    if status == "failed":
        raise HTTPException(502, f"WhatsApp rejected the message: {error_detail}")
    return {"status": "sent", "wa_message_id": wa_id}


@router.post("/conversations/{contact_id}/send-media")
async def send_media(contact_id: int, file: UploadFile = File(...), caption: str | None = Form(None)):
    with db_cursor() as cur:
        contact = cur.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        if not contact:
            raise HTTPException(404, "Contact not found")

    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    media_type = whatsapp.infer_media_type(mime_type)

    wa_id = None
    error_detail = None
    try:
        media_id = whatsapp.upload_media(content, file.filename, mime_type)
        resp = whatsapp.send_media_message(contact["phone"], media_type, media_id, caption, file.filename)
        wa_id = (resp.get("messages") or [{}])[0].get("id")
        status = "sent"
    except Exception as e:
        status = "failed"
        error_detail = str(e)[:500]

    # Save a local copy too, regardless of send success/failure, so it's visible in
    # our own Inbox thread the same way incoming media is (and so a failed send is
    # still visible with what was attempted, not silently lost).
    local_url = None
    try:
        ext = Path(file.filename).suffix if file.filename else ""
        if not ext:
            ext = mimetypes.guess_extension(mime_type.split(";")[0].strip()) or ""
        safe_name = f"out_{contact_id}_{now().replace(':', '').replace('-', '').replace('.', '')}{ext}"
        (config.MEDIA_DIR / safe_name).write_bytes(content)
        local_url = f"/media/{safe_name}"
    except Exception as e:
        logger.error("Failed to save local copy of outgoing media: %s", e)

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO messages (contact_id, direction, wa_message_id, body, message_type,
                                  media_url, media_mime_type, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (contact_id, "out", wa_id, caption or file.filename, media_type,
              local_url, mime_type, status, now()))

    if status == "failed":
        raise HTTPException(502, f"WhatsApp rejected the media: {error_detail}")
    return {"status": "sent", "wa_message_id": wa_id, "media_url": local_url}
