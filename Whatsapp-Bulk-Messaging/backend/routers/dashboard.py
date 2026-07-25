from fastapi import APIRouter
from database import db_cursor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats():
    with db_cursor() as cur:
        total_contacts = cur.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        active_campaigns = cur.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status IN ('sending','scheduled')").fetchone()[0]
        messages_sent = cur.execute("SELECT COUNT(*) FROM messages WHERE direction='out'").fetchone()[0]
        delivered = cur.execute(
            "SELECT COUNT(*) FROM campaign_recipients WHERE status IN ('delivered','read','replied')").fetchone()[0]
        read = cur.execute(
            "SELECT COUNT(*) FROM campaign_recipients WHERE status IN ('read','replied')").fetchone()[0]
        replies_received = cur.execute("SELECT COUNT(*) FROM messages WHERE direction='in'").fetchone()[0]
        failed = cur.execute("SELECT COUNT(*) FROM campaign_recipients WHERE status='failed'").fetchone()[0]

        recent = cur.execute("""
            SELECT m.*, c.name AS contact_name, c.phone
            FROM messages m JOIN contacts c ON m.contact_id = c.id
            ORDER BY m.created_at DESC LIMIT 15
        """).fetchall()

    return {
        "total_contacts": total_contacts,
        "active_campaigns": active_campaigns,
        "messages_sent": messages_sent,
        "delivered": delivered,
        "read": read,
        "replies_received": replies_received,
        "failed_messages": failed,
        "recent_activity": [dict(r) for r in recent],
    }
