from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .database import complete_session, create_session, get_recent_sessions, init_db
from .detector import classify_focus_state
from .notifier import send_email_summary, send_sms_summary

load_dotenv()  # loads variables from .env into os.environ
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    sessions = get_recent_sessions(limit=50)
    sessions_list = [dict(row) for row in sessions]
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "sessions": sessions_list},
    )


@app.post("/start-session")
async def start_session(
    duration_minutes: int = Form(...),
    alert_threshold: float = Form(...),  # seconds
    alert_mode: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    send_email_flag: Optional[bool] = Form(False),
    send_sms_flag: Optional[bool] = Form(False),
):
    ends_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    alert_threshold_ms = int(alert_threshold * 1000)

    send_email_bool = bool(send_email_flag) and bool(email)
    send_sms_bool = bool(send_sms_flag) and bool(phone)

    session_id = create_session(
        duration_minutes=duration_minutes,
        email=email,
        phone=phone,
        alert_threshold_ms=alert_threshold_ms,
        alert_mode=alert_mode,
        send_email=send_email_bool,
        send_sms=send_sms_bool,
    )
    return {
        "session_id": session_id,
        "duration_minutes": duration_minutes,
        "email": email,
        "alert_threshold_ms": alert_threshold_ms,
        "alert_mode": alert_mode,
        "ends_at": ends_at.isoformat(),
    }


@app.post("/frame")
async def process_frame(
    session_id: int = Form(...),
    frame: UploadFile = File(...),  # noqa: B008
):
    data = await frame.read()
    focused = classify_focus_state(data)
    return {"focused": bool(focused)}


@app.post("/end-session")
async def end_session(
    session_id: int = Form(...),
    total_seconds: int = Form(...),
    focused_seconds: int = Form(...),
    unfocused_seconds: int = Form(...),
    breaks_count: int = Form(...),
    focus_percent: int = Form(...),
    ended_early: str = Form(...),
):
    ended_flag = ended_early.lower() == "true"

    session_row = complete_session(
        session_id=session_id,
        total_seconds=total_seconds,
        focused_seconds=focused_seconds,
        unfocused_seconds=unfocused_seconds,
        breaks_count=breaks_count,
        focus_percent=focus_percent,
        ended_early=ended_flag,
    )
    if session_row is None:
        return {"ok": False, "error": "Session not found"}

    # work with a plain dict so we can enrich it for the notifier
    session = dict(session_row)

    send_email = bool(session.get("send_email"))
    send_sms = bool(session.get("send_sms"))

    # provide the flags that notifier expects, in addition to the DB fields
    session["send_email_flag"] = 1 if send_email else 0
    session["send_sms_flag"] = 1 if send_sms else 0

    if send_email:
        send_email_summary(session)
    if send_sms:
        send_sms_summary(session)

    total_val = session.get("total_seconds") or 0
    focused_val = session.get("focused_seconds") or 0
    unfocused_val = session.get("unfocused_seconds") or 0
    breaks_val = session.get("breaks_count") or 0
    fp_val = session.get("focus_percent") or 0

    return {
        "ok": True,
        "session_id": session.get("id"),
        "total_seconds": total_val,
        "focused_seconds": focused_val,
        "unfocused_seconds": unfocused_val,
        "breaks_count": breaks_val,
        "focus_percent": fp_val,
        "ended_early": bool(session.get("ended_early")),
    }
