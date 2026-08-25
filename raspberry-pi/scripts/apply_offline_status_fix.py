from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "app" / "main.py"
text = MAIN.read_text()

if "DEVICE_STALE_SECONDS = 15" not in text:
    marker = "device_state: dict[str, dict[str, Any]] = {}\n"
    replacement = marker + "\n# ESP32 telemetry arrives about every 5 seconds.\nDEVICE_STALE_SECONDS = 15\nDEVICE_OFFLINE_SECONDS = 30\n"
    if marker not in text:
        raise SystemExit("Could not find device_state declaration")
    text = text.replace(marker, replacement, 1)

start = text.find("def get_state_snapshot()")
if start == -1:
    raise SystemExit("Could not find get_state_snapshot()")
next_def = text.find("\ndef ", start + 5)
if next_def == -1:
    raise SystemExit("Could not locate function following get_state_snapshot()")

freshness = '''def parse_iso_time(value: str | None) -> datetime | None:\n    if not value:\n        return None\n    try:\n        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))\n    except (TypeError, ValueError):\n        return None\n    if dt.tzinfo is None:\n        dt = dt.replace(tzinfo=timezone.utc)\n    return dt.astimezone(timezone.utc)\n\n\ndef device_connection_status(state: dict[str, Any]) -> tuple[str, bool, float | None]:\n    last_seen = parse_iso_time(state.get("last_seen"))\n    if last_seen is None:\n        return "OFFLINE", False, None\n    age = max(0.0, (datetime.now(timezone.utc) - last_seen).total_seconds())\n    if age <= DEVICE_STALE_SECONDS:\n        return "LIVE", True, age\n    if age <= DEVICE_OFFLINE_SECONDS:\n        return "STALE", False, age\n    return "OFFLINE", False, age\n\n\ndef get_state_snapshot() -> dict[str, dict[str, Any]]:\n    with state_lock:\n        snapshot = copy.deepcopy(device_state)\n    for state in snapshot.values():\n        status, online, age = device_connection_status(state)\n        state["online"] = online\n        state["connection_status"] = status\n        state["age_seconds"] = round(age, 1) if age is not None else None\n    return snapshot\n\n'''
text = text[:start] + freshness + text[next_def + 1:]

start = text.find("def update_device_online_state(")
if start == -1:
    raise SystemExit("Could not find update_device_online_state()")
next_def = text.find("\ndef ", start + 5)
if next_def == -1:
    raise SystemExit("Could not locate function following update_device_online_state()")

status_func = '''def update_device_online_state(\n    device_id: str,\n    online: bool,\n) -> None:\n    # Retained MQTT online messages are advisory only.\n    # Actual LIVE/STALE/OFFLINE is derived from telemetry last_seen.\n    with state_lock:\n        state = device_state.setdefault(\n            device_id,\n            {\n                "device_id": device_id,\n                "node_type": "smart_hospital_ward",\n                "last_seen": None,\n                "online": False,\n                "data": {},\n            },\n        )\n        state["mqtt_status"] = "online" if online else "offline"\n        state["mqtt_status_updated_at"] = utc_now()\n        if not online:\n            state["online"] = False\n\n'''
text = text[:start] + status_func + text[next_def + 1:]

backup = MAIN.with_suffix(".py.before-freshness-fix")
if not backup.exists():
    backup.write_text(MAIN.read_text())

MAIN.write_text(text)
print(f"Patched {MAIN}")
print(f"Backup: {backup}")
print("LIVE <=15s, STALE 15-30s, OFFLINE >30s since last telemetry")
