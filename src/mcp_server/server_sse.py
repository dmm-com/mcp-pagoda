import logging
from typing import Literal

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP

from mcp_server.lib.auth.azure import get_azure_mcp_server
from mcp_server.lib.auth.common import ServerSettings
from mcp_server.lib.pagoda import is_token_valid
from mcp_server.prompts.lb import LB_LIST
from mcp_server.tools.common import COMMON_LIST
from mcp_server.tools.datacenter import DC_LIST
from mcp_server.tools.router import ROUTER_LIST

TOOL_LIST = COMMON_LIST + DC_LIST + ROUTER_LIST
PROMPT_LIST = LB_LIST


logger = logging.getLogger(__name__)


class PagodaBearer(TokenVerifier):
    def __init__(self, pagoda_url_base: str):
        super().__init__()
        self.pagoda_url_base = pagoda_url_base

    async def verify_token(self, token: str) -> AccessToken | None:
        # Verify the token using Pagoda's token introspection endpoint
        if is_token_valid(self.pagoda_url_base, token):
            return AccessToken(
                token=token,
                client_id="pagoda",
                scopes=[],
            )


def create_mcp_server(
    host, port, pagoda_endpoint, auth_method: Literal["bearer", "azure"]
) -> FastMCP:
    """Create a simple FastMCP server"""
    if auth_method == "azure":
        server = get_azure_mcp_server(host, port)
    else:
        server_settings = ServerSettings(host=host, port=port)

        server = FastMCP(
            name="Simple Bearer MCP Server",
            instructions="A simple MCP server with Bearer token authentication",
            host=host,
            port=port,
            debug=True,
            auth=AuthSettings(
                issuer_url=server_settings.server_url,
                resource_server_url=None,
            ),
            token_verifier=PagodaBearer(pagoda_url_base=pagoda_endpoint),
        )

    for func in TOOL_LIST:
        # By using the server.tool() decorator, each tool function can be registered to the MCP server
        server.tool()(func)

    for title, func in PROMPT_LIST:
        # By using the server.prompt() decorator, each prompt function can be registered to the MCP server
        server.prompt(title=title)(func)

    return server


def serve(
    host: str,
    port: int,
    auth_method: Literal["bearer", "azure"],
    endpoint: str,
    token: str,
) -> int:
    """Run the simple Azure AD MCP server."""
    logging.basicConfig(level=logging.INFO)

    # initialize Pagoda instance
    from mcp_server.tools.common import Pagoda

    Pagoda.initialize(
        endpoint=endpoint, token=token, is_bearer=(auth_method == "bearer")
    )

    mcp_server = create_mcp_server(host, port, endpoint, auth_method)
    mcp_server.run(transport="sse")
    return 0
