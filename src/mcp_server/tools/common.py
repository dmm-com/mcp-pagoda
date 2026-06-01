import json
from typing import Optional

from mcp.server.fastmcp import Context
from mcp_server.drivers.pagoda import (
    advanced_search_api,
    get_item_detail_api,
    get_item_list_api,
    get_me_api,
    get_model_detail_api,
    get_model_list_api,
    get_user_activity_api,
    restore_item_attribute_value_api,
    rollback_items_api,
    search_item_api,
)
from mcp_server.lib.log import get_prefix
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
        log_prefix=get_prefix(ctx),
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
        log_prefix=get_prefix(ctx),
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
        log_prefix=get_prefix(ctx),
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
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(item_detail.model_dump())


def search_item(query: str, ctx: Context) -> str:
    """search items by partial match of the item name"""
    endpoint, token = get_backend_param(ctx)

    item_list = search_item_api(
        endpoint=endpoint,
        token=token,
        query=query,
        log_prefix=get_prefix(ctx),
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
        log_prefix=get_prefix(ctx),
    )
    return json.dumps(result.model_dump())


def get_user_activity(
    user_id: int,
    since: str = "",
    to: str = "",
    within_minutes: int = 0,
    ctx: Context = None,
) -> str:
    """get activity history for a user. since and to are ISO 8601 datetime strings that define the start and end of the time range. within_minutes limits results to activities within that many minutes of since."""
    endpoint, token = get_backend_param(ctx)

    result = get_user_activity_api(
        endpoint=endpoint,
        token=token,
        user_id=user_id,
        since=since or None,
        to=to or None,
        within_minutes=within_minutes or None,
    )

    return json.dumps(result)


def get_me(ctx: Context = None) -> str:
    """get the current authenticated user's profile"""
    endpoint, token = get_backend_param(ctx)

    user = get_me_api(
        endpoint=endpoint,
        token=token,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(user.model_dump())


def restore_item_attribute_value(attribute_value_id: int, ctx: Context) -> str:
    """restore an attribute value to its previous state by attribute value ID"""
    endpoint, token = get_backend_param(ctx)

    result = restore_item_attribute_value_api(
        endpoint=endpoint,
        token=token,
        attribute_value_id=attribute_value_id,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(result)


def rollback_items(targets: list[int], at: str, ctx: Context = None) -> str:
    """roll back items to their configuration state at the specified datetime. targets is a list of item IDs. at is an ISO 8601 datetime string."""
    endpoint, token = get_backend_param(ctx)

    result = rollback_items_api(
        endpoint=endpoint,
        token=token,
        targets=targets,
        at=at,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(result)


COMMON_LIST = [
    get_me,
    get_model_list,
    get_model_detail,
    get_item_list,
    get_item_detail,
    search_item,
    advanced_search,
    get_user_activity,
    restore_item_attribute_value,
    rollback_items,
]
