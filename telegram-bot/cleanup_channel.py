#!/usr/bin/env python3
"""Delete recent messages from the configured Telegram channel.

Run without --delete to discover and save message IDs only. Deletion requires
the explicit --delete flag and is limited by Telegram to messages under 48
hours old.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ID_FILE = HERE / "cleanup-message-ids.json"


def load_env() -> None:
    path = HERE / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def api_call(token: str, method: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.load(response)
                if not result.get("ok"):
                    raise RuntimeError(result.get("description", "Telegram rejected the request"))
                return result["result"]
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read().decode() or "{}")
            retry_after = detail.get("parameters", {}).get("retry_after")
            if error.code == 429 and retry_after is not None and attempt < 4:
                time.sleep(int(retry_after) + 1)
                continue
            raise RuntimeError(
                f"Telegram {method} failed ({error.code}): "
                f"{detail.get('description', 'unknown error')}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Telegram {method} connection failed") from error
    raise RuntimeError(f"Telegram {method} failed after retries")


def discover_message_ids(token: str, channel: str) -> list[int]:
    ids: set[int] = set()
    offset: int | None = None
    while True:
        payload: dict[str, Any] = {
            "limit": 100,
            "timeout": 0,
            "allowed_updates": ["channel_post"],
        }
        if offset is not None:
            payload["offset"] = offset
        updates = api_call(token, "getUpdates", payload)
        if not updates:
            break
        for update in updates:
            offset = max(offset or 0, update["update_id"] + 1)
            post = update.get("channel_post")
            if not post:
                continue
            chat = post.get("chat", {})
            username = chat.get("username")
            if username and f"@{username}".lower() == channel.lower():
                ids.add(int(post["message_id"]))
        if len(updates) < 100:
            break
    return sorted(ids)


def load_saved_ids() -> list[int]:
    try:
        return [int(value) for value in json.loads(ID_FILE.read_text())["messageIds"]]
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return []


def save_ids(ids: list[int]) -> None:
    ID_FILE.write_text(json.dumps({"messageIds": sorted(set(ids))}, indent=2) + "\n")


def create_cleanup_probe(token: str, channel: str) -> int:
    """Post a temporary message to obtain the channel's current highest message ID."""
    message = api_call(
        token,
        "sendMessage",
        {
            "chat_id": channel,
            "text": "🧹 Cleanup in progress…",
            "disable_notification": True,
        },
    )
    return int(message["message_id"])


def delete_eligible_ids(
    token: str, channel: str, message_ids: list[int]
) -> tuple[int, list[int]]:
    """Delete a batch, splitting it to isolate IDs Telegram refuses to delete."""
    if not message_ids:
        return 0, []
    try:
        api_call(
            token,
            "deleteMessages",
            {"chat_id": channel, "message_ids": message_ids},
        )
        return len(message_ids), []
    except RuntimeError as error:
        if "message can't be deleted" not in str(error):
            raise
        if len(message_ids) == 1:
            return 0, message_ids
        middle = len(message_ids) // 2
        left_deleted, left_skipped = delete_eligible_ids(
            token, channel, message_ids[:middle]
        )
        right_deleted, right_skipped = delete_eligible_ids(
            token, channel, message_ids[middle:]
        )
        return left_deleted + right_deleted, left_skipped + right_skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the discovered messages. Without this flag nothing is deleted.",
    )
    args = parser.parse_args()

    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL", "@dtjobalerts")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured")

    saved = load_saved_ids()
    discovered = discover_message_ids(token, channel)
    message_ids = sorted(set(saved) | set(discovered))
    save_ids(message_ids)
    print(f"Found {len(message_ids)} recent channel message IDs; saved to {ID_FILE.name}.")

    if not args.delete:
        print("Dry run only. Run again with --delete to remove these messages.")
        return
    if not message_ids:
        highest_id = create_cleanup_probe(token, channel)
        message_ids = list(range(1, highest_id + 1))
        save_ids(message_ids)
        print(
            f"Outgoing posts were absent from getUpdates. The cleanup probe returned "
            f"message ID {highest_id}; deletion will cover IDs 1-{highest_id}."
        )
    if not message_ids:
        print("Nothing to delete.")
        return

    deleted = 0
    skipped: list[int] = []
    for start in range(0, len(message_ids), 100):
        batch = message_ids[start : start + 100]
        batch_deleted, batch_skipped = delete_eligible_ids(token, channel, batch)
        deleted += batch_deleted
        skipped.extend(batch_skipped)
        processed = min(start + len(batch), len(message_ids))
        print(
            f"Processed {processed}/{len(message_ids)} IDs: "
            f"deleted {deleted}, skipped {len(skipped)}."
        )
    ID_FILE.unlink(missing_ok=True)
    print(
        f"Cleanup complete: deleted {deleted}; skipped {len(skipped)} "
        "nonexistent, expired, service, or unauthorized messages."
    )


if __name__ == "__main__":
    main()
