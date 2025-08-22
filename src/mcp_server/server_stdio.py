import logging

from mcp.server.fastmcp.server import FastMCP

from mcp_server.prompts.lb import LB_LIST
from mcp_server.tools.common import COMMON_LIST
from mcp_server.tools.datacenter import DC_LIST
from mcp_server.tools.router import ROUTER_LIST

TOOL_LIST = COMMON_LIST + DC_LIST + ROUTER_LIST
PROMPT_LIST = LB_LIST

TOOL_ROUTERS = dict()
PROMPT_ROUTERS = dict()

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    server = FastMCP()

    for func in TOOL_LIST:
        # By using the server.tool() decorator, each tool function can be registered to the MCP server
        server.tool()(func)

    for title, func in PROMPT_LIST:
        # By using the server.prompt() decorator, each prompt function can be registered to the MCP server
        server.prompt(title=title)(func)

    return server


def serve(endpoint: str, token: str) -> int:
    logging.basicConfig(level=logging.INFO)

    # initialize Pagoda instance
    from mcp_server.tools.common import Pagoda

    Pagoda.initialize(endpoint=endpoint, token=token)

    mcp_server = create_mcp_server()
    mcp_server.run(transport="stdio")
    return 0
