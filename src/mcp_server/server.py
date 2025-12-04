from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import GetPromptResult, Prompt, Resource, TextContent, Tool

from mcp_server.lib import PagodaCert
from mcp_server.prompts.lb import PROMPT_LB_ROUTERS
from mcp_server.tools.common import TOOL_COMMON_ROUTERS
from mcp_server.tools.datacenter import TOOL_DC_ROUTERS
from mcp_server.tools.router import TOOL_ROUTER_ROUTERS

TOOL_ROUTERS = dict(**TOOL_COMMON_ROUTERS, **TOOL_DC_ROUTERS, **TOOL_ROUTER_ROUTERS)
PROMPT_ROUTERS = dict(**PROMPT_LB_ROUTERS)


async def serve(endpoint: str, token: str) -> None:
    server: Server = Server("mcp-pagoda")

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name=name,
                description=handler.desc,
                arguments=handler.args,
            )
            for (name, handler) in PROMPT_ROUTERS.items()
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict) -> GetPromptResult:
        if name in PROMPT_ROUTERS:
            return PROMPT_ROUTERS[name].handler(arguments)
        else:
            raise ValueError(f"Unknown prompt name: {name}")

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return []

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=name,
                description=handler.desc,
                inputSchema=handler.input_schema.model_json_schema(),
            )
            for (name, handler) in TOOL_ROUTERS.items()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name in TOOL_ROUTERS:
            return TOOL_ROUTERS[name].handler(PagodaCert(endpoint=endpoint, token=token), arguments)
        else:
            raise ValueError(f"Unknown tool name: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
