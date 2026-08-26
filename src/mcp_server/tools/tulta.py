"""MCP tools for Tulta, the on-call rotation ("輪番") feature of Pagoda.

Every tool here is a thin wrapper of the Tulta APIs that the Pagoda custom_view
provides. The endpoints and the payloads are the very ones that the Tulta UI
uses, so the following files of the airone repository are the reference:

- custom_view/api_v2/tulta/urls.py     : the endpoints below
- custom_view/api_v2/tulta/views.py    : what each endpoint returns
- custom_view/api_v2/tulta/serializers.py
                                       : TultaRetrieveRotationSerializer (read)
                                         TultaUpdateRotationSerializer (write)
- custom_view/lib/settings.py          : Model / Attribute names of Tulta
- custom_view/lib/tulta.py             : how members of a day are calculated
- airone.react.custom/src/pages/TultaTopPage.tsx
                                       : how the UI finds the rotations of the
                                         logged-in user
- airone.react.custom/src/pages/EditTultaRotationPage.tsx
                                       : how the UI builds the update payload
"""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import Context

from mcp_server.drivers.pagoda import (
    Item,
    get_item_list_api,
    get_model_id,
    get_tulta_myself_api,
    get_tulta_rotation_api,
    get_tulta_rotation_terms_api,
    search_chain_api,
    update_tulta_rotation_api,
)
from mcp_server.lib.log import get_prefix
from mcp_server.tools.common import get_backend_param

# Model ("Entity") names of Tulta.
# see airone: custom_view/lib/settings.py (ADAPTED_ENTITY)
MODEL_TULTA_ROTATION = "Tulta輪番"
MODEL_TULTA_CONTACT = "Tulta連絡先"

# Attribute names that make the reference chain
# "Tulta輪番" -> "Tultaレイヤ" -> "Tultaユニット" -> "Tulta連絡先".
# see airone: custom_view/lib/settings.py (ADAPTED_ENTITY)
ATTR_PRIMARY_LAYERS = "一次対応輪番"
ATTR_UNITS = "ユニット"
ATTR_MEMBERS = "メンバー"

# Pagoda runs on JST, so "today" and "this week" have to be decided on it.
# see airone: airone/settings_common.py (TIME_ZONE = "Asia/Tokyo")
TIMEZONE = ZoneInfo("Asia/Tokyo")

# The "members/terms/" endpoint refuses a longer term than this.
# see airone: entry/settings.py (CONFIG.MAX_LIST_ENTRIES) and
# custom_view/api_v2/tulta/views.py (TultaRetrieveMembersWithTermAPI.list)
MAX_TERM_DAYS = 100


def _today() -> date:
    return datetime.now(TIMEZONE).date()


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise RuntimeError(f"Invalid date '{value}' was specified. Use YYYY-MM-DD.")


def _resolve_term(start_date: str, end_date: str) -> tuple[date, date]:
    """This decides the term to be shown from the (optional) parameters.

    Both of them being empty means "this week", which starts on Monday because
    Tulta itself orders weekdays from Monday.
    see airone: custom_view/api_v2/tulta/serializers.py (TULTA_WEEKDAYS)
    """
    if not start_date and not end_date:
        today = _today()
        monday = today - timedelta(days=today.weekday())
        return (monday, monday + timedelta(days=6))

    if start_date and not end_date:
        parsed = _parse_date(start_date)
        return (parsed, parsed)

    if end_date and not start_date:
        parsed = _parse_date(end_date)
        return (parsed, parsed)

    (src, dst) = (_parse_date(start_date), _parse_date(end_date))
    if dst < src:
        raise RuntimeError("The end date is set earlier than the start date.")
    if (dst - src).days > MAX_TERM_DAYS:
        raise RuntimeError(f"The longest term is up to {MAX_TERM_DAYS} days.")

    return (src, dst)


def _rotation_summary(rotation: dict) -> dict:
    return {"id": rotation["id"], "name": rotation["name"]}


def _layer_param(layer: dict) -> dict:
    """This converts a layer of the retrieve API into an update API parameter."""
    param = {
        "id": layer["id"],
        "shift_days": layer["shift_days"],
        "start_date": layer["start_date"],
        # The retrieve API falls back to "Custom" when the Attribute has no value,
        # but the update API accepts only the lower-cased choices.
        # see airone: custom_view/api_v2/tulta/serializers.py
        #             (TULTA_INTERVALS, DEFAULT_ROTATION_INTERVAL)
        "rotation_interval": str(layer.get("rotation_interval") or "custom").lower(),
        "will_delete": False,
        "units": [
            {
                "id": unit["id"],
                "shift_days": unit["shift_days"],
                "will_delete": False,
                # Only the reference to each Tulta contact Item is stored, and the
                # order of this array decides the on-call order.
                # see airone: custom_view/api_v2/tulta/serializers.py
                #             (TultaUpdateRotationSerializer._update_unit)
                "members": [
                    {"id": member["id"], "name": member["name"]}
                    for member in unit.get("members") or []
                ],
            }
            for unit in layer.get("units") or []
        ],
    }
    # The retrieve API returns null when no end date is set, and the update API
    # clears the Attribute for a null value, so it is passed only when it exists.
    if layer.get("end_date"):
        param["end_date"] = layer["end_date"]

    return param


def _override_param(override: dict) -> dict:
    """This converts an override of the retrieve API into an update API parameter."""
    return {
        "id": override["id"],
        "date": override["date"],
        "members": [
            {"id": member["id"], "name": member["name"]}
            for member in override.get("members") or []
        ],
        "is_override_rotation": override.get("is_override_rotation", True),
    }


def _build_update_payload(rotation: dict, primary_override: list[dict]) -> dict:
    """This builds the whole update payload out of a retrieve API response.

    The Tulta update API accepts only the full representation (PATCH is disabled
    at custom_view/api_v2/tulta/urls.py) and clears every parameter that is not
    sent, so everything but "primary_override" is carried over as it is. This is
    the same thing that the "保存" button of the UI does.
    see airone.react.custom: src/pages/EditTultaRotationPage.tsx (handleSubmit)
    """
    return {
        # The update API rejects a different name, so it must be sent unchanged.
        # see airone: custom_view/api_v2/tulta/serializers.py (validate_name)
        "name": rotation["name"],
        "slack_mention": rotation.get("slack_mention") or "",
        "keyword": rotation.get("keyword") or "",
        "annotation": rotation.get("annotation") or "",
        "boundary_time": rotation.get("boundary_time") or "",
        "primary_layers": [
            _layer_param(layer) for layer in rotation.get("primary_layers") or []
        ],
        "secondary_layers": [
            _layer_param(layer) for layer in rotation.get("secondary_layers") or []
        ],
        "primary_override": primary_override,
        "secondary_override": [
            _override_param(override)
            for override in rotation.get("secondary_override") or []
        ],
    }


def _collect_update_warnings(rotation: dict) -> list[str]:
    """This tells what the update API drops besides the requested change.

    An override Item is deleted when it has no member, and every override Item of
    a past date is deleted as well. Both of them also happen when the UI saves a
    rotation, so they are reported instead of being prevented.
    see airone: custom_view/api_v2/tulta/serializers.py
                (_update_tulta_override, _settle_the_past)
    """
    warnings = []
    today = _today()
    for key in ["primary_override", "secondary_override"]:
        for override in rotation.get(key) or []:
            if not (override.get("members") or []):
                warnings.append(
                    f"The override of {key} on {override['date']} has no member, "
                    "so Pagoda deletes it on this update (this is the same "
                    "behavior as saving the rotation on the UI)."
                )
            elif _parse_date(override["date"]) < today:
                warnings.append(
                    f"The override of {key} on {override['date']} is already past, "
                    "so Pagoda deletes it on this update and may shift the start "
                    "date of the layers accordingly."
                )

    return warnings


def _collect_known_members(rotation: dict) -> dict[str, int]:
    """This gathers the Tulta contact Items that the rotation already refers to."""
    known: dict[str, int] = {}
    for key in ["primary_layers", "secondary_layers"]:
        for layer in rotation.get(key) or []:
            for unit in layer.get("units") or []:
                for member in unit.get("members") or []:
                    known.setdefault(member["name"], member["id"])

    for key in ["primary_override", "secondary_override"]:
        for override in rotation.get(key) or []:
            for member in override.get("members") or []:
                known.setdefault(member["name"], member["id"])

    return known


def _resolve_members(
    endpoint: str,
    token: str,
    rotation: dict,
    names: list[str],
    log_prefix: str = "",
) -> list[dict]:
    """This converts member names into references of Tulta contact Items.

    Members of the rotation itself are looked up first, then every Tulta contact
    Item, because the UI also lets any contact Item be picked as an on-call
    member.
    see airone.react.custom: src/pages/EditTultaRotationPage.tsx (onCallMembers)
    """
    known = _collect_known_members(rotation)
    contact_items: list[Item] | None = None

    resolved = []
    for name in names:
        if name in known:
            resolved.append({"id": known[name], "name": name})
            continue

        if contact_items is None:
            contact_items = get_item_list_api(
                endpoint=endpoint,
                token=token,
                model_id=get_model_id(
                    endpoint=endpoint, token=token, search=MODEL_TULTA_CONTACT
                ),
                log_prefix=log_prefix,
            )

        candidates = [x for x in contact_items if x.name == name]
        if not candidates:
            raise RuntimeError(
                f"There is no '{MODEL_TULTA_CONTACT}' Item that is named '{name}'. "
                f"The members of this rotation are {sorted(known.keys())}."
            )
        if len(candidates) > 1:
            raise RuntimeError(
                f"There are multiple '{MODEL_TULTA_CONTACT}' Items that are named "
                f"'{name}' (ids: {[x.id for x in candidates]}). "
                "Please fix the duplication on Pagoda."
            )

        resolved.append({"id": candidates[0].id, "name": name})

    return resolved


def _require_not_past(target: date) -> None:
    if target < _today():
        raise RuntimeError(
            f"The date {target} is already past. Pagoda deletes every override of "
            "a past date when a rotation is updated, so the change could not be "
            "stored. Please specify today or a later date."
        )


# This is a MCP tool function
def get_tulta_my_contacts(ctx: Context = None) -> str:
    """list the Tulta contact ("Tulta連絡先") items of the authenticated user. These items identify the user as an on-call member of Tulta rotations, so this is the starting point to know which rotation the user belongs to."""
    endpoint, token = get_backend_param(ctx)

    contacts = get_tulta_myself_api(
        endpoint=endpoint,
        token=token,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps({"contacts": contacts})


def get_tulta_my_rotations(ctx: Context = None) -> str:
    """list the Tulta rotation ("Tulta輪番") items that the authenticated user belongs to, by looking for rotations whose primary rotation refers to one of the user's Tulta contact items. Each rotation corresponds to a team."""
    endpoint, token = get_backend_param(ctx)
    log_prefix = get_prefix(ctx)

    contacts = get_tulta_myself_api(
        endpoint=endpoint, token=token, log_prefix=log_prefix
    )
    if not contacts:
        return json.dumps(
            {
                "contacts": [],
                "rotations": [],
                "message": (
                    f"The authenticated user has no '{MODEL_TULTA_CONTACT}' Item, "
                    "so the rotations they belong to could not be identified. "
                    "It has to be registered at the Tulta top page of Pagoda."
                ),
            }
        )

    # This is the same chained condition that the Tulta top page sends.
    # see airone.react.custom: src/pages/TultaTopPage.tsx
    rotations = search_chain_api(
        endpoint=endpoint,
        token=token,
        entities=[MODEL_TULTA_ROTATION],
        attrs=[
            {
                "name": ATTR_PRIMARY_LAYERS,
                "attrs": [
                    {
                        "name": ATTR_UNITS,
                        "attrs": [
                            {
                                "name": ATTR_MEMBERS,
                                "value": "|".join(x["name"] for x in contacts),
                            }
                        ],
                    }
                ],
            }
        ],
        log_prefix=log_prefix,
    )

    return json.dumps(
        {
            "contacts": contacts,
            "rotations": [{"id": x.id, "name": x.name} for x in rotations],
        }
    )


def get_tulta_rotation_list(search: str = "", ctx: Context = None) -> str:
    """list all Tulta rotation ("Tulta輪番") items, optionally narrowed down by a partial match of the item name. Use this to find the rotation of a team that the user does not belong to."""
    endpoint, token = get_backend_param(ctx)
    log_prefix = get_prefix(ctx)

    rotations = get_item_list_api(
        endpoint=endpoint,
        token=token,
        model_id=get_model_id(
            endpoint=endpoint, token=token, search=MODEL_TULTA_ROTATION
        ),
        search=search,
        log_prefix=log_prefix,
    )

    return json.dumps({"rotations": [{"id": x.id, "name": x.name} for x in rotations]})


def get_tulta_rotation_schedule(
    rotation_item_id: int,
    start_date: str = "",
    end_date: str = "",
    ctx: Context = None,
) -> str:
    """get the on-call members of a Tulta rotation for each day of a term. start_date and end_date are YYYY-MM-DD; when both are omitted the current week (Monday to Sunday, JST) is used, and when only one is given that single day is used. The term must not be longer than 100 days. The result maps each date to the on-call members in their on-call order, and it covers the primary rotation ("一次対応輪番")."""
    endpoint, token = get_backend_param(ctx)

    (src, dst) = _resolve_term(start_date, end_date)
    schedule = get_tulta_rotation_terms_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        src_date=str(src),
        dst_date=str(dst),
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(
        {
            "rotation_item_id": rotation_item_id,
            "start_date": str(src),
            "end_date": str(dst),
            "schedule": schedule,
        }
    )


def get_tulta_my_schedule(
    start_date: str = "",
    end_date: str = "",
    ctx: Context = None,
) -> str:
    """get the on-call members of every Tulta rotation that the authenticated user belongs to, for each day of a term. This answers questions like "who is on call in my team this week?". start_date and end_date are YYYY-MM-DD; when both are omitted the current week (Monday to Sunday, JST) is used."""
    endpoint, token = get_backend_param(ctx)
    log_prefix = get_prefix(ctx)

    (src, dst) = _resolve_term(start_date, end_date)

    contacts = get_tulta_myself_api(
        endpoint=endpoint, token=token, log_prefix=log_prefix
    )
    if not contacts:
        return json.dumps(
            {
                "start_date": str(src),
                "end_date": str(dst),
                "rotations": [],
                "message": (
                    f"The authenticated user has no '{MODEL_TULTA_CONTACT}' Item, "
                    "so the rotations they belong to could not be identified. "
                    "It has to be registered at the Tulta top page of Pagoda."
                ),
            }
        )

    rotations = search_chain_api(
        endpoint=endpoint,
        token=token,
        entities=[MODEL_TULTA_ROTATION],
        attrs=[
            {
                "name": ATTR_PRIMARY_LAYERS,
                "attrs": [
                    {
                        "name": ATTR_UNITS,
                        "attrs": [
                            {
                                "name": ATTR_MEMBERS,
                                "value": "|".join(x["name"] for x in contacts),
                            }
                        ],
                    }
                ],
            }
        ],
        log_prefix=log_prefix,
    )

    results = []
    for rotation in rotations:
        results.append(
            {
                "id": rotation.id,
                "name": rotation.name,
                "schedule": get_tulta_rotation_terms_api(
                    endpoint=endpoint,
                    token=token,
                    rotation_item_id=rotation.id,
                    src_date=str(src),
                    dst_date=str(dst),
                    log_prefix=log_prefix,
                ),
            }
        )

    return json.dumps(
        {
            "contacts": contacts,
            "start_date": str(src),
            "end_date": str(dst),
            "rotations": results,
        }
    )


def get_tulta_rotation_detail(rotation_item_id: int, ctx: Context = None) -> str:
    """get the whole configuration of a Tulta rotation item: its layers, the units of each layer, the members of each unit and the registered overrides ("特別輪番"). Use this to see how the rotation is built before editing it."""
    endpoint, token = get_backend_param(ctx)

    rotation = get_tulta_rotation_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        log_prefix=get_prefix(ctx),
    )

    return json.dumps(rotation)


def set_tulta_rotation_override(
    rotation_item_id: int,
    target_date: str,
    member_names: list[str],
    ctx: Context = None,
) -> str:
    """override the on-call members of a Tulta rotation on a single date. target_date is YYYY-MM-DD and must not be past. member_names replaces the whole on-call list of that date in the given order; passing an empty list removes an existing override so that the date falls back to the calculated rotation. This affects the primary rotation ("一次対応輪番") only."""
    endpoint, token = get_backend_param(ctx)
    log_prefix = get_prefix(ctx)

    target = _parse_date(target_date)
    _require_not_past(target)

    rotation = get_tulta_rotation_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        log_prefix=log_prefix,
    )
    members = _resolve_members(
        endpoint=endpoint,
        token=token,
        rotation=rotation,
        names=member_names,
        log_prefix=log_prefix,
    )

    overrides = [_override_param(x) for x in rotation.get("primary_override") or []]
    current = next((x for x in overrides if x["date"] == str(target)), None)

    if current is not None:
        # An existing override Item is reused, because Pagoda refuses to register
        # another override on a date that already has one.
        # see airone: custom_view/api_v2/tulta/serializers.py
        #             (_validate_update_check)
        current["members"] = members
        # Pagoda deletes an override Item that has no member, which is exactly
        # what the "Clear" button of the UI does.
        # see airone.react.custom: src/components/TultaOverrideScheduleModal.tsx
        action = "updated" if members else "cleared"
    elif members:
        overrides.append(
            {
                "id": 0,
                "date": str(target),
                "members": members,
                # True means "replace the members of this date, and let the
                # rotation go on", which is what the UI sets when members are
                # picked on the override modal.
                "is_override_rotation": True,
            }
        )
        action = "created"
    else:
        return json.dumps(
            {
                "rotation": _rotation_summary(rotation),
                "date": str(target),
                "action": "noop",
                "message": f"There is no override on {target} to be removed.",
            }
        )

    warnings = _collect_update_warnings(rotation)
    update_tulta_rotation_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        data=_build_update_payload(rotation, overrides),
        log_prefix=log_prefix,
    )

    return json.dumps(
        {
            "rotation": _rotation_summary(rotation),
            "date": str(target),
            "action": action,
            "members": members,
            "warnings": warnings,
        }
    )


def swap_tulta_rotation_members(
    rotation_item_id: int,
    member_a: str,
    member_b: str,
    start_date: str = "",
    end_date: str = "",
    ctx: Context = None,
) -> str:
    """exchange two on-call members of a Tulta rotation within a term. Every date of the term on which member_a is on call is overridden with member_b in their place and vice versa, so the two members trade their duties. member_a and member_b are the item names of Tulta contacts. start_date and end_date are YYYY-MM-DD; when both are omitted the current week (Monday to Sunday, JST) is used, and when only one is given that single day is used. Past dates are reported as skipped because Pagoda cannot store an override for them. This affects the primary rotation ("一次対応輪番") only."""
    endpoint, token = get_backend_param(ctx)
    log_prefix = get_prefix(ctx)

    if member_a == member_b:
        raise RuntimeError("The same member was specified for both sides of the swap.")

    (src, dst) = _resolve_term(start_date, end_date)

    rotation = get_tulta_rotation_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        log_prefix=log_prefix,
    )
    schedule = get_tulta_rotation_terms_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        src_date=str(src),
        dst_date=str(dst),
        log_prefix=log_prefix,
    )

    today = _today()
    swapped = []
    skipped_past_dates = []

    for target_date in sorted(schedule.keys()):
        # The schedule of each date is the on-call members in their on-call order.
        # see airone: custom_view/api_v2/tulta/views.py
        #             (TultaRetrieveMembersWithTermAPI.list)
        before = [x["name"] for x in schedule[target_date]]
        after = [
            member_b if x == member_a else member_a if x == member_b else x
            for x in before
        ]
        if after == before:
            continue

        if _parse_date(target_date) < today:
            skipped_past_dates.append(target_date)
            continue

        swapped.append({"date": target_date, "before": before, "after": after})

    if not swapped:
        return json.dumps(
            {
                "rotation": _rotation_summary(rotation),
                "start_date": str(src),
                "end_date": str(dst),
                "swapped": [],
                "skipped_past_dates": skipped_past_dates,
                "message": (
                    f"Neither '{member_a}' nor '{member_b}' is on call between "
                    f"{src} and {dst}, so nothing was changed."
                ),
            }
        )

    # Every name is resolved at once, because one of the swapped members may not
    # belong to this rotation yet and looking it up needs the contact Item list.
    resolved = {
        x["name"]: x
        for x in _resolve_members(
            endpoint=endpoint,
            token=token,
            rotation=rotation,
            names=sorted({name for x in swapped for name in x["after"]}),
            log_prefix=log_prefix,
        )
    }

    overrides = [_override_param(x) for x in rotation.get("primary_override") or []]
    for change in swapped:
        members = [resolved[name] for name in change["after"]]
        current = next(
            (x for x in overrides if x["date"] == change["date"]),
            None,
        )
        if current is not None:
            # An existing override Item is reused, because Pagoda refuses to
            # register another override on a date that already has one.
            # see airone: custom_view/api_v2/tulta/serializers.py
            #             (_validate_update_check)
            current["members"] = members
        else:
            overrides.append(
                {
                    "id": 0,
                    "date": change["date"],
                    "members": members,
                    "is_override_rotation": True,
                }
            )

    warnings = _collect_update_warnings(rotation)
    update_tulta_rotation_api(
        endpoint=endpoint,
        token=token,
        rotation_item_id=rotation_item_id,
        data=_build_update_payload(rotation, overrides),
        log_prefix=log_prefix,
    )

    return json.dumps(
        {
            "rotation": _rotation_summary(rotation),
            "start_date": str(src),
            "end_date": str(dst),
            "swapped": swapped,
            "skipped_past_dates": skipped_past_dates,
            "warnings": warnings,
        }
    )


TULTA_LIST = [
    get_tulta_my_contacts,
    get_tulta_my_rotations,
    get_tulta_rotation_list,
    get_tulta_rotation_schedule,
    get_tulta_my_schedule,
    get_tulta_rotation_detail,
    set_tulta_rotation_override,
    swap_tulta_rotation_members,
]
