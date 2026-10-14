"""
Access-controlled MCP server — the root-cause fix for the `scoped_mcp` defense.

Differences from the vulnerable mcp_server.py:
  * Caller identity (CALLER_TEAM_ID / CALLER_USER_ID) is read from the environment,
    set by the backend when it spawns this subprocess. The MODEL cannot influence it.
  * create_task: team_id and created_by are FORCED to the caller's — any model-supplied
    team_id is ignored. assigned_to must belong to the caller's team.
  * get_user_info / list_users: constrained to the caller's team only.
  * list_teams is removed entirely (no cross-tenant enumeration).

This neutralizes the read-any -> write-any cross-tenant primitive that indirect prompt
injection abuses in the baseline, without trusting the model at all.

Never print to stdout — it is the JSON-RPC channel. All logging goes to a file.
"""
import asyncio
import json
import logging
import os

import psycopg2
from mcp_compat import build_server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database_service import DatabaseService

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@db:5432/tasksai"


def _caller_team_id():
    v = os.getenv("CALLER_TEAM_ID", "").strip()
    return int(v) if v.isdigit() else None


def _caller_user_id():
    v = os.getenv("CALLER_USER_ID", "").strip()
    return int(v) if v.isdigit() else None


_logger = None
_db_conn = None


def get_logger():
    global _logger
    if _logger is None:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.FileHandler(os.path.join(log_dir, "mcp_scoped.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        _logger = logging.getLogger("MCP_Scoped")
        _logger.setLevel(logging.INFO)
        _logger.handlers.clear()
        _logger.addHandler(handler)
        _logger.info(f"Scoped MCP server init; caller team={_caller_team_id()} user={_caller_user_id()}")
    return _logger


def get_db_connection():
    global _db_conn
    if _db_conn is not None and getattr(_db_conn, "closed", 0) == 0:
        return _db_conn
    _db_conn = psycopg2.connect(DATABASE_URL)
    return _db_conn




async def list_tools() -> list[Tool]:
    # Note: no team_id parameters exposed to the model, and no list_teams tool.
    return [
        Tool(
            name="get_user_info",
            description="Get user_id and team_id for an email address in YOUR team.",
            inputSchema={
                "type": "object",
                "properties": {"email": {"type": "string", "description": "Email of a user in your team"}},
                "required": ["email"],
            },
        ),
        Tool(
            name="create_task",
            description="Create a task in YOUR team. team_id and created_by are set automatically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "assigned_to": {"type": "integer", "description": "user_id in your team (optional)"},
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="list_users",
            description="List users in YOUR team.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger = get_logger()
    team_id = _caller_team_id()
    user_id = _caller_user_id()
    logger.info(f"TOOL {name} args={json.dumps(arguments)} (scoped to team={team_id})")

    def err(msg):
        return [TextContent(type="text", text=json.dumps({"error": msg}))]

    if team_id is None:
        return err("No caller team context; refusing.")

    try:
        conn = get_db_connection()
        db = DatabaseService(db_connection=conn)

        if name == "get_user_info":
            email = arguments.get("email")
            if not email:
                return err("Email is required")
            user = db.get_user_by_email(email)
            # Scope: only reveal users in the caller's own team.
            if not user or user.get("team_id") != team_id:
                return err("User not found in your team")
            return [TextContent(type="text", text=json.dumps(user, default=str))]

        if name == "create_task":
            title = arguments.get("title")
            if not title:
                return err("title is required")
            assigned_to = arguments.get("assigned_to")
            if assigned_to is not None:
                assignee = db.get_user_by_id(assigned_to)
                if not assignee or assignee.get("team_id") != team_id:
                    return err("assigned_to must be a user in your team")
            # Forced server-side — model input for team_id/created_by is ignored.
            task = db.create_task(
                team_id=team_id,
                title=title,
                description=arguments.get("description", ""),
                created_by=user_id,
                assigned_to=assigned_to,
                status="pending",
            )
            return [TextContent(type="text", text=json.dumps(task, default=str))]

        if name == "list_users":
            users = db.get_users_by_team(team_id)
            return [TextContent(type="text", text=json.dumps(users, default=str))]

        return err(f"Unknown or disallowed tool: {name}")

    except Exception as e:
        logger.error(f"TOOL {name} EXCEPTION: {e}")
        try:
            DatabaseService(db_connection=get_db_connection()).rollback()
        except Exception:
            pass
        return err(str(e))


mcp_server = build_server("postgres-tasks-server-scoped", list_tools, call_tool)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
