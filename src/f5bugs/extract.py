"""Turn the cached pages into data/extracted/ and log what changed.

Each page repeats the fixes of the earlier releases of its line and the details
of every bug it lists: keeping each page whole would store the same text
hundreds of times. So the extraction writes:

- data/extracted/<source>/releases/<release>.json: what the page of a release
  says, as IDs only: the bugs listed as fixed in each release of its line, and
  those listed as known in its branch;
- data/extracted/<source>/bugs.json: one line per bug, with the text of the
  newest page that details it, and every fixed release the pages give.

The sources are the four sets of notes: bigip, f5os-a, f5os-c and f5os (2.x).

The results are committed: emptying the cache of the CI does not make the next
run read every page again.
"""
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .collect import cache_path, load_pages
from .parser import Page, parse_page
from .versions import version_key

log = logging.getLogger(__name__)

TEXT_FIELDS = ["title", "component", "symptoms", "conditions", "impact", "workaround", "fix", "behavior", "article"]


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def release_path(output: Path, source: str, version: str) -> Path:
    return output / source / "releases" / f"{version}.json"


def write_release(target: Path, page: Page) -> None:
    """One release of the line per line, so that a revision gives a readable git diff."""
    head = {"product": page.product, "version": page.version, "updated": page.updated, "skipped": page.skipped}
    fixed = sorted(page.fixed.items(), key=lambda item: version_key(item[0]))
    lines = [f'  {json.dumps(release)}: {json.dumps(sorted(ids, key=int))}' for release, ids in fixed]
    body = json.dumps(head, ensure_ascii=False)[:-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'{body}, "fixed": {{\n' + ",\n".join(lines) + '\n}, "known": '
                      + json.dumps(sorted(page.known, key=int)) + "}\n", encoding="utf-8")


def read_release(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_bugs(pages: List[Page]) -> Dict[str, dict]:
    """The bugs of all the pages: the newest page that details a bug gives its text."""
    bugs: Dict[str, dict] = {}
    for page in sorted(pages, key=lambda p: (version_key(p.version), p.updated or "")):
        for bug in page.bugs.values():
            entry = bugs.setdefault(bug.id, {"id": bug.id, "fixed_versions": [], "severity": None, "star": False})
            detailed = bool(bug.component or bug.symptoms)
            for name in TEXT_FIELDS:
                value = getattr(bug, name)
                if value and (detailed or not entry.get(name)):
                    entry[name] = value
            entry["severity"] = bug.severity or entry["severity"]
            entry["star"] = entry["star"] or bug.star
            entry["fixed_versions"] = sorted(set(entry["fixed_versions"]) | set(bug.fixed_versions), key=version_key)
    return bugs


def write_bugs(path: Path, bugs: Dict[str, dict]) -> None:
    lines = ",\n".join("  " + json.dumps(bugs[key], ensure_ascii=False) for key in sorted(bugs, key=int))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'{{"bugs": [\n{lines}\n]}}\n', encoding="utf-8")


def load_bugs(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    return {entry["id"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))["bugs"]}


def change_key(change: dict):
    return change["date"], change.get("source", "bigip"), version_key(change["version"]), change["kind"]


def read_changes(path: Path) -> List[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def write_changes(path: Path, changes: List[dict]) -> None:
    lines = ",\n".join("  " + json.dumps(change, ensure_ascii=False) for change in sorted(changes, key=change_key))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"[\n{lines}\n]\n" if lines else "[]\n", encoding="utf-8")


def page_changes(page: Page, previous: Optional[dict], date: str) -> List[dict]:
    """A new release, and the bugs F5 adds to a page already published."""
    own = set(page.fixed.get(page.version, []))
    if previous is None:
        return [{"date": date, "version": page.version, "kind": "version", "bugs": sorted(own, key=int)}]
    entries = []
    added = own - set(previous.get("fixed", {}).get(page.version, []))
    if added:
        entries.append({"date": date, "version": page.version, "kind": "fixed_added", "bugs": sorted(added, key=int)})
    known = set(page.known) - set(previous.get("known", []))
    if known:
        entries.append({"date": date, "version": page.version, "kind": "known_added", "bugs": sorted(known, key=int)})
    return entries


def extract_all(cache: Path, output: Path, changes_path: Path, pages_path: Path,
                date: Optional[str] = None) -> Dict[str, List[str]]:
    """Parse every page downloaded since its last extraction and return the warnings per page.

    Without a change log the data is a baseline: nothing tells when the
    releases already published came out, so none is recorded. A source read
    for the first time is a baseline of its own.
    """
    date = date or today()
    baseline = not changes_path.exists()
    changes = read_changes(changes_path)
    problems: Dict[str, List[str]] = {}
    pages_by_source: Dict[str, List[Page]] = {}
    # Nothing is written before every page read cleanly: a failed run leaves the data as it was.
    written = []
    entries = sorted(load_pages(pages_path).values(), key=lambda e: (e["source"], version_key(e["version"])))
    new_sources = {e["source"] for e in entries if not (output / e["source"] / "bugs.json").exists()}
    for entry in entries:
        source, version = entry["source"], entry["version"]
        path = cache_path(cache, source, version)
        if entry.get("missing") or not path.exists():
            continue
        target = release_path(output, source, version)
        # A page read already and not downloaded since is not read again.
        if target.exists() and (output / source / "bugs.json").exists() and path.stat().st_mtime <= target.stat().st_mtime:
            continue
        page = parse_page(path.read_text(encoding="utf-8", errors="replace"))
        if page.missing:
            continue
        if page.version != version:
            problems[f"{source}:{version}"] = [f"the page is that of {page.version}"]
            continue
        previous = read_release(target) if target.exists() else None
        if not baseline and source not in new_sources:
            changes.extend({**change, "source": source} for change in page_changes(page, previous, date))
        written.append((target, page))
        pages_by_source.setdefault(source, []).append(page)
        if page.warnings:
            problems[f"{source}:{version}"] = page.warnings
    if problems:
        return problems
    for target, page in written:
        write_release(target, page)
    for source, pages in pages_by_source.items():
        # The bugs read earlier stay; the pages read now, newest last, update them.
        bugs = load_bugs(output / source / "bugs.json")
        for bug_id, entry in merge_bugs(pages).items():
            old = bugs.get(bug_id)
            if old:
                entry = {**old, **{k: v for k, v in entry.items() if v}}
                entry["fixed_versions"] = sorted(set(old.get("fixed_versions", [])) | set(entry["fixed_versions"]), key=version_key)
            bugs[bug_id] = entry
        write_bugs(output / source / "bugs.json", bugs)
    write_changes(changes_path, changes)
    return problems
