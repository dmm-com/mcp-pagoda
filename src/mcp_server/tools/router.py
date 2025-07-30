import json

from mcp.types import TextContent
from pydantic import BaseModel

from mcp_server.drivers.pagoda import get_router_topology
from mcp_server.lib import PagodaCert, ToolHandler


class TopologyList(BaseModel):
    pass


class NeighborRouter(BaseModel):
    id: int
    name: str
    description: str


class RouterTopologyResult(BaseModel):
    id: int
    name: str
    description: str
    neighbors: list[NeighborRouter]


def router_topology(cert: PagodaCert, arguments: dict) -> list[RouterTopologyResult]:
    return [
        TextContent(
            type="text",
            text=json.dumps(
                get_router_topology(
                    endpoint=cert.endpoint,
                    token=cert.token,
                )
            ),
        )
    ]


TOOL_ROUTER_ROUTERS = {
    "router_topology": ToolHandler(
        handler=router_topology,
        desc="returns router topology",
        input_schema=TopologyList,
    ),
}
