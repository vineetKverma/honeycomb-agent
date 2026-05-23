"""Non-interactive test: the Honeycomb agent answering graph queries via the
MongoDB MCP server.

Auto-runs two scripted queries that should route through MCP tools:
  1. "How many concepts ...?"  -> expect a `count` call (not a find/list).
  2. "Show me 3 concepts about philosophy" -> expect a `find` (filter + limit).

Prints the agent's response and the tool calls it made for each, then exits.
ASCII-only output for Windows PowerShell (cp1252).
"""
import asyncio
import os
import sys
from pathlib import Path

# Allow running as `python scripts/test_agent_with_mcp.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

# Force the AI Studio backend (API key). USE_VERTEXAI=false guards against an
# ambient Vertex env var routing us back to Vertex.
os.environ.setdefault("GOOGLE_API_KEY", config.GEMINI_API_KEY)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.agent import honeycomb_agent, mongo_mcp_toolset

APP_NAME = "honeycomb"
USER_ID = "mcp-test"

QUERIES = [
    "How many concepts do I have in my knowledge graph?",
    "Show me 3 concepts about philosophy.",
]


def _ascii(text: str) -> str:
    return (text or "").encode("ascii", "replace").decode("ascii")


async def _ask(runner, session_id: str, prompt: str) -> None:
    print(f"\nyou> {prompt}")
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        for call in event.get_function_calls():
            print(f"  [tool call] {_ascii(call.name)}({_ascii(str(dict(call.args or {})))})")
        for resp in event.get_function_responses():
            print(f"  [tool done] {_ascii(resp.name)}")
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text for p in event.content.parts if p.text)
            if text:
                print(f"honeycomb> {_ascii(text)}")


async def _run() -> None:
    runner = InMemoryRunner(agent=honeycomb_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    try:
        for prompt in QUERIES:
            await _ask(runner, session.id, prompt)
    finally:
        await mongo_mcp_toolset.close()


def main() -> int:
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[error] {type(e).__name__}: {_ascii(str(e))}")
        return 1
    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
