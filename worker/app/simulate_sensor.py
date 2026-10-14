"""Post one sensor reading to the edge webhook. Run inside the worker container."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one sensor reading to the edge webhook")
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--state", default="open")
    parser.add_argument("--url", default=os.environ.get("SENSOR_WEBHOOK_URL", "http://127.0.0.1:8081/sensors"))
    args = parser.parse_args()
    token = os.environ.get("SENSOR_WEBHOOK_TOKEN", "").strip()
    if not token:
        print("SENSOR_WEBHOOK_TOKEN is empty", file=sys.stderr)
        sys.exit(1)
    payload = {
        "external_id": args.external_id,
        "state": args.state,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    request = urllib.request.Request(
        args.url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
