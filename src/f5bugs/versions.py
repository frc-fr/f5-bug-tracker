"""Helpers for BIG-IP version strings.

A maintenance release is "<major>.<minor>.<maintenance>", as 17.1.3, and its
point releases add a fourth number, as 17.1.3.7. A branch is "<major>.<minor>":
17.1, 17.5, 21.1. A point release only follows its own maintenance release: a
fix in 17.1.3.6 is in 17.1.3.7, but the notes must say whether it is in 17.1.4.

Engineering hotfixes (17.1.1.4-0.100.9) are builds for a few customers: the
site leaves them out.

F5OS writes its patch releases 1.8.4, then its Hardened Releases 1.8.4-HR-1 and
1.8.4-HR-2, then its Critical Release 1.8.4-CR, which carries the fixes of both:
they are the point releases of 1.8.4, in that order, shown as F5 writes them.
"""
import re
from typing import Optional, Tuple

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+)|-(HR-\d+|CR))?$")
# The F5 writings of a release, as the notes, the articles and the addresses give them.
LOOSE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+)|[.\-\s]+(HR)[-\s]?(\d+)|[.\-\s]+(CR|Critical Release))?$", re.I)
PRODUCT = "BIG-IP"
SYSTEMS = {"bigip": "BIG-IP", "f5osa": "F5OS-A", "f5osc": "F5OS-C"}
# The release notes of each system: F5OS 2.x has one set of notes for rSeries and VELOS.
SOURCES = {"bigip": ["bigip"], "f5osa": ["f5os-a", "f5os"], "f5osc": ["f5os-c", "f5os"]}
CRITICAL = 50


def version_key(version: str) -> Tuple[int, ...]:
    match = VERSION.match(version)
    if not match:
        raise ValueError(f"not a BIG-IP release: {version!r}")
    major, minor, maintenance, point, variant = match.groups()
    if variant:
        return int(major), int(minor), int(maintenance), CRITICAL if variant == "CR" else int(variant[3:])
    return int(major), int(minor), int(maintenance), int(point or 0)


def is_version(version: str) -> bool:
    return bool(VERSION.match(version))


def normalize(version: str) -> Optional[str]:
    """17.1.3.0 is 17.1.3, 1.8.4.HR-2 is 1.8.4-HR-2, 1.8.4.CR is 1.8.4-CR; anything that is no release, None."""
    match = LOOSE.match(version.strip())
    if not match:
        return None
    major, minor, maintenance, point, hardened, number, critical = match.groups()
    base = f"{int(major)}.{int(minor)}.{int(maintenance)}"
    if hardened:
        return f"{base}-HR-{int(number)}"
    if critical:
        return f"{base}-CR"
    return base + (f".{int(point)}" if point and int(point) else "")


def branch_of(version: str) -> str:
    return ".".join(version.split(".")[:2])


def train_of(version: str) -> str:
    """The maintenance release a point release belongs to: 17.1.3 for 17.1.3.7, 1.8.4 for 1.8.4-CR."""
    return ".".join(version.split("-")[0].split(".")[:3])


def is_point(version: str) -> bool:
    return version_key(version)[3] > 0


def branch_key(branch: str) -> Tuple[int, int]:
    major, minor = branch.split(".")
    return int(major), int(minor)


def slug(version: str) -> str:
    """The form of a release in the addresses of the notes: 17-1-3-7, 1-8-4-hr-1."""
    return version.replace(".", "-").lower()


def bug_key(bug_id: str) -> int:
    return int(bug_id)
