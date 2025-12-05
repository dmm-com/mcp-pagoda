import json
from typing import Callable

import requests
from mcp_server.lib.log import Logger
from mcp_server.model import AdvancedSearchAttrInfo
from pydantic import BaseModel, Field


class ModelBase(BaseModel):
    id: int
    name: str


class Model(ModelBase):
    note: str
    item_name_pattern: str
    status: int
    is_toplevel: bool


class ModelAttr(BaseModel):
    id: int
    name: str


class ModelDetail(Model):
    attrs: list[ModelAttr]


class ItemBase(BaseModel):
    id: int
    name: str


class Item(ItemBase):
    model: ModelBase = Field(alias="schema")


class ItemDetail(Item):
    is_active: bool
    attrs: list[dict] = Field(default_factory=list)


class AdvancedSearchResultItem(BaseModel):
    entry: ItemBase
    entity: ModelBase
    attrs: dict
    referrals: list[Item] | None


class AdvancedSearchResult(BaseModel):
    total_count: int
    values: list[AdvancedSearchResultItem]


def request_to_airone(
    method: Callable, url: str, token: str, params: dict | None, data: dict | None
) -> requests.Response:
    """
    This sends request to the Pagoda.
    """
    return method(
        url=url,
        params=params,
        data=json.dumps(data),
        headers={
            "Content-Type": "application/json;charset=utf-8",
            "Authorization": "Token " + token,
        },
        verify=False,
    )


def request_get(
    url: str, token: str, params: dict | None = None, data: dict | None = None
) -> requests.Response:
    return request_to_airone(requests.get, url, token, params, data)


def request_post(
    url: str, token: str, params: dict | None = None, data: dict | None = None
) -> requests.Response:
    return request_to_airone(requests.post, url, token, params, data)


def get_model_list_api(
    endpoint: str,
    token: str,
    search: str = "",
    log_prefix: str = "",
) -> list[Model]:
    Logger.debug(log_prefix + f"get_model_list_api(Input) search={search}")
    results = []
    limit = 100
    offset = 0

    while True:
        resp = request_get(
            url=endpoint + "/entity/api/v2/",
            params={
                "search": search,
                "limit": str(limit),
                "offset": str(offset),
            },
            token=token,
        )
        if resp.status_code != 200:
            raise RuntimeError("Request failed /entity/api/v2/")
        for result in resp.json()["results"]:
            results.append(result)
        if resp.json()["next"] is None:
            break
        offset += limit

    Logger.debug(log_prefix + f"get_model_list_api(Output) {results}")
    return [Model(**result) for result in results]


def get_item_list_api(
    endpoint: str,
    token: str,
    model_id: int,
    search: str = "",
    log_prefix: str = "",
) -> list[Item]:
    Logger.debug(log_prefix + f"get_item_list_api(Input) model_id={model_id}, search={search}")
    results = []
    page = 1
    while True:
        resp = request_get(
            url=endpoint + f"/entity/api/v2/{model_id}/entries/",
            params={
                "search": search,
                "is_active": "true",
                "page": str(page),
            },
            token=token,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Request failed /entity/api/v2/{model_id}/entries/")
        for result in resp.json()["results"]:
            results.append(result)
        if resp.json()["next"] is None:
            break
        page += 1

    Logger.debug(log_prefix + f"get_item_list_api(Output) {results}")
    return [Item(**result) for result in results]


def advanced_search_api(
    endpoint: str,
    token: str,
    entities: list[int],
    attrinfos: list[AdvancedSearchAttrInfo],
    item_filter_key: int = 0,
    item_keyword: str = "",
    has_referral: bool = False,
    referral_name: str = "",
    limit: int = 100,
    offset: int = 0,
    log_prefix: str = "",
) -> AdvancedSearchResult:
    Logger.debug(
        log_prefix + f"advanced_search_api(Input) entities={entities}, attrinfos={attrinfos}, "
        f"item_filter_key={item_filter_key}, item_keyword={item_keyword},"
        f"has_referral={has_referral}, referral_name={referral_name}"
    )
    data = {
        "entities": entities,
        "attrinfo": [attrinfo.model_dump() for attrinfo in attrinfos],
        "hint_entry": {
            "filter_key": item_filter_key,
            "keyword": item_keyword,
        },
        "has_referral": has_referral,
        "referral_name": referral_name,
        "is_output_all": False,
        "entry_limit": limit,
        "entry_offset": offset,
    }
    resp = request_post(
        url=endpoint + "/entry/api/v2/advanced_search/",
        data=data,
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError("Request failed /entry/api/v2/advanced_search/")

    Logger.debug(log_prefix + f"advanced_search_api(Output) {resp.json()}")
    return AdvancedSearchResult(**resp.json())


def get_model_id(
    endpoint: str,
    token: str,
    search: str = "",
) -> int:
    results = get_model_list_api(
        endpoint=endpoint,
        token=token,
        search=search,
    )
    for result in results:
        if result.name == search:
            return result.id
    raise RuntimeError(f"Model {search} not found")


def get_model_detail_api(
    endpoint: str,
    token: str,
    model_id: int,
    log_prefix: str = "",
) -> ModelDetail:
    """
    This retrieves model details from the Pagoda API.
    e.g. https://airone.dmmlabs.jp/entity/api/v2/533972/
    """
    Logger.debug(log_prefix + f"get_model_detail_api(Input) model_id={model_id}")
    resp = request_get(
        url=endpoint + f"/entity/api/v2/{model_id}/",
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Request failed /entity/api/v2/{model_id}/")

    Logger.debug(log_prefix + f"get_model_detail_api(Output) {resp.json()}")
    return ModelDetail(**resp.json())


def get_item_detail_api(
    endpoint: str,
    token: str,
    item_id: int,
    log_prefix: str = "",
) -> ItemDetail:
    """
    This retrieves item details from the Pagoda API.
    e.g. https://airone.dmmlabs.jp/entry/api/v2/533972/
    """
    Logger.debug(log_prefix + f"get_item_detail_api(Input) item_id={item_id}")
    resp = request_get(
        url=endpoint + f"/entry/api/v2/{item_id}/",
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Request failed /entry/api/v2/{item_id}/")

    Logger.debug(log_prefix + f"get_item_detail_api(Output) {resp.json()}")
    return ItemDetail(**resp.json())


def search_item_api(
    endpoint: str,
    token: str,
    query: str = "",
    log_prefix: str = "",
) -> list[Item]:
    Logger.debug(log_prefix + f"search_item_api(Input) query={query}")
    resp = request_get(
        url=endpoint + "/entry/api/v2/search/",
        params={
            "query": query,
        },
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError("Request failed /api/v2/search/")
    results = resp.json()

    Logger.debug(log_prefix + f"search_item_api(Output) {results}")
    return [Item(**result) for result in results]


def get_router_topology(
    endpoint: str,
    token: str,
    log_prefix: str = "",
) -> list[ItemDetail]:
    """
    This retrieves topology from the Pagoda API.
    """
    Logger.debug(log_prefix + "get_router_topology(Input)")
    resp = request_get(
        url=endpoint + "/api/v2/custom/network/get_router_topology/",
        params={},
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError("/api/v2/custom/network/get_router_topology/")

    Logger.debug(log_prefix + f"get_router_topology(Output) {resp.json()}")
    return resp.json()
