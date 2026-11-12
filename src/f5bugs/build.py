"""Generate the static site: copy site/ and cross the extracted data into dist/data/.

The bugs come from the "Fixes and Known Issues" pages and from the Bug Tracker;
the life of the branches from K5903; the hardware from K9412 and K4309; the
current releases from K2200.

An event is [release, status, page, source]: "r" fixed, "k" known; the page is
the position of the page of the release in the list of pages, or None; the
source is 0 for the release notes and 2 for the Bug Tracker, whose address the
browser builds from the bug number.

The texts a bug only shows when opened (symptoms, conditions, impact, behavior
change) are split into dist/data/details/<n>.json, loaded on demand: the list
the page loads at first stays light.
"""
import json
import logging
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .collect import notes_url, page_url
from .extract import load_bugs, read_changes, read_release
from .feed import build_feed, latest_changes
from .normalize import FAMILIES, canonical, families_in, family_of, model_key, models_in
from .versions import SOURCES, SYSTEMS, branch_key, branch_of, is_point, version_key

log = logging.getLogger(__name__)

DETAIL_BUCKETS = 64
OWN_FAMILY = {"f5osa": "rSeries", "f5osc": "VELOS"}
NOTES_SOURCE = 0
TRACKER_SOURCE = 2


def read_schedule(path: Path) -> Optional[dict]:
    """The crons of the automatic update, read in sources/schedule.yml so the site cannot contradict it."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    crons = re.findall(r'cron:\s*"([^"]+)"', text)
    timezone_name = re.search(r'timezone:\s*"([^"]+)"', text)
    if not crons:
        return None
    return {"crons": crons, "timezone": timezone_name.group(1) if timezone_name else "UTC"}


def load_releases(directory: Path, sources: List[str]) -> Dict[str, dict]:
    """The releases of a system, with the source of their page; F5OS 2.x comes after F5OS 1.x."""
    releases = {}
    for source in sources:
        for path in (directory / source / "releases").glob("*.json"):
            releases[path.stem] = {**read_release(path), "source": source}
    return releases


def load_system_bugs(directory: Path, sources: List[str]) -> Dict[str, dict]:
    """The bugs of the sets of notes of a system; a later set of notes gives the newer text."""
    bugs: Dict[str, dict] = {}
    for source in sources:
        for bug_id, entry in load_bugs(directory / source / "bugs.json").items():
            old = bugs.get(bug_id)
            if old:
                entry = {**old, **{k: v for k, v in entry.items() if v},
                         "fixed_versions": sorted(set(old["fixed_versions"]) | set(entry["fixed_versions"]), key=version_key)}
            bugs[bug_id] = entry
    return bugs


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def lifecycle_of(system: str, articles: dict, versions: List[str]) -> dict:
    """The support dates of the branches, as the browser reads them: support is the end of technical support.

    BIG-IP: K5903. F5OS: K21501912, whose "2.x.x" row covers every 2.y branch.
    """
    if system == "bigip":
        article = articles.get("K5903", {})
        dated = article.get("data", {})
    else:
        article = articles.get("K21501912", {})
        dated = {}
        for source in SOURCES[system]:
            for branch, dates in article.get("data", {}).get(source, {}).items():
                targets = sorted({branch_of(v) for v in versions if v.split(".")[0] == branch}) if "." not in branch else [branch]
                for target in targets or ([f"{branch}.0"] if "." not in branch else []):
                    dated[target] = dates
    branches = {branch: {"released": dates.get("released"), "development": dates.get("development", dates.get("support")),
                         "support": dates.get("support"), "extended": None}
                for branch, dates in dated.items()}
    return {"source": article.get("url"), "branches": branches}


def hardware_index(system: str, articles: dict, cited: List[str], today: str) -> dict:
    """The platforms of K4309 and K9412, with the last branch K9412 lists them in and their end of software support.

    K9412 lists the hardware of each maintenance release of the branches it
    still covers: a platform missing from the latest branch stopped after the
    last branch that lists it, as forti-bug-tracker shows for FortiOS. K4309
    gives the end of software support: after it, F5 publishes no fix for that
    platform. The browser decides the status, as it depends on the day.
    """
    lifecycles = articles.get("K4309", {}).get("data", {})
    listed: Dict[str, List[str]] = defaultdict(list)
    if system == "bigip":
        matrix = articles.get("K9412", {})
        for release, entry in matrix.get("data", {}).items():
            for name in entry["platforms"]:
                listed[canonical(name)].append(release)
        families = None
    else:
        # F5OS: K86001294 lists the F5OS releases of each rSeries and VELOS platform.
        matrix = articles.get("K86001294", {})
        for name, releases in matrix.get("data", {}).get("releases", {}).items():
            listed[canonical(name)].extend(releases)
        families = {"f5osa": {"rSeries"}, "f5osc": {"VELOS"}}[system]
    newest = max((branch_of(r) for rs in listed.values() for r in rs), key=branch_key, default=None)
    names = {canonical(n) for n in lifecycles} | set(listed) | set(cited)
    source = articles.get("K4309", {}).get("url")
    # The F5OS releases of each rSeries and VELOS platform, shown in every system, and the hardware revisions.
    f5os = articles.get("K86001294", {}).get("data", {})
    f5os_releases = {canonical(n): r for n, r in f5os.get("releases", {}).items()}
    revisions = {canonical(n): r for n, r in f5os.get("revisions", {}).items()}
    models = {}
    for name in sorted(names, key=model_key):
        family = family_of(name)
        if not family or (families and family not in families):
            continue
        dates = lifecycles.get(name) or next((d for n, d in lifecycles.items() if canonical(n) == name), {})
        branches = sorted({branch_of(r) for r in listed.get(name, [])}, key=branch_key)
        last = branches[-1] if branches else None
        groups = []
        stopped = bool(last and newest and branch_key(last) < branch_key(newest))
        # The last branch only counts when it is not the latest: "up to 21.1" would say nothing.
        # A date of first shipment says nothing of an end: only an announced end of sale or of software support does.
        if stopped or dates.get("end_of_sale") or dates.get("end_of_software"):
            groups.append([[name], None, last if stopped else None, dates.get("end_of_software"), source])
        models[name] = {
            "family": family,
            "cited": name in cited,
            "eol": groups,
            "suggested": [],
            "listed": [min(listed[name], key=version_key), max(listed[name], key=version_key)] if listed.get(name) else None,
            "end_of_sale": dates.get("end_of_sale"),
            "end_of_support": dates.get("end_of_support"),
            "f5os": [f5os_releases[name][0], f5os_releases[name][-1]] if f5os_releases.get(name) else None,
            "revision": revisions.get(name),
        }
    current = articles.get("K2200", {})
    releases = current.get("data", {}).get(system, []) + (current.get("data", {}).get("f5os", []) if system != "bigip" else [])
    return {
        "eol_source": source,
        "matrix_source": matrix.get("url"),
        "matrix_branch": newest,
        "f5os_source": articles.get("K86001294", {}).get("url"),
        "suggested_source": None,
        "as_of": None,
        "general": [],
        "current": {"source": current.get("url"), "updated": current.get("updated"), "releases": releases},
        "models": models,
    }


def build_data(system: str, releases: Dict[str, dict], bugs: Dict[str, dict], tracker: Dict[str, dict], articles: dict,
               today: str, notes: Optional[Dict[str, dict]] = None) -> dict:
    with_page = sorted(releases, key=version_key)
    lowest = branch_key(branch_of(with_page[0])) if with_page else (0, 0)
    named = set(with_page)
    for bug in bugs.values():
        named.update(bug.get("fixed_versions", []))
    # The Bug Tracker gives the releases of every product a bug touches: only those of this system's bugs count.
    for bug_id in bugs:
        named.update(tracker.get(bug_id, {}).get("affected", []))
        named.update(tracker.get(bug_id, {}).get("fixed", []))
    # An F5OS bug can name the BIG-IP releases of a fix: only the majors whose notes belong to this system count.
    majors = {v.split(".")[0] for v in with_page}
    versions = sorted((v for v in named if branch_key(branch_of(v)) >= lowest and v.split(".")[0] in majors), key=version_key)
    positions = {v: i for i, v in enumerate(versions)}
    pages = [page_url(releases[v]["source"], v) for v in with_page]
    page_of = {v: i for i, v in enumerate(with_page)}

    events: Dict[str, dict] = defaultdict(dict)

    def add(bug_id: str, version: str, code: str, source: int = NOTES_SOURCE):
        if version not in positions:
            return
        key = (positions[version], code)
        page = page_of.get(version)
        current = events[bug_id].get(key)
        # The page of the release itself wins over another page or the Bug Tracker.
        if current is None or (current[2] is None and page is not None) or (current[3] and not source):
            events[bug_id][key] = [positions[version], code, page, source]

    for version in with_page:
        release = releases[version]
        for fixed_in, ids in release.get("fixed", {}).items():
            for bug_id in ids:
                if bug_id in bugs:
                    add(bug_id, fixed_in, "r")
        for bug_id in release.get("known", []):
            if bug_id in bugs:
                add(bug_id, version, "k")
    for bug_id, bug in bugs.items():
        for version in bug.get("fixed_versions", []):
            add(bug_id, version, "r")
        entry = tracker.get(bug_id, {})
        for version in entry.get("affected", []):
            add(bug_id, version, "k", TRACKER_SOURCE)
        for version in entry.get("fixed", []):
            add(bug_id, version, "r", TRACKER_SOURCE)

    # "1000s of connections" is no platform: a v or s appliance counts only when F5's articles list it.
    known_platforms = {canonical(n) for n in articles.get("K4309", {}).get("data", {})}
    known_platforms |= {canonical(n) for entry in articles.get("K9412", {}).get("data", {}).values() for n in entry["platforms"]}
    known_platforms |= {canonical(n) for n in articles.get("K86001294", {}).get("data", {}).get("releases", {})}

    def platforms_in(text: str) -> List[str]:
        # "r5000 Series" or "i2000" name no platform: a platform counts only when F5's articles list it.
        return [m for m in models_in(text) if m in known_platforms]

    components = sorted({bug.get("component") or "" for bug in bugs.values()} - {""}, key=str.lower)
    component_positions = {name: i for i, name in enumerate(components)}
    model_names, family_names, texts = set(), set(), {}
    for bug_id, bug in bugs.items():
        text = " ".join(bug.get(k) or "" for k in ("title", "symptoms", "conditions", "impact", "workaround"))
        texts[bug_id] = text
        model_names.update(platforms_in(text))
        family_names.update(families_in(text))
    family_names |= {family_of(m) for m in model_names}
    # F5OS-A only runs on rSeries, F5OS-C only on VELOS: their hardware filter offers that family alone,
    # even when a text, as the shared notes of F5OS 2.x, names the other one.
    if system in OWN_FAMILY:
        family_names &= {OWN_FAMILY[system]}
        model_names = {m for m in model_names if family_of(m) == OWN_FAMILY[system]}
    families = [f for f in FAMILIES if f in family_names]
    family_positions = {name: i for i, name in enumerate(families)}
    models = sorted(model_names, key=model_key)

    rows, details = [], defaultdict(dict)
    changes_of: Dict[str, list] = defaultdict(list)
    for bug_id in sorted(bugs, key=int, reverse=True):
        bug = bugs[bug_id]
        if not events[bug_id]:
            continue
        cited = platforms_in(texts[bug_id])
        named_families = set(families_in(texts[bug_id])) | {family_of(m) for m in cited}
        tracker_entry = tracker.get(bug_id, {})
        bug_events = sorted(events[bug_id].values(), key=lambda e: (e[0], e[1]))
        rows.append([
            bug_id, bug.get("title") or "", bug.get("workaround"), cited,
            sorted(family_positions[f] for f in named_families if f in family_positions),
            bug_events, bug.get("fix"), None,
            component_positions.get(bug.get("component") or "", -1),
            tracker_entry.get("severity") or bug.get("severity"),
            1 if bug.get("star") else 0,
            bug.get("article"),
            1 if bug.get("behavior") else 0,
            1 if bug_id in tracker and not tracker[bug_id].get("missing") else 0,
        ])
        details[int(bug_id) % DETAIL_BUCKETS][bug_id] = [bug.get("symptoms"), bug.get("conditions"), bug.get("impact"),
                                                         bug.get("behavior")]
        if bug.get("behavior"):
            # A fix that changes a behavior is listed among the changes of the releases that bring it.
            for version, code, page, _source in bug_events:
                if code == "r":
                    changes_of[versions[version]].append([bug.get("component") or "", f"{bug_id} — {bug['title']}: {bug['behavior']}", page])

    index_versions = []
    for version in versions:
        release = releases.get(version, {})
        page = page_of.get(version)
        index_versions.append({
            "v": version,
            "branch": branch_of(version),
            "hotfix": is_point(version),
            "released": None,
            "revised": release.get("updated"),
            "addressed": page,
            "known": page,
            "changes": changes_of.get(version, []),
        })
    # The "Read" panel: new features and upgrade chapters of the newest release notes of each branch.
    branch_pages = {}
    for version in sorted((v for v, e in (notes or {}).items() if e.get("found")), key=version_key):
        base = notes_url(version)
        pages.append(base)
        pages.append(base.replace(".html", "/big-ip-upgrade.html"))
        branch_pages[branch_of(version)] = {"changes": len(pages) - 2, "limitations": len(pages) - 1, "version": version}
    k9412 = articles.get("K9412", {}).get("data", {})
    for entry in index_versions:
        if entry["v"] in k9412:
            entry["released"] = k9412[entry["v"]].get("released")
    index = {
        "system": system,
        "product": SYSTEMS[system],
        "site": "",
        "pages": pages,
        "branches": branch_pages,
        "series": {},
        "families": families,
        "models": [[m, family_positions[family_of(m)]] for m in models],
        "components": components,
        "versions": index_versions,
        "lifecycle": lifecycle_of(system, articles, versions),
        "hardware": hardware_index(system, articles, models, today),
        "details": DETAIL_BUCKETS,
    }
    return {"index": index, "bugs": {"bugs": rows}, "details": details}


def build_site(extracted: Path, changes_path: Path, articles_path: Path, schedule_path: Path, sources: Path, dist: Path,
               base_url: str, tracker_path: Path, notes_path: Optional[Path] = None) -> dict:
    tracker = {entry["id"]: entry for entry in load_json(tracker_path, {"bugs": []})["bugs"]}
    articles = load_json(articles_path, {})
    now = datetime.now(timezone.utc)
    notes = load_json(notes_path, {}) if notes_path else {}
    schedule = read_schedule(schedule_path)
    all_changes = read_changes(changes_path)
    documents = {f"{source}:{path.stem}": read_release(path)
                 for source in {s for ss in SOURCES.values() for s in ss}
                 for path in (extracted / source / "releases").glob("*.json")}

    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(sources, dist)
    summary, descriptions = {}, {}
    for system, system_sources in SOURCES.items():
        releases = load_releases(extracted, system_sources)
        if not releases:
            continue
        bugs = load_system_bugs(extracted, system_sources)
        data = build_data(system, releases, bugs, tracker, articles, now.strftime("%Y-%m-%d"),
                          notes if system == "bigip" else None)
        data["index"].update({"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "schedule": schedule})
        changes = latest_changes([c for c in all_changes if c.get("source", "bigip") in system_sources], documents)
        folder = dist / "data" / system
        (folder / "details").mkdir(parents=True)
        for name, content in (("index.json", data["index"]), ("bugs.json", data["bugs"]), ("changes.json", changes)):
            (folder / name).write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for bucket in range(DETAIL_BUCKETS):
            (folder / "details" / f"{bucket}.json").write_text(
                json.dumps(data["details"].get(bucket, {}), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        descriptions.update({row[0]: row[1] for row in data["bugs"]["bugs"]})
        rows = data["bugs"]["bugs"]
        summary[system] = {
            "versions": len(data["index"]["versions"]),
            "pages": sum(1 for v in data["index"]["versions"] if v["addressed"] is not None),
            "bugs": len(rows),
            "with model": sum(1 for row in rows if row[3]),
            "with severity": sum(1 for row in rows if row[9]),
            "with tracker": sum(1 for row in rows if row[13]),
            "hardware": len(data["index"]["hardware"]["models"]),
        }
    (dist / "feed.xml").write_bytes(build_feed(latest_changes(all_changes, documents), descriptions, base_url))
    return summary
