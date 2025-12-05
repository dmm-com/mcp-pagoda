import json

from mcp.server.fastmcp import Context
from mcp_server.drivers.pagoda import get_router_topology
from mcp_server.lib.log import get_prefix
from mcp_server.tools.common import get_backend_param


def router_topology(ctx: Context) -> str:
    """Get router topology"""
    endpoint, token = get_backend_param(ctx)

    topology = get_router_topology(
        endpoint=endpoint,
        token=token,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(topology)


ROUTER_LIST = [
    router_topology,
]
