from __future__ import annotations

import argparse
import json
import signal
import threading
from typing import Iterable

import paho.mqtt.client as mqtt

try:
    from .hospital_node import HOSPITALS, SCENARIOS, HospitalNode
    from .simulator_config import SimulatorConfig
except ImportError:  # Direct script execution from raspberry-pi/simulator.
    from hospital_node import HOSPITALS, SCENARIOS, HospitalNode
    from simulator_config import SimulatorConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish deterministic CareGrid hospital resource-node scenarios over MQTT."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--hospital", choices=sorted(HOSPITALS), help="Run one simulated hospital node.")
    selection.add_argument("--all", action="store_true", help="Run all four simulated hospital nodes in one process.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="NORMAL", help="Deterministic scenario to publish.")
    return parser


def selected_nodes(hospital_id: str | None, all_nodes: bool, scenario: str) -> list[HospitalNode]:
    ids: Iterable[str] = sorted(HOSPITALS) if all_nodes else [str(hospital_id)]
    nodes = [HospitalNode(item) for item in ids]
    for node in nodes:
        node.apply_scenario(scenario)
    return nodes


def publish(client: mqtt.Client, node: HospitalNode) -> None:
    client.publish(node.status_topic, json.dumps(node.status_payload()), qos=1, retain=True)
    if node.online:
        client.publish(node.resource_topic, json.dumps(node.resource_payload()), qos=1, retain=True)


def run(nodes: list[HospitalNode], config: SimulatorConfig) -> None:
    stopped = threading.Event()

    def stop(*_: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="caregrid-multi-hospital-simulator")
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)
    client.connect(config.mqtt_host, config.mqtt_port, keepalive=60)
    client.loop_start()
    try:
        while not stopped.is_set():
            for node in nodes:
                publish(client, node)
            stopped.wait(config.publish_interval)
    finally:
        for node in nodes:
            client.publish(node.status_topic, json.dumps(node.status_payload(online=False)), qos=1, retain=True)
        client.disconnect()
        client.loop_stop()


def main() -> None:
    args = build_parser().parse_args()
    nodes = selected_nodes(args.hospital, args.all, args.scenario)
    run(nodes, SimulatorConfig.from_environment())


if __name__ == "__main__":
    main()
