#!/usr/bin/env python3
"""
Upload the contents of an HTML file into a Canvas PAGE body field,
using ONLY the Python standard library.

Usage:
  export CANVAS_ACCESS_TOKEN="..."
  python upload_page_html_stdlib.py page.html \
    https://osu.instructure.com/courses/205092/pages/some-page-slug

Notes:
- This REPLACES the page body with the file contents (or <body> contents if present).
- The page identifier in the URL is the page "url"/slug (not the numeric page id).
"""

import argparse
import json
import os
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse, urlencode, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def parse_page_url(url: str):
    p = urlparse(url)
    if not p.scheme or not p.netloc:
        raise ValueError(f"Not a valid URL: {url}")

    parts = [x for x in p.path.split("/") if x]
    # Expect: /courses/{course_id}/pages/{page_slug}
    try:
        i = parts.index("courses")
        course_id = parts[i + 1]
        j = parts.index("pages")
        page_slug = parts[j + 1]
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"URL path must look like /courses/<course_id>/pages/<page_slug>, got: {p.path}"
        ) from e

    base = f"{p.scheme}://{p.netloc}"
    # Canvas uses the "url" field for pages; it is URL-decoded in API paths.
    page_slug = unquote(page_slug)
    return base, course_id, page_slug


def http_json(method: str, url: str, token: str, data_dict=None, timeout=60):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    data_bytes = None
    if data_dict is not None:
        # Canvas accepts x-www-form-urlencoded for updates
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


class BodyExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_body = False
        self.seen_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "body":
            self.in_body = True
            self.seen_body = True
            return
        if self.in_body:
            self.parts.append(self._format_starttag(tag, attrs, closed=False))

    def handle_startendtag(self, tag, attrs):
        if self.in_body:
            self.parts.append(self._format_starttag(tag, attrs, closed=True))

    def handle_endtag(self, tag):
        if tag.lower() == "body":
            self.in_body = False
            return
        if self.in_body:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.in_body:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.in_body:
            self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        if self.in_body:
            self.parts.append(f"<!--{data}-->")

    def _format_starttag(self, tag, attrs, closed: bool):
        return format_starttag(tag, attrs, closed)


def format_starttag(tag, attrs, closed: bool):
    if not attrs:
        return f"<{tag}{' /' if closed else ''}>"
    attr_strs = []
    for key, value in attrs:
        if value is None:
            attr_strs.append(key)
        else:
            escaped = value.replace('"', "&quot;")
            attr_strs.append(f'{key}="{escaped}"')
    attr_section = " ".join(attr_strs)
    return f"<{tag} {attr_section}{' /' if closed else ''}>"


HEADER_STYLE = (
    "margin: 0 0 1.5rem 0; padding: 1rem 1.25rem; "
    "background: #f7f4ea; border-left: 4px solid #b07c2b; "
    "border-radius: 6px;"
)
TITLE_STYLE = (
    "margin: 0 0 0.35rem 0; font-size: 1.6rem; font-weight: 700; "
    "line-height: 1.2; color: #2d2110;"
)
AUTHOR_STYLE = "margin: 0; font-size: 1rem; font-weight: 600; color: #4b3a1a;"
DATE_STYLE = "margin: 0.1rem 0 0; font-size: 0.95rem; color: #6a5b3a;"
UNNUMBERED_H1_STYLE = (
    "margin: 1.5rem 0 0.5rem; font-size: 1.25rem; text-transform: uppercase; "
    "letter-spacing: 0.04em; color: #3a2c17; border-bottom: 1px solid #d8c8a2; "
    "padding-bottom: 0.2rem;"
)
PARAGRAPH_STYLE = (
    "margin: 0 0 0.9rem; font-size: 1.02rem; line-height: 1.6; color: #2f2a22;"
)


def merge_style(attrs, style_add):
    if not style_add:
        return attrs
    style_idx = None
    for i, (key, _) in enumerate(attrs):
        if key == "style":
            style_idx = i
            break
    if style_idx is None:
        attrs.append(("style", style_add))
        return attrs
    existing = attrs[style_idx][1] or ""
    existing = existing.strip()
    if existing.endswith(";"):
        merged = f"{existing} {style_add}"
    elif existing:
        merged = f"{existing}; {style_add}"
    else:
        merged = style_add
    attrs[style_idx] = ("style", merged)
    return attrs


def class_list(attrs):
    for key, value in attrs:
        if key == "class" and value:
            return value.split()
    return []


class HTMLStyler(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.in_title_header = False

    def handle_starttag(self, tag, attrs):
        attrs = list(attrs)
        attrs_map = {key: value for key, value in attrs}
        classes = class_list(attrs)
        style_add = ""

        if tag.lower() == "header" and attrs_map.get("id") == "title-block-header":
            self.in_title_header = True
            style_add = HEADER_STYLE
        elif tag.lower() == "h1" and "title" in classes:
            style_add = TITLE_STYLE
        elif tag.lower() == "h1" and "unnumbered" in classes:
            style_add = UNNUMBERED_H1_STYLE
        elif tag.lower() == "p":
            if self.in_title_header and "author" in classes:
                style_add = AUTHOR_STYLE
            elif self.in_title_header and "date" in classes:
                style_add = DATE_STYLE
            elif not self.in_title_header:
                style_add = PARAGRAPH_STYLE

        attrs = merge_style(attrs, style_add)
        self.parts.append(format_starttag(tag, attrs, closed=False))

    def handle_startendtag(self, tag, attrs):
        attrs = list(attrs)
        attrs_map = {key: value for key, value in attrs}
        classes = class_list(attrs)
        style_add = ""

        if tag.lower() == "header" and attrs_map.get("id") == "title-block-header":
            style_add = HEADER_STYLE
        elif tag.lower() == "h1" and "title" in classes:
            style_add = TITLE_STYLE
        elif tag.lower() == "h1" and "unnumbered" in classes:
            style_add = UNNUMBERED_H1_STYLE
        elif tag.lower() == "p" and not self.in_title_header:
            style_add = PARAGRAPH_STYLE

        attrs = merge_style(attrs, style_add)
        self.parts.append(format_starttag(tag, attrs, closed=True))

    def handle_endtag(self, tag):
        if tag.lower() == "header" and self.in_title_header:
            self.in_title_header = False
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")


def extract_body_html(html: str):
    parser = BodyExtractor()
    parser.feed(html)
    parser.close()
    if parser.seen_body:
        return "".join(parser.parts), True
    return html, False


def style_html(html: str):
    parser = HTMLStyler()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html_file", help="Path to HTML file (e.g., page.html)")
    ap.add_argument("page_url", help="Canvas page URL (e.g., .../courses/123/pages/slug)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would happen, but don't update")
    ap.add_argument("--publish", action="store_true",
                    help="Also publish the page (wiki_page[published]=true)")
    args = ap.parse_args()

    token = os.environ.get("CANVAS_ACCESS_TOKEN")
    if token is not None:
        token = token.strip()
    if not token:
        print("ERROR: CANVAS_ACCESS_TOKEN is not set in the environment.", file=sys.stderr)
        sys.exit(2)

    base_url, course_id, page_slug = parse_page_url(args.page_url)
    api = f"{base_url}/api/v1/courses/{course_id}/pages/{page_slug}"

    # Read HTML file
    try:
        with open(args.html_file, "r", encoding="utf-8") as f:
            new_html = f.read()
    except OSError as e:
        print(f"ERROR: Could not read {args.html_file}: {e}", file=sys.stderr)
        sys.exit(2)

    new_html, used_body = extract_body_html(new_html)
    new_html = style_html(new_html)

    # Fetch current page (useful sanity check)
    page = http_json("GET", api, token, timeout=30)
    title = page.get("title", "(no title)")
    current_pub = page.get("published", None)
    print(f"Page: {title} (slug: {page_slug})")
    if current_pub is not None:
        print(f"Currently published: {current_pub}")
    if used_body:
        print("Using <body> contents only.")
    print(f"Replacing page body with {len(new_html)} characters from {args.html_file}")

    if args.dry_run:
        print("Dry run: not updating.")
        return

    payload = {"wiki_page[body]": new_html}
    if args.publish:
        payload["wiki_page[published]"] = "true"

    updated = http_json(
        "PUT",
        api,
        token,
        data_dict=payload,
        timeout=60,
    )

    print("Update successful.")
    print(f"Updated body length: {len(updated.get('body') or '')}")
    if "published" in updated:
        print(f"Published now: {updated.get('published')}")


if __name__ == "__main__":
    main()
