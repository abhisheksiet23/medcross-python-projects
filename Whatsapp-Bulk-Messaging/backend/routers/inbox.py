from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db_cursor, now
import whatsapp

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

    try:
        resp = whatsapp.send_message(contact["phone"], body.text)
        wa_id = (resp.get("messages") or [{}])[0].get("id")
        status = "sent"
    except Exception as e:
        wa_id = None
        status = "failed"

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO messages (contact_id, direction, wa_message_id, body, message_type, status, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (contact_id, "out", wa_id, body.text, "text", status, now()))

    if status == "failed":
        raise HTTPException(502, "Failed to send message via WhatsApp API")
    return {"status": "sent", "wa_message_id": wa_id}
