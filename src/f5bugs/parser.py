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

Every bug ID the page lists, in a table or as the title of a detail, ends in one
bucket of the processing report: read, left out by a known rule ("ruled"), or
not understood ("failed"). An ID found in none of them is a silent path of the
code: the report calls the page suspect.
"""
import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple

from .report import accounting, finding
from .versions import normalize, train_of, version_key

BUG_ID = re.compile(r"^\s*(\d{5,8})(?:-\d+)?\s*$")
# A cell that is a bug ID in any F5 writing ("2201813-3", "BT2201813", "ID2201813"): what the page lists,
# even in a form the parser does not read. In a row the parser reads, only its ID cell counts.
LISTED = re.compile(r"^\W*(?:ID|BT)?\s?(\d{5,8})(?:-\d+)?\W*$")
# A bug the text cites outside the lists: "ID1032405", "BT1032405".
CITED = re.compile(r"\b(?:ID|BT)(\d{6,8})\b")
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
SECTION_LIKE = re.compile(rf"\b(?:Fixes|Issues?|details) (?:in|for|from) {PRODUCT}\b", re.I)
# The frame of every techdocs.f5.com page, not its content: never reported as a section left unread.
FRAME = re.compile(r"^(?:Applies To|Supplemental Document|Note: This content is cur|Updated Date|Original Publication Date|"
                   r"Manual Chapter|Copyright|Have a Question|Follow Us|About F5|Education|F5 Sites|Support Tasks)", re.I)
# Read for the release and the date: "BIG-IP Release Information", "F5OS-A 1.5.4 Critical Release - Release Information".
RELEASE_INFO = re.compile(r"Release Information$", re.I)
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
    # The security fixes left out, one per table row.
    skipped: int = 0
    # What is not read, and why: a known rule ("left_out"), or a layout to adapt the code to.
    findings: List[dict] = field(default_factory=list)
    # Each bug ID the page lists: (page, place) where it lists it first.
    listed: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # Each section title, and whether the code reads it.
    headings: Dict[str, bool] = field(default_factory=dict)
    # Bug IDs the text cites outside the lists.
    prose: Set[str] = field(default_factory=set)

    @property
    def warnings(self) -> List[str]:
        """What the code cannot read: it has to be adapted."""
        return [f"{f['count']} bugs under {f['where']!r}: {f['detail']}" for f in self.findings if f["kind"] == "not_understood"]

    def read(self) -> Set[str]:
        return {i for ids in self.fixed.values() for i in ids} | set(self.known)

    def accounting(self) -> Dict[str, Set[str]]:
        """Each bug ID the page lists, in one bucket: read, ruled out, failed, or unaccounted."""
        return accounting(set(self.listed), self.read(), self.findings)


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
        # The texts set apart outside the tables (underlined, bold, h2): the section titles are among them.
        self.marked: Set[str] = set()
        self._mark: Optional[List[str]] = None
        self._mark_tag = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._title = True
        if tag == "a" and (attrs.get("href") or "").startswith("#"):
            self._toc += 1
        if tag == "a" and attrs.get("href"):
            self._href = attrs["href"]
        if tag in ("u", "b", "strong", "h2") and not self._table and self._mark is None:
            self._mark, self._mark_tag = [], tag
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
        if tag == self._mark_tag and self._mark is not None:
            text = " ".join("".join(self._mark).split())
            if text:
                self.marked.add(text)
            self._mark = None
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
        if self._mark is not None:
            self._mark.append(data)
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


def parse_page(source: str, url: str = "") -> Page:
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
    # Where the page is: its section ("Cumulative fixes from BIG-IP v17.1.3.6…") and subsection ("TMOS Fixes").
    top = sub = ""

    def place() -> str:
        return " / ".join(part for part in (top, sub) if part)

    def note(kind: str, rule: str, where: str, ids: List[str], why: str) -> None:
        page.findings.append(finding(kind, rule, url, where, ids, why))

    for event in reader.events:
        kind = event[0]
        if kind == "text":
            text = event[1]
            page.prose.update(CITED.findall(text))
            subsection = not details and bool(SECURITY_SECTION.match(text) or SUBSECTION.match(text) or text == "Fixes")
            section = bool(KNOWN.match(text) or CUMULATIVE.search(text) or DETAILS.match(text)) or not details and bool(
                THIS_RELEASE.match(text) or (RELEASE_INFO.search(text) and text in reader.marked))
            # In the details, a bold text is a field name or a word of a workaround, not a section title,
            # unless it reads as one: "Behavior Change Issues in BIG-IP v14.1.x".
            other = text in reader.marked and not text.endswith(":") and len(text) <= 120 and (
                not details or bool(SECTION_LIKE.search(text)))
            if (subsection or section or other) and not FRAME.match(text):
                page.headings[text] = page.headings.get(text, False) or subsection or section
                if subsection:
                    sub = text
                else:
                    top, sub = text, ""
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
            elif text.startswith("Cumulative fixes from"):
                # A release the code cannot write: its fixes are not given to the release before.
                current, known, security = None, False, False
            elif KNOWN.match(text):
                known, security = True, False
            elif THIS_RELEASE.match(text):
                current, known, security = page.version, False, False
            elif SECURITY_SECTION.match(text):
                security = True
            elif SUBSECTION.match(text):
                security = False
        elif kind == "row":
            cells, links = event[1], event[2]
            match = BUG_ID.match(cells[0]) if cells else None
            # A row the parser reads lists the bug of its ID cell; another lists any cell that is a bug ID.
            for bug_id in [match.group(1)] if match else [m.group(1) for cell in cells for m in [LISTED.match(cell)] if m]:
                page.listed.setdefault(bug_id, (url, place()))
            if details:
                continue
            if cells and cells[0].lower() == "id number":
                columns = [cell.lower() for cell in cells]
                continue
            if not match:
                continue
            row = dict(zip(columns, cells))
            description = row.get("description", cells[-1])
            bug_id = match.group(1)
            if security or "cve" in columns or SECURITY.search(description):
                page.skipped += 1
                page.bugs.pop(bug_id, None)
                if security or "cve" in columns:
                    note("left_out", "security", sub or top, [bug_id], "a list of security fixes")
                else:
                    note("left_out", "security", sub or top, [bug_id], "a vulnerability fix in a list of fixes or issues")
                continue
            if not known and not current:
                note("not_understood", "release_unknown", place(), [bug_id],
                     "a section of cumulative fixes whose release the code cannot read")
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
            else:
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
            # A detail lists its bug too: one that no table lists is a table the code does not read.
            if bug_id not in page.listed and SECURITY.search(title):
                note("left_out", "security", place(), [bug_id], "a vulnerability fix detailed without a table row")
            page.listed.setdefault(bug_id, (url, place()))
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
        page.findings.append(finding("not_understood", "empty_page", url, "", [], "no fix and no known issue found"))
    page.prose -= set(page.listed)
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
