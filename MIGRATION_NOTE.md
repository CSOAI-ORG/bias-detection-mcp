# MCP 2026-07-28 wire migration note

This repository has been moved to the **MCP 2026-07-28 stateless wire** by the
M4 lane of CSOAI Ltd (UK 16939677).

## What changed

* `pyproject.toml` now pins `mcp>=2.0.0` (2.3.0 is the current 2026-07-28 SDK).
* `from mcp.server.fastmcp import FastMCP` renamed to
  `from mcp.server.mcpserver import MCPServer as FastMCP` (the
  `mcp.server.fastmcp` module is removed in 2.x).
* `mcp2026_shim.py` vendored at the repo root for `ShimASGI` /
  `ShimWSGI` front-ends.
* The new wire is **stateless** — no `initialize` / `notifications/initialized`
  handshake, no `Mcp-Session-Id` header.
* Every request carries a mandatory `Mcp-Method` header.
* `tools/call`, `resources/read`, `prompts/get` carry a mandatory
  `Mcp-Name` header.
* `server/discover` is the only discovery path.
* MRTR (`resultType: "input_required"`) passes through untouched.

## Deadline

The old wire dies **2027-07-28** (12-month deprecation clock that opened with
the 2026-07-28 revision).

## Verify

```bash
PYTHONPATH= /opt/homebrew/bin/python3.11 ~/clawd/mcp_wire_audit.py audit --local bias-detection-mcp
```

## Plan

See `MCP_2026_WIRE_MIGRATION_PLAN_2026-10-07.md` in the `clawd` workspace.

---

## Batch-3 verification addendum (M4 wave 2, batch 3 - 2026-10-08)

Appended by the batch-3 lane after the PR above was opened by an earlier lane; the original text is preserved verbatim above. Batch 3 found the runbook incomplete on this branch and added the missing steps (same branch, PR-only, no default-branch push, no force).

### What batch 3 added to this branch

* `server.py` - migration note block + FastMCP->MCPServer import
* `pyproject.toml` - SDK pin + shim packaging include

### Audit rows (`mcp_wire_audit.py`, reconstructed default branch, batch-3 tree)

```bash
PYTHONPATH= /opt/homebrew/bin/python3.11 ~/clawd/mcp_wire_audit.py audit --local bias-detection-mcp
```

| state | era | migration |
|---|---|---|
| before (default branch) | 2026-07 | header-add |
| **after (this branch)** | **2026-07** | **handshake-removal** |
| control (migration-note block removed) | 2026-07 | header-add |

**After-rows are note-text-driven until post-merge re-audit.** The scanner excludes its own shim (`SELF_FILES`) and does not scan `.md`, so `protocol-2026-07-28` / `mcp-method-header` / `mcp-name-header` / `server-discover` in the after record are read from the migration-note text, and `session-id` there is prose (the shim *strips* that header) - the control run, which removes only that note block, drops back to the row above. Runtime evidence for the wire is the `mcp>=2.0.0` SDK pin (2.3.0 speaks 2026-07-28) plus the vendored shim at the ingress; `mcp>=2.0.0` alone is not a wire signal for this scanner.

**After-rows are note-text-driven until post-merge re-audit.** Acceptance target for class
`header-add` is `era: 2026-07`, `migration: none` - re-run the command above after merge.
Plan: `MCP_2026_WIRE_MIGRATION_PLAN_2026-10-07.md` - deadline **2027-07-28** - measurement,
not certification.
