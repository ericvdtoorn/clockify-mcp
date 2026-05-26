# clockify-mcp

A small [Clockify](https://clockify.me) Python SDK, CLI, and [MCP](https://modelcontextprotocol.io) server for reading and adding time entries.

- `Clockify` — a minimal Python client (workspaces, projects, time entries).
- `clockify` — a CLI to list projects, list recent entries, and add an entry.
- `clockify-mcp` — an MCP server exposing the same operations as tools.

## Install

Requires Python 3.10+.

From a local checkout with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/ericvdtoorn/clockify-mcp.git
cd clockify-mcp
uv sync
```

Or with pip:

```bash
pip install git+https://github.com/ericvdtoorn/clockify-mcp.git
```

## Configuration

Set your Clockify API key (find it under *Profile settings → API* in Clockify):

```bash
export CLOCKIFY_API_KEY=...
```

All commands operate on your *active workspace* by default.

## CLI

```bash
# List projects in the active workspace
clockify projects

# List the 20 most recent time entries
clockify entries --limit 20

# Add a completed entry (project name is case-insensitive)
clockify add "Acme Website" 09:00 10:30 "Refactor checkout"

# Start a running timer (omit end)
clockify add "Acme Website" 14:00 "Pairing session"

# Mark billable
clockify add "Acme Website" 09:00 10:30 "Client call" --billable

# Update an entry (only fields you pass change; IDs come from `clockify entries`)
clockify update 65f1abc...  --end 11:00 --description "Refactor + tests"
clockify update 65f1abc...  --project "Acme Internal" --no-billable

# Delete an entry
clockify delete 65f1abc...
```

Times accept `HH:MM`, `HH:MM:SS`, or ISO 8601 (`2026-05-26T09:00`, `2026-05-26T09:00:00Z`). Naive values are interpreted as local time.

## MCP server

Run the server over stdio:

```bash
clockify-mcp
```

Example Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clockify": {
      "command": "clockify-mcp",
      "env": { "CLOCKIFY_API_KEY": "..." }
    }
  }
}
```

Exposed tools:

- `list_workspaces()`
- `list_projects(workspace_id?)`
- `list_time_entries(workspace_id?, page?, page_size?, start?, end?)`
- `get_all_time_entries(start, end, workspace_id?)` — every entry in the window, returned as CSV (`id, project, description, start, end, duration_minutes, billable`). `start` and `end` may be dates (`YYYY-MM-DD`) or full ISO 8601 timestamps. Paginates internally.
- `add_time_entries(entries, workspace_id?)` — `entries` is a list; pass a single-item list for one entry. Each item takes `project`, `start`, optional `end`, `description`, `billable`.

`project` may be a project ID or a name (case-insensitive). `start` and `end` are ISO 8601 timestamps (e.g. `2026-05-26T09:00:00Z`). Omit `end` to start a running timer.

### Deliberately not exposed via MCP

The CLI supports `clockify update` and `clockify delete`, but the MCP server does **not**. Editing or deleting prior time entries is destructive and easy for a model to get wrong (wrong ID, wrong day, hallucinated correction). Keeping those operations off the MCP surface means the worst an AI agent can do is add an entry you'll notice and fix — never silently rewrite or wipe history. Run destructive changes yourself from the CLI.

## Library

```python
from datetime import datetime
from clockify_mcp import Clockify

with Clockify() as c:
    for p in c.projects():
        print(p["id"], p["name"])

    c.add_time_entry(
        project="Acme Website",
        start=datetime(2026, 5, 26, 9, 0).astimezone(),
        end=datetime(2026, 5, 26, 10, 30).astimezone(),
        description="Refactor checkout",
    )
```

## Releases

Tag-driven. Push a `v*` tag and GitHub Actions builds `clockify.mcpb` (+ a `.zip` copy) and attaches both to a release:

```bash
git tag v0.1.0
git push --tags
```

The bundle uses [MCPB](https://github.com/modelcontextprotocol/mcpb) manifest 0.4 with `server.type: "uv"`. It ships source only — no vendored wheels or platform-specific binaries. Claude Desktop's bundled `uv` resolves dependencies (and downloads a matching Python via `python-build-standalone`) on first launch, so the same `.mcpb` works on macOS, Linux, and Windows for any supported CPython.

## License

[MIT](LICENSE)
