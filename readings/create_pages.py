#!/usr/bin/env python3
"""
Create Canvas wiki pages for each week so that upload.py can later update them.

Usage:
  export CANVAS_ACCESS_TOKEN="..."
  python create_pages.py
  python create_pages.py --dry-run
  python create_pages.py --course-id 205090 --weeks 14
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
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{method} {url} -> Could not parse JSON response") from e


def page_exists(api_base: str, slug: str, token: str) -> bool:
    url = f"{api_base}/{slug}"
    try:
        http_json("GET", url, token, timeout=15)
        return True
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return False
        raise


def main():
    ap = argparse.ArgumentParser(description="Create Canvas pages for weekly readings")
    ap.add_argument("--course-id", default=COURSE_ID, help="Canvas course ID")
    ap.add_argument(
        "--weeks", type=int, default=NUM_WEEKS, help="Number of weeks to create"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without creating"
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip pages that already exist (default: true)",
    )
    ap.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    args = ap.parse_args()

    token = os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
    if not token:
        print(
            "ERROR: CANVAS_ACCESS_TOKEN is not set in the environment.", file=sys.stderr
        )
        sys.exit(2)

    api_base = f"{BASE_URL}/api/v1/courses/{args.course_id}/pages"

    created = 0
    skipped = 0
    errors = 0

    for week in range(1, args.weeks + 1):
        title = f"Week {week}"
        slug = f"week-{week}"

        print(f"Week {week:2d}: '{title}' (slug: {slug})", end="")

        if args.dry_run:
            print(" [dry-run, would create]")
            continue

        if args.skip_existing and page_exists(api_base, slug, token):
            print(" [exists, skipped]")
            skipped += 1
            continue

        try:
            result = http_json(
                "POST",
                api_base,
                token,
                data_dict={
                    "wiki_page[title]": title,
                    "wiki_page[body]": "",
                    "wiki_page[published]": "false",
                },
            )
            actual_slug = result.get("url", slug)
            print(f" [created, actual slug: {actual_slug}]")
            created += 1
        except RuntimeError as e:
            print(f" [ERROR: {e}]")
            errors += 1

    if not args.dry_run:
        print(f"\nDone. Created: {created}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
