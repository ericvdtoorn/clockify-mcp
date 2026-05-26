from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import Clockify


def _to_iso_window(value: str, end_of_day: bool) -> str:
    """`YYYY-MM-DD` expands to the start or end of that day in UTC. Anything
    that already looks like an ISO timestamp (contains `T`) is passed through."""
    if "T" in value:
        return value
    return f"{value}T23:59:59Z" if end_of_day else f"{value}T00:00:00Z"


def _duration_minutes(start: str | None, end: str | None) -> str:
    if not start or not end:
        return ""
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return str(int((e - s).total_seconds() // 60))


def _entries_to_csv(entries: list[dict[str, Any]], project_names: dict[str, str]) -> str:
    out = StringIO()
    w = csv.writer(out)
    w.writerow(["id", "project", "description", "start", "end", "duration_minutes", "billable"])
    for e in entries:
        ti = e.get("timeInterval") or {}
        start = ti.get("start") or ""
        end = ti.get("end") or ""
        w.writerow([
            e.get("id", ""),
            project_names.get(e.get("projectId") or "", ""),
            e.get("description") or "",
            start,
            end,
            _duration_minutes(start, end),
            "true" if e.get("billable") else "false",
        ])
    return out.getvalue()

mcp = FastMCP("clockify")
_client: Clockify | None = None


def _c() -> Clockify:
    global _client
    if _client is None:
        _client = Clockify()
    return _client


@mcp.tool()
def list_workspaces() -> list[dict[str, Any]]:
    """List all Clockify workspaces the current user belongs to."""
    return [{"id": w["id"], "name": w["name"]} for w in _c().workspaces()]


@mcp.tool()
def list_projects(workspace_id: str | None = None) -> list[dict[str, Any]]:
    """List projects in a workspace. Defaults to the user's active workspace."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "clientName": p.get("clientName"),
            "archived": p.get("archived", False),
        }
        for p in _c().projects(workspace_id=workspace_id, page_size=200)
    ]


@mcp.tool()
def list_time_entries(
    workspace_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """List recent time entries for the current user.

    `start` and `end` are ISO 8601 UTC timestamps (e.g. "2026-05-01T00:00:00Z")
    used to filter the window.
    """
    return _c().time_entries(
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
    )


@mcp.tool()
def get_all_time_entries(start: str, end: str, workspace_id: str | None = None) -> str:
    """Fetch every time entry between `start` and `end` and return CSV.

    `start` and `end` are dates (`YYYY-MM-DD`) or full ISO 8601 timestamps. A
    bare date is expanded to cover the whole day in UTC — `start` becomes
    `00:00:00Z`, `end` becomes `23:59:59Z`. Paginates internally, so it's safe
    on multi-week ranges. Columns: `id, project, description, start, end,
    duration_minutes, billable`. Project names are resolved from the
    workspace's project list. CSV is preferred over paged JSON when you want
    to summarize, aggregate, or compare a window.
    """
    c = _c()
    entries = c.all_time_entries(
        start=_to_iso_window(start, end_of_day=False),
        end=_to_iso_window(end, end_of_day=True),
        workspace_id=workspace_id,
    )
    project_names = {p["id"]: p["name"] for p in c.projects(workspace_id=workspace_id, page_size=200)}
    return _entries_to_csv(entries, project_names)


@mcp.tool()
def add_time_entries(
    entries: list[dict[str, Any]],
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Add one or more time entries.

    Each item in `entries` is a dict with fields:
      - `project` (required): project ID or name (case-insensitive match)
      - `start` (required): ISO 8601 timestamp, e.g. "2026-05-26T09:00:00Z"
      - `end` (optional): ISO 8601 timestamp; omit to start a running timer
      - `description` (optional)
      - `billable` (optional, default false)

    Pass a single-item list for one entry. The top-level `workspace_id` is the
    default for items that don't set their own.

    Fail-fast: on the first failure, earlier entries have already been written
    and the error names which item failed. Use `list_time_entries` to inspect
    state before retrying.
    """
    return _c().add_time_entries(entries, workspace_id=workspace_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
