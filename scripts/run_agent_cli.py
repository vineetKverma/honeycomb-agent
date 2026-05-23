"""Local REPL for chatting with the Honeycomb ADK agent.

Uses ADK's InMemoryRunner (stateless, in-memory session/artifact services) for
quick local testing -- no database-backed session store. Type 'exit' or press
Ctrl+C to quit. ASCII-only output for Windows PowerShell (cp1252).
"""
import asyncio
import os
import sys
from pathlib import Path

# Allow running as `python scripts/run_agent_cli.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

# ADK authenticates the Gemini backend from env vars. Use the AI Studio API key
# from .env, and force USE_VERTEXAI=false so an ambient Vertex env var cannot
# route us back to Vertex (which caused the billing wall).
os.environ.setdefault("GOOGLE_API_KEY", config.GEMINI_API_KEY)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"

from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.agent import honeycomb_agent, mongo_mcp_toolset

APP_NAME = "honeycomb"
USER_ID = "local-user"


def _ascii(text: str) -> str:
    return (text or "").encode("ascii", "replace").decode("ascii")


def _print_events_text(event) -> None:
    """Surface tool activity and final text from one ADK event."""
    for call in event.get_function_calls():
        print(f"  [tool call] {_ascii(call.name)}({_ascii(str(dict(call.args or {})))})")
    for resp in event.get_function_responses():
        print(f"  [tool done] {_ascii(resp.name)}")
    if event.is_final_response() and event.content and event.content.parts:
        text = "".join(p.text for p in event.content.parts if p.text)
        if text:
            print(f"honeycomb> {_ascii(text)}")


async def _chat() -> None:
    runner = InMemoryRunner(agent=honeycomb_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)

    print("Honeycomb agent ready. Type 'exit' to quit.")
    print("Try: Ingest https://www.youtube.com/watch?v=aircAruvnKk")
    print("-" * 60)

    try:
        while True:
            try:
                user_input = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[bye]")
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("[bye]")
                break

            message = types.Content(role="user", parts=[types.Part(text=user_input)])
            try:
                async for event in runner.run_async(
                    user_id=USER_ID, session_id=session.id, new_message=message
                ):
                    _print_events_text(event)
            except Exception as e:
                print(f"[error] {type(e).__name__}: {_ascii(str(e))}")
    finally:
        # MCPToolset owns a subprocess + stdio session that must be closed.
        await mongo_mcp_toolset.close()


def main() -> int:
    try:
        asyncio.run(_chat())
    except KeyboardInterrupt:
        print("\n[bye]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
