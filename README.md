# Draw Me Linux — Software List

A curated, hackable list of Linux software, shipped as data + a tiny zero-dependency CLI.

No build step, no npm install, no network calls. Python 3.8+ only.

## Why

"Draw me a list of Linux software" usually gets you a wall of text. This repo gives you:

- **`data/software.json`** — the actual dataset (name, category, license, package, tags, description).
- **`linuxlist.py`** — a CLI that filters, searches, and renders the list as a table, Markdown, or a standalone HTML page.
- **`data/categories.md`** — a human-readable index generated from the JSON.

## Usage

```bash
# Everything, as a table
python3 linuxlist.py

# Filter by category
python3 linuxlist.py --category "Audio"

# Search names, tags and descriptions
python3 linuxlist.py --search "tag editor"

# Only free/open-source entries
python3 linuxlist.py --foss

# Only entries in a given package manager
python3 linuxlist.py --package apt

# Render Markdown (great for pasting into a wiki)
python3 linuxlist.py --format md > LIST.md

# Render a single self-contained HTML page
python3 linuxlist.py --format html > list.html

# Machine-readable output
python3 linuxlist.py --format json --foss
```

Run `python3 linuxlist.py --help` for the full flag list.

## Data model

Each entry in `data/software.json` looks like:

```json
{
  "name": "Krita",
  "category": "Graphics",
  "description": "Digital painting and illustration studio.",
  "license": "GPL-3.0",
  "foss": true,
  "package": "apt",
  "tags": ["painting", "illustration", "tablet"]
}
```

Fields:

| field | type | notes |
|---|---|---|
| `name` | string | Display name, unique |
| `category` | string | One of the categories in `CATEGORIES` |
| `description` | string | One line, no trailing period required |
| `license` | string | SPDX-ish identifier, or `Proprietary` |
| `foss` | bool | Whether source is available under a free license |
| `package` | string | Primary install source: `apt`, `dnf`, `pacman`, `flatpak`, `snap`, `appimage`, `manual` |
| `tags` | list of strings | Lowercase search helpers |

## Adding software

1. Add an object to `data/software.json`.
2. Keep `name` unique and `category` inside the known set.
3. Run `python3 linuxlist.py --format md > data/categories.md` to refresh the index.

`linuxlist.py` validates the dataset on load and tells you exactly which entry is malformed.

## Scope

This is a *starter* list — roughly a hundred entries across desktop, dev, audio, graphics, and sysadmin work. It is deliberately opinionated and incomplete. Fork it, prune it, make it yours.
