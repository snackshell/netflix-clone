#!/usr/bin/env python3
"""linuxlist - browse a curated list of Linux software.

Zero dependencies. Python 3.8+.

Examples:
    python3 linuxlist.py
    python3 linuxlist.py --category Audio
    python3 linuxlist.py --search "tag editor" --foss
    python3 linuxlist.py --format md > LIST.md
    python3 linuxlist.py --format html > list.html
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Sequence

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "software.json")

CATEGORIES: Sequence[str] = (
    "Audio",
    "Communication",
    "Development",
    "Education",
    "File Management",
    "Graphics",
    "Internet",
    "Office",
    "Security",
    "System",
    "Utilities",
    "Video",
)

PACKAGES: Sequence[str] = (
    "apt",
    "dnf",
    "pacman",
    "flatpak",
    "snap",
    "appimage",
    "manual",
)

REQUIRED_FIELDS = ("name", "category", "description", "license", "foss", "package", "tags")


class DataError(Exception):
    """Raised when the dataset is malformed."""


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------

def load_software(path: str = DATA_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise DataError("dataset not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except json.JSONDecodeError as exc:
            raise DataError("{} is not valid JSON: {}".format(path, exc)) from exc

    if not isinstance(raw, list):
        raise DataError("top-level JSON value must be a list of software entries")

    validate(raw)
    return raw


def validate(entries: Iterable[Any]) -> None:
    seen = set()
    for index, entry in enumerate(entries):
        where = "entry #{}".format(index)
        if not isinstance(entry, dict):
            raise DataError("{} is not an object".format(where))
        for field in REQUIRED_FIELDS:
            if field not in entry:
                raise DataError("{} is missing field '{}'".format(where, field))

        name = entry["name"]
        where = "entry #{} ({})".format(index, name)

        if not isinstance(name, str) or not name.strip():
            raise DataError("{} has an empty name".format(where))
        if name in seen:
            raise DataError("{} is a duplicate name".format(where))
        seen.add(name)

        if entry["category"] not in CATEGORIES:
            raise DataError("{} has unknown category '{}'".format(where, entry["category"]))
        if entry["package"] not in PACKAGES:
            raise DataError("{} has unknown package source '{}'".format(where, entry["package"]))
        if not isinstance(entry["foss"], bool):
            raise DataError("{} has non-boolean 'foss'".format(where))
        if not isinstance(entry["tags"], list) or not all(isinstance(t, str) for t in entry["tags"]):
            raise DataError("{} has invalid 'tags'".format(where))
        for field in ("description", "license"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise DataError("{} has an empty '{}'".format(where, field))


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------

def filter_entries(
    entries: Sequence[Dict[str, Any]],
    category: str | None = None,
    search: str | None = None,
    foss_only: bool = False,
    package: str | None = None,
) -> List[Dict[str, Any]]:
    result = list(entries)

    if category:
        needle = category.strip().lower()
        result = [e for e in result if e["category"].lower() == needle]

    if package:
        needle = package.strip().lower()
        result = [e for e in result if e["package"].lower() == needle]

    if foss_only:
        result = [e for e in result if e["foss"]]

    if search:
        terms = [t for t in search.lower().split() if t]
        result = [e for e in result if _matches(e, terms)]

    result.sort(key=lambda e: (e["category"].lower(), e["name"].lower()))
    return result


def _haystack(entry: Dict[str, Any]) -> str:
    return " ".join(
        [
            entry["name"],
            entry["category"],
            entry["description"],
            entry["license"],
            entry["package"],
            " ".join(entry["tags"]),
        ]
    ).lower()


def _matches(entry: Dict[str, Any], terms: Sequence[str]) -> bool:
    haystack = _haystack(entry)
    return all(term in haystack for term in terms)


# --------------------------------------------------------------------------
# Renderers
# --------------------------------------------------------------------------

def render_table(entries: Sequence[Dict[str, Any]]) -> str:
    if not entries:
        return "No matching software."

    headers = ("Name", "Category", "License", "Package", "Description")
    rows = [
        (
            e["name"],
            e["category"],
            e["license"],
            e["package"],
            e["description"],
        )
        for e in entries
    ]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(row: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines.extend(fmt(row) for row in rows)
    lines.append("")
    lines.append("{} entr{}.".format(len(rows), "y" if len(rows) == 1 else "ies"))
    return "\n".join(lines)


def render_markdown(entries: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = ["# Linux Software List", ""]
    if not entries:
        lines.append("_No matching software._")
        return "\n".join(lines) + "\n"

    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        by_category.setdefault(entry["category"], []).append(entry)

    for category in sorted(by_category):
        lines.append("## {}".format(category))
        lines.append("")
        for entry in sorted(by_category[category], key=lambda e: e["name"].lower()):
            meta = [entry["license"], entry["package"]]
            if not entry["foss"]:
                meta.append("closed source")
            lines.append(
                "- **{}** — {} _({})_".format(
                    entry["name"],
                    entry["description"],
                    ", ".join(meta),
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(entries: Sequence[Dict[str, Any]]) -> str:
    return json.dumps(list(entries), indent=2, ensure_ascii=False) + "\n"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Linux Software List</title>
<style>
  :root {
    --bg: #10131a;
    --panel: #171b24;
    --line: #262c3a;
    --text: #e6e9f0;
    --muted: #8b93a7;
    --accent: #6ea8fe;
    --foss: #3ddc97;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 2.5rem 1.25rem 4rem;
    background: var(--bg);
    color: var(--text);
    font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  main { max-width: 68rem; margin: 0 auto; }
  h1 { font-size: 1.9rem; margin: 0 0 .35rem; letter-spacing: -.02em; }
  .sub { color: var(--muted); margin: 0 0 2rem; }
  h2 {
    font-size: .82rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    color: var(--accent);
    margin: 2.4rem 0 .8rem;
    padding-bottom: .4rem;
    border-bottom: 1px solid var(--line);
  }
  .grid { display: grid; gap: .7rem; grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr)); }
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: .85rem 1rem;
  }
  .card h3 { margin: 0 0 .3rem; font-size: 1rem; font-weight: 600; }
  .card p { margin: 0 0 .6rem; color: var(--muted); font-size: .88rem; }
  .meta { display: flex; flex-wrap: wrap; gap: .35rem; font-size: .72rem; }
  .pill {
    padding: .12rem .5rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    color: var(--muted);
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
  }
  .pill.foss { color: var(--foss); border-color: rgba(61, 220, 151, .35); }
  .empty { color: var(--muted); }
  footer { margin-top: 3rem; color: var(--muted); font-size: .8rem; }
</style>
</head>
<body>
<main>
  <h1>Linux Software List</h1>
  <p class="sub">__COUNT__ entries &middot; generated by linuxlist.py</p>
  __BODY__
  <footer>Data lives in data/software.json. Regenerate with <code>python3 linuxlist.py --format html</code>.</footer>
</main>
</body>
</html>
"""


def render_html(entries: Sequence[Dict[str, Any]]) -> str:
    if not entries:
        body = '<p class="empty">No matching software.</p>'
    else:
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries:
            by_category.setdefault(entry["category"], []).append(entry)

        chunks: List[str] = []
        for category in sorted(by_category):
            chunks.append("<h2>{}</h2>".format(html.escape(category)))
            chunks.append('<div class="grid">')
            for entry in sorted(by_category[category], key=lambda e: e["name"].lower()):
                foss_class = " foss" if entry["foss"] else ""
                chunks.append(
                    '  <article class="card">\n'
                    "    <h3>{name}</h3>\n"
                    "    <p>{desc}</p>\n"
                    '    <div class="meta">\n'
                    '      <span class="pill{foss_class}">{license}</span>\n'
                    '      <span class="pill">{package}</span>\n'
                    "    </div>\n"
                    "  </article>".format(
                        name=html.escape(entry["name"]),
                        desc=html.escape(entry["description"]),
                        license=html.escape(entry["license"]),
                        package=html.escape(entry["package"]),
                        foss_class=foss_class,
                    )
                )
            chunks.append("</div>")
        body = "\n".join(chunks)

    return (
        HTML_TEMPLATE.replace("__COUNT__", str(len(entries)))
        .replace("__BODY__", body)
    )


RENDERERS = {
    "table": render_table,
    "md": render_markdown,
    "markdown": render_markdown,
    "json": render_json,
    "html": render_html,
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linuxlist",
        description="Browse a curated list of Linux software.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "categories: {}\n"
            "packages:   {}".format(", ".join(CATEGORIES), ", ".join(PACKAGES))
        ),
    )
    parser.add_argument("-c", "--category", help="filter by category (case-insensitive)")
    parser.add_argument("-s", "--search", help="search names, tags, descriptions (all terms must match)")
    parser.add_argument("--foss", action="store_true", help="only free/open-source entries")
    parser.add_argument("-p", "--package", help="filter by primary package source")
    parser.add_argument(
        "-f",
        "--format",
        default="table",
        choices=sorted(RENDERERS),
        help="output format (default: table)",
    )
    parser.add_argument("--data", default=DATA_PATH, help="path to software.json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        entries = load_software(args.data)
    except DataError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    selected = filter_entries(
        entries,
        category=args.category,
        search=args.search,
        foss_only=args.foss,
        package=args.package,
    )

    renderer = RENDERERS[args.format]
    output = renderer(selected)
    sys.stdout.write(output if output.endswith("\n") else output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
