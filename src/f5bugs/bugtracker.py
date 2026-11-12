"""The page of each bug in F5's public Bug Tracker.

cdn.f5.com/product/bugtracker/ID<number>.html is public and answers robots;
the release notes link to it. It adds what the notes do not give: the releases
known to be affected, the severity, the dates the bug was opened and last
modified.

There is one page per bug, tens of thousands in all, read two seconds apart:
each run reads a batch, newest bugs first, and the results are committed, so
the first collection spreads over several runs. A bug is read again when the
release notes give it a fixed release its page did not list yet.
"""
import html
import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .versions import normalize, version_key

log = logging.getLogger(__name__)

PAGE_URL = "https://cdn.f5.com/product/bugtracker/ID{number}.html"
BATCH = 1200
FIELD = re.compile(r'<span class="standard-text">\s*([^<:]+):\s*</span>\s*<br\s*/?>\s*<span>(.*?)</span>\s*</p>', re.S)
MODIFIED = re.compile(r"Last Modified:\s*</span>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})")
OPENED = re.compile(r"Opened:\s*</span>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})")
SEVERITY = re.compile(r"(\d-(?:Critical|Major|Minor|Trivial|Blocking))")


def page_url(bug_id: str) -> str:
    return PAGE_URL.format(number=bug_id)


def text_of(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def versions_in(text: str) -> List[str]:
    found = []
    for token in re.split(r"[,\s]+", text):
        version = normalize(token)
        if version and version not in found:
            found.append(version)
    return found


def iso(text: Optional[str]) -> Optional[str]:
    from datetime import datetime
    try:
        return datetime.strptime(text.strip(), "%b %d, %Y").strftime("%Y-%m-%d") if text else None
    except ValueError:
        return None


def parse_bug(page: str) -> dict:
    """{affected, fixed, severity, opened, modified} of a Bug Tracker page."""
    fields = {name.strip().lower(): text_of(value) for name, value in FIELD.findall(page)}
    severity = SEVERITY.search(page)
    opened = OPENED.search(page)
    modified = MODIFIED.search(page)
    return {
        "affected": versions_in(fields.get("known affected versions", "")),
        "fixed": versions_in(fields.get("fixed in", "")),
        "severity": severity.group(1) if severity else None,
        "opened": iso(opened.group(1)) if opened else None,
        "modified": iso(modified.group(1)) if modified else None,
    }


def load(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    return {entry["id"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))["bugs"]}


def save(path: Path, bugs: Dict[str, dict]) -> None:
    """One bug per line, for readable diffs."""
    lines = ",\n".join("  " + json.dumps(bugs[key], ensure_ascii=False) for key in sorted(bugs, key=int))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'{{"bugs": [\n{lines}\n]}}\n', encoding="utf-8")


def wanted(notes: Dict[str, List[str]], known: Dict[str, dict]) -> List[str]:
    """The bugs to read: never read, or given a fixed release their page did not list; newest first."""
    todo = []
    for bug_id, fixed in notes.items():
        entry = known.get(bug_id)
        if entry is None or (not entry.get("missing") and not set(fixed) <= set(entry.get("fixed", []))):
            todo.append(bug_id)
    return sorted(todo, key=int, reverse=True)


def update(path: Path, notes: Dict[str, List[str]], client, batch: int = BATCH) -> int:
    """Read a batch of Bug Tracker pages; return how many remain to read."""
    known = load(path)
    todo = wanted(notes, known)
    for count, bug_id in enumerate(todo[:batch], 1):
        try:
            response = client.request("GET", page_url(bug_id))
        except (RuntimeError, OSError) as error:
            log.error("bug %s not read: %s", bug_id, error)
            continue
        if response.status_code == 404:
            known[bug_id] = {"id": bug_id, "missing": True}
        elif response.status_code == 200:
            known[bug_id] = {"id": bug_id, **parse_bug(response.text)}
        else:
            log.error("bug %s returned %s", bug_id, response.status_code)
        # An interrupted run keeps what it read.
        if count % 100 == 0:
            save(path, known)
    save(path, known)
    return max(0, len(todo) - batch)
