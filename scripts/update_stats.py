#!/usr/bin/env python3
"""
Refreshes stats.json with current counts pulled from each profile page.

None of these sites offer a public API for this kind of data (Goodreads
killed its public API in 2020; the others never had one), so this works by
fetching the public profile page and finding the number that sits next to a
known label (e.g. "Films", "Played", "Completed"). That makes it inherently
a best-effort scraper: if a site redesigns its profile page layout, the
matching may need a small tweak. Each site is wrapped in its own try/except
so one broken site never blocks the others — on failure, that entry in
stats.json is just left as-is.

Run manually with:  python3 scripts/update_stats.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path
from datetime import date

STATS_PATH = Path(__file__).resolve().parent.parent / "stats.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def find_number_near(html, label, window=250):
    """Find the first integer that appears within `window` chars after the
    first occurrence of `label` in the raw HTML. Proximity-based rather than
    tag-based, so it's a bit more resistant to markup changes than a strict
    CSS-path/regex would be."""
    idx = html.find(label)
    if idx == -1:
        return None
    segment = html[idx : idx + window]
    m = re.search(r"([\d][\d,]*)", segment)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def get_letterboxd(url):
    html = fetch(url)
    # Letterboxd profile stats bar includes a "Films" stat with the count
    # rendered right next to it.
    count = find_number_near(html, "Films")
    return count


def get_goodreads(url):
    html = fetch(url)
    # Shelf breakdown looks like: ...shelf=read">read (65)</a>
    idx = html.find("shelf=read")
    if idx == -1:
        return None
    segment = html[idx : idx + 200]
    m = re.search(r"\((\d[\d,]*)\)", segment)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def get_backloggd(url):
    html = fetch(url)
    count = find_number_near(html, "Played")
    return count


def get_aoty(url):
    html = fetch(url)
    count = find_number_near(html, "Ratings")
    return count


def get_mal(url):
    html = fetch(url)
    # Anime Stats section lists "Completed" before the Manga Stats section
    # does, so the first match corresponds to anime, not manga.
    count = find_number_near(html, "Completed", window=120)
    return count


SITES = {
    "letterboxd": {
        "url": "https://letterboxd.com/Trashd/",
        "label": "Films Logged",
        "fetcher": get_letterboxd,
    },
    "goodreads": {
        "url": "https://www.goodreads.com/user/show/192709611-trashbks",
        "label": "Books Read",
        "fetcher": get_goodreads,
    },
    "backloggd": {
        "url": "https://backloggd.com/u/Trashd/",
        "label": "Games Played",
        "fetcher": get_backloggd,
    },
    "aoty": {
        "url": "https://www.albumoftheyear.org/user/trashkan/",
        "label": "Albums Rated",
        "fetcher": get_aoty,
    },
    "mal": {
        "url": "https://myanimelist.net/profile/TrashKan_",
        "label": "Anime Completed",
        "fetcher": get_mal,
    },
}


def main():
    if STATS_PATH.exists():
        data = json.loads(STATS_PATH.read_text())
    else:
        data = {}

    today = date.today().isoformat()
    changed = False

    for key, cfg in SITES.items():
        try:
            count = cfg["fetcher"](cfg["url"])
        except Exception as exc:  # noqa: BLE001 - log and move on
            print(f"[{key}] fetch failed: {exc}", file=sys.stderr)
            continue

        if count is None:
            print(f"[{key}] could not find a count on the page", file=sys.stderr)
            continue

        prev = data.get(key, {})
        if prev.get("count") != count:
            print(f"[{key}] {prev.get('count')} -> {count}")
            changed = True

        data[key] = {"count": count, "label": cfg["label"], "updated": today}

    STATS_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print("changed" if changed else "no changes")


if __name__ == "__main__":
    main()
