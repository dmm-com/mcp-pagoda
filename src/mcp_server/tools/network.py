import json

from mcp.server.fastmcp import Context

from mcp_server.drivers.pagoda import ping_check_api
from mcp_server.lib.log import get_prefix
from mcp_server.tools.common import get_backend_param


def ping_check(cidr: str, ctx: Context = None) -> str:
    """check IP reachability for a CIDR"""
    endpoint, token = get_backend_param(ctx)

    result = ping_check_api(
        endpoint=endpoint,
        token=token,
        cidr=cidr,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(result)


NETWORK_LIST = [
    ping_check,
]
