import json

from mcp.types import TextContent

from mcp_server.drivers.pagoda import (
    advanced_search_api,
    get_item_detail_api,
    get_item_list_api,
    get_model_detail_api,
    get_model_list_api,
    search_item_api,
)
from mcp_server.lib import PagodaCert, ToolHandler
from mcp_server.model import (
    AdvancedSearch,
    AdvancedSearchAttrInfo,
    ItemDetailInput,
    ItemList,
    ModelDetailInput,
    ModelList,
    SearchItem,
)


def get_model_list(cert: PagodaCert, args: dict):
    model_list = get_model_list_api(
        endpoint=cert.endpoint,
        token=cert.token,
        search=args["search"],
    )

    return [
        TextContent(
            type="text",
            text=json.dumps(
                [
                    {
                        "id": model.id,
                        "name": model.name,
                        "note": model.note,
                    }
                    for model in model_list
                ]
            ),
        )
    ]


def get_model_detail(cert: PagodaCert, args: dict):
    model_detail = get_model_detail_api(
        endpoint=cert.endpoint,
        token=cert.token,
        model_id=int(args["model_id"]),
    )

    return [
        TextContent(
            type="text",
            text=json.dumps(model_detail.model_dump()),
        )
    ]


def get_item_list(cert: PagodaCert, args: dict):
    item_list = get_item_list_api(
        endpoint=cert.endpoint,
        token=cert.token,
        model_id=int(args["model_id"]),
        search=args["search"],
    )
    return [
        TextContent(
            type="text",
            text=json.dumps(
                [
                    {
                        "id": item.id,
                        "name": item.name,
                        "schema": item.model.name,
                    }
                    for item in item_list
                ]
            ),
        )
    ]


def get_item_detail(cert: PagodaCert, args: dict):
    # call request to get item detail
    item_detail = get_item_detail_api(
        endpoint=cert.endpoint,
        token=cert.token,
        item_id=int(args["item_id"]),
    )

    return [
        TextContent(
            type="text",
            text=json.dumps(item_detail.model_dump()),
        )
    ]


def search_item(
    cert: PagodaCert,
    args: dict,
):
    item_list = search_item_api(
        endpoint=cert.endpoint,
        token=cert.token,
        query=args["query"],
    )

    return [
        TextContent(
            type="text",
            text=json.dumps([item.model_dump() for item in item_list]),
        )
    ]


def advanced_search(
    cert: PagodaCert,
    args: dict,
):
    result = advanced_search_api(
        endpoint=cert.endpoint,
        token=cert.token,
        entities=args["entities"],
        attrinfos=[AdvancedSearchAttrInfo(**attrinfo) for attrinfo in args["attrinfo"]],
        item_filter_key=args.get("item_filter_key", 0),
        item_keyword=args.get("item_keyword", ""),
        has_referral=args.get("has_referral", False),
        referral_name=args.get("referral_name", ""),
        limit=args.get("limit", 100),
        offset=args.get("offset", 0),
    )
    return [
        TextContent(
            type="text",
            text=json.dumps(result.model_dump()),
        )
    ]


TOOL_COMMON_ROUTERS = {
    "model_list": ToolHandler(
        handler=get_model_list, desc="list all models", input_schema=ModelList
    ),
    "model_detail": ToolHandler(
        handler=get_model_detail, desc="get model detail", input_schema=ModelDetailInput
    ),
    "item_list": ToolHandler(
        handler=get_item_list, desc="list all items", input_schema=ItemList
    ),
    "item_detail": ToolHandler(
        handler=get_item_detail, desc="get item detail", input_schema=ItemDetailInput
    ),
    "search_item": ToolHandler(
        handler=search_item,
        desc="Returns a list of items by partial match of the item name",
        input_schema=SearchItem,
    ),
    "advanced_search": ToolHandler(
        handler=advanced_search,
        desc="""
Returns a list of item details.
Filter by selecting attributes.
Also returns the referenced items.
""",
        input_schema=AdvancedSearch,
    ),
}
