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

try:
    from curl_cffi import requests as curl_requests  # TLS-fingerprint impersonation
except ImportError:
    curl_requests = None

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


def find_number_near(html, marker, window=250):
    """Find the first integer that appears within `window` chars *after*
    the first occurrence of `marker` (usually a distinctive href fragment
    that sits right next to the number in the real markup — verified by
    hand against each site's actual HTML rather than guessed)."""
    idx = html.find(marker)
    if idx == -1:
        return None
    segment = html[idx : idx + window]
    m = re.search(r"([\d][\d,]*)", segment)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def get_letterboxd(url):
    html = fetch(url)
    # Profile stat block: <a href="/trashd/films/">136<...>Films</...></a>
    # the number sits inside the same link as the /films/ href.
    return find_number_near(html, '/trashd/films/"', window=150)


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
    # Main "Games Played" stat links to this exact path, with the number
    # (rendered as a zero-padded odometer, e.g. "008") right inside it.
    return find_number_near(html, "/u/Trashd/played/added/categories:games/", window=150)


def get_aoty(url):
    html = fetch(url)
    # Top stat row: <a href="/user/trashkan/ratings/">23 Ratings</a>
    return find_number_near(html, "/user/trashkan/ratings/", window=100)


def get_mal(url):
    html = fetch(url)
    # Anime Stats "Completed" row: <a href="...animelist/TrashKan_?status=2">
    # Completed</a>25 — anchoring on the animelist-specific href avoids
    # accidentally matching the Manga Stats "Completed" row further down.
    return find_number_near(html, "animelist/TrashKan_?status=2", window=80)


def get_rym(url):
    # RateYourMusic sits behind Cloudflare bot-detection that blocks plain
    # requests (including urllib, requests, etc.) with a 403. curl_cffi
    # impersonates a real browser's TLS/HTTP fingerprint, which is enough to
    # get through in most cases — but Cloudflare's rules change over time,
    # so this one is more likely than the others to eventually need a fix.
    if curl_requests is None:
        raise RuntimeError("curl_cffi is not installed (pip install curl_cffi)")

    resp = curl_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"got HTTP {resp.status_code}")

    m = re.search(r"([\d,]+)\s+ratings", resp.text, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


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
    "rym": {
        "url": "https://rateyourmusic.com/~RymKan",
        "label": "Ratings",
        "fetcher": get_rym,
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
