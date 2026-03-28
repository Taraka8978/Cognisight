from focus_sentry import database


def create_session_for_test(client):
    payload = {
        "duration_minutes": "15",
        "alert_threshold": "2.0",
        "alert_mode": "popup",
        "email": "user@example.com",
        "phone": "+12345678901",
        "send_email_flag": "true",
        "send_sms_flag": "true",
    }
    resp = client.post("/start-session", data=payload)
    assert resp.status_code == 200
    data = resp.json()
    return data["session_id"]


def test_end_session_updates_totals_and_focus_percent(client, monkeypatch):
    session_id = create_session_for_test(client)

    end_payload = {
        "session_id": str(session_id),
        "total_seconds": "300",
        "focused_seconds": "240",
        "unfocused_seconds": "60",
        "breaks_count": "3",
        "focus_percent": "80",
        "ended_early": "false",
    }

    resp = client.post("/end-session", data=end_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["ok"] is True
    assert data["session_id"] == session_id
    assert data["total_seconds"] == 300
    assert data["focused_seconds"] == 240
    assert data["unfocused_seconds"] == 60
    assert data["breaks_count"] == 3
    assert data["focus_percent"] == 80
    assert data["ended_early"] is False

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM focus_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["total_seconds"] == 300
    assert row["focused_seconds"] == 240
    assert row["unfocused_seconds"] == 60
    assert row["breaks_count"] == 3
    assert row["focus_percent"] == 80
    assert row["ended_early"] == 0
