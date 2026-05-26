from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import Clockify

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
def add_time_entry(
    project: str,
    start: str,
    end: str | None = None,
    description: str = "",
    workspace_id: str | None = None,
    billable: bool = False,
) -> dict[str, Any]:
    """Add a time entry to a project.

    `project` may be either a project ID or a name (case-insensitive match).
    `start` and `end` are ISO 8601 UTC timestamps (e.g. "2026-05-26T09:00:00Z").
    Omit `end` to start a running timer.
    """
    return _c().add_time_entry(
        project=project,
        start=start,
        end=end,
        description=description,
        workspace_id=workspace_id,
        billable=billable,
    )


@mcp.tool()
def add_time_entries(
    entries: list[dict[str, Any]],
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Add multiple time entries in one call.

    Each item in `entries` is a dict with the same fields as `add_time_entry`:
    `project` (required), `start` (required, ISO 8601), and optional `end`,
    `description`, `billable`. Per-item `workspace_id` is also accepted; the
    top-level `workspace_id` is the default for items that don't set their own.

    Fail-fast: on the first failure, earlier entries have already been written
    and the error names which item failed. Use `list_time_entries` to inspect
    state before retrying.
    """
    return _c().add_time_entries(entries, workspace_id=workspace_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
