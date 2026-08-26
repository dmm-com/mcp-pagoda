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


def get_user_activity_api(
    endpoint: str,
    token: str,
    user_id: int,
    since: str | None = None,
    to: str | None = None,
    within_minutes: int | None = None,
    log_prefix: str = "",
) -> list:
    Logger.debug(
        log_prefix
        + f"get_user_activity_api(Input) user_id={user_id}, since={since}, to={to}, within_minutes={within_minutes}"
    )
    params = {}
    if since is not None:
        params["since"] = since
    if to is not None:
        params["to"] = to
    if within_minutes is not None:
        params["within_minutes"] = within_minutes

    resp = request_get(
        url=endpoint + f"/user/api/v2/{user_id}/activity",
        params=params,
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Request failed /user/api/v2/{user_id}/activity")

    Logger.debug(log_prefix + f"get_user_activity_api(Output) {resp.json()}")
    return resp.json()


class CoUser(BaseModel):
    user_id: int
    username: str
    email: str


class User(BaseModel):
    user_id: int
    username: str
    email: str
    co_users: list[CoUser] | None


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


def request_patch(
    url: str, token: str, params: dict | None = None, data: dict | None = None
) -> requests.Response:
    return request_to_airone(requests.patch, url, token, params, data)


def request_put(
    url: str, token: str, params: dict | None = None, data: dict | None = None
) -> requests.Response:
    return request_to_airone(requests.put, url, token, params, data)


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
    Logger.debug(
        log_prefix + f"get_item_list_api(Input) model_id={model_id}, search={search}"
    )
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
        log_prefix
        + f"advanced_search_api(Input) entities={entities}, attrinfos={attrinfos}, "
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


def get_me_api(
    endpoint: str,
    token: str,
    log_prefix: str = "",
) -> User:
    Logger.debug(log_prefix + "get_me_api(Input)")
    resp = request_get(
        url=endpoint + "/user/api/v2/me",
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError("Request failed /user/api/v2/me")

    Logger.debug(log_prefix + f"get_me_api(Output) {resp.json()}")
    return User(**resp.json())


def restore_item_attribute_value_api(
    endpoint: str,
    token: str,
    attribute_value_id: int,
    log_prefix: str = "",
) -> dict:
    """
    This restores an attribute value via the Pagoda API.
    """
    Logger.debug(
        log_prefix
        + f"restore_item_attribute_value_api(Input) attribute_value_id={attribute_value_id}"
    )
    resp = request_patch(
        url=endpoint + f"/entry/api/v2/{attribute_value_id}/attrv_restore/",
        token=token,
        data={},
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(
            f"Request failed /entry/api/v2/{attribute_value_id}/attrv_restore/ "
            f"status={resp.status_code}"
        )

    result = resp.json() if resp.content else {}
    Logger.debug(log_prefix + f"restore_item_attribute_value_api(Output) {result}")
    return result


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


def rollback_items_api(
    endpoint: str,
    token: str,
    targets: list[int],
    at: str,
    log_prefix: str = "",
) -> dict:
    """
    This rolls back items to their state at the specified datetime via the Pagoda API.
    """
    Logger.debug(log_prefix + f"rollback_items_api(Input) targets={targets}, at={at}")
    resp = request_post(
        url=endpoint + "/entry/api/v2/rollback/",
        token=token,
        data={"targets": targets, "at": at},
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(
            f"Request failed /entry/api/v2/rollback status={resp.status_code}"
        )

    result = resp.json() if resp.content else {}
    Logger.debug(log_prefix + f"rollback_items_api(Output) {result}")
    return result


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


def search_chain_api(
    endpoint: str,
    token: str,
    entities: list[str],
    attrs: list[dict],
    log_prefix: str = "",
) -> list[Item]:
    """
    This searches Items by chaining referral Attributes of them.

    The condition tree ("attrs") is the same one that the Pagoda UI sends, e.g.
    [{"name": "一次対応輪番", "attrs": [{"name": "ユニット", "attrs": [...]}]}].
    see airone: entry/api_v2/urls.py (advanced_search_chain/) and
    api_v1/entry/serializer.py (EntrySearchChainSerializer)
    """
    Logger.debug(
        log_prefix + f"search_chain_api(Input) entities={entities}, attrs={attrs}"
    )
    resp = request_post(
        url=endpoint + "/entry/api/v2/advanced_search_chain/",
        token=token,
        data={"entities": entities, "attrs": attrs},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Request failed /entry/api/v2/advanced_search_chain/ "
            f"status={resp.status_code} body={resp.text}"
        )

    Logger.debug(log_prefix + f"search_chain_api(Output) {resp.json()}")
    return [Item(**result) for result in resp.json()]


def get_tulta_myself_api(
    endpoint: str,
    token: str,
    log_prefix: str = "",
) -> list[dict]:
    """
    This retrieves the Tulta contact ("Tulta連絡先") Items that the authenticated
    user has registered by themselves.

    see airone: custom_view/api_v2/tulta/urls.py ("myself/") and
    custom_view/api_v2/tulta/views.py (SelfInformationAPI)
    """
    Logger.debug(log_prefix + "get_tulta_myself_api(Input)")
    resp = request_get(
        url=endpoint + "/api/v2/custom/tulta/myself/",
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Request failed /api/v2/custom/tulta/myself/ status={resp.status_code}"
        )

    Logger.debug(log_prefix + f"get_tulta_myself_api(Output) {resp.json()}")
    return resp.json()


def get_tulta_rotation_api(
    endpoint: str,
    token: str,
    rotation_item_id: int,
    log_prefix: str = "",
) -> dict:
    """
    This retrieves the whole structure (layers, units, members and overrides) of
    the specified Tulta rotation ("Tulta輪番") Item.

    see airone: custom_view/api_v2/tulta/urls.py ("<int:entry_id>/") and
    custom_view/api_v2/tulta/serializers.py (TultaRetrieveRotationSerializer)
    """
    Logger.debug(
        log_prefix
        + f"get_tulta_rotation_api(Input) rotation_item_id={rotation_item_id}"
    )
    resp = request_get(
        url=endpoint + f"/api/v2/custom/tulta/{rotation_item_id}/",
        token=token,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Request failed /api/v2/custom/tulta/{rotation_item_id}/ "
            f"status={resp.status_code} body={resp.text}"
        )

    Logger.debug(log_prefix + f"get_tulta_rotation_api(Output) {resp.json()}")
    return resp.json()


def update_tulta_rotation_api(
    endpoint: str,
    token: str,
    rotation_item_id: int,
    data: dict,
    log_prefix: str = "",
) -> dict:
    """
    This updates the specified Tulta rotation Item. The Pagoda side accepts only
    the full representation (PATCH is disabled at its urls.py), so "data" must
    carry every layer and override that has to be kept.

    see airone: custom_view/api_v2/tulta/urls.py ("<int:entry_id>/") and
    custom_view/api_v2/tulta/serializers.py (TultaUpdateRotationSerializer)
    """
    Logger.debug(
        log_prefix
        + f"update_tulta_rotation_api(Input) rotation_item_id={rotation_item_id}, data={data}"
    )
    resp = request_put(
        url=endpoint + f"/api/v2/custom/tulta/{rotation_item_id}/",
        token=token,
        data=data,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(
            f"Request failed /api/v2/custom/tulta/{rotation_item_id}/ "
            f"status={resp.status_code} body={resp.text}"
        )

    result = resp.json() if resp.content else {}
    Logger.debug(log_prefix + f"update_tulta_rotation_api(Output) {result}")
    return result


def get_tulta_rotation_terms_api(
    endpoint: str,
    token: str,
    rotation_item_id: int,
    src_date: str,
    dst_date: str,
    log_prefix: str = "",
) -> dict:
    """
    This retrieves on-call members of the primary rotation for each day between
    src_date and dst_date, e.g. {"2026-08-24": [{"name": "denji", "order": 1}]}.

    see airone: custom_view/api_v2/tulta/urls.py ("members/terms/...") and
    custom_view/api_v2/tulta/views.py (TultaRetrieveMembersWithTermAPI)
    """
    Logger.debug(
        log_prefix + f"get_tulta_rotation_terms_api(Input) rotation_item_id="
        f"{rotation_item_id}, src_date={src_date}, dst_date={dst_date}"
    )
    path = (
        f"/api/v2/custom/tulta/members/terms/{rotation_item_id}/{src_date}/{dst_date}/"
    )
    resp = request_get(url=endpoint + path, token=token)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Request failed {path} status={resp.status_code} body={resp.text}"
        )

    Logger.debug(log_prefix + f"get_tulta_rotation_terms_api(Output) {resp.json()}")
    return resp.json()


def ping_check_api(
    endpoint: str,
    token: str,
    cidr: str,
    log_prefix: str = "",
) -> dict:
    """
    This checks IP reachability via the Pagoda API.
    """
    Logger.debug(log_prefix + f"ping_check_api(Input) cidr={cidr}")
    resp = request_post(
        url=endpoint + "/api/v2/custom/network/ping_check/",
        token=token,
        data={"cidr": cidr},
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(
            f"Request failed /api/v2/custom/network/ping_check/ status={resp.status_code}"
        )

    result = resp.json() if resp.content else {}
    Logger.debug(log_prefix + f"ping_check_api(Output) {result}")
    return result
