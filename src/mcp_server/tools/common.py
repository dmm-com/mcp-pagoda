import json
from typing import Optional

from mcp.server.fastmcp import Context

from mcp_server.drivers.pagoda import (
    advanced_search_api,
    get_item_detail_api,
    get_item_list_api,
    get_model_detail_api,
    get_model_list_api,
    search_item_api,
)
from mcp_server.model import AdvancedSearchAttrInfo


# FIXME: This refers PagodaDriver
class Pagoda:
    """シングルトンパターンを使用したPagodaクライアントクラス"""

    _instance: Optional["Pagoda"] = None

    def __init__(self):
        # これらの変数はSimpleAzureADOAuthProviderから設定される
        self.endpoint: str = ""
        self.token: str | None = None

    @classmethod
    def get_instance(cls) -> "Pagoda":
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(cls, endpoint: str, token: str, is_bearer: bool) -> "Pagoda":
        """エンドポイントとトークンでPagodaを初期化"""
        instance = cls.get_instance()
        instance.endpoint = endpoint
        instance.token = token
        instance.is_bearer = is_bearer
        return instance


def get_backend_param(ctx: Context = None) -> tuple[str, str]:
    pagoda_instance = Pagoda.get_instance()
    if pagoda_instance.token is None or pagoda_instance.is_bearer:
        return (
            pagoda_instance.endpoint,
            ctx.request_context.request.user.access_token.token,
        )
    return pagoda_instance.endpoint, pagoda_instance.token


# This is a MCP tool function
def get_model_list(search: str = "", ctx: Context = None) -> str:
    """list all models"""
    endpoint, token = get_backend_param(ctx)

    # access to backend service (Pagoda)
    model_list = get_model_list_api(
        endpoint=endpoint,
        token=token,
        search=search,
    )

    return json.dumps(
        [
            {
                "id": model.id,
                "name": model.name,
                "note": model.note,
            }
            for model in model_list
        ]
    )


def get_model_detail(model_id: int, ctx: Context) -> str:
    """get model detail"""
    endpoint, token = get_backend_param(ctx)

    model_detail = get_model_detail_api(
        endpoint=endpoint,
        token=token,
        model_id=model_id,
    )

    return json.dumps(model_detail.model_dump())


def get_item_list(model_id: int, search: str = "", ctx: Context = None) -> str:
    """list all items for a model"""
    endpoint, token = get_backend_param(ctx)

    item_list = get_item_list_api(
        endpoint=endpoint,
        token=token,
        model_id=model_id,
        search=search,
    )

    return json.dumps(
        [
            {
                "id": item.id,
                "name": item.name,
                "schema": item.model.name,
            }
            for item in item_list
        ]
    )


def get_item_detail(item_id: int, ctx: Context) -> str:
    """get item detail"""
    endpoint, token = get_backend_param(ctx)

    item_detail = get_item_detail_api(
        endpoint=endpoint,
        token=token,
        item_id=item_id,
    )

    return json.dumps(item_detail.model_dump())


def search_item(query: str, ctx: Context) -> str:
    """search items by partial match of the item name"""
    endpoint, token = get_backend_param(ctx)

    item_list = search_item_api(
        endpoint=endpoint,
        token=token,
        query=query,
    )

    return json.dumps([item.model_dump() for item in item_list])


def advanced_search(
    entities: list,
    attrinfo: list,
    item_filter_key: int = 0,
    item_keyword: str = "",
    has_referral: bool = False,
    referral_name: str = "",
    limit: int = 100,
    offset: int = 0,
    ctx: Context = None,
) -> str:
    """advanced search for items"""
    endpoint, token = get_backend_param(ctx)

    result = advanced_search_api(
        endpoint=endpoint,
        token=token,
        entities=entities,
        attrinfos=[AdvancedSearchAttrInfo(**info) for info in attrinfo],
        item_filter_key=item_filter_key,
        item_keyword=item_keyword,
        has_referral=has_referral,
        referral_name=referral_name,
        limit=limit,
        offset=offset,
    )
    return json.dumps(result.model_dump())


COMMON_LIST = [
    get_model_list,
    get_model_detail,
    get_item_list,
    get_item_detail,
    search_item,
    advanced_search,
]
