from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatorConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    publish_interval: float

    @classmethod
    def from_environment(cls) -> "SimulatorConfig":
        username = os.getenv("CAREGRID_MQTT_USERNAME", "caregrid").strip()
        password = os.getenv("CAREGRID_MQTT_PASSWORD", "").strip()
        interval = float(os.getenv("CAREGRID_SIMULATOR_PUBLISH_INTERVAL", "5"))
        if interval <= 0:
            raise ValueError("CAREGRID_SIMULATOR_PUBLISH_INTERVAL must be positive")
        return cls(
            mqtt_host=os.getenv("CAREGRID_MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(os.getenv("CAREGRID_MQTT_PORT", "1883")),
            mqtt_username=username or None,
            mqtt_password=password or None,
            publish_interval=interval,
        )
