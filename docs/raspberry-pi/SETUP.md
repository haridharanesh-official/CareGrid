# CareGrid Raspberry Pi Setup

This document records the Raspberry Pi 4 control-unit setup used for CareGrid.

## Confirmed Base Environment

- Hostname: `hari`
- Username: `hari`
- Architecture: `aarch64`
- Python: 3.13.x
- Repository path: `/opt/caregrid`
- Raspberry Pi gateway path: `/opt/caregrid/raspberry-pi`

## Core Services

### Mosquitto MQTT

Mosquitto is installed as a native systemd service and configured with authentication.

CareGrid configuration:

```text
/etc/mosquitto/conf.d/caregrid.conf
```

Recommended content:

```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
```

The password file must be readable by the Mosquitto service:

```bash
sudo chown root:mosquitto /etc/mosquitto/passwd
sudo chmod 640 /etc/mosquitto/passwd
```

Verify:

```bash
systemctl is-active mosquitto
```

Expected:

```text
active
```

## CareGrid Gateway

Create the Python environment:

```bash
cd /opt/caregrid/raspberry-pi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create the runtime environment file:

```bash
cp .env.example .env
chmod 600 .env
```

The real MQTT password must only be stored in `.env`; it must never be committed to GitHub.

Manual gateway test:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health endpoint:

```text
GET http://<raspberry-pi-ip>:8000/health
```

A healthy gateway returns `mqtt_connected: true`.

## systemd Installation

Install the provided unit:

```bash
sudo cp /opt/caregrid/raspberry-pi/systemd/caregrid-gateway.service /etc/systemd/system/caregrid-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable caregrid-gateway
sudo systemctl start caregrid-gateway
```

Verify both CareGrid services:

```bash
systemctl is-active mosquitto
systemctl is-active caregrid-gateway
```

Both should report `active`.

## Current Network Services

- SSH: `22/tcp`
- MQTT: `1883/tcp`
- CareGrid API: `8000/tcp`
- Home Assistant: `8123/tcp` (planned next stage)

## Security Notes

- Never commit `.env`, MQTT passwords, Wi-Fi credentials, API keys, tokens, or private certificates.
- Anonymous MQTT access remains disabled.
- Device telemetry is validated before being persisted by the CareGrid gateway.
