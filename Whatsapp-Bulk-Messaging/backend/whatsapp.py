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
    try:
        resp = requests.post(_url(phone_id, api_version), json=payload, headers=_headers(token), timeout=10)
        resp.raise_for_status()
        logger.info("Text sent to %s: %.60s", to, text)
        return resp.json()
    except Exception as e:
        logger.error("send_message failed: %s", e)
        raise


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


def parse_incoming(payload: dict):
    """
    Returns a dict describing what happened, or None if not relevant:
      {"kind": "message", "phone": str, "text": str, "wa_message_id": str, "msg_type": str}
      {"kind": "status", "wa_message_id": str, "status": str, "recipient": str, "errors": list}
    """
    try:
        value = payload["entry"][0]["changes"][0]["value"]

        if "messages" in value:
            message = value["messages"][0]
            phone = message["from"]
            wa_message_id = message.get("id")
            msg_type = message.get("type")

            if msg_type == "text":
                return {"kind": "message", "phone": phone, "text": message["text"]["body"].strip(),
                        "wa_message_id": wa_message_id, "msg_type": "text"}

            if msg_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    text = interactive["button_reply"]["title"]
                elif interactive["type"] == "list_reply":
                    text = interactive["list_reply"]["title"]
                else:
                    text = "[unsupported interactive reply]"
                return {"kind": "message", "phone": phone, "text": text,
                        "wa_message_id": wa_message_id, "msg_type": "interactive"}

            # Non-text types (image, audio, location, etc.) — store a placeholder
            return {"kind": "message", "phone": phone, "text": f"[{msg_type} message]",
                    "wa_message_id": wa_message_id, "msg_type": msg_type}

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
