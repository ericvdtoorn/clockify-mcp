from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import Any

from .client import Clockify, ClockifyError


def _parse_time(s: str) -> datetime:
    """HH:MM, HH:MM:SS, ISO local, or ISO with Z/offset. Naive values are local."""
    s = s.strip()
    if len(s) in (5, 8) and s[2] == ":":
        fmt = "%H:%M" if len(s) == 5 else "%H:%M:%S"
        t = datetime.strptime(s, fmt).time()
        return datetime.combine(date.today(), t).astimezone()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClockifyError(f"could not parse time {s!r}: {exc}") from exc
    return dt if dt.tzinfo else dt.astimezone()


def _fmt_dt(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return s


def _cmd_projects(c: Clockify, _: argparse.Namespace) -> int:
    for p in c.projects(page_size=200):
        client = p.get("clientName") or ""
        archived = " (archived)" if p.get("archived") else ""
        print(f"{p['id']}  {p['name']}{archived}  {client}".rstrip())
    return 0


def _cmd_entries(c: Clockify, args: argparse.Namespace) -> int:
    entries = c.time_entries(page_size=args.limit)
    names = {p["id"]: p["name"] for p in c.projects(page_size=200)}
    for e in entries:
        ti = e.get("timeInterval") or {}
        start = _fmt_dt(ti.get("start"))
        end = _fmt_dt(ti.get("end"))
        pname = names.get(e.get("projectId") or "", "—")
        desc = e.get("description") or ""
        print(f"{e['id']}  {start} → {end}  [{pname}]  {desc}".rstrip())
    return 0


def _cmd_add(c: Clockify, args: argparse.Namespace) -> int:
    start = _parse_time(args.start)
    end = _parse_time(args.end) if args.end else None
    entry: dict[str, Any] = c.add_time_entry(
        project=args.project,
        start=start,
        end=end,
        description=args.description,
        billable=args.billable,
    )
    print(f"added {entry['id']}  {_fmt_dt(entry.get('timeInterval', {}).get('start'))} → "
          f"{_fmt_dt(entry.get('timeInterval', {}).get('end'))}  [{args.project}]")
    return 0


def _cmd_update(c: Clockify, args: argparse.Namespace) -> int:
    kwargs: dict[str, Any] = {}
    if args.start is not None:
        kwargs["start"] = _parse_time(args.start)
    if args.end is not None:
        kwargs["end"] = _parse_time(args.end)
    if args.project is not None:
        kwargs["project"] = args.project
    if args.description is not None:
        kwargs["description"] = args.description
    if args.billable is not None:
        kwargs["billable"] = args.billable
    entry = c.update_time_entry(args.entry_id, **kwargs)
    ti = entry.get("timeInterval") or {}
    print(f"updated {entry['id']}  {_fmt_dt(ti.get('start'))} → {_fmt_dt(ti.get('end'))}")
    return 0


def _cmd_delete(c: Clockify, args: argparse.Namespace) -> int:
    c.delete_time_entry(args.entry_id)
    print(f"deleted {args.entry_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clockify", description="Tiny Clockify CLI.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("projects", help="List projects in the active workspace.")

    e = sub.add_parser("entries", help="List recent time entries.")
    e.add_argument("--limit", type=int, default=20)

    a = sub.add_parser("add", help="Add a time entry to a project.")
    a.add_argument("project", help="Project name (case-insensitive) or ID.")
    a.add_argument("start", help='Start, e.g. "09:00" or "2026-05-26T09:00".')
    a.add_argument("end", nargs="?", help="End time. Omit to start a running timer.")
    a.add_argument("description", nargs="?", default="")
    a.add_argument("--billable", action="store_true")

    u = sub.add_parser("update", help="Update a time entry. Only fields you pass change.")
    u.add_argument("entry_id")
    u.add_argument("--start")
    u.add_argument("--end")
    u.add_argument("--project", help="Project name or ID.")
    u.add_argument("--description")
    billable = u.add_mutually_exclusive_group()
    billable.add_argument("--billable", dest="billable", action="store_true", default=None)
    billable.add_argument("--no-billable", dest="billable", action="store_false")

    d = sub.add_parser("delete", help="Delete a time entry.")
    d.add_argument("entry_id")

    args = p.parse_args(argv)
    handlers = {
        "projects": _cmd_projects,
        "entries": _cmd_entries,
        "add": _cmd_add,
        "update": _cmd_update,
        "delete": _cmd_delete,
    }
    try:
        with Clockify() as c:
            return handlers[args.cmd](c, args)
    except ClockifyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
