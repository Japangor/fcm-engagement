#!/usr/bin/env python3
"""Send scheduled engagement FCM notifications to one or both Firebase projects.

Picks a rotating message from fcm_messages.json based on day-of-year and broadcasts
to the ``all`` topic (clients auto-subscribe via FirebaseKit / FirebaseService).

Usage:
  python3 fcm_engagement.py
  python3 fcm_engagement.py --dry-run
  python3 fcm_engagement.py --category education_exam

Environment / secrets:
  FCM_SA_RAIL24_MOBILE  path to rail24-mobile service account JSON (or --sa-cricket)
                        [legacy fallback: FCM_SA_CRICKET]
  FCM_SA_JAPANGOR       path to japangor service account JSON (or --sa-japangor)

A project is skipped (not an error) when its service account file is absent,
so the workflow keeps working even if only one secret is configured.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from google.oauth2 import service_account
    import google.auth.transport.requests
    import requests
except ImportError:
    print("pip install google-auth requests", file=sys.stderr)
    sys.exit(1)

HERE = Path(__file__).resolve().parent
MESSAGES = HERE / "fcm_messages.json"
SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
TOPIC = "all"
# CricAi devices are registered in the rail24-mobile Firebase project, so the
# cricket service account MUST belong to rail24-mobile (NOT cricket-c7b8f, which
# is only used for Play Console / indexing tooling).
EXPECTED_CRICKET_PROJECT = "rail24-mobile"


def access_token(sa_path: Path) -> tuple[str, str]:
    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=SCOPES
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token, creds.project_id


def pick_message(category: str | None, *, use_announcement: bool) -> tuple[str, str]:
    bank = json.loads(MESSAGES.read_text(encoding="utf-8"))
    if use_announcement:
        items = bank.get("announcements", [])
        if items:
            idx = datetime.now(timezone.utc).timetuple().tm_yday % len(items)
            m = items[idx]
            return m["title"], m["body"]
    cats = bank["categories"]
    key = category if category and category in cats else "general"
    items = cats.get(key) or cats["general"]
    idx = datetime.now(timezone.utc).timetuple().tm_yday % len(items)
    m = items[idx]
    return m["title"], m["body"]


def send_push(sa_path: Path, title: str, body: str, *, dry_run: bool) -> bool:
    if not sa_path or not sa_path.exists():
        print(f"SKIP — service account missing: {sa_path}", file=sys.stderr)
        return False
    payload = {
        "message": {
            "topic": TOPIC,
            "notification": {"title": title, "body": body},
            "data": {"type": "engagement", "source": "fcm_engagement.py"},
            "android": {
                "priority": "high",
                "notification": {"sound": "default"},
            },
        }
    }
    if dry_run:
        print(f"[dry-run] {sa_path.name}: {title!r} — {body!r}")
        return True
    token, project_id = access_token(sa_path)
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; UTF-8",
        },
        data=json.dumps(payload),
        timeout=30,
    )
    if resp.status_code == 200:
        print(f"OK project={project_id}: {resp.json().get('name')}")
        return True
    print(f"FAIL project={project_id} {resp.status_code}: {resp.text}", file=sys.stderr)
    return False


def _env_path(*vars: str) -> Path | None:
    """First non-empty env var among `vars` -> Path, else None."""
    for var in vars:
        val = os.environ.get(var)
        if val:
            return Path(val)
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Engagement FCM broadcast (both projects).")
    # Prefer the new rail24-mobile name; fall back to legacy FCM_SA_CRICKET.
    p.add_argument("--sa-cricket", type=Path,
                   default=_env_path("FCM_SA_RAIL24_MOBILE", "FCM_SA_CRICKET"),
                   help="rail24-mobile FCM service account (env FCM_SA_RAIL24_MOBILE)")
    p.add_argument("--sa-japangor", type=Path, default=_env_path("FCM_SA_JAPANGOR"))
    p.add_argument("--category", choices=[
        "education_code", "education_exam", "finance", "utility", "general",
    ], help="message pool (default: general)")
    p.add_argument("--announcement", action="store_true",
                   help="use announcement pool instead of category")
    p.add_argument("--title", help="override title")
    p.add_argument("--body", help="override body")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.title and args.body:
        title, body = args.title, args.body
    else:
        title, body = pick_message(args.category, use_announcement=args.announcement)

    print(f"Message: {title!r} — {body!r}")

    # Guard: the CricAi SA must be rail24-mobile, else pushes reach no devices.
    try:
        if args.sa_cricket and args.sa_cricket.exists():
            proj = json.loads(args.sa_cricket.read_text()).get("project_id")
            if proj and proj != EXPECTED_CRICKET_PROJECT:
                print(
                    f"WARNING: cricket SA project_id={proj!r} (expected "
                    f"{EXPECTED_CRICKET_PROJECT!r}). CricAi devices are on "
                    f"{EXPECTED_CRICKET_PROJECT!r}; pushes will not be delivered.",
                    file=sys.stderr,
                )
    except Exception:
        pass

    attempted = False
    ok_any = False
    for sa in (args.sa_cricket, args.sa_japangor):
        if sa and sa.exists():
            attempted = True
            ok_any = send_push(sa, title, body, dry_run=args.dry_run) or ok_any

    if not attempted:
        print("No service accounts configured (set FCM_SA_CRICKET / FCM_SA_JAPANGOR).",
              file=sys.stderr)
        return 1
    return 0 if ok_any else 1


if __name__ == "__main__":
    sys.exit(main())
