"""
WhatsApp Cloud API layer.
Credentials can be overridden at runtime via the Settings page (stored in
the `settings` table); falls back to the .env values in config.py.
"""
import logging
import requests
import json
import config
from database import get_setting

logger = logging.getLogger(__name__)


def _creds():
    token = get_setting("whatsapp_token") or config.WHATSAPP_TOKEN
    phone_id = get_setting("whatsapp_phone_number_id") or config.WHATSAPP_PHONE_NUMBER_ID
    api_version = get_setting("whatsapp_api_version") or config.WHATSAPP_API_VERSION
    return token, phone_id, api_version


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _url(phone_id: str, api_version: str) -> str:
    return f"https://graph.facebook.com/{api_version}/{phone_id}/messages"


def send_message(to: str, text: str) -> dict:
    token, phone_id, api_version = _creds()
    payload = {
        "messaging_product": "whatsapp",
        "to": to, "type": "text",
        "text": {"body": text},
    }
    resp = None
    try:
        resp = requests.post(_url(phone_id, api_version), json=payload, headers=_headers(token), timeout=10)
        resp.raise_for_status()
        logger.info("Text sent to %s: %.60s", to, text)
        return resp.json()
    except Exception as e:
        logger.error("send_message failed: %s", e)
        if resp is not None:
            logger.error("WhatsApp response body: %s", resp.text)
        # Surface the real WhatsApp error body (not just "400 Bad Request") to the caller
        raise RuntimeError(resp.text if resp is not None else str(e))


def send_template_message(to: str, template_name: str, language_code: str = "en_US",
                          body_params: list[str] | None = None) -> dict:
    token, phone_id, api_version = _creds()
    template = {"name": template_name, "language": {"code": language_code}}
    if body_params:
        template["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in body_params],
        }]
    payload = {
        "messaging_product": "whatsapp",
        "to": to, "type": "template",
        "template": template,
    }
    try:
        resp = requests.post(_url(phone_id, api_version), json=payload, headers=_headers(token), timeout=10)
        resp.raise_for_status()
        logger.info("Template '%s' sent to %s", template_name, to)
        return resp.json()
    except Exception as e:
        logger.error("send_template_message failed for %s: %s", to, e)
        try:
            logger.error("WhatsApp response body: %s", resp.text)
        except Exception:
            pass
        raise


def mark_as_read(message_id: str) -> None:
    token, phone_id, api_version = _creds()
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        requests.post(_url(phone_id, api_version), json=payload, headers=_headers(token), timeout=5)
    except Exception:
        pass


def get_media_info(media_id: str) -> dict:
    """Step 1 of downloading media: resolve a media ID to a short-lived CDN URL.
    https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media#retrieve-media-url
    """
    token, _phone_id, api_version = _creds()
    url = f"https://graph.facebook.com/{api_version}/{media_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    resp.raise_for_status()
    return resp.json()  # {"url": ..., "mime_type": ..., "sha256": ..., "file_size": ..., "id": ...}


def download_media_bytes(media_url: str) -> tuple[bytes, str]:
    """Step 2: download the actual file bytes from the CDN URL returned by get_media_info().
    This URL is only valid briefly and requires the same bearer token to fetch."""
    token, _phone_id, _api_version = _creds()
    resp = requests.get(media_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def parse_incoming(payload: dict):
    """
    Returns a dict describing what happened, or None if not relevant:
      {"kind": "message", "phone": str, "text": str, "wa_message_id": str, "msg_type": str,
       "media_id": str|None, "mime_type": str|None, "filename": str|None,
       "reaction_emoji": str|None, "reacted_to_wa_id": str|None}
      {"kind": "status", "wa_message_id": str, "status": str, "recipient": str, "errors": list}
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]

        if "messages" in value:
            message = value["messages"][0]
            phone = message["from"]
            wa_message_id = message.get("id")
            msg_type = message.get("type")
            base = {"kind": "message", "phone": phone, "wa_message_id": wa_message_id, "msg_type": msg_type,
                    "media_id": None, "mime_type": None, "filename": None,
                    "reaction_emoji": None, "reacted_to_wa_id": None}

            if msg_type == "text":
                return {**base, "text": message["text"]["body"].strip()}

            if msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    text = interactive["button_reply"]["title"]
                elif interactive["type"] == "list_reply":
                    text = interactive["list_reply"]["title"]
                else:
                    text = "[unsupported interactive reply]"
                return {**base, "text": text}

            if msg_type == "reaction":
                reaction = message.get("reaction", {})
                emoji = reaction.get("emoji")  # absent/empty if the person removed their reaction
                return {**base, "text": emoji or "[removed reaction]",
                        "reaction_emoji": emoji, "reacted_to_wa_id": reaction.get("message_id")}

            if msg_type in ("image", "video", "audio", "document", "sticker"):
                media = message.get(msg_type, {})
                caption = media.get("caption", "")
                filename = media.get("filename")
                label = "Voice message" if (msg_type == "audio" and media.get("voice")) else msg_type.capitalize()
                text = caption or (filename or f"[{label}]")
                return {**base, "text": text, "media_id": media.get("id"), "mime_type": media.get("mime_type"),
                        "filename": filename}

            if msg_type == "location":
                loc = message.get("location", {})
                name = loc.get("name") or "Shared location"
                return {**base, "text": f"📍 {name} ({loc.get('latitude')}, {loc.get('longitude')})"}

            # Anything else we don't specifically handle yet (contacts, unknown types, etc.)
            return {**base, "text": f"[{msg_type} message]"}

        if "statuses" in value:
            st = value["statuses"][0]
            return {
                "kind": "status",
                "wa_message_id": st.get("id"),
                "status": st.get("status"),   # sent/delivered/read/failed
                "recipient": st.get("recipient_id"),
                "errors": st.get("errors", []),
            }

        return None

    except (KeyError, IndexError) as e:
        logger.warning("Could not parse webhook payload: %s", e)
        return None


def upload_media(file_bytes: bytes, filename: str, mime_type: str) -> str:
    """Uploads a file to WhatsApp's Media API. Returns a media ID to reference
    in a subsequent send_media_message() call — media must be uploaded first,
    you can't attach raw bytes directly to a /messages call.
    https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media#upload-media
    """
    token, phone_id, api_version = _creds()
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/media"
    files = {"file": (filename or "upload", file_bytes, mime_type)}
    data = {"messaging_product": "whatsapp", "type": mime_type}
    resp = None
    try:
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, files=files, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["id"]
    except Exception as e:
        logger.error("upload_media failed: %s", e)
        if resp is not None:
            logger.error("WhatsApp response body: %s", resp.text)
        raise RuntimeError(resp.text if resp is not None else str(e))


def send_media_message(to: str, media_type: str, media_id: str, caption: str | None = None,
                        filename: str | None = None) -> dict:
    """media_type must be one of: image, video, audio, document, sticker."""
    token, phone_id, api_version = _creds()
    media_obj = {"id": media_id}
    if caption and media_type in ("image", "video", "document"):
        media_obj["caption"] = caption
    if filename and media_type == "document":
        media_obj["filename"] = filename
    payload = {
        "messaging_product": "whatsapp",
        "to": to, "type": media_type,
        media_type: media_obj,
    }
    resp = None
    try:
        resp = requests.post(_url(phone_id, api_version), json=payload, headers=_headers(token), timeout=15)
        resp.raise_for_status()
        logger.info("Media (%s) sent to %s", media_type, to)
        return resp.json()
    except Exception as e:
        logger.error("send_media_message failed: %s", e)
        if resp is not None:
            logger.error("WhatsApp response body: %s", resp.text)
        raise RuntimeError(resp.text if resp is not None else str(e))


def infer_media_type(mime_type: str) -> str:
    """WhatsApp only accepts a handful of top-level message types for media —
    map a browser-supplied MIME type onto the closest one."""
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    return "document"
