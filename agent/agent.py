"""Honeycomb ADK agent entry point.

Tool strategy (Phase A3):
  - Direct Python tools for the write path (ingest pipeline) and quizzing --
    these are performance-critical and not worth a round trip through MCP.
  - MongoDB MCP server (read-only) for agent-facing queries -- this is the
    hackathon's required partner integration, demonstrably in the call path.
"""
import sys

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters, get_default_environment

from config import MONGODB_URI

from .system_prompt import SYSTEM_PROMPT
from .tools import (
    daily_review,
    grade_my_answer,
    ingest_learning_source,
    quiz_concept,
    record_quiz_attempt,
)

# The MongoDB MCP server is a `.cmd` shim on Windows and cannot be exec'd
# directly (ENOENT). Route through `cmd /c` on Windows -- the same approach
# proven by scripts/test_mongo_mcp.py. POSIX execs the binary directly.
if sys.platform == "win32":
    _MONGO_COMMAND, _MONGO_ARGS = "cmd", ["/c", "mongodb-mcp-server", "--readOnly"]
else:
    _MONGO_COMMAND, _MONGO_ARGS = "mongodb-mcp-server", ["--readOnly"]

# StdioServerParameters.env REPLACES the child environment when set, so passing
# only the connection string would strip PATH/SYSTEMROOT and the server would
# fail to launch. Start from the SDK's safe default env and inject the string.
_mongo_env = get_default_environment()
_mongo_env["MDB_MCP_CONNECTION_STRING"] = MONGODB_URI

mongo_mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=_MONGO_COMMAND,
            args=_MONGO_ARGS,
            env=_mongo_env,
        )
    ),
    # Read-only query tools only; writes happen via the direct Python pipeline.
    tool_filter=["find", "aggregate", "count", "list-collections"],
)

honeycomb_agent = Agent(
    name="honeycomb",
    model="gemini-2.5-flash",
    description="A learning agent that builds and maintains your personal knowledge graph from your sources.",
    instruction=SYSTEM_PROMPT,
    tools=[
        ingest_learning_source,
        quiz_concept,
        grade_my_answer,
        record_quiz_attempt,
        daily_review,
        mongo_mcp_toolset,  # MCP-mediated MongoDB read tools
    ],
)

# ADK CLI tools (`adk run`, `adk web`) auto-discover a module-level `root_agent`.
root_agent = honeycomb_agent
