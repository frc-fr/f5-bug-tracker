"""Read one "Fixes and Known Issues" page of BIG-IP.

A page belongs to one release (17.1.3.7) and repeats the fixes of the earlier
releases of its line, each under "Cumulative fixes from BIG-IP v17.1.3.6 that
are included in this release", then lists the known issues of the branch under
"Known Issues in BIG-IP v17.1.x". The tables give, per bug, its ID, its
description and, since 16.1, the releases that fix it on every branch ("Fixed
Versions"); older tables give its severity instead. Then come the details of
each bug: component, symptoms, conditions, impact, workaround, fix, and a
behavior change when the fix changes how the system behaves.

The layout changed over the years: the parser follows the headings and the
column names, not the markup. Old hotfixes ("v12.1.2 Hotfix 2") are the point
releases of today (12.1.2.2).

Security fixes are left out: the "Vulnerability Fixes" tables, the bugs whose
title is a vulnerability, and the CVE references of the texts.
"""
import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional

from .versions import normalize, train_of, version_key

BUG_ID = re.compile(r"^\s*(\d{5,8})(?:-\d+)?\s*$")
PRODUCT = r"(?:BIG-IP|F5OS-A|F5OS-C|F5OS)"
# "BIG-IP 17.1.3.7 Fixes…", "F5OS-A 1.8.4-HR-1 Fixes…", "F5OS-A 1.8.4 Critical Release Fixes…", "F5OS-2.0.0 Fixes…".
TITLE = re.compile(rf"({PRODUCT})[\s-]+(\d+(?:\.\d+){{2,3}}(?:[.\s-]*(?:HR-?\d+|Critical Release|CR))?)\s+Fixes and Known Issues", re.I)
RELEASE_LINE = re.compile(r"^Version:\s*(\S+(?:\s+Critical Release)?)$")
CUMULATIVE = re.compile(rf"Cumulative fixes from {PRODUCT} v(\d+(?:\.\d+){{2,3}}(?:[.-]HR-\d+|[.-]CR)?)(?:\s+Hotfix\s+(\d+))?\s+that are", re.I)
KNOWN = re.compile(rf"^Known Issues in {PRODUCT} v", re.I)
THIS_RELEASE = re.compile(r"^Fixed in this Release$", re.I)
SECURITY_SECTION = re.compile(r"^(?:Vulnerability|Security) Fixes$", re.I)
SUBSECTION = re.compile(r"^[\w ()/&.-]{2,60} (?:Fixes|Issues)$")
DETAILS = re.compile(rf"^(?:Cumulative fix details|Known Issue details) for {PRODUCT}", re.I)
DETAIL_TITLE = re.compile(r"^\s*(\d{5,8})(?:-\d+)?\s*:\s*(.*)$", re.S)
# F5 sometimes doubles the prefix ("CVECVE-2016-9063") or mistypes the year ("CVE-20919-8696").
SECURITY = re.compile(r"CVE-\d{4,5}-\d+|vulnerabilit", re.I)
CVE = re.compile(r"\s*\(?(?:CVE)*CVE-\d{4,5}-\d{4,}\b\)?,?", re.I)
FIELDS = {
    "links to more info": "links", "component": "component", "symptoms": "symptoms", "conditions": "conditions",
    "impact": "impact", "workaround": "workaround", "fix": "fix", "behavior change": "behavior",
    "fixed versions": "fixed_versions",
}
NONE = re.compile(r"^(?:none|n/a|none\.)$", re.I)
SEVERITY = re.compile(r"^\d-(?:Critical|Major|Minor|Trivial|Blocking)$", re.I)
BLOCKS = {"p", "div", "br", "li", "tr", "table", "h2", "h3", "h4", "hr"}


def clean(text: str) -> str:
    return " ".join(CVE.sub("", text).split()).strip(" ,")


def versions_in(text: str) -> List[str]:
    found = []
    for token in re.split(r"[,\s]+", text):
        version = normalize(token)
        if version and version not in found:
            found.append(version)
    return found


@dataclass
class Bug:
    id: str
    title: str = ""
    star: bool = False
    severity: Optional[str] = None
    component: Optional[str] = None
    symptoms: Optional[str] = None
    conditions: Optional[str] = None
    impact: Optional[str] = None
    workaround: Optional[str] = None
    fix: Optional[str] = None
    behavior: Optional[str] = None
    fixed_versions: List[str] = field(default_factory=list)
    article: Optional[str] = None


@dataclass
class Page:
    product: Optional[str] = None
    version: Optional[str] = None
    updated: Optional[str] = None
    missing: bool = False
    # Release -> IDs the page lists as fixed in it; the IDs it lists as known in the branch.
    fixed: Dict[str, List[str]] = field(default_factory=dict)
    known: List[str] = field(default_factory=list)
    bugs: Dict[str, Bug] = field(default_factory=dict)
    skipped: int = 0
    warnings: List[str] = field(default_factory=list)


class Reader(HTMLParser):
    """A flat stream of headings, table rows and detail blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []
        self.text: List[str] = []
        self.title = ""
        self._title = False
        self._table = 0
        self._row: Optional[List[str]] = None
        self._links: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._toc = 0
        self._h4: Optional[List[str]] = None
        self._href: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._title = True
        if tag == "a" and (attrs.get("href") or "").startswith("#"):
            self._toc += 1
        if tag == "a" and attrs.get("href"):
            self._href = attrs["href"]
        if tag == "table":
            self.flush()
            self._table += 1
        elif tag == "tr" and self._table:
            self._row, self._links = [], []
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "h4":
            self.flush()
            self._h4 = []
        elif tag in BLOCKS:
            self.flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        if tag == "a":
            if self._toc:
                self._toc -= 1
            self._href = None
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.events.append(("row", self._row, self._links))
            self._row = None
        elif tag == "table":
            self._table = max(0, self._table - 1)
        elif tag == "h4" and self._h4 is not None:
            self.events.append(("h4", " ".join("".join(self._h4).split())))
            self._h4 = None
        elif tag in BLOCKS:
            self.flush()

    def handle_data(self, data):
        if self._title:
            self.title += data
        if self._cell is not None:
            self._cell.append(data)
            if self._href and self._links is not None and data.strip():
                self._links.append((data.strip(), self._href))
        elif self._h4 is not None:
            self._h4.append(data)
        elif not self._toc:
            self.text.append(data)

    def flush(self):
        text = " ".join("".join(self.text).split())
        self.text = []
        if text:
            self.events.append(("text", text))


def field_of(text: str):
    """("component", "TMOS") for "Component: TMOS"; None for other text."""
    head, sep, rest = text.partition(":")
    name = FIELDS.get(head.strip().lower()) if sep else None
    return (name, rest.strip()) if name else None


def parse_page(source: str) -> Page:
    reader = Reader()
    reader.feed(source)
    reader.flush()
    page = Page()
    title = TITLE.search(reader.title)
    if not title:
        # The site answers 200 with a "404 Page not found" page for a release it no longer has.
        page.missing = True
        return page
    page.product = title.group(1).upper()
    page.version = normalize(title.group(2))
    # The "Version:" line can give the release more exactly, as "1.8.4.HR-2"; it only refines the title,
    # as it is sometimes wrong: the page of 17.1.1.4 says "Version: 17.1.2".
    for event in reader.events[:400]:
        line = RELEASE_LINE.match(event[1]) if event[0] == "text" else None
        exact = normalize(line.group(1)) if line else None
        # Only to add an HR or CR the title does not give: the page of 13.1.1.3 says "Version: 13.1.1.4".
        if exact and page.version and "-" in exact and "-" not in page.version and train_of(exact) == train_of(page.version):
            page.version = exact
            break
    current = page.version
    known = security = details = False
    columns: List[str] = []
    detail: Optional[Bug] = None
    last_field = None
    for event in reader.events:
        kind = event[0]
        if kind == "text":
            text = event[1]
            # The details of the fixes come before the tables of the known issues.
            if KNOWN.match(text) or CUMULATIVE.search(text):
                details, detail = False, None
            if details and detail is not None:
                named = field_of(text)
                if named:
                    last_field = named[0]
                    setattr_field(detail, *named)
                elif last_field in ("symptoms", "conditions", "impact", "workaround", "fix", "behavior"):
                    setattr_field(detail, last_field, f"{getattr(detail, last_field) or ''} {text}")
                elif last_field in ("fixed_versions", "component", "links"):
                    setattr_field(detail, last_field, text)
                continue
            updated = re.search(r"Updated Date\s*:?\s*(\d{2})/(\d{2})/(\d{4})", text)
            if updated and not page.updated:
                page.updated = f"{updated.group(3)}-{updated.group(1)}-{updated.group(2)}"
            if DETAILS.match(text):
                details = True
                continue
            cumulative = CUMULATIVE.search(text)
            if cumulative:
                current = normalize(cumulative.group(1) + (f".{cumulative.group(2)}" if cumulative.group(2) else ""))
                known = security = False
            elif KNOWN.match(text):
                known, security = True, False
            elif THIS_RELEASE.match(text):
                current, known, security = page.version, False, False
            elif SECURITY_SECTION.match(text):
                security = True
            elif SUBSECTION.match(text):
                security = False
        elif kind == "row" and not details:
            cells, links = event[1], event[2]
            if cells and cells[0].lower() == "id number":
                columns = [cell.lower() for cell in cells]
                continue
            match = BUG_ID.match(cells[0]) if cells else None
            if not match:
                continue
            row = dict(zip(columns, cells))
            description = row.get("description", cells[-1])
            bug_id = match.group(1)
            if security or "cve" in columns or SECURITY.search(description):
                page.skipped += 1
                page.bugs.pop(bug_id, None)
                continue
            bug = page.bugs.setdefault(bug_id, Bug(bug_id))
            bug.title = bug.title or clean(description.replace("★", ""))
            bug.star = bug.star or "★" in description
            severity = row.get("severity", "")
            if SEVERITY.match(severity):
                bug.severity = severity
            if row.get("fixed versions"):
                bug.fixed_versions = versions_in(row["fixed versions"])
            for label, href in links:
                if re.match(r"^K\d+", label) and not bug.article:
                    bug.article = label
            if known:
                if bug_id not in page.known:
                    page.known.append(bug_id)
            elif current:
                listed = page.fixed.setdefault(current, [])
                if bug_id not in listed:
                    listed.append(bug_id)
        elif kind == "h4" and details:
            match = DETAIL_TITLE.match(event[1])
            last_field = None
            detail = None
            if not match:
                continue
            bug_id, title = match.groups()
            if SECURITY.search(title) or (bug_id not in page.bugs and not any(bug_id in ids for ids in page.fixed.values())
                                          and bug_id not in page.known):
                # Not in a table, or left out with the vulnerabilities.
                continue
            detail = page.bugs.setdefault(bug_id, Bug(bug_id))
            detail.star = detail.star or "★" in title
            detail.title = clean(title.replace("★", "")) or detail.title
    for bug in page.bugs.values():
        for name in ("symptoms", "conditions", "impact", "workaround", "fix", "behavior"):
            value = getattr(bug, name)
            if value is not None:
                value = clean(value)
                setattr(bug, name, None if not value or NONE.match(value) else value)
    if not page.fixed and not page.known:
        page.warnings.append("no fix and no known issue found")
    return page


def setattr_field(bug: Bug, name: str, value: str) -> None:
    if name == "fixed_versions":
        if value:
            bug.fixed_versions = versions_in(value)
    elif name == "component":
        bug.component = value or bug.component
    elif name == "links":
        article = re.search(r"\bK\d{4,}\b", value)
        if article and not bug.article:
            bug.article = article.group(0)
    else:
        setattr(bug, name, value)
