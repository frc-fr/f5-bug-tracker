"""Command line entry point."""
import argparse
import json
import logging
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="f5bugs")
    parser.add_argument("--pages", type=Path, default=Path("sources/pages.json"))
    parser.add_argument("--articles", type=Path, default=Path("sources/articles.json"))
    parser.add_argument("--notes", type=Path, default=Path("sources/notes.json"))
    parser.add_argument("--schedule", type=Path, default=Path("sources/schedule.yml"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/html"))
    parser.add_argument("--output", type=Path, default=Path("data/extracted"))
    parser.add_argument("--tracker", type=Path, default=Path("data/extracted/bugtracker.json"))
    parser.add_argument("--changes", type=Path, default=Path("data/changes.json"))
    parser.add_argument("--report", type=Path, default=Path("data/report.json"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--base-url", default="https://frc-fr.github.io/f5-bug-tracker/")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--batch", type=int, default=None, help="Bug Tracker pages read per run")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("collect", help="update the articles and the release list, download the new or changed pages")
    commands.add_parser("extract", help="parse the cached pages and write the processing report; fails only under the publication minimum")
    commands.add_parser("tracker", help="read a batch of Bug Tracker pages for the extracted bugs")
    commands.add_parser("build", help="generate the static site from the extracted data")
    commands.add_parser("check", help="fail when the processing report lists something to fix")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "collect":
        from . import collect, kb, report
        client = collect.Client()
        with report.source(args.report, "articles"):
            articles = kb.update_articles(args.articles, client)
        with report.source(args.report, "pages"):
            downloaded = collect.update(args.pages, args.cache, client, articles)
        with report.source(args.report, "notes"):
            collect.update_notes(args.notes, client, articles)
        logging.info("%d pages downloaded", len(downloaded))
    elif args.command == "extract":
        from . import extract
        stops = extract.extract_all(args.cache, args.output, args.changes, args.pages, args.report)
        for reason in stops:
            logging.error("%s", reason)
        sys.exit(1 if stops else 0)
    elif args.command == "check":
        from . import report
        left = report.check(report.load(args.report))
        for line in left:
            print(line)
        sys.exit(1 if left else 0)
    elif args.command == "tracker":
        from . import bugtracker, collect, extract, report
        # Every set of notes: the Bug Tracker covers BIG-IP and F5OS alike.
        notes = {}
        for path in sorted(args.output.glob("*/bugs.json")):
            for bug_id, bug in extract.load_bugs(path).items():
                notes[bug_id] = sorted(set(notes.get(bug_id, [])) | set(bug.get("fixed_versions", [])))
        with report.source(args.report, "bugtracker"):
            left = bugtracker.update(args.tracker, notes, collect.Client(), args.batch or bugtracker.BATCH)
        logging.info("%d Bug Tracker pages left to read", left)
    elif args.command == "build":
        from . import build
        summary = build.build_site(args.output, args.changes, args.articles, args.schedule, args.site, args.dist,
                                   args.base_url, args.tracker, args.notes, args.report)
        logging.info("%s", json.dumps(summary))
