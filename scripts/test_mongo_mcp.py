"""Smoke test for the MongoDB MCP server over stdio.

Spawns the globally-installed `mongodb-mcp-server` binary as a subprocess,
performs the MCP initialize handshake, lists the tools, calls a read-only
tool (list-collections), and finally calls `find` to prove a full
MCP -> Atlas -> data round trip.

Uses the official `mcp` Python SDK (anyio-based). The stdio_client /
ClientSession context managers own the subprocess lifecycle and JSON-RPC
framing (newline-delimited JSON, NOT LSP Content-Length headers), and tear
the subprocess down on exit -- including on error or timeout.

The server's stderr is captured to a temp file and printed at the end on any
failure, so a hang shows WHY it failed instead of a bare "timeout".

ASCII-only output for Windows PowerShell (cp1252).
"""
import json
import re
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

# Allow running as `python scripts/test_mongo_mcp.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anyio

import config
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment

TIMEOUT_SECONDS = 60


def _ascii(text: str) -> str:
    """Make external server text safe for cp1252 stdout."""
    return (text or "").encode("ascii", "replace").decode("ascii")


def _server_command() -> tuple[str, list[str]]:
    """Build the spawn command for the global mongodb-mcp-server binary.

    StdioServerParameters has no `shell=True` option, so on Windows -- where
    the binary is `mongodb-mcp-server.cmd` and a bare exec raises ENOENT -- we
    route through `cmd /c`, which is exactly what shell=True does under the
    hood. On POSIX we exec the binary directly.
    """
    if sys.platform == "win32":
        return "cmd", ["/c", "mongodb-mcp-server"]
    return "mongodb-mcp-server", []


def _render_result(result) -> str:
    """Flatten an MCP CallToolResult's content blocks into ASCII text."""
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(_ascii(text) if text is not None else _ascii(str(block)))
    return " ".join(parts).strip() or "(empty result)"


def _extract_first_name(text: str) -> str | None:
    """Best-effort pull of a concept 'name' out of the find tool's output."""
    try:
        data = json.loads(text)
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict) and "name" in data:
            return _ascii(str(data["name"]))
    except (ValueError, TypeError):
        pass
    m = re.search(r'"name"\s*:\s*"([^"]*)"', text)
    return _ascii(m.group(1)) if m else None


async def _run(errlog) -> int:
    command, args = _server_command()

    # Start from the SDK's safe default env (PATH, SYSTEMROOT, APPDATA, etc.)
    # and inject the connection string.
    env = get_default_environment()
    env["MDB_MCP_CONNECTION_STRING"] = config.MONGODB_URI

    server_params = StdioServerParameters(command=command, args=args, env=env)

    print(f"[mcp] Spawning: {command} {' '.join(args)}".rstrip())
    with anyio.fail_after(TIMEOUT_SECONDS):
        # errlog captures the server's stderr to a real file (needs a fileno()).
        async with stdio_client(server_params, errlog=errlog) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=TIMEOUT_SECONDS)
            ) as session:
                print("[mcp] Sending initialize handshake...")
                init = await session.initialize()  # also sends notifications/initialized
                info = init.serverInfo
                print(f"[mcp] Connected -> {_ascii(info.name)} v{_ascii(info.version)}")

                print("[mcp] Requesting tools/list...")
                tools = (await session.list_tools()).tools
                tool_names = {t.name for t in tools}
                print(f"[mcp] {len(tools)} tool(s) available:")
                for tool in tools:
                    desc = _ascii(tool.description or "").replace("\n", " ").strip()
                    if len(desc) > 70:
                        desc = desc[:67] + "..."
                    print(f"  - {_ascii(tool.name):<22} {desc}")

                # Connectivity proof: list collections in the configured DB.
                if "list-collections" in tool_names:
                    print("[mcp] Calling list-collections...")
                    result = await session.call_tool(
                        "list-collections", {"database": config.MONGODB_DB}
                    )
                    print(f"[mcp] list-collections({config.MONGODB_DB}) -> {_render_result(result)}")
                elif "list-databases" in tool_names:
                    print("[mcp] Calling list-databases...")
                    result = await session.call_tool("list-databases", {})
                    print(f"[mcp] list-databases -> {_render_result(result)}")
                else:
                    print("[mcp] WARN: no list-collections/list-databases tool found.")

                # Round-trip proof: read one concept document back through MCP.
                if "find" in tool_names:
                    print("[mcp] Calling find (1 doc) to prove MCP -> Atlas data round trip...")
                    result = await session.call_tool(
                        "find",
                        {
                            "database": config.MONGODB_DB,
                            "collection": config.MONGODB_COLLECTION,
                            "filter": {},
                            "limit": 1,
                            "projection": {"name": 1, "_id": 0},
                        },
                    )
                    rendered = _render_result(result)
                    name = _extract_first_name(rendered)
                    if name:
                        print(f"[mcp] find -> first concept name: {name}")
                    else:
                        print(f"[mcp] find -> {rendered[:200]}")
                else:
                    print("[mcp] WARN: no 'find' tool found; skipped round-trip proof.")

    print("[mcp] OK: smoke test complete, subprocess terminated cleanly.")
    return 0


def _dump_stderr(errlog) -> None:
    try:
        errlog.seek(0)
        captured = errlog.read()
    except (OSError, ValueError):
        captured = ""
    print("[mcp] ----- captured server stderr -----")
    print(_ascii(captured).rstrip() or "(server wrote nothing to stderr)")
    print("[mcp] -----------------------------------")


def main() -> int:
    errlog = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    failed = False
    try:
        return anyio.run(_run, errlog)
    except TimeoutError:
        failed = True
        print(f"[mcp] FAIL: timed out after {TIMEOUT_SECONDS}s.")
        print("[mcp] Likely a wrong MONGODB_URI, or your IP is not on the Atlas allowlist.")
        return 1
    except FileNotFoundError:
        failed = True
        print("[mcp] FAIL: command not found (ENOENT). Is mongodb-mcp-server installed globally and on PATH?")
        return 1
    except Exception as e:
        failed = True
        print(f"[mcp] FAIL: {type(e).__name__}: {_ascii(str(e))}")
        return 1
    finally:
        if failed:
            _dump_stderr(errlog)
        errlog.close()


if __name__ == "__main__":
    sys.exit(main())
