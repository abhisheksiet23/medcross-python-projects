from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db_cursor, now
import whatsapp

router = APIRouter(prefix="/api/bulk", tags=["bulk"])


@router.get("/filter")
def filter_contacts(campaign_id: int | None = None, response_contains: str | None = None,
                    group_id: int | None = None):
    """
    Find contacts matching filters, e.g. "everyone in campaign X whose reply contained YES".
    Any combination of filters can be used; all are optional.
    """
    where = []
    params: list = []
    joins = ""

    if campaign_id:
        joins += " JOIN campaign_recipients cr ON cr.contact_id = c.id AND cr.campaign_id = ? "
        params.append(campaign_id)

    if response_contains:
        joins += """ JOIN messages m ON m.contact_id = c.id AND m.direction='in'
                     AND m.body LIKE ? """
        params.append(f"%{response_contains}%")

    if group_id:
        where.append("c.group_id = ?")
        params.append(group_id)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db_cursor() as cur:
        rows = cur.execute(f"""
            SELECT DISTINCT c.id, c.name, c.phone, c.tags
            FROM contacts c
            {joins}
            {where_sql}
            ORDER BY c.name
        """, params).fetchall()
        return [dict(r) for r in rows]


class BulkSendIn(BaseModel):
    contact_ids: list[int]
    text: str


@router.post("/send")
def bulk_send(body: BulkSendIn):
    if not body.contact_ids:
        raise HTTPException(400, "No contacts selected")

    sent, failed = [], []
    with db_cursor() as cur:
        contacts = cur.execute(
            f"SELECT * FROM contacts WHERE id IN ({','.join('?' * len(body.contact_ids))})",
            body.contact_ids,
        ).fetchall()

    for contact in contacts:
        try:
            resp = whatsapp.send_message(contact["phone"], body.text)
            wa_id = (resp.get("messages") or [{}])[0].get("id")
            status = "sent"
            sent.append(contact["id"])
        except Exception as e:
            wa_id = None
            status = "failed"
            failed.append({"contact_id": contact["id"], "error": str(e)})

        with db_cursor() as cur:
            cur.execute("""
                INSERT INTO messages (contact_id, direction, wa_message_id, body, message_type, status, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (contact["id"], "out", wa_id, body.text, "text", status, now()))

    return {"sent": len(sent), "failed": failed}
