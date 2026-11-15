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
import hashlib
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import report
from .collect import cache_path, load_pages, page_key, page_url
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


# The name of each set of pages in the processing report: F5OS 2.x has one set of notes for rSeries and VELOS.
GROUPS = {"bigip": "BIG-IP", "f5os-a": "F5OS-A", "f5os-c": "F5OS-C", "f5os": "F5OS 2.x"}
PRODUCTS = {"bigip": "BIG-IP", "f5os-a": "F5OS-A", "f5os-c": "F5OS-C", "f5os": "F5OS"}
BUCKETS = ("vendor", "read", "ruled", "failed", "unaccounted")
# What the code reads of a page changes with the parser: a summary made by another parser is made again.
PARSER = hashlib.sha1((Path(__file__).parent / "parser.py").read_bytes()).hexdigest()[:12]


def summary_path(path: Path) -> Path:
    """Beside the cached page: what the report says of it, so that a page not downloaded again is not read again."""
    return path.with_suffix(".report.json")


def summarize(page: Page) -> dict:
    """What the processing report needs of a page: its findings, the buckets of its IDs, its sections and citations."""
    ids = page.accounting()
    places: Dict[tuple, List[str]] = {}
    for bug in sorted(ids["unaccounted"], key=int):
        places.setdefault(page.listed[bug], []).append(bug)
    findings = report.merged(page.findings) + [
        report.finding("suspect", "unaccounted", url, where, bugs, "bug IDs the page lists that no rule of the code accounts for")
        for (url, where), bugs in places.items()]
    return {"parser": PARSER, "version": page.version, "missing": page.missing, "findings": findings,
            "ids": {bucket: sorted(ids[bucket], key=int) for bucket in BUCKETS},
            "headings": page.headings, "prose": sorted(page.prose, key=int)}


def read_summary(path: Path) -> Optional[dict]:
    target = summary_path(path)
    if not target.exists() or target.stat().st_mtime < path.stat().st_mtime:
        return None
    summary = json.loads(target.read_text(encoding="utf-8"))
    return summary if summary.get("parser") == PARSER else None


def extract_all(cache: Path, output: Path, changes_path: Path, pages_path: Path, report_path: Path,
                date: Optional[str] = None) -> List[str]:
    """Parse the pages downloaded since their last extraction, write what is read and the processing report;
    return why the update stops.

    A page is published for what the code reads of it; what it does not read is in the
    report. A page that no longer parses, is that of another release, or loses most of
    its bugs keeps its last reading. The update stops only when too few pages are read
    (report.PUBLISH_MINIMUM): the site then keeps its last version rather than an empty one.

    The report covers every page at each run: a page not downloaded again keeps the
    summary of its last reading, saved beside it in the cache, unless the parser changed.

    Without a change log the data is a baseline: nothing tells when the
    releases already published came out, so none is recorded. A source read
    for the first time is a baseline of its own.
    """
    date = date or today()
    baseline = not changes_path.exists()
    changes = read_changes(changes_path)
    previous = {d["key"]: d for d in report.load(report_path).get("documents", [])}
    pages_by_source: Dict[str, List[Page]] = {}
    # Nothing is written before the report says to publish: a stopped run leaves the data as it was.
    written = []
    entries_report: List[dict] = []
    groups: Dict[str, dict] = {}
    headings: Dict[str, Dict[str, bool]] = {}
    urls: Dict[str, str] = {}
    prose: List[dict] = []
    total = 0
    entries = sorted(load_pages(pages_path).values(), key=lambda e: (e["source"], version_key(e["version"])))
    new_sources = {e["source"] for e in entries if not (output / e["source"] / "bugs.json").exists()}
    for entry in entries:
        source, version = entry["source"], entry["version"]
        path = cache_path(cache, source, version)
        target = release_path(output, source, version)
        # A release that never had a page (a guessed number, an article naming a release without notes) is no document.
        if not path.exists() and not target.exists():
            continue
        total += 1
        key, url, group = page_key(source, version), page_url(source, version), GROUPS[source]
        title = f"{PRODUCTS[source]} {version} Fixes and Known Issues"
        old = read_release(target) if target.exists() else None
        findings: List[dict] = []
        summary: Optional[dict] = None
        page: Optional[Page] = None
        # A page read already and not downloaded since is not read again: its summary stays.
        fresh = not (target.exists() and (output / source / "bugs.json").exists() and path.exists()
                     and path.stat().st_mtime <= target.stat().st_mtime)
        if entry.get("missing"):
            findings.append(report.finding("unreachable", "http", url, "", [],
                                           'the site answers "Page not found" for this release: its last reading stays'))
        elif not path.exists():
            findings.append(report.finding("unreachable", "http", url, "", [],
                                           "the page could not be downloaded: its last reading stays"))
        else:
            summary = None if fresh else read_summary(path)
            if summary is None:
                try:
                    page = parse_page(path.read_text(encoding="utf-8", errors="replace"), url)
                except Exception as error:  # A page that breaks the parser must not pass silently.
                    findings.append(report.finding("not_understood", "parse_error", url, "", [], f"the parser stops: {error!r}"))
                else:
                    summary = summarize(page)
                    summary_path(path).write_text(json.dumps(summary, ensure_ascii=False) + "\n", encoding="utf-8")
        ids = {bucket: [] for bucket in BUCKETS}
        if summary:
            if summary["missing"]:
                findings.append(report.finding("unreachable", "http", url, "", [],
                                               'the cached page is the "Page not found" of the site: its last reading stays'))
            elif summary["version"] != version:
                findings.append(report.finding("not_understood", "release_unknown", url, "", [],
                                               f"the page is that of {summary['version']}: its last reading stays"))
            else:
                findings += summary["findings"]
                ids = summary["ids"]
                headings[key] = summary["headings"]
                if summary["prose"]:
                    prose.append({"key": key, "title": title, "page": url, "count": len(summary["prose"]),
                                  "ids": summary["prose"][:report.EXAMPLES]})
                if fresh and old:
                    count = len(ids["read"])
                    had = len({i for listed in old.get("fixed", {}).values() for i in listed} | set(old.get("known", [])))
                    if had and not count:
                        findings.append(report.finding("suspect", "lost_bugs", url, "", [], f"the page had {had} bugs and has none now"))
                    elif had and count < (1 - report.DROP_LIMIT) * had:
                        findings.append(report.finding("suspect", "drop", url, "", [], f"{count} bugs read, {had} before"))
        urls[key] = url
        keep = summary is None or summary["missing"] or summary["version"] != version or any(
            f["rule"] in ("lost_bugs", "drop") for f in findings)
        # A page parsed again only for the report (the parser changed) leaves the data as it was.
        if page and fresh and not keep:
            previous_release = read_release(target) if target.exists() else None
            if not baseline and source not in new_sources:
                changes.extend({**change, "source": source} for change in page_changes(page, previous_release, date))
            written.append((target, page))
            pages_by_source.setdefault(source, []).append(page)
            log.info("%s: %d releases, %d known issues, %d security entries left out", key, len(page.fixed), len(page.known), page.skipped)
        totals = groups.setdefault(group, {"name": group, "documents": 0, **{bucket: 0 for bucket in BUCKETS}})
        totals["documents"] += 1
        for bucket in BUCKETS:
            totals[bucket] += len(ids[bucket])
        if report.status_of(findings) != "read":
            kept = ((old or {}).get("updated") or "—") if keep and old else None
            entries_report.append(report.document(key, group, title, url, findings, ids, previous.get(key), kept))
    for found in entries_report:
        if found["status"] in report.TO_FIX:
            log.warning("%s: %s %s", found["key"], found["status"], ", ".join(sorted({f["rule"] for f in found["findings"]})))
    order = list(GROUPS.values())
    built = report.build(report_path, entries_report, total, sorted(groups.values(), key=lambda g: order.index(g["name"])),
                         report.unused_sections(headings, urls), prose)
    publication = built["publication"]
    if not publication["published"]:
        return [f"only {publication['read_share']:.0%} of the pages read, under {publication['minimum']:.0%}: the site keeps its last version"]
    for target, page in written:
        write_release(target, page)
    for source, pages in pages_by_source.items():
        # The bugs read earlier stay; the pages read now, newest last, update them.
        bugs = load_bugs(output / source / "bugs.json")
        for bug_id, entry in merge_bugs(pages).items():
            old_bug = bugs.get(bug_id)
            if old_bug:
                entry = {**old_bug, **{k: v for k, v in entry.items() if v}}
                entry["fixed_versions"] = sorted(set(old_bug.get("fixed_versions", [])) | set(entry["fixed_versions"]), key=version_key)
            bugs[bug_id] = entry
        write_bugs(output / source / "bugs.json", bugs)
    write_changes(changes_path, changes)
    return []
