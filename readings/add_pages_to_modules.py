#!/usr/bin/env python3
"""
Add week-N pages to their corresponding modules in a Canvas course.

Fetches all modules, matches each one to a week number by parsing digits
from the module name (e.g. "Week 1", "Module 1", "Unit 1" all map to week 1),
then adds the page "week-N" as a module item of type Page.

Usage:
  export CANVAS_ACCESS_TOKEN="..."
  python add_pages_to_modules.py
  python add_pages_to_modules.py --dry-run
  python add_pages_to_modules.py --course-id 212754
  python add_pages_to_modules.py --list-modules   # just print modules and exit
"""

import argparse
import json
import os
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://osu.instructure.com"
COURSE_ID = "212754"


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


def get_all_pages(url: str, token: str) -> list:
    """Fetch all pages of a paginated Canvas API endpoint."""
    results = []
    next_url = url
    while next_url:
        req = Request(next_url, method="GET", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        try:
            with urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                results.extend(json.loads(raw))
                # Parse Link header for next page
                link_header = resp.headers.get("Link", "")
                next_url = None
                for part in link_header.split(","):
                    part = part.strip()
                    if 'rel="next"' in part:
                        m = re.search(r"<([^>]+)>", part)
                        if m:
                            next_url = m.group(1)
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GET {next_url} -> HTTP {e.code}\n{err_body}") from e
        except URLError as e:
            raise RuntimeError(f"GET {next_url} -> Network error: {e}") from e
    return results


def week_number_from_name(name: str) -> int | None:
    """Extract a week number from a module name, or return None."""
    m = re.search(r"\b(\d+)\b", name)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(
        description="Add week-N pages to matching Canvas modules"
    )
    ap.add_argument("--course-id", default=COURSE_ID, help="Canvas course ID")
    ap.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without changing anything"
    )
    ap.add_argument(
        "--list-modules", action="store_true", help="Print all modules and exit"
    )
    ap.add_argument(
        "--position", type=int, default=1,
        help="Position within the module to insert the page item (default: 1)"
    )
    args = ap.parse_args()

    token = os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: CANVAS_ACCESS_TOKEN is not set in the environment.", file=sys.stderr)
        sys.exit(2)

    modules_url = f"{BASE_URL}/api/v1/courses/{args.course_id}/modules?per_page=100"
    print("Fetching modules...")
    modules = get_all_pages(modules_url, token)
    print(f"Found {len(modules)} module(s).\n")

    if args.list_modules:
        for mod in modules:
            week = week_number_from_name(mod["name"])
            week_str = f"-> week-{week}" if week else "(no week number found)"
            print(f"  [{mod['id']}] pos={mod['position']:2d}  {mod['name']!r}  {week_str}")
        return

    # Build a map: week_number -> module
    week_to_module = {}
    for mod in modules:
        week = week_number_from_name(mod["name"])
        if week is not None:
            if week in week_to_module:
                print(
                    f"WARNING: multiple modules match week {week} "
                    f"({week_to_module[week]['name']!r} and {mod['name']!r}); "
                    f"using first match.",
                    file=sys.stderr,
                )
            else:
                week_to_module[week] = mod

    if not week_to_module:
        print("ERROR: Could not parse a week number from any module name.", file=sys.stderr)
        print("Run with --list-modules to inspect module names.", file=sys.stderr)
        sys.exit(1)

    added = 0
    skipped = 0
    errors = 0

    for week, mod in sorted(week_to_module.items()):
        page_slug = f"week-{week}"
        module_id = mod["id"]
        module_name = mod["name"]
        items_url = f"{BASE_URL}/api/v1/courses/{args.course_id}/modules/{module_id}/items"

        print(f"Week {week:2d}: adding page '{page_slug}' to module {module_id} ({module_name!r})", end="")

        if args.dry_run:
            print(" [dry-run]")
            continue

        try:
            result = http_json("POST", items_url, token, data_dict={
                "module_item[type]": "Page",
                "module_item[page_url]": page_slug,
                "module_item[position]": str(args.position),
            })
            print(f" [added, item id: {result.get('id')}]")
            added += 1
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                print(f" [page '{page_slug}' not found on Canvas, skipped]")
                skipped += 1
            else:
                print(f" [ERROR: {e}]")
                errors += 1

    if not args.dry_run:
        print(f"\nDone. Added: {added}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
