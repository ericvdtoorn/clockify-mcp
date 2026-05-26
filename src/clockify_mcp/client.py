from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.clockify.me/api/v1"


class ClockifyError(RuntimeError):
    pass


def _iso(value: datetime | str) -> str:
    """Normalize to Clockify's UTC ISO format. Naive values are interpreted as
    local time; values with `Z` or an offset are honored as-is."""
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value  # date-only or other; let the caller handle
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _looks_like_id(s: str) -> bool:
    return len(s) == 24 and all(c in "0123456789abcdef" for c in s.lower())


class Clockify:
    def __init__(self, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL):
        key = api_key or os.environ.get("CLOCKIFY_API_KEY")
        if not key:
            raise ClockifyError("CLOCKIFY_API_KEY is not set")
        self._http = httpx.Client(
            base_url=base_url,
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
            timeout=30.0,
        )
        self._user: dict[str, Any] | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Clockify":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        r = self._http.request(method, path, **kw)
        if r.status_code >= 400:
            raise ClockifyError(f"{r.status_code} {method} {path}: {r.text}")
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    def user(self) -> dict[str, Any]:
        if self._user is None:
            self._user = self._request("GET", "/user")
        return self._user

    @property
    def default_workspace_id(self) -> str:
        return self.user()["activeWorkspace"]

    @property
    def user_id(self) -> str:
        return self.user()["id"]

    def workspaces(self) -> list[dict[str, Any]]:
        return self._request("GET", "/workspaces") or []

    def projects(
        self,
        workspace_id: str | None = None,
        name: str | None = None,
        page: int = 1,
        page_size: int = 50,
        archived: bool | None = False,
    ) -> list[dict[str, Any]]:
        ws = workspace_id or self.default_workspace_id
        params: dict[str, Any] = {"page": page, "page-size": page_size}
        if name:
            params["name"] = name
        if archived is not None:
            params["archived"] = "true" if archived else "false"
        return self._request("GET", f"/workspaces/{ws}/projects", params=params) or []

    def find_project(self, name_or_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        ws = workspace_id or self.default_workspace_id
        if _looks_like_id(name_or_id):
            return self._request("GET", f"/workspaces/{ws}/projects/{name_or_id}")
        matches = self.projects(workspace_id=ws, name=name_or_id, page_size=50)
        target = name_or_id.lower()
        exact = [p for p in matches if p["name"].lower() == target]
        if exact:
            return exact[0]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ClockifyError(f"No project matches {name_or_id!r}")
        names = ", ".join(p["name"] for p in matches[:5])
        raise ClockifyError(f"Multiple projects match {name_or_id!r}: {names}")

    def time_entries(
        self,
        workspace_id: str | None = None,
        user_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        ws = workspace_id or self.default_workspace_id
        uid = user_id or self.user_id
        params: dict[str, Any] = {"page": page, "page-size": page_size}
        if start is not None:
            params["start"] = _iso(start)
        if end is not None:
            params["end"] = _iso(end)
        return self._request("GET", f"/workspaces/{ws}/user/{uid}/time-entries", params=params) or []

    def add_time_entry(
        self,
        project: str,
        start: datetime | str,
        end: datetime | str | None = None,
        description: str = "",
        workspace_id: str | None = None,
        billable: bool = False,
        task_id: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        ws = workspace_id or self.default_workspace_id
        proj = self.find_project(project, workspace_id=ws)
        body: dict[str, Any] = {
            "start": _iso(start),
            "projectId": proj["id"],
            "description": description,
            "billable": billable,
        }
        if end is not None:
            body["end"] = _iso(end)
        if task_id:
            body["taskId"] = task_id
        if tag_ids:
            body["tagIds"] = tag_ids
        return self._request("POST", f"/workspaces/{ws}/time-entries", json=body)

    def all_time_entries(
        self,
        start: datetime | str,
        end: datetime | str,
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ws = workspace_id or self.default_workspace_id
        uid = user_id or self.user_id
        out: list[dict[str, Any]] = []
        page = 1
        page_size = 200
        while True:
            chunk = self.time_entries(
                workspace_id=ws,
                user_id=uid,
                page=page,
                page_size=page_size,
                start=start,
                end=end,
            )
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < page_size:
                break
            page += 1
        return out

    def add_time_entries(
        self,
        items: list[dict[str, Any]],
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Fail-fast: on the first error, previously-created entries remain on the server.
        return [self.add_time_entry(workspace_id=workspace_id, **item) for item in items]

    def get_time_entry(self, entry_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        ws = workspace_id or self.default_workspace_id
        return self._request("GET", f"/workspaces/{ws}/time-entries/{entry_id}")

    def update_time_entry(
        self,
        entry_id: str,
        project: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        description: str | None = None,
        billable: bool | None = None,
        workspace_id: str | None = None,
        task_id: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        # Clockify's PUT replaces the entry, so we fetch first and merge.
        ws = workspace_id or self.default_workspace_id
        existing = self.get_time_entry(entry_id, workspace_id=ws)
        interval = existing.get("timeInterval") or {}
        body: dict[str, Any] = {
            "start": _iso(start) if start is not None else interval.get("start"),
            "projectId": (
                self.find_project(project, workspace_id=ws)["id"] if project else existing.get("projectId")
            ),
            "description": description if description is not None else (existing.get("description") or ""),
            "billable": billable if billable is not None else bool(existing.get("billable")),
        }
        new_end = _iso(end) if end is not None else interval.get("end")
        if new_end is not None:
            body["end"] = new_end
        new_task = task_id if task_id is not None else existing.get("taskId")
        if new_task:
            body["taskId"] = new_task
        new_tags = tag_ids if tag_ids is not None else existing.get("tagIds")
        if new_tags:
            body["tagIds"] = new_tags
        return self._request("PUT", f"/workspaces/{ws}/time-entries/{entry_id}", json=body)

    def delete_time_entry(self, entry_id: str, workspace_id: str | None = None) -> None:
        ws = workspace_id or self.default_workspace_id
        self._request("DELETE", f"/workspaces/{ws}/time-entries/{entry_id}")
