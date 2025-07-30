import json

from mcp.types import TextContent
from pydantic import BaseModel

from mcp_server.drivers.pagoda import advanced_search_api, get_model_id
from mcp_server.lib import PagodaCert, ToolHandler
from mcp_server.model import AdvancedSearchAttrInfo

ATTRNAME_UNIT = "ユニット数"


class RackList(BaseModel):
    floor_name: str = ""


def get_rack_list(cert: PagodaCert, arguments: dict):
    rack_model_id = get_model_id(
        endpoint=cert.endpoint,
        token=cert.token,
        search="ラック",
    )

    row_results = advanced_search_api(
        endpoint=cert.endpoint,
        token=cert.token,
        entities=[rack_model_id],
        attrinfos=[
            AdvancedSearchAttrInfo(name=ATTRNAME_UNIT),
            AdvancedSearchAttrInfo(name="RackSpace"),
            AdvancedSearchAttrInfo(
                name="フロア",
                filter_key=3,
                keyword=arguments["floor_name"],
            ),
        ],
    )

    results = []
    for row_result in row_results:
        try:
            unit_count = int(row_result.attrs[ATTRNAME_UNIT]["value"]["as_string"])
        except (KeyError, ValueError):
            unit_count = 0
        result = {
            "name": row_result.entry.name,
            ATTRNAME_UNIT: unit_count,
            "フロア": "",
            "RackSpace": {},
        }
        if row_result.attrs["フロア"]["value"]["as_object"] != {}:
            result["フロア"] = row_result.attrs["フロア"]["value"]["as_object"]["name"]

        for unit_number in range(1, unit_count + 1):
            rack_space = []
            for unit in row_result.attrs["RackSpace"]["value"]["as_array_named_object"]:
                if unit["name"] == str(unit_number):
                    rack_space.append(unit["object"]["name"])
            result["RackSpace"][str(unit_number)] = rack_space
        results.append(result)

    return [TextContent(type="text", text=json.dumps(results))]


TOOL_DC_ROUTERS = {
    "rack_list": ToolHandler(
        handler=get_rack_list, desc="list all racks", input_schema=RackList
    ),
}
