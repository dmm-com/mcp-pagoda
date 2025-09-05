import json

from mcp_server.drivers.pagoda import advanced_search_api, get_model_id
from mcp.server.fastmcp import Context
from mcp_server.model import AdvancedSearchAttrInfo
from mcp_server.tools.common import get_backend_param

ATTRNAME_UNIT = "ユニット数"

ATTRNAME_UNIT = "ユニット数"


def get_rack_list(floor_name: str, ctx: Context) -> str:
    """list all racks"""
    endpoint, token = get_backend_param(ctx)

    rack_model_id = get_model_id(
        endpoint=endpoint,
        token=token,
        search="ラック",
    )

    row_results = advanced_search_api(
        endpoint=endpoint,
        token=token,
        entities=[rack_model_id],
        attrinfos=[
            AdvancedSearchAttrInfo(name=ATTRNAME_UNIT),
            AdvancedSearchAttrInfo(name="RackSpace"),
            AdvancedSearchAttrInfo(
                name="フロア",
                filter_key=3,
                keyword=floor_name,
            ),
        ],
    )

    results = []
    for row_result in row_results.values:
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

    return json.dumps({"rack_list": results})


DC_LIST = [get_rack_list]
