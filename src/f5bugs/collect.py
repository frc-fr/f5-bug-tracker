"""Keep sources/pages.json up to date and download the "Fixes and Known Issues" pages.

Each release has a page on techdocs.f5.com at a predictable address, whose
robots.txt allows every robot. There are four sets of pages:

- bigip: .../products/big-ip_ltm/releasenotes/related/relnote-supplement-bigip-17-1-3-7.html
- f5os-a, the F5OS of the rSeries: .../products/f5os-a/.../relnote-supplement-f5os-a-1-8-4-hr-1.html
- f5os-c, the F5OS of VELOS: .../products/f5os-c/.../relnote-supplement-f5os-c-1-8-3.html
- f5os, F5OS 2.x, one set of notes for both: .../products/f5os/.../relnote-supplement-f5os-2-0-0.html

The releases come from several places, none complete on its own: the KB
sitemap of techdocs (it stops at some point), the articles K9412 and K9502
for BIG-IP and K21501912 for F5OS, and, for the branches still supported, a
check of the next numbers.

For a release it no longer has, the site answers 200 with a "Page not found"
page that always has the same size: it is recognized as such. The site stamps
every page again when it is deployed, so a new ETag alone says little: a page
is downloaded again when its size changed. The pages of the supported branches
are checked at each run, the others once a week.
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests

from .versions import branch_key, branch_of, normalize, slug, train_of, version_key

log = logging.getLogger(__name__)

PAGE_URLS = {
    "bigip": "https://techdocs.f5.com/kb/en-us/products/big-ip_ltm/releasenotes/related/relnote-supplement-bigip-{slug}.html",
    "f5os-a": "https://techdocs.f5.com/kb/en-us/products/f5os-a/releasenotes/related/relnote-supplement-f5os-a-{slug}.html",
    "f5os-c": "https://techdocs.f5.com/kb/en-us/products/f5os-c/releasenotes/related/relnote-supplement-f5os-c-{slug}.html",
    "f5os": "https://techdocs.f5.com/kb/en-us/products/f5os/releasenotes/related/relnote-supplement-f5os-{slug}.html",
}
# The KB sitemap stops at some point; the main one lists the newer F5OS Hardened and Critical Releases.
SITEMAP_URLS = ["https://techdocs.f5.com/kb/sitemap.xml", "https://techdocs.f5.com/sitemap.xml"]
SITEMAP_PAGE = re.compile(r"relnote-supplement-(bigip|f5os-a|f5os-c|f5os)-(\d+(?:-\d+){2,3}(?:-hr-\d+|-cr)?)\.html")
USER_AGENT = "f5-bug-tracker/0.1 (+https://github.com/frc-fr/f5-bug-tracker)"
CRAWL_DELAY = 2.0
# Below this size a page is the "Page not found" one: a real page weighs hundreds of kilobytes.
MISSING_SIZE = 100_000
LOWEST_BRANCH = {"bigip": (11, 5), "f5os-a": (1, 0), "f5os-c": (1, 0), "f5os": (2, 0)}
WEEKLY_DAYS = 7


def page_url(source: str, version: str) -> str:
    return PAGE_URLS[source].format(slug=slug(version))


def page_key(source: str, version: str) -> str:
    return f"{source}:{version}"


class Client:
    """HTTP client that spaces out requests and retries transient failures."""

    def __init__(self, delay: float = CRAWL_DELAY, retries: int = 4):
        self.delay = delay
        self.retries = retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0

    def request(self, method: str, url: str) -> requests.Response:
        for attempt in range(self.retries):
            wait = self._last + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                response = self.session.request(method, url, timeout=120)
            except requests.RequestException as error:
                log.warning("%s %s failed: %s", method, url, error)
            else:
                if response.status_code not in (429, 500, 502, 503, 504):
                    return response
                log.warning("%s %s returned %s", method, url, response.status_code)
            time.sleep(self.delay * 2 ** (attempt + 1))
        raise RuntimeError(f"{method} {url}: giving up after {self.retries} attempts")


def load_pages(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    return {page_key(e["source"], e["version"]): e for e in json.loads(path.read_text(encoding="utf-8"))["pages"]}


def save_pages(path: Path, pages: Dict[str, dict]) -> None:
    """One page per line, for readable diffs."""
    entries = sorted(pages.values(), key=lambda e: (e["source"], version_key(e["version"])))
    lines = ",\n".join("  " + json.dumps(entry, ensure_ascii=False) for entry in entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'{{"pages": [\n{lines}\n]}}\n', encoding="utf-8")


def cache_path(cache: Path, source: str, version: str) -> Path:
    return cache / source / f"{version}.html"


def in_scope(source: str, version: str) -> bool:
    return branch_key(branch_of(version)) >= LOWEST_BRANCH[source]


def sitemap_versions(client: Client) -> Set[Tuple[str, str]]:
    found = set()
    text = ""
    for url in SITEMAP_URLS:
        response = client.request("GET", url)
        response.raise_for_status()
        text += response.text
    for source, name in SITEMAP_PAGE.findall(text):
        parts = name.split("-")
        version = normalize(".".join(parts[:3]) + ("-" + "-".join(parts[3:]) if len(parts) > 3 and not parts[3].isdigit()
                                                   else "".join("." + p for p in parts[3:])))
        if version and in_scope(source, version):
            found.add((source, version))
    return found


def f5os_branches(articles: dict) -> Dict[str, Dict[str, dict]]:
    """K21501912 by source: {"f5os-a": {"1.8": {...}}, "f5os-c": {...}, "f5os": {"2": {...}}}."""
    return articles.get("K21501912", {}).get("data", {})


def article_versions(articles: dict) -> Set[Tuple[str, str]]:
    """Every release the articles name: BIG-IP by K9412 and K9502, F5OS by the latest patch release of K21501912."""
    found = {("bigip", v) for v in articles.get("K9412", {}).get("data", {})}
    for release, latest in articles.get("K9502", {}).get("data", {}).items():
        found.add(("bigip", release))
        if latest:
            found.update(("bigip", f"{release}.{n}") for n in range(1, version_key(latest)[3] + 1))
    for source, branches in f5os_branches(articles).items():
        for entry in branches.values():
            latest = entry.get("latest")
            if latest:
                major, minor, patch, _ = version_key(latest)
                found.update((source, f"{major}.{minor}.{n}") for n in range(0, patch + 1))
    return {(s, v) for s, v in found if normalize(v) and in_scope(s, v)}


def supported_branches(articles: dict, today: str) -> Dict[str, Set[str]]:
    """The branches still supported, by source; "2" stands for every F5OS 2.x branch."""
    supported = {"bigip": {b for b, d in articles.get("K5903", {}).get("data", {}).items() if d.get("support") and d["support"] >= today}}
    for source, branches in f5os_branches(articles).items():
        supported[source] = {b for b, d in branches.items() if d.get("support") and d["support"] >= today}
    return supported


def branch_supported(source: str, version: str, supported: Dict[str, Set[str]]) -> bool:
    branches = supported.get(source, set())
    return branch_of(version) in branches or version.split(".")[0] in branches


def candidates(source: str, known: Iterable[str], supported: Dict[str, Set[str]]) -> Set[str]:
    """For each supported branch: the next point release of its latest release, its next maintenance release,
    and, for F5OS, the next Hardened Release and the Critical Release of its latest patch release."""
    latest: Dict[str, str] = {}
    for version in known:
        branch = branch_of(version)
        if branch_supported(source, version, supported) and version_key(version) > version_key(latest.get(branch, "0.0.0")):
            latest[branch] = version
    found = set()
    for version in latest.values():
        major, minor, maintenance, point = version_key(version)
        found.add(f"{major}.{minor}.{maintenance + 1}")
        if source == "bigip":
            found.add(f"{major}.{minor}.{maintenance}.{point + 1}")
        elif point < 50:
            train = train_of(version)
            found.add(f"{train}-HR-{point + 1}")
            found.add(f"{train}-CR")
    return found


def due(entry: dict, supported: Dict[str, Set[str]], today: datetime) -> bool:
    """A page of a supported branch at each run; the others once a week, each on its own day."""
    if branch_supported(entry["source"], entry["version"], supported):
        return True
    checked = entry.get("checked")
    if not checked:
        return True
    if datetime.strptime(checked, "%Y-%m-%d").replace(tzinfo=timezone.utc) < today - timedelta(days=WEEKLY_DAYS):
        return True
    return int(hashlib.sha1(page_key(entry["source"], entry["version"]).encode()).hexdigest(), 16) % 7 == today.weekday()


def check(client: Client, entry: dict, cache: Path, today: str) -> bool:
    """HEAD the page; download it when it is new or its size changed. True when downloaded."""
    url = page_url(entry["source"], entry["version"])
    response = client.request("HEAD", url)
    entry["checked"] = today
    size = int(response.headers.get("Content-Length") or 0)
    if response.status_code == 404 or (response.status_code == 200 and size and size < MISSING_SIZE):
        entry["missing"] = True
        return False
    if response.status_code != 200:
        log.error("%s returned %s", url, response.status_code)
        return False
    entry.pop("missing", None)
    target = cache_path(cache, entry["source"], entry["version"])
    etag = response.headers.get("ETag", "").strip('"') or None
    # Sizes compare HEAD to HEAD: the server gives the size of the compressed page, not of the one saved.
    unchanged = entry.get("size") == size if size else entry.get("etag") == etag
    if target.exists() and unchanged:
        return False
    page = client.request("GET", url)
    if page.status_code != 200 or len(page.content) < MISSING_SIZE:
        entry["missing"] = True
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(page.content)
    entry["size"] = size
    entry["etag"] = etag
    return True


def update(pages_path: Path, cache: Path, client: Client, articles: dict, today: Optional[datetime] = None) -> List[str]:
    """Find the releases, check their pages, download the new or changed ones; return them."""
    now = today or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    pages = load_pages(pages_path)
    supported = supported_branches(articles, day)
    found = article_versions(articles)
    if not pages or now.weekday() == 0:
        try:
            found |= sitemap_versions(client)
        except (RuntimeError, OSError, requests.HTTPError) as error:
            log.error("sitemap not read: %s", error)
    for source in PAGE_URLS:
        known = {e["version"] for e in pages.values() if e["source"] == source} | {v for s, v in found if s == source}
        found |= {(source, v) for v in candidates(source, known, supported)}
    for source, version in found:
        pages.setdefault(page_key(source, version), {"source": source, "version": version})
    downloaded = []
    for key, entry in sorted(pages.items(), key=lambda item: (item[1]["source"], version_key(item[1]["version"]))):
        # A release that never existed is only looked for again while its branch is supported.
        if entry.get("missing") and not branch_supported(entry["source"], entry["version"], supported) and entry.get("checked"):
            continue
        if not due(entry, supported, now):
            continue
        try:
            if check(client, entry, cache, day):
                downloaded.append(key)
        except (RuntimeError, OSError) as error:
            log.error("%s not checked: %s", key, error)
        if len(downloaded) % 10 == 0:
            save_pages(pages_path, pages)
    # A guessed number that answered "not found" is no release: it is not kept, and is guessed again next time.
    named = article_versions(articles)
    for key in [k for k, e in pages.items() if e.get("missing") and (e["source"], e["version"]) not in named
                and not cache_path(cache, e["source"], e["version"]).exists()]:
        del pages[key]
    save_pages(pages_path, pages)
    return downloaded


NOTES_URL = "https://techdocs.f5.com/en-us/bigip-{slug}/big-ip-release-notes.html"
NOTES_SITEMAP = "https://techdocs.f5.com/en-us/sitemap.xml"
NOTES_PAGE = re.compile(r"/en-us/bigip-(\d+(?:-\d+){2,3})/big-ip-release-notes\.html")


def notes_url(version: str) -> str:
    return NOTES_URL.format(slug=slug(version))


def load_notes(path: Path) -> Dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_notes(path: Path, client: Client, articles: dict, today: Optional[datetime] = None) -> Dict[str, dict]:
    """The release notes of the maintenance releases: new features and upgrade chapters, for the "Read" panel.

    The sitemap of techdocs lists some of them, K9412 names the others: each
    candidate is read once, and one that did not exist is tried again weekly.
    The site answers "Page not found" with a 200: the title tells.
    """
    now = today or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    notes = load_notes(path)
    found = set(articles.get("K9412", {}).get("data", {}))
    if not notes or now.weekday() == 0:
        try:
            response = client.request("GET", NOTES_SITEMAP)
            response.raise_for_status()
            found |= {normalize(name.replace("-", ".")) for name in NOTES_PAGE.findall(response.text)} - {None}
        except (RuntimeError, OSError, requests.HTTPError) as error:
            log.error("release notes sitemap not read: %s", error)
    for version in sorted(found, key=version_key):
        entry = notes.get(version)
        if entry and (entry["found"] or entry["checked"] > (now - timedelta(days=WEEKLY_DAYS)).strftime("%Y-%m-%d")):
            continue
        try:
            response = client.request("GET", notes_url(version))
        except (RuntimeError, OSError) as error:
            log.error("release notes of %s not checked: %s", version, error)
            continue
        title = re.search(r"<title>(.*?)</title>", response.text, re.S)
        notes[version] = {"found": response.status_code == 200 and bool(title) and "Release Notes" in title.group(1),
                          "checked": day}
    path.write_text(json.dumps(dict(sorted(notes.items(), key=lambda item: version_key(item[0]))), indent=1) + "\n",
                    encoding="utf-8")
    return notes
