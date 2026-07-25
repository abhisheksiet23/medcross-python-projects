import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database import db_cursor, now
import whatsapp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignIn(BaseModel):
    name: str
    template_id: int
    group_id: int
    scheduled_at: str | None = None   # ISO datetime; None = send immediately when /send is called


def _campaign_row(cur, campaign_id: int):
    row = cur.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Campaign not found")
    return row


def _stats_for(cur, campaign_id: int) -> dict:
    total = cur.execute("SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id=?", (campaign_id,)).fetchone()[0]
    counts = {r["status"]: r["c"] for r in cur.execute(
        "SELECT status, COUNT(*) c FROM campaign_recipients WHERE campaign_id=? GROUP BY status",
        (campaign_id,)).fetchall()}
    sent = sum(v for k, v in counts.items() if k != "pending")
    delivered = counts.get("delivered", 0) + counts.get("read", 0) + counts.get("replied", 0)
    read = counts.get("read", 0) + counts.get("replied", 0)
    failed = counts.get("failed", 0)
    replied = counts.get("replied", 0)
    return {
        "recipients": total,
        "sent": sent,
        "delivered": delivered,
        "read": read,
        "failed": failed,
        "replied": replied,
        "delivery_rate": round(delivered / sent * 100, 1) if sent else 0,
        "read_rate": round(read / sent * 100, 1) if sent else 0,
        "response_rate": round(replied / sent * 100, 1) if sent else 0,
    }


@router.get("")
def list_campaigns():
    with db_cursor() as cur:
        rows = cur.execute("""
            SELECT c.*, t.name AS template_name, g.name AS group_name
            FROM campaigns c
            LEFT JOIN templates t ON c.template_id = t.id
            LEFT JOIN groups g ON c.group_id = g.id
            ORDER BY c.created_at DESC
        """).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["stats"] = _stats_for(cur, r["id"])
            result.append(d)
        return result


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int):
    with db_cursor() as cur:
        row = _campaign_row(cur, campaign_id)
        d = dict(row)
        d["stats"] = _stats_for(cur, campaign_id)
        d["recipients"] = [dict(x) for x in cur.execute("""
            SELECT cr.*, c.name AS contact_name, c.phone
            FROM campaign_recipients cr JOIN contacts c ON cr.contact_id = c.id
            WHERE cr.campaign_id=? ORDER BY cr.id
        """, (campaign_id,)).fetchall()]
        return d


@router.post("")
def create_campaign(body: CampaignIn):
    with db_cursor() as cur:
        status = "scheduled" if body.scheduled_at else "draft"
        cur.execute("""
            INSERT INTO campaigns (name, template_id, group_id, status, scheduled_at, created_at)
            VALUES (?,?,?,?,?,?)
        """, (body.name, body.template_id, body.group_id, status, body.scheduled_at, now()))
        return {"id": cur.lastrowid, "status": status}


@router.post("/{campaign_id}/duplicate")
def duplicate_campaign(campaign_id: int):
    with db_cursor() as cur:
        row = _campaign_row(cur, campaign_id)
        cur.execute("""
            INSERT INTO campaigns (name, template_id, group_id, status, created_at)
            VALUES (?,?,?,?,?)
        """, (f"{row['name']} (copy)", row["template_id"], row["group_id"], "draft", now()))
        return {"id": cur.lastrowid}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: int):
    with db_cursor() as cur:
        _campaign_row(cur, campaign_id)
        cur.execute("UPDATE campaigns SET status='paused' WHERE id=?", (campaign_id,))
    return {"status": "paused"}


@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: int, background_tasks: BackgroundTasks):
    with db_cursor() as cur:
        _campaign_row(cur, campaign_id)
        cur.execute("UPDATE campaigns SET status='sending' WHERE id=?", (campaign_id,))
    background_tasks.add_task(execute_campaign, campaign_id)
    return {"status": "sending"}


@router.post("/{campaign_id}/send")
def send_campaign(campaign_id: int, background_tasks: BackgroundTasks):
    """Trigger immediate sending (runs in the background so the request returns fast)."""
    with db_cursor() as cur:
        row = _campaign_row(cur, campaign_id)
        if row["status"] in ("sending", "completed"):
            raise HTTPException(400, f"Campaign already {row['status']}")
        cur.execute("UPDATE campaigns SET status='sending', started_at=? WHERE id=?", (now(), campaign_id))

        # Create pending recipient rows the first time this campaign is sent
        existing = cur.execute("SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id=?",
                                (campaign_id,)).fetchone()[0]
        if existing == 0:
            contacts = cur.execute("SELECT id FROM contacts WHERE group_id=? AND opted_in=1",
                                    (row["group_id"],)).fetchall()
            for c in contacts:
                cur.execute("INSERT INTO campaign_recipients (campaign_id, contact_id, status) VALUES (?,?,?)",
                            (campaign_id, c["id"], "pending"))

    background_tasks.add_task(execute_campaign, campaign_id)
    return {"status": "sending"}


def execute_campaign(campaign_id: int) -> None:
    """Runs in the background: sends the template to every pending recipient."""
    with db_cursor() as cur:
        campaign = cur.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if not campaign:
            return
        template = cur.execute("SELECT * FROM templates WHERE id=?", (campaign["template_id"],)).fetchone()
        pending = cur.execute(
            "SELECT cr.id AS rec_id, c.id AS contact_id, c.phone FROM campaign_recipients cr "
            "JOIN contacts c ON cr.contact_id = c.id "
            "WHERE cr.campaign_id=? AND cr.status='pending'", (campaign_id,)).fetchall()

    for rec in pending:
        # Re-check status each loop so Pause takes effect between sends
        with db_cursor() as cur:
            current = cur.execute("SELECT status FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if current["status"] == "paused":
            logger.info("Campaign %s paused mid-send", campaign_id)
            return

        try:
            resp = whatsapp.send_template_message(rec["phone"], template["name"], template["language_code"])
            wa_id = (resp.get("messages") or [{}])[0].get("id")
            with db_cursor() as cur:
                cur.execute("UPDATE campaign_recipients SET status='sent', wa_message_id=?, sent_at=? WHERE id=?",
                            (wa_id, now(), rec["rec_id"]))
                cur.execute("""
                    INSERT INTO messages (contact_id, campaign_id, direction, wa_message_id, body,
                                          message_type, template_name, status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (rec["contact_id"], campaign_id, "out", wa_id, template["body_preview"],
                      "template", template["name"], "sent", now()))
        except Exception as e:
            with db_cursor() as cur:
                cur.execute("UPDATE campaign_recipients SET status='failed', failed_reason=? WHERE id=?",
                            (str(e)[:500], rec["rec_id"]))

    with db_cursor() as cur:
        remaining = cur.execute(
            "SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id=? AND status='pending'",
            (campaign_id,)).fetchone()[0]
        if remaining == 0:
            cur.execute("UPDATE campaigns SET status='completed', completed_at=? WHERE id=?",
                        (now(), campaign_id))
