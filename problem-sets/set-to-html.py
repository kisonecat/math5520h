#!/usr/bin/env python3
r"""
tex_problemset_to_html.py

Convert a LaTeX problem set written in Jim's `homework.cls` style into a single
Canvas-friendly HTML file (NO <style> blocks; everything uses inline style).

Key features:
- Recursively inlines \\input{...} files (adds .tex if missing).
- Converts $...$ -> \( ... \) and $$...$$ -> \[ ... \] (and preserves existing \( \), \[ \]).
- Extracts \\newcommand / \\renewcommand definitions and emits them in a hidden
  MathJax block so MathJax knows your macros.
- Converts \\section{...} -> styled <h1>.
- Converts \\begin{problem} ... \\end{problem} -> styled "card" with problem id S01P02 etc.
- Converts \\emph{...}, \\textbf{...}, \\textit{...} to HTML.
- Converts enumerate/itemize to <ol>/<ul>.
- Uses the problem set number from the filename digits (first run of digits), padded to 2.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# --------------------------
# Utilities
# --------------------------

DIGITS_RE = re.compile(r"(\d+)")
SECTION_RE = re.compile(r"\\section\{")
BEGIN_PROBLEM_RE = re.compile(r"\\begin\{problem\*?\}")
END_PROBLEM_RE = re.compile(r"\\end\{problem\*?\}")
BEGIN_ENV_RE = re.compile(r"\\begin\{([a-zA-Z*]+)\}")
END_ENV_RE = re.compile(r"\\end\{([a-zA-Z*]+)\}")

MATH_BLOCK_ENVS = {
    "equation", "equation*",
    "align", "align*",
    "gather", "gather*",
    "multline", "multline*",
    "flalign", "flalign*",
    "alignat", "alignat*",
}

NEWCOMMAND_START_RE = re.compile(
    r"""\\(re)?newcommand\b|\\DeclareMathOperator\b|\\def\b""",
    re.MULTILINE
)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(r"\\ref\{([^}]+)\}")
SET_TEX_RE = re.compile(r"^set\d+\.tex$")

# Match \input{foo} and \input foo
INPUT_RE = re.compile(r"""\\input\s*(\{([^}]+)\}|([^\s%]+))""")

def html_escape_content(s: str) -> str:
    # Escape content that will appear as text (including TeX for MathJax).
    # Do NOT escape quotes; leave them alone.
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def replace_tex_dashes(s: str) -> str:
    # Convert TeX-style dashes to Unicode en/em dashes.
    # This avoids entities being rendered literally by downstream HTML sanitizers.
    return s.replace("---", "—").replace("--", "–")


def strip_comments(tex: str) -> str:
    # Remove TeX comments: everything after an unescaped %
    out_lines = []
    for line in tex.splitlines():
        i = 0
        while True:
            j = line.find("%", i)
            if j == -1:
                out_lines.append(line)
                break
            # if escaped \%
            if j > 0 and line[j - 1] == "\\":
                i = j + 1
                continue
            out_lines.append(line[:j])
            break
    return "\n".join(out_lines)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def resolve_inputs(tex: str, base_dir: str, seen: Optional[set] = None) -> str:
    r"""
    Recursively inline \\input{...} files.
    """
    if seen is None:
        seen = set()

    def repl(match: re.Match) -> str:
        fname = match.group(2) or match.group(3) or ""
        fname = fname.strip()
        if not fname:
            return ""

        # If no extension, add .tex
        if not os.path.splitext(fname)[1]:
            fname2 = fname + ".tex"
        else:
            fname2 = fname

        path = os.path.normpath(os.path.join(base_dir, fname2))
        if path in seen:
            return f"\n% (skipping recursive input: {fname2})\n"
        if not os.path.exists(path):
            # If file not found, leave a marker rather than failing.
            return f"\n% (missing input file: {fname2})\n"

        seen.add(path)
        content = read_text(path)
        content = strip_comments(content)
        content = resolve_inputs(content, os.path.dirname(path), seen)
        return "\n" + content + "\n"

    # Expand until no more \input occurrences (in case inputs introduce more inputs)
    prev = None
    cur = tex
    while prev != cur:
        prev = cur
        cur = INPUT_RE.sub(repl, cur)
    return cur


def first_digits_from_filename(path: str) -> int:
    base = os.path.splitext(os.path.basename(path))[0]
    m = DIGITS_RE.search(base)
    if not m:
        return 1
    return int(m.group(1))


def pad2(n: int) -> str:
    return f"{n:02d}"

def find_set_tex_files(base_dir: str) -> List[str]:
    return [
        os.path.join(base_dir, name)
        for name in os.listdir(base_dir)
        if SET_TEX_RE.match(name)
    ]


# --------------------------
# Math delimiter conversion
# --------------------------

def convert_dollar_math_to_paren_bracket(tex: str) -> str:
    r"""
    Convert:
      $$...$$ -> \[...\]
      $...$   -> \(...\)
    while respecting:
      - escaped \$ (ignored)
      - existing \( \) and \[ \] remain
      - do not convert inside \verb (not handled) or verbatim (not handled)
    This is a best-effort converter appropriate for typical homework sets.
    """
    s = tex
    out = []
    i = 0
    n = len(s)
    in_inline = False
    in_display = False

    while i < n:
        ch = s[i]

        # Handle escaped dollars
        if ch == "\\" and i + 1 < n and s[i + 1] == "$":
            out.append("\\$")
            i += 2
            continue

        # If we see $$ toggle display math
        if ch == "$" and i + 1 < n and s[i + 1] == "$":
            if in_display:
                out.append(r"\]")
                in_display = False
            else:
                out.append(r"\[")
                in_display = True
            i += 2
            continue

        # Single $ toggles inline math, but only if not in display mode
        if ch == "$" and not in_display:
            if in_inline:
                out.append(r"\)")
                in_inline = False
            else:
                out.append(r"\(")
                in_inline = True
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def wrap_math_environments_in_brackets(tex: str) -> str:
    r"""
    Wrap display math environments in \[ ... \] if they aren't already.
    E.g. \begin{align}...\end{align} becomes \[\begin{align}...\end{align}\]
    """
    def repl(match: re.Match) -> str:
        env = match.group(1)
        body = match.group(2)
        if env in MATH_BLOCK_ENVS:
            return r"\[" + f"\\begin{{{env}}}" + body + f"\\end{{{env}}}" + r"\]"
        return match.group(0)

    pattern = re.compile(r"\\begin\{([a-zA-Z*]+)\}(.*?)\\end\{\1\}", re.DOTALL)
    return pattern.sub(repl, tex)


# --------------------------
# Macro extraction
# --------------------------

def extract_newcommand_blocks(tex: str) -> Tuple[List[str], str]:
    r"""
    Extract \newcommand/\renewcommand/\DeclareMathOperator/\def blocks
    using a lightweight parser. Returns (list_of_macro_defs, tex_with_macros_removed).
    """
    def skip_ws(s: str, pos: int) -> int:
        while pos < len(s) and s[pos].isspace():
            pos += 1
        return pos

    def parse_control_sequence(s: str, pos: int) -> Optional[int]:
        if pos >= len(s) or s[pos] != "\\":
            return None
        pos += 1
        if pos >= len(s):
            return pos
        if s[pos].isalpha():
            while pos < len(s) and s[pos].isalpha():
                pos += 1
            return pos
        # Single-char control sequence like \{
        return pos + 1

    def parse_balanced(s: str, pos: int, open_ch: str, close_ch: str) -> Optional[int]:
        if pos >= len(s) or s[pos] != open_ch:
            return None
        depth = 1
        pos += 1
        while pos < len(s) and depth > 0:
            c = s[pos]
            if c == "\\" and pos + 1 < len(s):
                pos += 2
                continue
            if c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
            pos += 1
        return pos if depth == 0 else None

    def find_unescaped(s: str, pos: int, ch: str) -> int:
        while pos < len(s):
            if s[pos] == "\\" and pos + 1 < len(s):
                pos += 2
                continue
            if s[pos] == ch:
                return pos
            pos += 1
        return -1

    macros: List[str] = []
    keep = []
    i = 0
    n = len(tex)

    while i < n:
        m = NEWCOMMAND_START_RE.search(tex, i)
        if not m:
            keep.append(tex[i:])
            break

        start = m.start()
        keep.append(tex[i:start])

        cmd = m.group(0)
        j = m.end()

        j = skip_ws(tex, j)
        if cmd == r"\DeclareMathOperator":
            if j < n and tex[j] == "*":
                j += 1
            j = skip_ws(tex, j)
            # macro name
            if j < n and tex[j] == "{":
                end = parse_balanced(tex, j, "{", "}")
                j = end if end is not None else j
            else:
                end = parse_control_sequence(tex, j)
                j = end if end is not None else j
            j = skip_ws(tex, j)
            # operator text
            if j < n and tex[j] == "{":
                end = parse_balanced(tex, j, "{", "}")
                j = end if end is not None else j
        elif cmd in (r"\newcommand", r"\renewcommand"):
            # macro name (either {..} or control sequence)
            if j < n and tex[j] == "{":
                end = parse_balanced(tex, j, "{", "}")
                j = end if end is not None else j
            else:
                end = parse_control_sequence(tex, j)
                j = end if end is not None else j
            j = skip_ws(tex, j)
            # optional [n] and [default]
            if j < n and tex[j] == "[":
                end = parse_balanced(tex, j, "[", "]")
                j = end if end is not None else j
                j = skip_ws(tex, j)
                if j < n and tex[j] == "[":
                    end = parse_balanced(tex, j, "[", "]")
                    j = end if end is not None else j
                    j = skip_ws(tex, j)
            # definition body
            if j < n and tex[j] == "{":
                end = parse_balanced(tex, j, "{", "}")
                j = end if end is not None else j
        elif cmd == r"\def":
            # \def\foo#1{...}
            end = parse_control_sequence(tex, j)
            j = end if end is not None else j
            brace_pos = find_unescaped(tex, j, "{")
            if brace_pos != -1:
                end = parse_balanced(tex, brace_pos, "{", "}")
                j = end if end is not None else brace_pos

        block = tex[start:j].strip()
        if block:
            macros.append(block)
        i = j

    return macros, "".join(keep)


# --------------------------
# LaTeX -> HTML (within sections/problems)
# --------------------------

def find_matching_env(tex: str, begin_pos: int, envname: str) -> int:
    r"""
    Given position at the '\' of \begin{envname}, find matching \end{envname}.
    Returns index of the start of the matching \end{...}. Raises ValueError if not found.
    """
    # Find the first \begin{envname} at/after begin_pos to sync
    m0 = re.compile(rf"\\begin\{{{re.escape(envname)}\}}").search(tex, begin_pos)
    if not m0:
        raise ValueError(f"begin not found for env {envname}")
    i = m0.end()
    depth = 1
    begin_pat = re.compile(rf"\\begin\{{{re.escape(envname)}\}}")
    end_pat = re.compile(rf"\\end\{{{re.escape(envname)}\}}")
    while i < len(tex):
        mb = begin_pat.search(tex, i)
        me = end_pat.search(tex, i)
        if not me:
            break
        if mb and mb.start() < me.start():
            depth += 1
            i = mb.end()
        else:
            depth -= 1
            if depth == 0:
                return me.start()
            i = me.end()
    raise ValueError(f"end not found for env {envname}")


def split_top_level_items(env_body: str) -> List[str]:
    r"""
    Split an enumerate/itemize body into top-level \item chunks.
    We ignore nested environments when searching for \item by doing a lightweight scan.
    """
    items: List[str] = []
    i = 0
    n = len(env_body)

    # Find first \item
    item_re = re.compile(r"\\item\b")
    m = item_re.search(env_body)
    if not m:
        return [env_body.strip()] if env_body.strip() else []

    starts = []
    while m:
        starts.append(m.start())
        m = item_re.search(env_body, m.end())

    # Now slice between these starts
    for k, st in enumerate(starts):
        en = starts[k + 1] if k + 1 < len(starts) else n
        chunk = env_body[st:]
        # remove leading \item
        chunk = chunk[len(r"\item"):]
        # up to next item
        chunk = env_body[st + len(r"\item"):en]
        items.append(chunk.strip())
    return items


def convert_lists(tex: str) -> str:
    r"""
    Convert enumerate/itemize environments recursively to <ol>/<ul>.
    """
    # Convert deepest-first by repeatedly replacing the first occurrence.
    begin_list = re.compile(r"\\begin\{(enumerate|itemize)\}")
    while True:
        m = begin_list.search(tex)
        if not m:
            break
        env = m.group(1)
        begin_pos = m.start()
        end_pos = find_matching_env(tex, begin_pos, env)
        end_tag = re.compile(rf"\\end\{{{re.escape(env)}\}}").search(tex, end_pos)
        if not end_tag:
            break

        inner = tex[m.end():end_pos]
        # Recurse first (handle nested)
        inner = convert_lists(inner)

        items = split_top_level_items(inner)
        tag = "ol" if env == "enumerate" else "ul"
        li_html = []
        for it in items:
            li_html.append(f"<li style=\"margin: 0.35em 0;\">{latex_to_html_inline(it)}</li>")
        block = f"<{tag} style=\"margin: 0.6em 0 0.6em 1.2em; padding-left: 1.2em;\">{''.join(li_html)}</{tag}>"

        tex = tex[:begin_pos] + block + tex[end_tag.end():]
    return tex


def replace_command_arg_balanced(s: str, cmd: str, open_tag: str, close_tag: str) -> str:
    r"""
    Replace occurrences of \cmd{...} with open_tag ... close_tag, brace-balanced.
    """
    pat = re.compile(rf"\\{re.escape(cmd)}\{{")
    i = 0
    out = []
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        j = m.end()  # position after \cmd{
        depth = 1
        start_content = j
        while j < len(s) and depth > 0:
            if s[j] == "\\" and j + 1 < len(s):
                j += 2
                continue
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
            j += 1
        content = s[start_content:j - 1]  # exclude final }
        content_html = latex_to_html_inline(content)
        out.append(open_tag + content_html + close_tag)
        i = j
    return "".join(out)


def replace_grouped_command(tex: str, cmd: str, open_tag: str, close_tag: str) -> str:
    r"""
    Replace occurrences of {\cmd ...} with open_tag ... close_tag, brace-balanced.
    """
    i = 0
    out = []
    needle = r"{\%s" % cmd
    while True:
        start = tex.find(needle, i)
        if start == -1:
            out.append(tex[i:])
            break
        out.append(tex[i:start])
        j = start + 1  # at '{'
        depth = 1
        while j < len(tex) and tex[j].isspace():
            j += 1
        if tex.startswith(r"\%s" % cmd, j):
            j += len(cmd) + 1
        while j < len(tex) and tex[j].isspace():
            j += 1
        content_start = j
        while j < len(tex) and depth > 0:
            if tex[j] == "\\" and j + 1 < len(tex):
                j += 2
                continue
            if tex[j] == "{":
                depth += 1
            elif tex[j] == "}":
                depth -= 1
            j += 1
        content = tex[content_start:j - 1]
        content_html = latex_to_html_inline(content)
        out.append(open_tag + content_html + close_tag)
        i = j
    return "".join(out)


def split_by_math_segments(tex: str) -> List[Tuple[bool, str]]:
    r"""
    Split into segments (is_math, text) based on \( \) and \[ \].
    """
    segs: List[Tuple[bool, str]] = []
    i = 0
    n = len(tex)

    def startswith_at(prefix: str, pos: int) -> bool:
        return tex.startswith(prefix, pos)

    while i < n:
        if startswith_at(r"\(", i):
            # inline math
            j = i + 2
            while j < n and not startswith_at(r"\)", j):
                # skip escaped sequences
                if tex[j] == "\\" and j + 1 < n:
                    j += 2
                else:
                    j += 1
            if j >= n:
                # unmatched, treat as text
                segs.append((False, tex[i:]))
                break
            segs.append((True, tex[i:j + 2]))
            i = j + 2
            continue

        if startswith_at(r"\[", i):
            # display math
            j = i + 2
            while j < n and not startswith_at(r"\]", j):
                if tex[j] == "\\" and j + 1 < n:
                    j += 2
                else:
                    j += 1
            if j >= n:
                segs.append((False, tex[i:]))
                break
            segs.append((True, tex[i:j + 2]))
            i = j + 2
            continue

        # text chunk until next math start
        j = i
        while j < n and not startswith_at(r"\(", j) and not startswith_at(r"\[", j):
            j += 1
        segs.append((False, tex[i:j]))
        i = j

    return segs


def latex_to_html_inline(tex: str) -> str:
    r"""
    Convert a LaTeX fragment to HTML (inline), preserving MathJax TeX.
    """
    def protect_tags(text: str) -> Tuple[str, List[str]]:
        protected: List[str] = []

        def repl(m: re.Match) -> str:
            protected.append(m.group(0))
            return f"@@TAG{len(protected) - 1}@@"

        tag_re = re.compile(r"</?(?:em|strong|ol|ul|li|span)\b[^>]*>|<br\s*/?>")
        return tag_re.sub(repl, text), protected

    def restore_tags(text: str, protected: List[str]) -> str:
        for i, tag in enumerate(protected):
            text = text.replace(f"@@TAG{i}@@", tag)
        return text

    # First convert lists at block-level (it returns HTML for lists)
    tex = convert_lists(tex)

    # Convert dollar math to \( \) / \[ \], and wrap math envs
    tex = wrap_math_environments_in_brackets(tex)
    tex = convert_dollar_math_to_paren_bracket(tex)

    tex = replace_grouped_command(tex, "footnotesize", "<span style=\"font-size: 0.9em;\">", "</span>")

    # Basic inline formatting commands (balanced braces), before math splitting
    tex = replace_command_arg_balanced(tex, "emph", "<em>", "</em>")
    tex = replace_command_arg_balanced(tex, "textbf", "<strong>", "</strong>")
    tex = replace_command_arg_balanced(tex, "textit", "<em>", "</em>")

    # Split by math segments so we don't clobber TeX with HTML escaping rules too much
    segs = split_by_math_segments(tex)

    out_parts: List[str] = []
    for is_math, seg in segs:
        if is_math:
            # Escape HTML special chars but keep TeX
            out_parts.append(html_escape_content(seg))
        else:
            t = seg
            # line breaks
            t = t.replace(r"\\", "<br/>")
            # Clean whitespace
            t = re.sub(r"[ \t]+\n", "\n", t)
            t = re.sub(r"\n[ \t]+", "\n", t)
            # Escape HTML without escaping tags we generated.
            t, protected = protect_tags(t)
            t = html_escape_content(t)
            # TeX-style quotes (use entities after escaping so & stays intact)
            t = t.replace("``", "&ldquo;").replace("''", "&rdquo;")
            t = replace_tex_dashes(t)
            t = restore_tags(t, protected)
            out_parts.append(t)

    return "".join(out_parts)


def wrap_paragraphs(html: str) -> str:
    r"""
    Turn plain text chunks into <p>...</p>, leaving existing block tags alone.
    Assumes html may already contain <ol>/<ul>/<li>.
    """
    chunks = re.split(r"\n\s*\n", html.strip(), flags=re.MULTILINE)
    out = []
    for ch in chunks:
        ch_strip = ch.strip()
        if not ch_strip:
            continue
        # If it begins with a block tag, keep as-is
        if re.match(r"^\s*<(ol|ul|div|h1|h2|h3|blockquote)\b", ch_strip):
            out.append(ch_strip)
        else:
            # Replace remaining newlines with spaces
            ch_strip = re.sub(r"\s*\n\s*", " ", ch_strip)
            out.append(f"<p style=\"margin: 0.6em 0; line-height: 1.45;\">{ch_strip}</p>")
    return "\n".join(out)


# --------------------------
# Document structure parsing
# --------------------------

@dataclass
class DocMeta:
    course: str = ""
    author: str = ""
    hwtitle: str = ""
    inspiration: str = ""  # raw LaTeX inside inspiration env


def extract_braced_arg(tex: str, cmd: str) -> str:
    m = re.search(rf"\\{re.escape(cmd)}\{{", tex)
    if not m:
        return ""
    i = m.end()
    depth = 1
    start = i
    while i < len(tex) and depth > 0:
        if tex[i] == "\\" and i + 1 < len(tex):
            i += 2
            continue
        if tex[i] == "{":
            depth += 1
        elif tex[i] == "}":
            depth -= 1
        i += 1
    return tex[start:i - 1].strip()


def extract_env(tex: str, env: str) -> str:
    m = re.search(rf"\\begin\{{{re.escape(env)}\}}", tex)
    if not m:
        return ""
    start = m.end()
    end = find_matching_env(tex, m.start(), env)
    return tex[start:end].strip()

def remove_env(tex: str, env: str) -> str:
    while True:
        m = re.search(rf"\\begin\{{{re.escape(env)}\}}", tex)
        if not m:
            return tex
        end = find_matching_env(tex, m.start(), env)
        end_tag = re.search(rf"\\end\{{{re.escape(env)}\}}", tex[end:])
        if not end_tag:
            return tex
        tex = tex[:m.start()] + tex[end + end_tag.end():]


def body_between_document(tex: str) -> str:
    m1 = re.search(r"\\begin\{document\}", tex)
    m2 = re.search(r"\\end\{document\}", tex)
    if not m1 or not m2 or m2.start() <= m1.end():
        return tex
    return tex[m1.end():m2.start()]


def parse_sections_and_problems(body: str) -> List[Tuple[str, str]]:
    r"""
    Produce a list of blocks: ("section", title) or ("problem"/"problem*", content)
    Keeps ordering.
    """
    blocks: List[Tuple[str, str]] = []
    i = 0
    n = len(body)

    # We'll search for next \section or \begin{problem}/\begin{problem*}
    marker_re = re.compile(r"\\section\{|\\begin\{problem\*?\}")

    while True:
        m = marker_re.search(body, i)
        if not m:
            break
        if m.start() > i:
            inter = body[i:m.start()].strip()
            if inter:
                blocks.append(("text", inter))

        if body.startswith(r"\section{", m.start()):
            # parse braced arg
            j = m.end()
            depth = 1
            start = j
            while j < n and depth > 0:
                if body[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            title = body[start:j - 1].strip()
            blocks.append(("section", title))
            i = j
            continue

        # problem or problem*
        pb = re.match(r"\\begin\{(problem\*?)\}", body[m.start():])
        if pb:
            env = pb.group(1)  # 'problem' or 'problem*'
            begin_pos = m.start()
            end_pos = find_matching_env(body, begin_pos, env)
            end_tag = re.compile(rf"\\end\{{{re.escape(env)}\}}").search(body, end_pos)
            if not end_tag:
                # malformed; stop
                break
            content = body[m.start() + len(pb.group(0)):end_pos].strip()
            blocks.append((env, content))
            i = end_tag.end()
            continue

        i = m.end()

    tail = body[i:].strip()
    if tail:
        blocks.append(("text", tail))
    return blocks


# --------------------------
# HTML rendering
# --------------------------

def build_label_map_for_tex(tex_path: str) -> dict[str, str]:
    base_dir = os.path.dirname(os.path.abspath(tex_path)) or "."
    raw = read_text(tex_path)
    raw = strip_comments(raw)
    raw = resolve_inputs(raw, base_dir)
    _, without_macros = extract_newcommand_blocks(raw)
    body = body_between_document(without_macros)
    body = re.sub(r"\\maketitle\b", "", body)
    body = remove_env(body, "inspiration")
    blocks = parse_sections_and_problems(body)

    setno = first_digits_from_filename(tex_path)
    set_id = pad2(setno)
    label_map: dict[str, str] = {}
    prob_counter = 0
    for kind, payload in blocks:
        if kind in ("problem", "problem*"):
            prob_counter += 1
            pid = f"S{set_id}P{pad2(prob_counter)}"
            for label in LABEL_RE.findall(payload):
                if label not in label_map:
                    label_map[label] = pid
    return label_map


def render_html(
    meta: DocMeta,
    setno: int,
    macros: List[str],
    blocks: List[Tuple[str, str]],
    label_map: dict[str, str],
) -> str:
    set_id = pad2(setno)
    term = "Spring 2026"

    # Styles
    page_style = (
        "max-width: 980px; margin: 0 auto; padding: 24px 18px; "
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; "
        "color: #111; background: #fff;"
    )
    header_style = (
        "padding: 6px 0 12px 0; margin: 0 0 18px 0;"
    )
    title_style = "margin: 0; font-size: 24px; line-height: 1.2;"
    subtitle_style = "margin: 6px 0 0 0; font-size: 14px; color: #444;"
    epi_style = (
        "margin: 14px 0 0 0; padding-left: 14px; border-left: 3px solid #e5e7eb; "
        "font-size: 14px; color: #333;"
    )
    section_style = (
        "margin: 22px 0 12px 0; padding-top: 10px; "
        "font-size: 20px; line-height: 1.25;"
    )
    card_style = (
        "margin: 12px 0; padding: 14px 16px; "
        "border: 1px solid #e5e7eb; border-radius: 14px; "
        "box-shadow: 0 6px 18px rgba(0,0,0,0.05); background: #fff;"
    )
    card_title_style = (
        "margin: 0 0 10px 0; font-size: 14px; letter-spacing: 0.02em; "
        "color: #374151; text-transform: uppercase;"
    )

    # Inspiration parsing: try to split \byline{...}
    insp_raw = meta.inspiration.strip()
    byline = ""
    quote = insp_raw
    m_by = re.search(r"\\byline\{", insp_raw)
    if m_by:
        quote = insp_raw[:m_by.start()].strip()
        byline = extract_braced_arg(insp_raw[m_by.start():], "byline").strip()

    quote_html = latex_to_html_inline(quote)
    byline_html = latex_to_html_inline(byline) if byline else ""

    # Hidden MathJax macros block
    macro_block = ""
    if macros:
        # Keep original TeX, but escape for HTML
        joined = " ".join(m.strip() for m in macros if m.strip())
        # Put macros in a hidden inline-math block so MathJax reads them.
        # MathJax v3 will parse macros appearing anywhere before use.
        macro_block = (
            f"<span style=\"display:none;\">{html_escape_content(r'\(' + joined + r'\)')}</span>"
        )

    # Header text
    hwtitle = meta.hwtitle or meta.course or "Problem Set"
    course = meta.course or ""
    header_title = replace_tex_dashes(html_escape_content(f"{hwtitle}: Problem Set #{setno}"))
    if course and term:
        header_sub_html = (
            f"{replace_tex_dashes(html_escape_content(course))}"
            f"&nbsp;&nbsp;{replace_tex_dashes(html_escape_content(term))}"
        )
    else:
        header_sub_html = replace_tex_dashes(html_escape_content(course or term))

    # Begin HTML
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append("<html>")
    parts.append("<head>")
    parts.append("<meta charset=\"utf-8\"/>")
    parts.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>")
    # MathJax (Canvas typically allows external JS in HTML uploads; if not, remove this line)
    parts.append("<script defer src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>")
    parts.append("<title>" + header_title + "</title>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"<div style=\"{page_style}\">")
    parts.append(macro_block)

    # Title area (includes epigraph)
    parts.append(f"<div style=\"{header_style}\">")
    parts.append(f"<h1 style=\"{title_style}\">{header_title}</h1>")
    if header_sub_html:
        parts.append(f"<div style=\"{subtitle_style}\">{header_sub_html}</div>")
    if quote_html or byline_html:
        parts.append(f"<div style=\"{epi_style}\">")
        if quote_html:
            parts.append(f"<div style=\"font-style: italic;\">{quote_html}</div>")
        if byline_html:
            parts.append(f"<div style=\"margin-top: 8px;\">&mdash; {byline_html}</div>")
        parts.append("</div>")
    parts.append("</div>")

    def replace_refs(tex: str) -> str:
        def repl(m: re.Match) -> str:
            return label_map.get(m.group(1), m.group(0))
        return REF_RE.sub(repl, tex)

    # Main blocks
    prob_counter = 0
    for kind, payload in blocks:
        if kind == "section":
            payload = LABEL_RE.sub("", payload)
            payload = replace_refs(payload)
            title = latex_to_html_inline(payload)
            parts.append(f"<h1 style=\"{section_style}\">{title}</h1>")
            continue
        if kind == "text":
            payload = LABEL_RE.sub("", payload)
            payload = replace_refs(payload)
            content_html = latex_to_html_inline(payload)
            content_html = wrap_paragraphs(content_html)
            parts.append(content_html)
            continue

        if kind in ("problem", "problem*"):
            prob_counter += 1
            pid = f"S{set_id}P{pad2(prob_counter)}"
            star = " ★" if kind == "problem*" else ""
            payload = LABEL_RE.sub("", payload)
            payload = replace_refs(payload)
            content_html = latex_to_html_inline(payload)
            content_html = wrap_paragraphs(content_html)

            parts.append(f"<div style=\"{card_style}\">")
            parts.append(f"<div style=\"{card_title_style}\">{html_escape_content(pid)}{html_escape_content(star)}</div>")
            parts.append(content_html)
            parts.append("</div>")
            continue

    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


# --------------------------
# Main
# --------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Convert homework-style LaTeX problem sets to Canvas-friendly HTML.")
    ap.add_argument("texfile", help="Input .tex file (problem set)")
    ap.add_argument("-o", "--output", help="Output .html path (default: same basename).")
    args = ap.parse_args()

    tex_path = args.texfile
    base_dir = os.path.dirname(os.path.abspath(tex_path)) or "."
    raw = read_text(tex_path)
    raw = strip_comments(raw)
    raw = resolve_inputs(raw, base_dir)

    # Extract macros from full expanded source
    macros, without_macros = extract_newcommand_blocks(raw)

    # Extract metadata from full expanded source
    meta = DocMeta(
        course=extract_braced_arg(without_macros, "course"),
        author=extract_braced_arg(without_macros, "author"),
        hwtitle=extract_braced_arg(without_macros, "hwtitle"),
        inspiration=extract_env(without_macros, "inspiration"),
    )

    # Use body only
    body = body_between_document(without_macros)

    # Remove \maketitle (we build our own header)
    body = re.sub(r"\\maketitle\b", "", body)
    body = remove_env(body, "inspiration")

    # Parse blocks
    blocks = parse_sections_and_problems(body)

    # Build label map across all sets in the directory, allowing cross-set refs.
    label_map: dict[str, str] = {}
    set_paths = find_set_tex_files(base_dir)
    current_abs = os.path.abspath(tex_path)
    set_paths.sort(key=first_digits_from_filename)
    for path in set_paths:
        if os.path.abspath(path) == current_abs:
            continue
        other_map = build_label_map_for_tex(path)
        for label, pid in other_map.items():
            if label not in label_map:
                label_map[label] = pid
    current_map = build_label_map_for_tex(tex_path)
    label_map.update(current_map)

    # Render
    setno = first_digits_from_filename(tex_path)
    html = render_html(meta, setno, macros, blocks, label_map)

    out_path = args.output
    if not out_path:
        out_path = os.path.splitext(tex_path)[0] + ".html"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
