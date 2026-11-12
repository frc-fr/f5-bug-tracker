"""Checks on the real pages; skipped when .cache/html is empty."""
import os
from pathlib import Path

import pytest

from f5bugs.parser import parse_page

CACHE = Path(os.environ.get("F5BUGS_CACHE", ".cache/html"))
PAGES = sorted(f"{path.parent.name}/{path.stem}" for path in CACHE.glob("*/*.html")) if CACHE.exists() else []
pytestmark = pytest.mark.corpus


def read(name: str):
    """name is "<source>/<release>", as "bigip/17.1.3.7" or "f5os-a/1.8.4-CR"."""
    return parse_page((CACHE / f"{name}.html").read_text(encoding="utf-8", errors="replace"))


@pytest.mark.skipif(not PAGES, reason="no cached page")
@pytest.mark.parametrize("name", PAGES)
def test_every_page_parses_cleanly(name):
    page = read(name)
    if page.missing:
        pytest.skip("page not found on the site")
    assert page.version == name.split("/")[1] and not page.warnings
    texts = " ".join(f"{b.title} {b.symptoms or ''} {b.workaround or ''} {b.fix or ''}" for b in page.bugs.values())
    assert "CVE-" not in texts
    # Some pages list a fix with one sentence and no detail: every bug has at least its description.
    assert all(b.title for b in page.bugs.values())


def test_known_facts_of_17_1_3_7():
    if "bigip/17.1.3.7" not in PAGES:
        pytest.skip("17.1.3.7 not cached")
    page = read("bigip/17.1.3.7")
    bug = page.bugs["2201813"]
    assert bug.fixed_versions == ["21.1.0", "21.0.0.2", "17.5.1.10", "17.1.3.6"]
    assert bug.component == "Local Traffic Manager" and bug.behavior
    assert "2201813" in page.fixed["17.1.3.6"]
    assert "2524317" in page.known and page.bugs["2524317"].star
