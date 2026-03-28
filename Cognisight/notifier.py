# focus_sentry/notifier.py

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Optional

from twilio.rest import Client


def _safe_get(row: Any, key: str, default: Any = None) -> Any:
    """
    Helper that works with sqlite3.Row or plain dict.
    """
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        return row[key]
    except Exception:
        return default


# ---------- Email ----------


def _get_smtp_config() -> Optional[dict]:
    """
    Read SMTP configuration from environment variables.
    Returns a dict if configuration looks complete, otherwise None.
    """

    host = os.getenv("FOCUS_SMTP_HOST")
    port = os.getenv("FOCUS_SMTP_PORT")
    user = os.getenv("FOCUS_SMTP_USERNAME")
    password = os.getenv("FOCUS_SMTP_PASSWORD")
    from_addr = os.getenv("FOCUS_EMAIL_FROM")
    use_tls = os.getenv("FOCUS_SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    if not host or not port or not from_addr:
        return None

    try:
        port_int = int(port)
    except ValueError:
        return None

    return {
        "host": host,
        "port": port_int,
        "user": user,
        "password": password,
        "from_addr": from_addr,
        "use_tls": use_tls,
    }


def _build_session_summary_text(session: Any) -> str:
    """
    Build a plain text summary from a session row.
    Works even if some fields are missing.
    """
    created_at = _safe_get(session, "created_at", "unknown start time")
    duration_minutes = _safe_get(session, "duration_minutes", None)

    total_seconds = _safe_get(session, "total_seconds", None)
    focused_seconds = _safe_get(session, "focused_seconds", None)
    unfocused_seconds = _safe_get(session, "unfocused_seconds", None)
    focus_percent = _safe_get(session, "focus_percent", None)
    breaks_count = _safe_get(session, "breaks_count", None)
    ended_early = bool(_safe_get(session, "ended_early", 0))

    parts = []

    parts.append(f"Session started at: {created_at}")
    if duration_minutes is not None:
        parts.append(f"Planned duration: {duration_minutes} minute(s)")

    if total_seconds is not None:
        parts.append(f"Total time recorded: {total_seconds} second(s)")
    if focused_seconds is not None:
        parts.append(f"Time focused: {focused_seconds} second(s)")
    if unfocused_seconds is not None:
        parts.append(f"Time unfocused: {unfocused_seconds} second(s)")
    if focus_percent is not None:
        parts.append(f"Focus percentage: {focus_percent} percent")
    if breaks_count is not None:
        parts.append(f"Number of breaks: {breaks_count}")

    parts.append(f"Ended early: {'Yes' if ended_early else 'No'}")

    return "\n".join(parts)


def send_email_summary(session: Any) -> None:
    """
    Send an email summary for the given session row.
    If configuration or recipient is missing, fall back to printing a log line.
    """

    email = _safe_get(session, "email", "").strip()
    send_email_flag = _safe_get(session, "send_email_flag", 0)

    if not email or not send_email_flag:
        # user did not request email or has no address
        return

    summary_text = _build_session_summary_text(session)

    cfg = _get_smtp_config()
    if not cfg:
        print(
            f"[focus_sentry] Email config missing, would send summary to {email}:\n"
            f"{summary_text}\n"
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Focus Sentry session summary"
    msg["From"] = cfg["from_addr"]
    msg["To"] = email
    msg.set_content(summary_text)

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                server.starttls()
                if cfg["user"] and cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                if cfg["user"] and cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)

        print(f"[focus_sentry] Email summary sent to {email}")
    except Exception as exc:
        print(f"[focus_sentry] Failed to send email to {email}: {exc}")
        print("[focus_sentry] Summary content was:")
        print(summary_text)


# ---------- SMS via Twilio ----------


def _get_twilio_client() -> Optional[Client]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        return None

    try:
        return Client(account_sid, auth_token)
    except Exception:
        return None


def _get_twilio_from_number() -> Optional[str]:
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    return from_number.strip() if from_number else None


def send_sms_summary(session: Any) -> None:
    """
    Send an SMS summary for the given session row using Twilio.
    If configuration or recipient is missing, fall back to logging.
    """

    phone = _safe_get(session, "phone", "").strip()
    send_sms_flag = _safe_get(session, "send_sms_flag", 0)

    if not phone or not send_sms_flag:
        return

    summary_text = _build_session_summary_text(session)

    client = _get_twilio_client()
    from_number = _get_twilio_from_number()

    if not client or not from_number:
        print(
            f"[focus_sentry] SMS config missing, would send SMS summary to {phone}:\n"
            f"{summary_text}\n"
        )
        return

    try:
        message = client.messages.create(
            body=summary_text,
            from_=from_number,
            to=phone,
        )
        print(f"[focus_sentry] SMS summary sent to {phone}, Twilio SID: {message.sid}")
    except Exception as exc:
        print(f"[focus_sentry] Failed to send SMS to {phone}: {exc}")
        print("[focus_sentry] SMS summary content would have been:")
        print(summary_text)
