"""Name the hardware: the platforms of F5's articles, and those the bug texts cite.

K9412 and K4309 do not write a platform the same way: "VELOS BX110" and "BX110
Blade", "10350v-N" and "10350v NEBS". The site gives each platform one name,
without the "Blade" or "Chassis" of the articles, and files it in the family
F5 uses: iSeries, rSeries, VELOS, VIPRION, the v and s appliances, or Virtual
Edition.

A bug text that cites a platform says "the notes cite it", never "only this
platform is affected".
"""
import re
from typing import List, Optional

FAMILIES = ["rSeries", "VELOS", "iSeries", "VIPRION", "Appliances v/s", "Virtual Edition"]
VARIANTS = {"-N": " NEBS", "-F": " FIPS"}


def canonical(name: str) -> str:
    """One name per platform: "VIPRION B2250", "BX110", "10350v NEBS", "i5820-DF"."""
    name = " ".join(name.replace("\\", "").split())
    name = re.sub(r"\s+(?:Blade|Chassis)\b", "", name, flags=re.I)
    name = re.sub(r"^VELOS\s+", "", name)
    match = re.match(r"^(\d{3,5}[sv])(-[NF])$", name)
    if match:
        name = match.group(1) + VARIANTS[match.group(2)]
    if re.match(r"^[BC]\d{4}", name):
        name = f"VIPRION {name}"
    return name


def family_of(name: str) -> Optional[str]:
    if re.match(r"^r\d{4,5}", name):
        return "rSeries"
    if re.match(r"^(?:BX|CX)\d{3,4}", name):
        return "VELOS"
    if re.match(r"^i\d{3,5}", name):
        return "iSeries"
    if name.startswith("VIPRION"):
        return "VIPRION"
    if re.match(r"^\d{3,5}[sv]\b", name):
        return "Appliances v/s"
    return None


# Cited in a text: i5800, i10800, i5820-DF; r5900, r10920-DF; BX110, CX410; B2250, C2400; 10350v, 4000s.
CITED = re.compile(
    r"(?<![\w.-])("
    r"i\d{3,5}(?:-D[FS])?"
    r"|r\d{4,5}(?:-D[FS])?"
    r"|[BC]X\d{3,4}"
    r"|[BC]\d{4}(?![\d.])"
    r"|\d{4,5}[sv]"
    r")(?![\w-])"
)
FAMILY_MENTIONS = [
    (re.compile(r"\biSeries\b", re.I), "iSeries"),
    (re.compile(r"\brSeries\b", re.I), "rSeries"),
    (re.compile(r"\bVELOS\b"), "VELOS"),
    (re.compile(r"\bVIPRION\b"), "VIPRION"),
    (re.compile(r"\bVirtual Edition\b|\bBIG-IP VE\b|(?<![\w-])VE(?![\w-])"), "Virtual Edition"),
]


def models_in(text: str) -> List[str]:
    found = []
    for raw in CITED.findall(text or ""):
        name = canonical(raw)
        if family_of(name) and name not in found:
            found.append(name)
    return sorted(found, key=model_key)


def families_in(text: str) -> List[str]:
    return sorted({family for pattern, family in FAMILY_MENTIONS if pattern.search(text or "")}, key=FAMILIES.index)


def model_key(name: str):
    family = family_of(name)
    numbers = re.findall(r"\d+", name)
    return (FAMILIES.index(family) if family in FAMILIES else len(FAMILIES), int(numbers[0]) if numbers else 0, name)
