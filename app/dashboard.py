"""Read-only HTML dashboard listing registered patients (bonus requirement).

Renders straight from the same `crud` layer the REST API and voice webhook
use, so it can never drift from what's actually in the database. Built with
a plain f-string instead of a template engine since one small table doesn't
justify adding Jinja2 as a dependency.

Every value is HTML-escaped before rendering: several patient fields
(address, city, insurance name, etc.) have no character-class restriction
in `schemas.py` -- only a max length -- and this endpoint is unauthenticated
like the rest of the API, so unescaped output here would be a stored-XSS hole.
"""
from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import crud
from .database import get_db

router = APIRouter(tags=["dashboard"])

_STYLE = """
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0b0f14; color:#e6edf3; margin:0; padding:2rem; }
  h1 { font-size:1.4rem; margin:0 0 0.25rem; }
  p.sub { color:#8b949e; margin:0 0 1.5rem; }
  table { border-collapse:collapse; width:100%; font-size:0.9rem; }
  th, td { text-align:left; padding:0.5rem 0.75rem; border-bottom:1px solid #21262d; white-space:nowrap; }
  th { color:#8b949e; font-weight:600; }
  tr:hover td { background:#161b22; }
  .empty { color:#8b949e; padding:2rem 0; }
  .badge { display:inline-block; padding:0.1rem 0.6rem; border-radius:999px; font-size:0.75rem; background:#1f6feb22; color:#58a6ff; margin-left:0.5rem; }
  .wrap { overflow-x:auto; }
</style>
"""


def _esc(value) -> str:
    return escape(str(value)) if value not in (None, "") else "—"


def _row(p) -> str:
    address = _esc(p.address_line_1)
    if p.address_line_2:
        address += f", {_esc(p.address_line_2)}"
    cells = [
        f"{_esc(p.first_name)} {_esc(p.last_name)}",
        _esc(p.date_of_birth),
        _esc(p.sex),
        _esc(p.phone_number),
        _esc(p.email),
        address,
        f"{_esc(p.city)}, {_esc(p.state)} {_esc(p.zip_code)}",
        _esc(p.insurance_provider),
        _esc(p.preferred_language),
        p.created_at.strftime("%Y-%m-%d %H:%M UTC"),
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):
    patients = crud.list_patients(db)

    if patients:
        headers = ["Name", "DOB", "Sex", "Phone", "Email", "Address", "City/State/Zip",
                   "Insurance", "Language", "Registered"]
        table = (
            "<div class='wrap'><table><thead><tr>"
            + "".join(f"<th>{h}</th>" for h in headers)
            + "</tr></thead><tbody>"
            + "".join(_row(p) for p in patients)
            + "</tbody></table></div>"
        )
    else:
        table = "<p class='empty'>No patients registered yet.</p>"

    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Patient Registration Dashboard</title>"
        f"{_STYLE}</head><body>"
        f"<h1>Patient Registration Dashboard<span class='badge'>{len(patients)} patients</span></h1>"
        "<p class='sub'>Read-only view, backed by the same data layer as GET /patients.</p>"
        f"{table}"
        "</body></html>"
    )
    return HTMLResponse(html)
