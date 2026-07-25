from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db_cursor, now

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateIn(BaseModel):
    name: str                 # must exactly match the name approved in Meta Business Manager
    category: str = "MARKETING"
    language_code: str = "en_US"
    body_preview: str = ""     # e.g. "Hi {{1}}, your appointment on {{2}} is confirmed."
    variable_count: int = 0
    status: str = "approved"


@router.get("")
def list_templates():
    with db_cursor() as cur:
        rows = cur.execute("SELECT * FROM templates ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@router.post("")
def create_template(body: TemplateIn):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO templates (name, category, language_code, body_preview, variable_count, status, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (body.name, body.category, body.language_code, body.body_preview,
              body.variable_count, body.status, now()))
        return {"id": cur.lastrowid}


@router.put("/{template_id}")
def update_template(template_id: int, body: TemplateIn):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE templates SET name=?, category=?, language_code=?, body_preview=?,
                variable_count=?, status=? WHERE id=?
        """, (body.name, body.category, body.language_code, body.body_preview,
              body.variable_count, body.status, template_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Template not found")
    return {"status": "updated"}


@router.delete("/{template_id}")
def delete_template(template_id: int):
    with db_cursor() as cur:
        cur.execute("DELETE FROM templates WHERE id=?", (template_id,))
    return {"status": "deleted"}
