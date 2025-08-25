import json
from typing import Optional

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
        self.token: str = ""

    @classmethod
    def get_instance(cls) -> "Pagoda":
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize(cls, endpoint: str, token: str) -> "Pagoda":
        """エンドポイントとトークンでPagodaを初期化"""
        instance = cls.get_instance()
        instance.endpoint = endpoint
        instance.token = token
        return instance


def get_pagoda_instance() -> Pagoda:
    """共通のPagodaインスタンス取得処理"""
    return Pagoda.get_instance()


# This is a MCP tool function
def get_model_list(search: str = "") -> str:
    """list all models"""
    backend = get_pagoda_instance()

    # access to backend service (Pagoda)
    model_list = get_model_list_api(
        endpoint=backend.endpoint,
        token=backend.token,
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


def get_model_detail(model_id: int) -> str:
    """get model detail"""
    backend = get_pagoda_instance()

    model_detail = get_model_detail_api(
        endpoint=backend.endpoint,
        token=backend.token,
        model_id=model_id,
    )

    return json.dumps(model_detail.model_dump())


def get_item_list(model_id: int, search: str = "") -> str:
    """list all items for a model"""
    backend = get_pagoda_instance()

    item_list = get_item_list_api(
        endpoint=backend.endpoint,
        token=backend.token,
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


def get_item_detail(item_id: int) -> str:
    """get item detail"""
    backend = get_pagoda_instance()

    item_detail = get_item_detail_api(
        endpoint=backend.endpoint,
        token=backend.token,
        item_id=item_id,
    )

    return json.dumps(item_detail.model_dump())


def search_item(query: str) -> str:
    """search items by partial match of the item name"""
    backend = get_pagoda_instance()

    item_list = search_item_api(
        endpoint=backend.endpoint,
        token=backend.token,
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
) -> str:
    """advanced search for items"""
    backend = get_pagoda_instance()

    result = advanced_search_api(
        endpoint=backend.endpoint,
        token=backend.token,
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
