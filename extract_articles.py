#!/usr/bin/env python3
"""Extract The Guardian Russia articles to markdown files.

For every date in the inclusive range [start, end] the script downloads the
daily listing page, collects all article hrefs and then downloads each article,
converting the content of its ``<article>`` element to a markdown file.

Usage:
    python extract_articles.py --start 10.10.2026 --end 12.10.2026 --dir ./out
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

LOG = logging.getLogger("extract-articles")

BASE_URL = "https://www.theguardian.com"
LIST_URL = BASE_URL + "/world/russia/{year}/{month}/{day}/all"
DATE_INPUT_FORMAT = "%d.%m.%Y"
DATE_DIR_FORMAT = "%d.%m.%Y"

MONTHS = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]

HREF_DATE_RE = re.compile(r"/(\d{4})/([a-z]{3})/(\d{2})/(.+?)/?$")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

TAGS_TO_REMOVE = ("script", "style", "noscript", "svg", "source", "button", "input", "form", "gu-island")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Guardian Russia articles and store them as markdown."
    )
    parser.add_argument("--start", required=True, help="Start date, format dd.mm.yyyy")
    parser.add_argument("--end", required=True, help="End date, format dd.mm.yyyy")
    parser.add_argument("--dir", required=True, help="Directory to store markdown files")
    return parser.parse_args(argv)


def parse_date(value: str, arg_name: str) -> date:
    try:
        return datetime.strptime(value, DATE_INPUT_FORMAT).date()
    except ValueError as exc:
        raise SystemExit(f"Invalid --{arg_name} date '{value}', expected dd.mm.yyyy") from exc


def date_range(start: date, end: date):
    if start > end:
        raise SystemExit("--start date must not be later than --end date")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def listing_url(day: date) -> str:
    return LIST_URL.format(year=day.year, month=MONTHS[day.month - 1], day=f"{day.day:02d}")


def fetch(url: str, session: requests.Session, retries: int = 3) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response
        except requests.RequestException as exc:
            last_error = exc
            LOG.warning("Attempt %d/%d failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def extract_hrefs(list_html: str) -> list[str]:
    """Return article hrefs from a listing page, in appearance order."""
    soup = BeautifulSoup(list_html, "html.parser")
    hrefs: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a.js-headline-text"):
        href = anchor.get("href")
        if not href:
            continue
        href = urljoin(BASE_URL, href)
        if href in seen:
            LOG.warning("Duplicate href skipped: %s", href)
            continue
        seen.add(href)
        hrefs.append(href)
    return hrefs


def parse_href(href: str) -> tuple[date | None, str]:
    """Split an article href into (publication date, mnemocode)."""
    path = urlparse(href).path
    match = HREF_DATE_RE.search(path)
    if not match:
        mnemocode = path.rstrip("/").rsplit("/", 1)[-1]
        return None, mnemocode
    year, month_symbol, day, mnemocode = match.groups()
    try:
        published = datetime.strptime(f"{day}.{month_symbol}.{year}", "%d.%b.%Y").date()
    except ValueError:
        published = None
    return published, mnemocode


def article_to_markdown(article_html: str) -> str:
    soup = BeautifulSoup(article_html, "html.parser")
    for tag in soup(TAGS_TO_REMOVE):
        tag.decompose()
    for node in soup.select('[data-ad-slot], [data-gu-name="right-column"]'):
        node.decompose()
    text = markdownify(str(soup), heading_style="ATX")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_article_markdown(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    article = soup.find("article")
    if article is None:
        return None
    return article_to_markdown(str(article))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    start = parse_date(args.start, "start")
    end = parse_date(args.end, "end")
    out_dir = Path(args.dir)

    session = requests.Session()

    hrefs: list[str] = []
    seen: set[str] = set()
    for day in date_range(start, end):
        url = listing_url(day)
        LOG.info("Downloading listing page %s", url)
        try:
            response = fetch(url, session)
        except RuntimeError as exc:
            LOG.error("%s", exc)
            continue
        for href in extract_hrefs(response.text):
            if href in seen:
                LOG.warning("Duplicate href skipped: %s", href)
                continue
            seen.add(href)
            hrefs.append(href)

    LOG.info("Collected %d unique article links", len(hrefs))

    for index, href in enumerate(hrefs, start=1):
        published, mnemocode = parse_href(href)
        LOG.info("[%d/%d] Downloading article %s", index, len(hrefs), href)
        try:
            response = fetch(href, session)
        except RuntimeError as exc:
            LOG.error("%s", exc)
            continue

        markdown = extract_article_markdown(response.text)
        if markdown is None:
            LOG.warning("No <article> element found in %s", href)
            continue

        day = published or start
        target_dir = out_dir / day.strftime(DATE_DIR_FORMAT)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{mnemocode}.md"
        target.write_text(markdown, encoding="utf-8")
        LOG.info("Saved %s", target)

    return 0


if __name__ == "__main__":
    sys.exit(main())
