"""F5 knowledge articles that tell the life of the releases and of the hardware.

They are public articles of my.f5.com, whose robots.txt allows robots. The
page is drawn by JavaScript: it is rendered by Lightpanda, a headless browser,
and read as markdown. The sitemaps of the portal give the date each article
last changed: an article is rendered again only when that date moved.

- K5903 "BIG-IP software support policy": the support dates of each branch.
- K9412 "The BIG-IP release matrix": the build, release date and supported
  hardware of each maintenance release, for the branches it still lists.
- K9502 "BIG-IP hotfix and point release matrix": the latest point release of
  each maintenance release, which tells which releases exist.
- K4309 "F5 hardware product lifecycle support policy": the end of sale, of new
  software support, of software support and of technical support of each platform.
- K2200 "Most recent versions of F5 software": the current releases of BIG-IP and F5OS.
- K21501912 "Software lifecycle policy for F5OS": the support dates of each F5OS branch.
- K86001294 "F5OS hardware/software support matrix": the F5OS releases each rSeries and VELOS platform supports.

Their content is the vendor's: the site keeps the facts it needs, with the
address of the article. A failed rendering keeps the last values.
"""
import json
import logging
import os
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .versions import branch_key, normalize, version_key

log = logging.getLogger(__name__)

ARTICLE_URL = "https://my.f5.com/manage/s/article/{name}"
SITEMAPS = ["https://my.f5.com/manage/s/sitemap-topicarticle-1.xml", "https://my.f5.com/manage/s/sitemap-topicarticle-2.xml"]
ARTICLES = ["K5903", "K9412", "K9502", "K4309", "K2200", "K21501912", "K86001294"]
RENDERER_ENV = "F5BUGS_LIGHTPANDA"
USER_AGENT_SUFFIX = "f5-bug-tracker/0.1 (+https://github.com/frc-fr/f5-bug-tracker)"
RENDER_TIMEOUT = 150
ROW = re.compile(r"^\|(.*)\|\s*$")
UPDATED = re.compile(r"Updated Date:\s*\*\*([A-Z][a-z]{2} \d{1,2}, \d{4})")


def article_url(name: str) -> str:
    return ARTICLE_URL.format(name=name)


def renderer() -> List[str]:
    """The Lightpanda command, from F5BUGS_LIGHTPANDA: a path, or a wrapper running it."""
    return shlex.split(os.environ.get(RENDERER_ENV, "lightpanda"))


def render(name: str) -> str:
    command = renderer() + [
        "fetch", "--user-agent-suffix", USER_AGENT_SUFFIX,
        "--wait-script", f"document.body && document.body.innerText.includes('{name}:') && document.body.innerText.includes('Updated Date')",
        "--wait-ms", "120000", "--dump", "markdown", article_url(name),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    if f"# {name}:" not in result.stdout:
        raise RuntimeError(f"{name}: rendering failed ({result.returncode})")
    return result.stdout


def unescape(text: str) -> str:
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"\\(.)", r"\1", text)
    return " ".join(text.replace("[", "").replace("]", "").split())


def rows(markdown: str) -> List[List[str]]:
    found = []
    for line in markdown.splitlines():
        match = ROW.match(line.strip())
        if match and not re.fullmatch(r"[|\-\s:]+", line.strip()):
            found.append([unescape(cell) for cell in match.group(1).split("|")])
    return found


def updated(markdown: str) -> Optional[str]:
    match = UPDATED.search(markdown)
    return datetime.strptime(match.group(1), "%b %d, %Y").strftime("%Y-%m-%d") if match else None


def iso(text: str) -> Optional[str]:
    text = re.sub(r"[¹²³\d]$", "", text.strip()) if re.search(r"\d{4}\d$", text.strip()) else text.strip()
    for layout in ("%B %d, %Y", "%b %d, %Y", "%d-%b-%Y", "%b-%Y"):
        try:
            return datetime.strptime(text, layout).strftime("%Y-%m-%d" if "%d" in layout else "%Y-%m")
        except ValueError:
            pass
    return None


def parse_k5903(markdown: str) -> Dict[str, dict]:
    """{branch: {released, development, support}}: the supported branches, then those ended.

    "17.5.x1" carries a footnote; "16.1.x (only iSeries with FIPS…)" is a
    special case left out; a list of releases ("11.5.10 11.5.9 …") is one branch.
    """
    branches: Dict[str, dict] = {}
    for cells in rows(markdown):
        if len(cells) < 3:
            continue
        name = cells[0]
        if "(" in name or name.lower().startswith(("major", "software")):
            continue
        match = re.match(r"^(\d+)\.(\d+)\.(?:x|\d+)", name)
        if not match:
            continue
        branch = f"{match.group(1)}.{match.group(2)}"
        dates = [iso(re.sub(r"\d$", "", c) if re.search(r"\d{4}\d$", c) else c) for c in cells[1:]]
        if len(cells) >= 5:
            entry = {"released": dates[0], "development": dates[1], "support": dates[2]}
        else:
            entry = {"released": None, "development": dates[0], "support": dates[1]}
        if not entry["support"]:
            continue
        # Several rows of one branch ("11.6.x" and "11.6.0"): the branch lives as long as its last one.
        if branch not in branches or entry["support"] > branches[branch]["support"]:
            branches[branch] = entry
    return dict(sorted(branches.items(), key=lambda item: branch_key(item[0]), reverse=True))


PLATFORM = re.compile(r"([A-Za-z0-9][\w/, -]*?)\s*\(([A-Z]\d{2,3}[a-z]?)\)\d?")


def platforms_in(cell: str) -> List[str]:
    """The platforms of a cell: "i5600, i5800 (C119) i5820-DF (C125)" gives i5600, i5800, i5820-DF."""
    found = []
    for names, _code in PLATFORM.findall(cell):
        for name in re.split(r",\s*|/", names):
            name = re.sub(r"\s*blade$", "", name.strip(), flags=re.I)
            name = re.sub(r"^\d\s+", "", name)
            if name and name not in found:
                found.append(name)
    return found


def parse_k9412(markdown: str) -> Dict[str, dict]:
    """{maintenance release: {build, released, platforms}}; the continuation rows add platforms."""
    releases: Dict[str, dict] = {}
    current = None
    for cells in rows(markdown):
        version = normalize(cells[0]) if cells else None
        if version and len(cells) >= 4:
            current = version
            releases[current] = {"build": cells[1], "released": iso(cells[2]), "platforms": platforms_in(cells[3])}
        elif current and cells and not cells[0].startswith("BIG-IP version"):
            for name in platforms_in(cells[0]):
                if name not in releases[current]["platforms"]:
                    releases[current]["platforms"].append(name)
    return dict(sorted(releases.items(), key=lambda item: version_key(item[0])))


def parse_k9502(markdown: str) -> Dict[str, Optional[str]]:
    """{maintenance release: latest point release or None}, for supported and ended releases."""
    latest: Dict[str, Optional[str]] = {}
    for cells in rows(markdown):
        if len(cells) != 2:
            continue
        release = normalize(cells[0])
        if not release:
            continue
        match = re.search(r"BIGIP-(\d+\.\d+\.\d+\.\d+)(?:$|\.0\.)", cells[1])
        point = normalize(match.group(1)) if match else None
        old = re.search(r"Hotfix-BIGIP-(\d+\.\d+\.\d+)\.\d+\.0\.\d+-HF(\d+)", cells[1])
        if old:
            point = normalize(f"{old.group(1)}.{old.group(2)}")
        latest[release] = point if point and point != release else None
    return dict(sorted(latest.items(), key=lambda item: version_key(item[0])))


LIFECYCLE_COLUMNS = ["shipped", "end_of_sale", "end_of_new_software", "end_of_software", "extended", "end_of_support", "end_of_rma"]


def parse_k4309(markdown: str) -> Dict[str, dict]:
    """{platform: milestones}; a date in the future may be announced, "---" means none yet."""
    found: Dict[str, dict] = {}
    for cells in rows(markdown):
        if len(cells) < 8 or cells[0].lower().startswith(("hardware products", "**")):
            continue
        match = re.match(r"^(.*?)\s*\(([A-Z]\d{2,3}[a-z]?)(?:/\d+)?\)", cells[0])
        if not match:
            continue
        name = re.sub(r"\s*blade$", "", match.group(1), flags=re.I).strip()
        values = [c for i, c in enumerate(cells[1:]) if i != 4]
        dates = {key: iso(value) for key, value in zip(["shipped", "end_of_sale", "end_of_new_software", "end_of_software",
                                                         "extended", "end_of_support", "end_of_rma"], values)}
        found[name] = {"code": match.group(2), **dates}
    return dict(sorted(found.items()))


K2200_PRODUCTS = {"BIG-IP": "bigip", "F5OS": "f5os", "F5OS-A": "f5osa", "F5OS-C": "f5osc"}


def parse_k2200(markdown: str) -> Dict[str, List[str]]:
    """The current releases of BIG-IP and F5OS: a product's row, then its continuation rows."""
    current: Dict[str, List[str]] = {}
    product = None
    for cells in rows(markdown):
        if len(cells) == 2:
            name = cells[0].split(" (")[0].strip()
            product = K2200_PRODUCTS.get(name)
            version = normalize(cells[1])
        elif len(cells) == 1:
            version = normalize(cells[0])
        else:
            product = None
            continue
        if product and version:
            current.setdefault(product, []).append(version)
    return current


F5OS_SECTIONS = {"F5OS": "f5os", "F5OS-C": "f5os-c", "F5OS-A": "f5os-a"}


def parse_k21501912(markdown: str) -> Dict[str, Dict[str, dict]]:
    """{source: {branch: {released, support, latest, lts}}}; F5OS 2.x is the branch "2".

    "1.5.x (excluding 1.5.0)" is the LTS branch 1.5, "1.5.0" an earlier STS
    release of it: the branch keeps the longest support. A support cell may add
    a later date for FIPS deployments only: the first date is the support.
    """
    found: Dict[str, Dict[str, dict]] = {}
    source = lts = None
    for cells in rows(markdown):
        heading = re.match(r"^\*\*\s*(F5OS(?:-[AC])?) (Long|Short) Term Support releases\s*\*\*$", cells[0]) if len(cells) == 1 else None
        if heading:
            source, lts = F5OS_SECTIONS[heading.group(1)], heading.group(2) == "Long"
            continue
        if not source or len(cells) < 4:
            continue
        match = re.match(r"^(\d+)\.(x|\d+)", cells[0])
        if not match:
            continue
        branch = match.group(1) if match.group(2) == "x" else f"{match.group(1)}.{match.group(2)}"
        support = iso(re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}", cells[2]).group(0)) if re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}", cells[2]) else None
        entry = {"released": iso(cells[1]), "support": support, "latest": normalize(cells[3]), "lts": lts}
        branches = found.setdefault(source, {})
        if support and (branch not in branches or support > (branches[branch]["support"] or "")):
            branches[branch] = entry
    return found


F5OS_PLATFORM = re.compile(r"\b(r\d{4,5}(?:-D[FS])?|CX\d{3,4}|BX\d{3})\b")


def parse_k86001294(markdown: str) -> Dict[str, dict]:
    """{"releases": {platform: F5OS releases}, "revisions": {platform: {"minimum", "article"}}}.

    Each table follows a line naming its platforms. A note under a table can
    tell that a revision of the hardware needs a later F5OS: "If your r5000
    device belongs to the updated F5 rSeries 5000 revision platform, it must
    run F5OS-A 1.8.4 or later", with the article announcing the revision.
    """
    found: Dict[str, List[str]] = {}
    revisions: Dict[str, dict] = {}
    platforms: List[str] = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            text = unescape(line)
            if re.match(r"^(?:VELOS CX\d|r\d{4,5})", text) and "(" in text and not text.startswith("The following"):
                platforms = list(dict.fromkeys(F5OS_PLATFORM.findall(text)))
            revision = re.search(r"revision platform, it must run (F5OS-[AC]) (\d+\.\d+\.\d+) or later", text)
            article = re.search(r"\b(K\d{6,})\b", line)
            if revision and platforms:
                for name in platforms:
                    revisions[name] = {"system": revision.group(1), "minimum": revision.group(2),
                                       "article": article.group(1) if article else None}
            continue
        cells = [unescape(c) for c in line.strip("|").split("|")]
        version = normalize(re.sub(r"\*", "", cells[0])) if cells else None
        if version and platforms:
            for name in platforms:
                if version not in found.setdefault(name, []):
                    found[name].append(version)
    return {"releases": {name: sorted(v, key=version_key) for name, v in sorted(found.items())},
            "revisions": dict(sorted(revisions.items()))}


PARSERS = {"K5903": parse_k5903, "K9412": parse_k9412, "K9502": parse_k9502, "K4309": parse_k4309, "K2200": parse_k2200,
           "K21501912": parse_k21501912, "K86001294": parse_k86001294}
MINIMUMS = {"K5903": 15, "K9412": 5, "K9502": 40, "K4309": 30, "K2200": 2, "K21501912": 3, "K86001294": 10}


def sitemap_dates(client) -> Dict[str, str]:
    dates = {}
    for url in SITEMAPS:
        response = client.request("GET", url)
        if response.status_code != 200:
            raise RuntimeError(f"{url}: {response.status_code}")
        for name, lastmod in re.findall(r"<loc>https://my\.f5\.com/manage/s/article/(K\d+)</loc><lastmod>([^<]+)</lastmod>", response.text):
            if name in ARTICLES:
                dates[name] = lastmod
    return dates


def load_articles(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_articles(path: Path, client) -> dict:
    """Render the articles that changed since the last run; keep the others, and any that fails."""
    state = load_articles(path)
    try:
        dates = sitemap_dates(client)
    except (RuntimeError, OSError) as error:
        log.error("articles kept as they were: %s", error)
        return state
    for name in ARTICLES:
        known = state.get(name, {})
        if known.get("lastmod") == dates.get(name) and known.get("data"):
            continue
        try:
            markdown = render(name)
            data = PARSERS[name](markdown)
            if len(data) < MINIMUMS[name]:
                raise ValueError(f"{name}: only {len(data)} entries")
        except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            log.error("%s kept as it was: %s", name, error)
            continue
        state[name] = {"url": article_url(name), "lastmod": dates.get(name), "updated": updated(markdown), "data": data}
    path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return state
