from fastapi import APIRouter
from database import db_cursor

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def message_logs(
    campaign_id: int | None = None,
    contact_id: int | None = None,
    phone: str | None = None,
    status: str | None = None,
    template_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    limit: int = 100,
):
    where = []
    params: list = []
    if campaign_id:
        where.append("m.campaign_id = ?")
        params.append(campaign_id)
    if contact_id:
        where.append("m.contact_id = ?")
        params.append(contact_id)
    if phone:
        where.append("c.phone LIKE ?")
        params.append(f"%{phone}%")
    if status:
        where.append("m.status = ?")
        params.append(status)
    if template_name:
        where.append("m.template_name LIKE ?")
        params.append(f"%{template_name}%")
    if date_from:
        where.append("m.created_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("m.created_at <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db_cursor() as cur:
        total = cur.execute(f"""
            SELECT COUNT(*) FROM messages m JOIN contacts c ON m.contact_id = c.id {where_sql}
        """, params).fetchone()[0]

        offset = (page - 1) * limit
        rows = cur.execute(f"""
            SELECT m.*, c.name AS contact_name, c.phone, camp.name AS campaign_name
            FROM messages m
            JOIN contacts c ON m.contact_id = c.id
            LEFT JOIN campaigns camp ON m.campaign_id = camp.id
            {where_sql}
            ORDER BY m.created_at DESC LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

    return {"total": total, "page": page, "limit": limit, "data": [dict(r) for r in rows]}
