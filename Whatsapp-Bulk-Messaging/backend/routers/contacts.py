import csv
import io
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from database import db_cursor, now

router = APIRouter(prefix="/api", tags=["contacts"])


# Groups 
class GroupIn(BaseModel):
    name: str
    description: str | None = None


@router.get("/groups")
def list_groups():
    with db_cursor() as cur:
        rows = cur.execute("""
            SELECT g.*, (SELECT COUNT(*) FROM contacts c WHERE c.group_id = g.id) AS contact_count
            FROM groups g ORDER BY g.name
        """).fetchall()
        return [dict(r) for r in rows]


@router.post("/groups")
def create_group(body: GroupIn):
    with db_cursor() as cur:
        try:
            cur.execute("INSERT INTO groups (name, description, created_at) VALUES (?,?,?)",
                        (body.name, body.description, now()))
        except Exception as e:
            raise HTTPException(400, f"Could not create group: {e}")
        return {"id": cur.lastrowid, "name": body.name}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int):
    with db_cursor() as cur:
        cur.execute("UPDATE contacts SET group_id=NULL WHERE group_id=?", (group_id,))
        cur.execute("DELETE FROM groups WHERE id=?", (group_id,))
    return {"status": "deleted"}


# ---------- Contacts ----------
class ContactIn(BaseModel):
    name: str | None = None
    phone: str
    email: str | None = None
    group_id: int | None = None
    tags: str | None = None   # comma separated
    notes: str | None = None


@router.get("/contacts")
def list_contacts(
    q: str | None = None,
    group_id: int | None = None,
    tag: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    where = []
    params: list = []
    if q:
        where.append("(name LIKE ? OR phone LIKE ? OR email LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if group_id:
        where.append("group_id = ?")
        params.append(group_id)
    if tag:
        where.append("tags LIKE ?")
        params.append(f"%{tag}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM contacts {where_sql}", params).fetchone()[0]
        offset = (page - 1) * limit
        rows = cur.execute(f"""
            SELECT c.*, g.name AS group_name
            FROM contacts c LEFT JOIN groups g ON c.group_id = g.id
            {where_sql}
            ORDER BY c.updated_at DESC LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

    return {"total": total, "page": page, "limit": limit, "data": [dict(r) for r in rows]}


@router.post("/contacts")
def create_contact(body: ContactIn):
    with db_cursor() as cur:
        ts = now()
        try:
            cur.execute("""
                INSERT INTO contacts (name, phone, email, group_id, tags, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (body.name, body.phone, body.email, body.group_id, body.tags, body.notes, ts, ts))
        except Exception as e:
            raise HTTPException(400, f"Could not create contact (duplicate phone?): {e}")
        return {"id": cur.lastrowid}


@router.put("/contacts/{contact_id}")
def update_contact(contact_id: int, body: ContactIn):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE contacts SET name=?, phone=?, email=?, group_id=?, tags=?, notes=?, updated_at=?
            WHERE id=?
        """, (body.name, body.phone, body.email, body.group_id, body.tags, body.notes, now(), contact_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Contact not found")
    return {"status": "updated"}


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int):
    with db_cursor() as cur:
        cur.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    return {"status": "deleted"}


@router.post("/contacts/import")
async def import_contacts(file: UploadFile = File(...), group_id: int | None = None):
    """Import contacts from a CSV file. Expected columns: name, phone, email, tags (all optional except phone)."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    # normalize header names (case-insensitive)
    fieldmap = {f.lower().strip(): f for f in (reader.fieldnames or [])}

    created, skipped, errors = 0, 0, []
    ts = now()
    with db_cursor() as cur:
        for i, row in enumerate(reader, start=2):
            phone = (row.get(fieldmap.get("phone", "phone"), "") or "").strip()
            phone = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
            if not phone:
                skipped += 1
                errors.append(f"Row {i}: missing phone")
                continue
            name = (row.get(fieldmap.get("name", "name"), "") or "").strip() or None
            email = (row.get(fieldmap.get("email", "email"), "") or "").strip() or None
            tags = (row.get(fieldmap.get("tags", "tags"), "") or "").strip() or None
            try:
                cur.execute("""
                    INSERT INTO contacts (name, phone, email, group_id, tags, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(phone) DO UPDATE SET
                        name=COALESCE(excluded.name, contacts.name),
                        email=COALESCE(excluded.email, contacts.email),
                        group_id=COALESCE(excluded.group_id, contacts.group_id),
                        tags=COALESCE(excluded.tags, contacts.tags),
                        updated_at=excluded.updated_at
                """, (name, phone, email, group_id, tags, ts, ts))
                created += 1
            except Exception as e:
                skipped += 1
                errors.append(f"Row {i} ({phone}): {e}")

    return {"imported_or_updated": created, "skipped": skipped, "errors": errors[:20]}


@router.get("/tags")
def list_tags():
    with db_cursor() as cur:
        rows = cur.execute("SELECT tags FROM contacts WHERE tags IS NOT NULL AND tags != ''").fetchall()
    tag_set = set()
    for r in rows:
        for t in r["tags"].split(","):
            t = t.strip()
            if t:
                tag_set.add(t)
    return sorted(tag_set)
