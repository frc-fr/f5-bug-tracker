from datetime import datetime, timezone

from f5bugs.bugtracker import parse_bug, wanted
from f5bugs.build import hardware_index
from f5bugs.collect import article_versions, candidates, due, page_url
from f5bugs.kb import parse_k21501912, parse_k2200, parse_k4309, parse_k5903, parse_k86001294, parse_k9412, parse_k9502, platforms_in
from f5bugs.normalize import canonical, family_of, models_in
from f5bugs.parser import parse_page
from f5bugs.versions import branch_of, normalize, train_of, version_key

RECENT = """<html><head><title>BIG-IP 17.1.3.7 Fixes and Known Issues | BIG-IP Documentation</title></head><body>
<p>Updated Date: 10/24/2026</p>
<a href="#v17.1.3.6">Cumulative fixes from BIG-IP v17.1.3.6 that are included in this release</a><br>
<a href="#KnownIssues">Known Issues in BIG-IP v17.1.x</a><br>
<font size="4"><u><strong>Fixed in this Release</strong></u></font>
<table><tr><td><u>ID Number</u></td><td><u>Links to More Info</u></td><td><u>Description</u></td><td><u>Fixed Versions</u></td></tr>
<tr><td><a href="#A2693429-1">2693429-1</a></td><td><a href="https://my.f5.com/manage/s/article/K000163821">K000163821</a></td>
<td>PHP vulnerabilities CVE-2026-109618 and CVE-2026-109619</td><td>17.1.3.7</td></tr></table>
<a name="v17.1.3.6"></a><font size="4"><b><u>Cumulative fixes from BIG-IP v17.1.3.6 that are included in this release</u></b></font>
<font size="4"><u><strong> Fixes</strong></u></font>
<table><tr><td><u>ID Number</u></td><td><u>Links to More Info</u></td><td><u>Description</u></td><td><u>Fixed Versions</u></td></tr>
<tr><td><a href="#A2201813-3">2201813-3</a></td><td><a href=http://cdn.f5.com/product/bugtracker/ID2201813.html>BT2201813</a></td>
<td>BIG-IP enforces maximum concurrent streams limit immediately over HTTP/2 connection</td><td>21.1.0, 21.0.0.2, 17.5.1.10, 17.1.3.6</td></tr></table>
<h2><u>Cumulative fix details for BIG-IP v17.1.3.7 that are included in this release</u></h2>
<div><h4><a name="A2201813-3"></a>2201813-3 : BIG-IP enforces maximum concurrent streams limit immediately over HTTP/2 connection</h4>
<p><strong>Links to More Info: </strong><a href=http://cdn.f5.com/product/bugtracker/ID2201813.html>BT2201813</a></p>
<p><strong>Component: </strong>Local Traffic Manager</p>
<p><strong>Symptoms:</strong><br>BIG-IP enforces the limit once the first frame is issued.</p>
<p><strong>Conditions:</strong><br> -- Virtual server with a http2 profile.<br> -- A client starts HTTP/2.</p>
<p><strong>Impact:</strong><br>The system may reset the extra streams.</p>
<p><strong>Workaround:</strong><br>None.</p>
<p><strong>Fix:</strong><br>The system no longer sends reset frames.</p>
<p><strong>Behavior Change:</strong><br>Concurrent streams are treated as unlimited until the SETTINGS/ACK frame arrives.</p>
<p><strong>Fixed Versions:</strong><br>21.1.0, 21.0.0.2, 17.5.1.10, 17.1.3.6</p></div>
<a name="KnownIssues"></a><font size="4"><b><u>Known Issues in BIG-IP v17.1.x</u></b></font>
<font size="4"><u><strong>TMOS Issues</strong></u></font>
<table><tr><td><u>ID Number</u></td><td><u>Links to More Info</u></td><td><u>Description</u></td></tr>
<tr><td><a href="#A2524317">2524317</a></td><td>BT2524317</td><td>Error installing hotfix on iSeries appliances<span>&starf;</span></td></tr></table>
<h2><u>Known Issue details for BIG-IP v17.1.x</u></h2>
<div><h4><a name="A2524317"></a>2524317 : Error installing hotfix on iSeries appliances<span>&starf;</span></h4>
<p><strong>Component: </strong>TMOS</p><p><strong>Symptoms:</strong><br>When installing the hotfix, an RPM error occurs.</p>
<p><strong>Workaround:</strong><br>Contact F5 Support for a fix</p></div>
</body></html>"""

OLD = """<html><head><title>BIG-IP 12.1.3 Fixes and Known Issues | BIG-IP Documentation</title></head><body>
<p><u><b>BIG-IP Release Information</b></u><br/>Version: 12.1.3<br/>
<a href="#v12.1.2-hf2">Cumulative fixes from BIG-IP v12.1.2 Hotfix 2 that are included in this release</a><br/>
<u><b>Vulnerability Fixes</b></u></p>
<table><tbody><tr><td><u>ID Number</u></td><td><u>CVE</u></td><td><u>Solution Article(s)</u></td><td><u>Description</u></td></tr>
<tr><td><a href="#A123456">123456</a></td><td>CVE-2017-1</td><td>K1</td><td>Multiple Oracle Java SE vulnerabilities</td></tr></tbody></table>
<p><br/><u><b>Functional Change Fixes</b></u></p>
<table><tbody><tr><td><u>ID Number</u></td><td><u>Severity</u></td><td><u>Solution Article(s)</u></td><td><u>Description</u></td></tr>
<tr><td><a href="#A697878"> 697878 </a></td><td> 2-Critical </td><td></td><td> High crypto request completion time </td></tr></tbody></table>
<p><a name="v12.1.2-hf2"></a><b><u>Cumulative fixes from BIG-IP v12.1.2 Hotfix 2 that are included in this release</u></b></p>
<table><tbody><tr><td><u>ID Number</u></td><td><u>Severity</u></td><td><u>Solution Article(s)</u></td><td><u>Description</u></td></tr>
<tr><td><a href="#A590795-1">590795-1</a></td><td>2-Critical</td><td></td><td>tmm crash when loading signatures <span title="x">&#9733;</span></td></tr></tbody></table>
<h2><u>Cumulative fix details for BIG-IP v12.1.3 that are included in this release</u></h2>
<h4><a id="A697878"></a> 697878 : High crypto request completion time under some workload patterns </h4>
<p><b>Component:</b> TMOS</p><p><b>Symptoms:</b><br/>Queues back up.</p>
<p><b>Workaround:</b><br/>Disable hardware crypto:<br/>tmsh modify sys db crypto.hwacceleration value disable</p>
<hr/><h4><a id="A123456"></a> 123456 : CVE-2017-1 Oracle Java SE vulnerability</h4><p><b>Component:</b> TMOS</p>
</body></html>"""


def test_versions():
    assert version_key("17.1.3.7") == (17, 1, 3, 7) and version_key("21.1.0") == (21, 1, 0, 0)
    assert normalize("17.1.3.0") == "17.1.3" and normalize("17.1.1.4-0.100.9") is None
    assert branch_of("17.1.3.7") == "17.1" and train_of("17.1.3.7") == "17.1.3"
    assert page_url("bigip", "17.1.3.7").endswith("/big-ip_ltm/releasenotes/related/relnote-supplement-bigip-17-1-3-7.html")
    assert page_url("f5os-a", "1.8.4-HR-1").endswith("/f5os-a/releasenotes/related/relnote-supplement-f5os-a-1-8-4-hr-1.html")
    assert page_url("f5os", "2.0.0").endswith("/f5os/releasenotes/related/relnote-supplement-f5os-2-0-0.html")


def test_f5os_releases():
    assert normalize("1.8.4.HR-2") == "1.8.4-HR-2" and normalize("1.8.4.CR") == "1.8.4-CR"
    assert sorted(["1.8.4-CR", "1.8.4", "1.8.4-HR-2", "1.8.4-HR-1"], key=version_key) == ["1.8.4", "1.8.4-HR-1", "1.8.4-HR-2", "1.8.4-CR"]
    assert train_of("1.8.4-CR") == "1.8.4" and branch_of("1.8.4-HR-1") == "1.8"


def test_recent_page_gives_fixes_known_issues_and_details():
    page = parse_page(RECENT)
    assert page.version == "17.1.3.7" and page.updated == "2026-10-24"
    assert page.fixed == {"17.1.3.6": ["2201813"]}
    assert page.skipped == 1 and "2693429" not in page.bugs
    assert page.known == ["2524317"]
    bug = page.bugs["2201813"]
    assert bug.component == "Local Traffic Manager"
    assert bug.fixed_versions == ["21.1.0", "21.0.0.2", "17.5.1.10", "17.1.3.6"]
    assert bug.conditions == "-- Virtual server with a http2 profile. -- A client starts HTTP/2."
    assert bug.workaround is None and bug.behavior.startswith("Concurrent streams are treated as unlimited")
    known = page.bugs["2524317"]
    assert known.star and known.title == "Error installing hotfix on iSeries appliances"
    assert known.workaround == "Contact F5 Support for a fix"


def test_old_page_reads_hotfixes_as_point_releases_and_severity():
    page = parse_page(OLD)
    assert page.version == "12.1.3"
    assert page.fixed == {"12.1.3": ["697878"], "12.1.2.2": ["590795"]}
    assert page.skipped == 1 and "123456" not in page.bugs
    assert page.bugs["697878"].severity == "2-Critical"
    assert page.bugs["697878"].workaround.endswith("crypto.hwacceleration value disable")
    assert page.bugs["590795"].star


def test_page_not_found():
    page = parse_page("<html><head><title>404 Page not found | BIG-IP Documentation</title></head></html>")
    assert page.missing and not page.warnings


K5903 = """| Major Release, Minor Release, and Long\\-Term Stability Release versions | First customer ship | End of Software Development | End of Technical Support | Latest maintenance release |
|---|---|---|---|---|
| 21.1.x | May 5, 2026 | May 5, 2029 | May 5, 2029 | None |
| 17.5.x1 | February 27, 2025 | January 1, 2029 | January 1, 2029 | 17.5.1 |
| Software version or branch | End of Software Development | End of Technical Support |
| 16.1.x \\(only iSeries with FIPS Addon license\\) | July 1, 2026 | July 1, 2026 |
| 16.1.x | July 31, 2025 | July 31, 2025 |
| 11.6.x | May 10, 2021 | May 10, 2022 |
| 11.6.0 | August 25, 2016 | August 25, 2017 |
| 11.5.10 11.5.9 11.5.8 | April 8, 2019 | April 8, 2020 |"""


def test_k5903_branches():
    branches = parse_k5903(K5903)
    assert branches["21.1"] == {"released": "2026-05-05", "development": "2029-05-05", "support": "2029-05-05"}
    assert branches["17.5"]["support"] == "2029-01-01"
    assert branches["16.1"]["support"] == "2025-07-31"
    assert branches["11.6"]["support"] == "2022-05-10" and branches["11.5"]["support"] == "2020-04-08"


def test_k9412_k9502_k4309_k2200():
    k9412 = """| BIG\\-IP version | Bld | Release date | Supported hardware products2 | EUD1,3 | AOM |
| [17.5.1](https://x) | 0.0.7 | June 26, 2025 | 10150s\\-N, 10350v\\-F, 10350v\\-N \\(D112\\) | EUD\\_T 2.8.2 | 8.1.137 |
| i850 \\(C117\\) i2600, i2800 \\(C117\\) | EUD\\_SF 4.0.1 | 8.0.14 |
| r5920\\-DF \\(C136\\)4 r5900, r5800, r5600 \\(C129\\)4 | N/A | N/A |
| VIPRION B2250 blade \\(A112\\) | 1.20.95 |
| VELOS BX110 \\(A118\\)4 VELOS BX520 \\(A119\\)4 | N/A | N/A |"""
    platforms = parse_k9412(k9412)["17.5.1"]["platforms"]
    assert platforms == ["10150s-N", "10350v-F", "10350v-N", "i850", "i2600", "i2800", "r5920-DF", "r5900", "r5800", "r5600",
                         "VIPRION B2250", "VELOS BX110", "VELOS BX520"]
    assert parse_k9412(k9412)["17.5.1"]["released"] == "2025-06-26"
    assert platforms_in("i15600/i15800 \\(D116\\)") == []
    k9502 = parse_k9502("| BIG\\-IP release | Latest hotfix and point release |\n| 17.1.3 | BIGIP\\-17.1.3.7 |\n| 17.5.0 | None |\n"
                        "| 12.1.2 | Hotfix\\-BIGIP\\-12.1.2.2.0.276\\-HF2 |")
    assert k9502 == {"12.1.2": "12.1.2.2", "17.1.3": "17.1.3.7", "17.5.0": None}
    k4309 = parse_k4309("| i5800 \\(C119\\) | Sep\\-2016 | [01\\-Jan\\-2024] | 01\\-Jan\\-2026 | 01\\-Jan\\-2027 |   | 01\\-Jan\\-2027 | 01\\-Jan\\-2031 | 01\\-Jan\\-2031 |\n"
                        "| r5900 \\(C129\\) | Jan\\-2022 | \\-\\-\\- | \\-\\-\\- | \\-\\-\\- |   | \\-\\-\\- | \\-\\-\\- | \\-\\-\\- |")
    assert k4309["i5800"]["end_of_sale"] == "2024-01-01" and k4309["i5800"]["end_of_software"] == "2027-01-01"
    assert k4309["r5900"]["end_of_sale"] is None
    velos = parse_k4309("| CX410 \\(F101\\) | Apr\\-2021 | \\-\\-\\- | \\-\\-\\- | \\-\\-\\- |   | \\-\\-\\- | \\-\\-\\- | \\-\\-\\- |")
    assert velos["CX410"]["shipped"] == "2021-04"
    k2200 = parse_k2200("| Product | Current release |\n| BIG\\-IP \\([LTM](x), [APM](y)\\) | 21.1.0 |\n| 17.5.1 |\n| 17.1.3 |\n"
                        "| [BIG\\-IP eBPF Observability](z) | 3.1.1 |\n| [F5OS](a) | 2.0.0 |\n| [F5OS\\-A](b) | 1.8.4 |")
    assert k2200 == {"bigip": ["21.1.0", "17.5.1", "17.1.3"], "f5os": ["2.0.0"], "f5osa": ["1.8.4"]}


def test_f5os_articles():
    k21501912 = "\n".join([
        "|  **F5OS Long Term Support releases**  |",
        "|  Software version or branch  |  First customer ship  |  EoSD/EoTS  |  Latest patch release  |",
        "|  2.x.x  |  June 30, 2026  |  June 30, 2029  |  2.0.0  |",
        "|  **F5OS\\-A Long Term Support releases**  |",
        "|  1.5.x \\(excluding 1.5.0\\)  |  August 31, 2023  |  August 31, 2026 December 31, 2027 \\(FIPS only\\)  |  1.5.4  |",
        "|  **F5OS\\-A Short Term Support releases**  |",
        "|  1.5.0  |  May 22, 2023  |  May 5, 2024  |  1.5.0  |",
    ])
    branches = parse_k21501912(k21501912)
    assert branches["f5os"]["2"] == {"released": "2026-06-30", "support": "2029-06-30", "latest": "2.0.0", "lts": True}
    assert branches["f5os-a"]["1.5"]["support"] == "2026-08-31" and branches["f5os-a"]["1.5"]["lts"]
    matrix = "\n".join([
        "r5900 / r5800 / r5600 \\(C129\\)",
        "The following table provides information about the F5 r5900 / r5800 / r5600 hardware products.",
        "| **F5OS\\-A supported versions** | **Supported tenant software versions** |",
        "| 1.5.4 | 1.5.4 | 21.0.0 \\- 21.1.0 | 17.1.0 \\- 17.5.1 |",
        "| 2.0.0 | 2.0.0 | 21.0.0 \\- 21.1.0 | 17.1.0 \\- 17.5.1 |",
        "VELOS CX410 \\(F101\\) chassis with SX410 system controllers and BX110 \\(A118\\) blade\\(s\\)",
        "| 1.8.3 | 1.8.3 | 1.8.3 | 1.8.3 | 21.0.0 \\- 21.1.0 | 17.1.0 \\- 17.5.1 |",
    ])
    parsed = parse_k86001294(matrix)
    assert parsed["releases"] == {"BX110": ["1.8.3"], "CX410": ["1.8.3"], "r5600": ["1.5.4", "2.0.0"],
                                  "r5800": ["1.5.4", "2.0.0"], "r5900": ["1.5.4", "2.0.0"]}
    revised = parse_k86001294("r5900 / r5800 / r5600 \\(C129\\)\n**Note**: If your r5000 device belongs to the updated F5 rSeries "
                              "5000 revision platform, it must run F5OS\\-A 1.8.4 or later. For more information, refer to "
                              "[K000160915: Product revision](https://x).\n| 1.8.4 | 1.8.4 |")
    assert revised["revisions"]["r5900"] == {"system": "F5OS-A", "minimum": "1.8.4", "article": "K000160915"}


def test_releases_from_articles_and_next_numbers():
    articles = {"K9412": {"data": {"17.5.1": {}}}, "K9502": {"data": {"17.1.3": "17.1.3.2", "11.4.0": None}},
                "K21501912": {"data": {"f5os-c": {"1.8": {"latest": "1.8.2"}}}}}
    assert article_versions(articles) == {("bigip", "17.5.1"), ("bigip", "17.1.3"), ("bigip", "17.1.3.1"), ("bigip", "17.1.3.2"),
                                          ("f5os-c", "1.8.0"), ("f5os-c", "1.8.1"), ("f5os-c", "1.8.2")}
    supported = {"bigip": {"17.1"}, "f5os-a": {"1.8"}, "f5os": {"2"}}
    assert candidates("bigip", {"17.1.3.7", "17.1.2", "16.1.6"}, supported) == {"17.1.3.8", "17.1.4"}
    assert candidates("f5os-a", {"1.8.4-HR-1", "1.5.4"}, supported) == {"1.8.4-HR-2", "1.8.4-CR", "1.8.5"}
    assert candidates("f5os", {"2.0.0"}, supported) == {"2.0.0-HR-1", "2.0.0-CR", "2.0.1"}


def test_ended_branches_are_checked_once_a_week():
    monday = datetime(2026, 11, 9, tzinfo=timezone.utc)
    supported = {"bigip": {"17.1"}}
    assert due({"source": "bigip", "version": "17.1.3"}, supported, monday)
    assert due({"source": "bigip", "version": "15.1.0"}, supported, monday)
    seen = {"source": "bigip", "version": "15.1.0", "checked": "2026-11-08"}
    days = [due(seen, supported, datetime(2026, 11, d, tzinfo=timezone.utc)) for d in range(9, 16)]
    assert days.count(True) == 1


def test_platform_names():
    assert canonical("VELOS BX110") == canonical("BX110 Blade") == "BX110"
    assert canonical("10350v-N") == "10350v NEBS"
    assert canonical("VIPRION B2250 Blade") == "VIPRION B2250"
    assert family_of("r5920-DF") == "rSeries" and family_of("i5800") == "iSeries" and family_of("4000s") == "Appliances v/s"
    assert models_in("On iSeries i5800 and VIPRION B2250 blades, and r10920-DF") == ["r10920-DF", "i5800", "VIPRION B2250"]


def test_hardware_status_from_k9412_and_k4309():
    articles = {
        "K9412": {"url": "m", "data": {"17.5.1": {"platforms": ["i5800", "r5900"]}, "21.1.0": {"platforms": ["r5900"]}}},
        "K4309": {"url": "l", "data": {"i5800": {"end_of_sale": "2024-01-01", "end_of_software": "2027-01-01"},
                                       "r5900": {"end_of_sale": None, "end_of_software": None},
                                       "4000s": {"end_of_sale": "2018-04-01", "end_of_software": "2021-04-01"}}},
        "K2200": {"url": "c", "data": {"bigip": ["21.1.0"]}},
    }
    index = hardware_index("bigip", articles, [], "2026-11-12")
    assert index["matrix_branch"] == "21.1"
    assert index["models"]["i5800"]["eol"] == [[["i5800"], None, "17.5", "2027-01-01", "l"]]
    assert index["models"]["r5900"]["eol"] == []
    assert index["models"]["r5900"]["listed"] == ["17.5.1", "21.1.0"]
    assert index["models"]["4000s"]["eol"] == [[["4000s"], None, None, "2021-04-01", "l"]]
    assert index["current"]["releases"] == ["21.1.0"]


def test_bug_tracker_page():
    page = ('<span class="standard-text standard-field">Last Modified: </span>Oct 16, 2026 </p>'
            '<p> <span class="standard-text">Known Affected Versions:</span><br/> <span>17.5.1, 17.5.1.2</span> </p>'
            '<p> <span class="standard-text">Fixed In:</span><br/> <span>21.1.0, 17.1.3.6</span> </p>'
            '<span class="standard-text standard-field">Opened: </span>Jan 14, 2026<br/>'
            '<p><span class="standard-text standard-field">Severity: </span>3-Major</p>')
    assert parse_bug(page) == {"affected": ["17.5.1", "17.5.1.2"], "fixed": ["21.1.0", "17.1.3.6"], "severity": "3-Major",
                               "opened": "2026-01-14", "modified": "2026-10-16"}
    known = {"1": {"id": "1", "fixed": ["17.1.3.6"]}, "2": {"id": "2", "fixed": []}, "3": {"id": "3", "missing": True}}
    notes = {"1": ["17.1.3.6"], "2": ["21.1.0"], "3": ["17.1.3"], "4": []}
    assert wanted(notes, known) == ["4", "2"]


def test_f5os_page_title_and_release_line():
    page = parse_page(RECENT.replace("BIG-IP 17.1.3.7 Fixes", "F5OS-A 1.8.4 Critical Release Fixes")
                      .replace("<p>Updated Date: 10/24/2026</p>", "<p>Updated Date: 10/24/2026</p><p>Version: 1.8.4.CR</p>")
                      .replace("Cumulative fixes from BIG-IP v17.1.3.6", "Cumulative fixes from F5OS-A v1.8.4.HR-2")
                      .replace("Known Issues in BIG-IP v17.1.x", "Known Issues in F5OS-A v1.8.x")
                      .replace("for BIG-IP v17.1", "for F5OS-A v1.8"))
    assert page.product == "F5OS-A" and page.version == "1.8.4-CR"
    assert page.fixed == {"1.8.4-HR-2": ["2201813"]} and page.known == ["2524317"]


def test_odd_cve_references_are_caught():
    from f5bugs.parser import CVE, SECURITY, clean
    assert SECURITY.search("CVECVE-2016-9063 firefox: Possible integer overflow")
    assert clean("versions were potentially susceptible to: CVE-20919-8696") == "versions were potentially susceptible to:"
