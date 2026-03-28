from focus_sentry import database


def test_start_session_creates_row_and_returns_json(client):
    payload = {
        "duration_minutes": "25",
        "alert_threshold": "2.5",
        "alert_mode": "popup",
        "email": "test@example.com",
        "phone": "+12345678901",
        "send_email_flag": "true",
        "send_sms_flag": "true",
    }

    resp = client.post("/start-session", data=payload)

    assert resp.status_code == 200
    data = resp.json()

    assert "session_id" in data
    assert data["duration_minutes"] == 25
    assert data["alert_threshold_ms"] == 2500
    assert data["alert_mode"] == "popup"
    assert data["email"] == "test@example.com"

    session_id = data["session_id"]

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM focus_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["duration_minutes"] == 25
    assert row["email"] == "test@example.com"
    assert row["phone"] == "+12345678901"
    assert row["alert_threshold_ms"] == 2500
    assert row["alert_mode"] == "popup"
    assert row["send_email"] == 1
    assert row["send_sms"] == 1
    assert row["total_seconds"] is None
    assert row["focus_percent"] is None
