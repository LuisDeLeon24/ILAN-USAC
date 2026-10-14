"""Local queue for events and usage when the API cannot be reached."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.client import PermanentError


class Outbox:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "outbox.sqlite"
        with self._connect() as db:
            db.execute(
                "create table if not exists events (id text primary key, meta text not null, created_at text not null)"
            )
            db.execute(
                "create table if not exists usage (id text primary key, meta text not null, created_at text not null)"
            )
            db.execute(
                "create table if not exists sensor_events (id text primary key, meta text not null, created_at text not null)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add_event(self, event_id: str, meta: dict, snapshot: bytes | None) -> None:
        if snapshot:
            (self.directory / f"{event_id}.jpg").write_bytes(snapshot)
        with self._connect() as db:
            db.execute(
                "insert or replace into events (id, meta, created_at) values (?, ?, ?)",
                (event_id, json.dumps(meta), _now()),
            )

    def add_usage(self, report_id: str, meta: dict) -> None:
        with self._connect() as db:
            db.execute(
                "insert or replace into usage (id, meta, created_at) values (?, ?, ?)",
                (report_id, json.dumps(meta), _now()),
            )

    def flush(self, client) -> None:
        with self._connect() as db:
            events = db.execute("select id, meta from events order by created_at asc").fetchall()
        for event_id, raw in events:
            meta = json.loads(raw)
            image_path = self.directory / f"{event_id}.jpg"
            snapshot = image_path.read_bytes() if image_path.exists() else None
            try:
                client.post_event(meta, snapshot)
            except PermanentError:
                self._drop_event(event_id)
                continue
            except Exception:
                return
            self._drop_event(event_id)
        with self._connect() as db:
            reports = db.execute("select id, meta from usage order by created_at asc").fetchall()
        for report_id, raw in reports:
            try:
                client.post_usage(json.loads(raw))
            except PermanentError:
                self._drop_usage(report_id)
                continue
            except Exception:
                return
            self._drop_usage(report_id)
        with self._connect() as db:
            sensors = db.execute("select id, meta from sensor_events order by created_at asc").fetchall()
        for event_id, raw in sensors:
            try:
                client.post_sensor(json.loads(raw))
            except PermanentError:
                self._drop_sensor(event_id)
                continue
            except Exception:
                return
            self._drop_sensor(event_id)

    def add_sensor(self, event_id: str, meta: dict) -> None:
        with self._connect() as db:
            db.execute(
                "insert or replace into sensor_events (id, meta, created_at) values (?, ?, ?)",
                (event_id, json.dumps(meta), _now()),
            )

    def _drop_event(self, event_id: str) -> None:
        image_path = self.directory / f"{event_id}.jpg"
        if image_path.exists():
            image_path.unlink()
        with self._connect() as db:
            db.execute("delete from events where id = ?", (event_id,))

    def _drop_usage(self, report_id: str) -> None:
        with self._connect() as db:
            db.execute("delete from usage where id = ?", (report_id,))

    def _drop_sensor(self, event_id: str) -> None:
        with self._connect() as db:
            db.execute("delete from sensor_events where id = ?", (event_id,))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
