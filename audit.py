"""Append-only audit log: one JSON line per tool call, allowed or blocked."""
import json
import os
import time

LOG_PATH = os.getenv("AUDIT_LOG", "audit.jsonl")


def log_event(**fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **fields}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
