#!/usr/bin/env python3
"""
Create the 13 problem set assignments in Canvas course 212754.

Due dates mirror the AU2025 course (194980) shifted forward 364 days,
preserving the same day-of-week and the same two midterm-week gaps.
Each assignment is worth 300 points and accepts file uploads.

Usage:
  export CANVAS_ACCESS_TOKEN="..."
  python create_assignments.py
  python create_assignments.py --dry-run
"""

import argparse
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://osu.instructure.com"
COURSE_ID = "212754"

# Due dates shifted 364 days from AU2025, same weekday and time.
# All at 11:59 pm Columbus local time:
#   EDT (UTC-4) through Oct 26  → 03:59:59Z
#   EST (UTC-5) from  Nov 2 on  → 04:59:59Z  (DST ends Nov 1, 2026)
ASSIGNMENTS = [
    ("🧮 Problem Set 1",  "2026-08-31T03:59:59Z"),
    ("🧮 Problem Set 2",  "2026-09-07T03:59:59Z"),
    ("🧮 Problem Set 3",  "2026-09-14T03:59:59Z"),
    ("🧮 Problem Set 4",  "2026-09-21T03:59:59Z"),
    # week of Sep 28 skipped — Midterm 1
    ("🧮 Problem Set 5",  "2026-10-05T03:59:59Z"),
    ("🧮 Problem Set 6",  "2026-10-12T03:59:59Z"),
    ("🧮 Problem Set 7",  "2026-10-19T03:59:59Z"),
    ("🧮 Problem Set 8",  "2026-10-26T03:59:59Z"),
    ("🧮 Problem Set 9",  "2026-11-02T04:59:59Z"),
    ("🧮 Problem Set 10", "2026-11-09T04:59:59Z"),
    # week of Nov 16 skipped — Midterm 2
    ("🧮 Problem Set 11", "2026-11-23T04:59:59Z"),
    ("🧮 Problem Set 12", "2026-11-30T04:59:59Z"),
    ("🧮 Problem Set 13", "2026-12-07T04:59:59Z"),
]


def http_json(method: str, url: str, token: str, data_dict=None, timeout=60):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    data_bytes = None
    if data_dict is not None:
        body = urlencode(data_dict).encode("utf-8")
        data_bytes = body
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"

    req = Request(url, method=method, headers=headers, data=data_bytes)

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if raw.strip() == "":
                return {}
            return json.loads(raw)
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}\n{err_body}") from e
    except URLError as e:
        raise RuntimeError(f"{method} {url} -> Network error: {e}") from e
    except json.JSONDecodeError:
        raise RuntimeError(f"{method} {url} -> Could not parse JSON response")


def main():
    ap = argparse.ArgumentParser(description="Create problem set assignments on Canvas")
    ap.add_argument("--course-id", default=COURSE_ID, help="Canvas course ID")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be created without calling the API")
    args = ap.parse_args()

    token = os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: CANVAS_ACCESS_TOKEN is not set in the environment.", file=sys.stderr)
        sys.exit(2)

    api_url = f"{BASE_URL}/api/v1/courses/{args.course_id}/assignments"

    created = 0
    errors = 0

    for name, due_at in ASSIGNMENTS:
        print(f"{name!r:30s}  due={due_at}", end="")

        if args.dry_run:
            print("  [dry-run]")
            continue

        try:
            result = http_json("POST", api_url, token, data_dict={
                "assignment[name]":             name,
                "assignment[due_at]":           due_at,
                "assignment[points_possible]":  "300",
                "assignment[submission_types][]": "online_upload",
                "assignment[published]":        "false",
            })
            print(f"  [created id={result.get('id')}]")
            created += 1
        except RuntimeError as e:
            print(f"  [ERROR: {e}]")
            errors += 1

    if not args.dry_run:
        print(f"\nDone. Created: {created}, Errors: {errors}")


if __name__ == "__main__":
    main()
