"""
MCP server implementation for PostgreSQL operations using MCP SDK.
This server exposes tools that are vulnerable to indirect prompt injection.
"""
import asyncio
import json
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from mcp_compat import build_server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from database_service import DatabaseService

# Load config - ensure it works in subprocess context
# Prioritize environment variable (which is set in Docker) over config file
# This ensures subprocess gets the correct DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Fallback to config import if environment variable is not set
    try:
        from config import Config
        DATABASE_URL = Config.DATABASE_URL
    except:
        # Final fallback - default for Docker environment
        DATABASE_URL = 'postgresql://postgres:postgres@db:5432/tasksai'

# Log the DATABASE_URL being used (mask password for security)
# This will be logged when logger is initialized
def _get_masked_db_url(url):
    """Mask password in database URL for logging"""
    if '@' in url:
        try:
            # Format: postgresql://user:pass@host -> postgresql://user:***@host
            parts = url.split('@')
            if '://' in parts[0]:
                protocol_user_pass = parts[0]
                protocol = protocol_user_pass.split('://')[0]
                user_pass = protocol_user_pass.split('://')[1]
                if ':' in user_pass:
                    user = user_pass.split(':')[0]
                    return f"{protocol}://{user}:***@{parts[1]}"
        except:
            pass
    return url

# Global database connection
_db_conn = None
_logger = None

def get_logger():
    """Get or create logger that writes to the same log file as AI agent"""
    global _logger
    if _logger is None:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(backend_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "ai_agent.log")
        
        # Configure logger
        _logger = logging.getLogger("MCP_Server")
        _logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        if _logger.handlers:
            _logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        _logger.addHandler(file_handler)
        
        # Log DATABASE_URL on initialization (masked for security)
        masked_url = _get_masked_db_url(DATABASE_URL)
        _logger.info(f"MCP Server initialized - Using DATABASE_URL: {masked_url}")
        _logger.info(f"Environment DATABASE_URL set: {os.getenv('DATABASE_URL') is not None}")
    
    return _logger

def get_db_connection():
    """Get or create database connection"""
    global _db_conn
    logger = get_logger()
    
    # Check if connection exists and is valid
    if _db_conn is not None:
        try:
            # Test if connection is still alive
            if hasattr(_db_conn, 'closed'):
                if _db_conn.closed != 0:  # psycopg2 uses 0 for open, non-zero for closed
                    logger.info("Database connection is closed, creating new connection")
                    _db_conn = None
                else:
                    # Try a simple query to verify connection
                    with _db_conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    return _db_conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
            logger.warning(f"Database connection is stale or invalid: {str(e)}, creating new connection")
            _db_conn = None
    
    # Create new connection
    try:
        logger.info(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else '***'}")
        _db_conn = psycopg2.connect(DATABASE_URL)
        logger.info("Database connection established successfully")
        return _db_conn
    except psycopg2.OperationalError as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to database: {str(e)}")
        raise

# Create MCP server instance

async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    logger = get_logger()
    logger.info("MCP list_tools() called - listing available tools")
    
    tools = [
        Tool(
            name="get_user_info",
            description="Get user_id and team_id from email address",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Email address of the user"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="create_task",
            description="Create a new task. Requires a valid team_id and optionally an assigned_to user_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "integer",
                        "description": "Team ID for the task (required)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "assigned_to": {
                        "type": "integer",
                        "description": "User ID to assign the task to (optional)"
                    },
                    "created_by": {
                        "type": "integer",
                        "description": "User ID who created the task"
                    }
                },
                "required": ["team_id", "title", "created_by"]
            }
        ),
        Tool(
            name="list_users",
            description="List users in a specific team",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "integer",
                        "description": "Team ID to list users from"
                    }
                },
                "required": ["team_id"]
            }
        ),
        Tool(
            name="list_teams",
            description="List all teams",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]
    
    tool_names = [tool.name for tool in tools]
    logger.info(f"MCP list_tools() returned {len(tools)} tools: {', '.join(tool_names)}")
    return tools

async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the agent"""
    logger = get_logger()
    logger.info("=" * 80)
    logger.info(f"MCP TOOL CALLED: {name}")
    logger.info(f"Tool Arguments: {json.dumps(arguments, indent=2)}")
    logger.info("=" * 80)
    
    try:
        # Get database connection - this can raise exceptions if connection fails
        conn = get_db_connection()
        if name == "get_user_info":
            email = arguments.get("email")
            if not email:
                error_msg = "Email is required"
                logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            
            logger.info(f"MCP Tool {name} - Executing with email={email}")
            db_service = DatabaseService(db_connection=conn)
            user = db_service.get_user_by_email(email)
            
            if user:
                logger.info(f"MCP Tool {name} - SUCCESS: User found")
                logger.info(f"MCP Tool {name} - Output: {json.dumps(user, indent=2, default=str)}")
                response = [TextContent(type="text", text=json.dumps(user, default=str))]
                return response
            else:
                error_msg = "User not found"
                logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
        
        elif name == "create_task":
            team_id = arguments.get("team_id")
            title = arguments.get("title")
            description = arguments.get("description", "")
            created_by = arguments.get("created_by")
            assigned_to = arguments.get("assigned_to")
            
            logger.info(f"MCP Tool {name} - Executing")
            logger.info(f"MCP Tool {name} - Parameters: team_id={team_id}, title={title}, created_by={created_by}, assigned_to={assigned_to}")
            
            db_service = DatabaseService(db_connection=conn)
            
            # Validate team_id exists
            team = db_service.get_team_by_id(team_id)
            if not team:
                error_msg = "Invalid team_id"
                logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            
            # If assigned_to is provided, validate it exists and belongs to the team
            if assigned_to is not None:
                user = db_service.get_user_by_id(assigned_to)
                if not user:
                    error_msg = "Invalid assigned_to user_id"
                    logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                    return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
                if user.get('team_id') != team_id:
                    error_msg = "User does not belong to the specified team"
                    logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                    return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            
            task = db_service.create_task(
                team_id=team_id,
                title=title,
                description=description,
                created_by=created_by,
                assigned_to=assigned_to,
                status='pending'
            )
            
            logger.info(f"MCP Tool {name} - SUCCESS: Task created")
            logger.info(f"MCP Tool {name} - Output: {json.dumps(task, indent=2, default=str)}")
            response = [TextContent(type="text", text=json.dumps(task, default=str))]
            return response
        
        elif name == "list_users":
            team_id = arguments.get("team_id")
            if team_id is None:
                error_msg = "team_id is required"
                logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            
            logger.info(f"MCP Tool {name} - Executing with team_id={team_id}")
            db_service = DatabaseService(db_connection=conn)
            
            # Validate team exists
            team = db_service.get_team_by_id(team_id)
            if not team:
                error_msg = "Invalid team_id"
                logger.warning(f"MCP Tool {name} - ERROR: {error_msg}")
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            
            users = db_service.get_users_by_team(team_id)
            logger.info(f"MCP Tool {name} - SUCCESS: Found {len(users)} users")
            logger.info(f"MCP Tool {name} - Output: {json.dumps(users, indent=2, default=str)}")
            response = [TextContent(type="text", text=json.dumps(users, default=str))]
            return response
        
        elif name == "list_teams":
            logger.info(f"MCP Tool {name} - Executing")
            db_service = DatabaseService(db_connection=conn)
            teams = db_service.get_all_teams()
            logger.info(f"MCP Tool {name} - SUCCESS: Found {len(teams)} teams")
            logger.info(f"MCP Tool {name} - Output: {json.dumps(teams, indent=2, default=str)}")
            response = [TextContent(type="text", text=json.dumps(teams, default=str))]
            return response
        
        else:
            error_msg = f"Unknown tool: {name}"
            logger.error(f"MCP Tool {name} - ERROR: {error_msg}")
            return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
    
    except psycopg2.OperationalError as e:
        # Database connection error
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"MCP Tool {name} - DATABASE CONNECTION ERROR: {str(e)}")
        logger.error(f"MCP Tool {name} - Traceback:\n{error_trace}")
        # Reset connection so next call will try to reconnect
        global _db_conn
        _db_conn = None
        return [TextContent(type="text", text=json.dumps({"error": f"Database connection error: {str(e)}"}))]
    except Exception as e:
        # Other exceptions
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"MCP Tool {name} - EXCEPTION: {str(e)}")
        logger.error(f"MCP Tool {name} - Traceback:\n{error_trace}")
        # Try to rollback if we have a connection
        try:
            if 'conn' in locals() and conn is not None:
                db_service = DatabaseService(db_connection=conn)
                db_service.rollback()
        except:
            pass
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

mcp_server = build_server("postgres-tasks-server", list_tools, call_tool)


async def main():
    """Main entry point for MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        # Initialize the server with the streams
        init_options = mcp_server.create_initialization_options()
        await mcp_server.run(
            read_stream,
            write_stream,
            init_options
        )

if __name__ == "__main__":
    asyncio.run(main())
