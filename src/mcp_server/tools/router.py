import json

from mcp_server.drivers.pagoda import get_router_topology
from mcp_server.tools.common import get_pagoda_instance


def router_topology() -> str:
    """Get router topology"""
    backend = get_pagoda_instance()

    topology = get_router_topology(
        endpoint=backend.endpoint,
        token=backend.token,
    )

    return json.dumps(topology)


ROUTER_LIST = [
    router_topology,
]
