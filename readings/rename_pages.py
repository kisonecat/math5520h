#!/usr/bin/env python3
"""
Rename Canvas pages from 'plan-for-week-N' slugs to 'week-N'.

Usage:
  export CANVAS_ACCESS_TOKEN="..."
  python rename_pages.py
  python rename_pages.py --dry-run
  python rename_pages.py --course-id 212754 --weeks 16
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
NUM_WEEKS = 16


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
    ap = argparse.ArgumentParser(description="Rename Canvas pages from plan-for-week-N to week-N")
    ap.add_argument("--course-id", default=COURSE_ID, help="Canvas course ID")
    ap.add_argument("--weeks", type=int, default=NUM_WEEKS, help="Number of weeks to rename")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen without renaming")
    args = ap.parse_args()

    token = os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: CANVAS_ACCESS_TOKEN is not set in the environment.", file=sys.stderr)
        sys.exit(2)

    api_base = f"{BASE_URL}/api/v1/courses/{args.course_id}/pages"

    renamed = 0
    skipped = 0
    errors = 0

    for week in range(1, args.weeks + 1):
        old_slug = f"plan-for-week-{week}"
        new_slug = f"week-{week}"
        new_title = f"Week {week}"
        old_url = f"{api_base}/{old_slug}"

        print(f"Week {week:2d}: {old_slug} -> {new_slug}", end="")

        if args.dry_run:
            print(" [dry-run]")
            continue

        try:
            result = http_json("PUT", old_url, token, data_dict={
                "wiki_page[url]": new_slug,
                "wiki_page[title]": new_title,
            })
            actual_slug = result.get("url", new_slug)
            print(f" [renamed, actual slug: {actual_slug}]")
            renamed += 1
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                print(" [not found, skipped]")
                skipped += 1
            else:
                print(f" [ERROR: {e}]")
                errors += 1

    if not args.dry_run:
        print(f"\nDone. Renamed: {renamed}, Not found: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
