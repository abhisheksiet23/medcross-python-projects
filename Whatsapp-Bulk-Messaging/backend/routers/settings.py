from fastapi import APIRouter
from pydantic import BaseModel
from database import get_setting, set_setting
import config

router = APIRouter(prefix="/api/settings", tags=["settings"])

KEYS = [
    "whatsapp_token",
    "whatsapp_phone_number_id",
    "whatsapp_business_account_id",
    "whatsapp_verify_token",
    "whatsapp_api_version",
    "business_name",
]

DEFAULTS = {
    "whatsapp_token": config.WHATSAPP_TOKEN,
    "whatsapp_phone_number_id": config.WHATSAPP_PHONE_NUMBER_ID,
    "whatsapp_business_account_id": config.WHATSAPP_BUSINESS_ACCOUNT_ID,
    "whatsapp_verify_token": config.WHATSAPP_VERIFY_TOKEN,
    "whatsapp_api_version": config.WHATSAPP_API_VERSION,
    "business_name": "",
}


def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return "*" * len(value) if value else ""
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("")
def get_settings():
    out = {}
    for key in KEYS:
        val = get_setting(key, DEFAULTS.get(key, ""))
        out[key] = _mask(val) if "token" in key else val
    return out


class SettingsIn(BaseModel):
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_api_version: str | None = None
    business_name: str | None = None


@router.put("")
def update_settings(body: SettingsIn):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        # Don't overwrite a real secret with an already-masked value coming back from the UI
        if "token" in key and "*" in value:
            continue
        set_setting(key, value)
    return {"status": "saved"}
