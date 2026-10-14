"""Supervise one process per camera. Each process talks only to the API."""

from __future__ import annotations

import logging
import multiprocessing
import signal
import threading
import time

from app.buffer import Outbox
from app.client import ApiClient
from app.config import load_settings
from app.rules import Cooldown
from app.live import OrganizationRef
from app.sensors import SensorDirectory, open_sensor_webhook

logger = logging.getLogger("sentinel.worker")


def run_camera(camera_id: str) -> None:
    from app.analyze import watch_camera

    watch_camera(camera_id)


def main() -> None:
    multiprocessing.set_start_method("spawn")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    if not settings.device_token:
        logger.error("DEVICE_TOKEN is empty")
        while True:
            time.sleep(15)
    client = ApiClient(settings.api_base_url, settings.device_token)
    processes: dict[str, multiprocessing.Process] = {}
    directory = SensorDirectory()
    outbox = Outbox(settings.buffer_dir / "sensors")
    organization = OrganizationRef()
    webhook = _start_webhook(settings, client, directory, outbox, organization)
    stop = False
    last_heartbeat = 0.0

    def request_stop(_signum, _frame) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop:
        now = time.monotonic()
        if now - last_heartbeat >= 30:
            try:
                client.heartbeat(settings.model_version)
                logger.info("heartbeat model=%s", settings.model_version)
            except Exception:
                logger.exception("heartbeat failed")
            last_heartbeat = now
        try:
            config = client.config()
        except Exception:
            logger.exception("config request failed")
        else:
            directory.update(config)
            organization.set(str(config.get("organization_id") or ""))
            _reconcile(processes, [camera["id"] for camera in config.get("cameras") or []])
        try:
            outbox.flush(client)
        except Exception:
            logger.exception("sensor outbox flush failed")
        time.sleep(5)
    if webhook is not None:
        webhook.shutdown()
        webhook.server_close()
    _stop_all(processes)


def _start_webhook(settings, client: ApiClient, directory: SensorDirectory, outbox: Outbox, organization: OrganizationRef):
    if not settings.sensor_webhook_port or (not settings.sensor_webhook_token and not settings.live_stream_secret):
        logger.error("edge http is off; set SENSOR_WEBHOOK_PORT and a sensor or live secret")
        return None
    server = open_sensor_webhook(
        settings.sensor_webhook_token,
        directory,
        client,
        outbox,
        Cooldown(),
        port=settings.sensor_webhook_port,
        live_dir=settings.live_dir,
        live_secret=settings.live_stream_secret,
        organization=organization,
        cors_origin=settings.live_cors_origin,
    )
    threading.Thread(target=server.serve_forever, name="sensor-webhook", daemon=True).start()
    logger.info("sensor webhook listening port=%s", settings.sensor_webhook_port)
    return server


def _reconcile(processes: dict[str, multiprocessing.Process], camera_ids: list[str]) -> None:
    wanted = set(camera_ids)
    for camera_id in list(processes):
        process = processes[camera_id]
        if camera_id not in wanted or not process.is_alive():
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            processes.pop(camera_id, None)
    for camera_id in camera_ids:
        if camera_id in processes:
            continue
        process = multiprocessing.Process(target=run_camera, args=(camera_id,), name=f"camera-{camera_id}", daemon=True)
        process.start()
        processes[camera_id] = process
        logger.info("camera process started camera=%s pid=%s", camera_id, process.pid)


def _stop_all(processes: dict[str, multiprocessing.Process]) -> None:
    for process in processes.values():
        if process.is_alive():
            process.terminate()
    for process in processes.values():
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
