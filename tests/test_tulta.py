"""Tests for the Tulta tools.

The update endpoint of Tulta accepts only the full representation of a rotation,
so a broken payload silently drops layers, units or overrides. These tests pin
down the payload that each write tool builds, and the term that each read tool
asks for.
"""

import json
from datetime import date

import pytest

from mcp_server.drivers.pagoda import Item
from mcp_server.tools import tulta

ROTATION_NAME = "公安対魔特異4課"


def _member(item_id: int, name: str) -> dict:
    """This mimics a member of the Tulta retrieve API response."""
    return {
        "id": item_id,
        "name": name,
        "phone_number": "090-0000-0000",
        "slack_id": "@%s" % name,
        "note": "note for %s" % name,
        "absent_days": [],
    }


@pytest.fixture
def rotation() -> dict:
    """This mimics a response of GET /api/v2/custom/tulta/{entry_id}/."""
    return {
        "id": 100,
        "name": ROTATION_NAME,
        "schema": 10,
        "slack_mention": "section4",
        "keyword": "chain-saw-man",
        "annotation": "power is half devil",
        "boundary_time": "10:00",
        "primary_layers": [
            {
                "id": 200,
                "units": [
                    {
                        "id": 300,
                        "shift_days": "1",
                        "members": [_member(1, "denji"), _member(2, "power")],
                    },
                    {
                        "id": 301,
                        "shift_days": "1",
                        "members": [_member(3, "aki"), _member(4, "himeno")],
                    },
                ],
                "shift_days": "2",
                "start_date": "2026-08-01",
                "end_date": None,
                # The retrieve API returns this capitalized fallback when the
                # Attribute has no value, while the update API refuses it.
                "rotation_interval": "Custom",
            }
        ],
        "secondary_layers": [
            {
                "id": 210,
                "units": [
                    {
                        "id": 310,
                        "shift_days": "1",
                        "members": [_member(5, "makima")],
                    }
                ],
                "shift_days": "1",
                "start_date": "2026-08-01",
                "end_date": "2026-12-31",
                "rotation_interval": "daily",
            }
        ],
        "primary_override": [],
        "secondary_override": [
            {
                "id": 400,
                "date": "2026-09-01",
                "members": [_member(6, "kishibe")],
                "is_override_rotation": True,
            }
        ],
    }


class FakePagoda:
    """This records what the tools send to Pagoda, and replays fixed responses."""

    def __init__(self, rotation: dict, schedule: dict | None = None):
        self.rotation = rotation
        self.schedule = schedule or {}
        self.updated: list[dict] = []

    def install(self, monkeypatch, today: date):
        monkeypatch.setattr(tulta, "_today", lambda: today)
        monkeypatch.setattr(
            tulta, "get_backend_param", lambda ctx=None: ("https://pagoda", "token")
        )
        monkeypatch.setattr(
            tulta, "get_tulta_rotation_api", lambda **kwargs: self.rotation
        )
        monkeypatch.setattr(
            tulta, "get_tulta_rotation_terms_api", lambda **kwargs: self.schedule
        )
        monkeypatch.setattr(
            tulta,
            "update_tulta_rotation_api",
            lambda **kwargs: self.updated.append(kwargs["data"]) or {},
        )
        # No tool under test may fall back to the whole contact Item list, because
        # every member it handles is already referred to by the rotation.
        monkeypatch.setattr(
            tulta,
            "get_item_list_api",
            lambda **kwargs: pytest.fail("The contact Items must not be listed"),
        )


def test_resolve_term_defaults_to_the_week_of_today(monkeypatch):
    # 2026-08-26 is a Wednesday, and Tulta orders weekdays from Monday
    monkeypatch.setattr(tulta, "_today", lambda: date(2026, 8, 26))

    assert tulta._resolve_term("", "") == (date(2026, 8, 24), date(2026, 8, 30))


def test_resolve_term_with_a_single_date():
    assert tulta._resolve_term("2026-08-26", "") == (
        date(2026, 8, 26),
        date(2026, 8, 26),
    )
    assert tulta._resolve_term("", "2026-08-26") == (
        date(2026, 8, 26),
        date(2026, 8, 26),
    )


def test_resolve_term_with_invalid_parameters():
    for start_date, end_date, message in [
        ("2026-08-26", "invalid", "Invalid date"),
        ("2026-08-26", "2026-08-25", "earlier than the start date"),
        ("2026-01-01", "2026-12-31", "longest term"),
    ]:
        with pytest.raises(RuntimeError, match=message):
            tulta._resolve_term(start_date, end_date)


def test_build_update_payload_carries_everything_over(rotation):
    payload = tulta._build_update_payload(rotation, primary_override=[])

    # The update API refuses a changed name, and clears every parameter that is
    # not sent, so all of them have to be carried over.
    assert payload["name"] == ROTATION_NAME
    assert payload["slack_mention"] == "section4"
    assert payload["keyword"] == "chain-saw-man"
    assert payload["annotation"] == "power is half devil"
    assert payload["boundary_time"] == "10:00"

    assert payload["primary_layers"] == [
        {
            "id": 200,
            "shift_days": "2",
            "start_date": "2026-08-01",
            # The capitalized fallback of the retrieve API is normalized here
            "rotation_interval": "custom",
            "will_delete": False,
            "units": [
                {
                    "id": 300,
                    "shift_days": "1",
                    "will_delete": False,
                    "members": [
                        {"id": 1, "name": "denji"},
                        {"id": 2, "name": "power"},
                    ],
                },
                {
                    "id": 301,
                    "shift_days": "1",
                    "will_delete": False,
                    "members": [
                        {"id": 3, "name": "aki"},
                        {"id": 4, "name": "himeno"},
                    ],
                },
            ],
        }
    ]
    # A null end date is left out, and an existing one is kept
    assert "end_date" not in payload["primary_layers"][0]
    assert payload["secondary_layers"][0]["end_date"] == "2026-12-31"

    # The secondary rotation is not touched by these tools, but it must survive
    assert payload["secondary_override"] == [
        {
            "id": 400,
            "date": "2026-09-01",
            "members": [{"id": 6, "name": "kishibe"}],
            "is_override_rotation": True,
        }
    ]


def test_set_override_creates_a_new_override(monkeypatch, rotation):
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.set_tulta_rotation_override(
            rotation_item_id=100,
            target_date="2026-08-26",
            member_names=["aki", "denji"],
        )
    )

    assert result["action"] == "created"
    assert fake.updated[0]["primary_override"] == [
        {
            "id": 0,
            "date": "2026-08-26",
            "members": [{"id": 3, "name": "aki"}, {"id": 1, "name": "denji"}],
            "is_override_rotation": True,
        }
    ]


def test_set_override_reuses_an_existing_override_of_the_same_date(
    monkeypatch, rotation
):
    # Pagoda refuses to register another override on a date that already has one,
    # so the id of the existing Item has to be reused.
    rotation["primary_override"] = [
        {
            "id": 401,
            "date": "2026-08-26",
            "members": [_member(1, "denji")],
            "is_override_rotation": True,
        }
    ]
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.set_tulta_rotation_override(
            rotation_item_id=100,
            target_date="2026-08-26",
            member_names=["power"],
        )
    )

    assert result["action"] == "updated"
    assert fake.updated[0]["primary_override"] == [
        {
            "id": 401,
            "date": "2026-08-26",
            "members": [{"id": 2, "name": "power"}],
            "is_override_rotation": True,
        }
    ]


def test_set_override_clears_an_existing_override(monkeypatch, rotation):
    rotation["primary_override"] = [
        {
            "id": 401,
            "date": "2026-08-26",
            "members": [_member(1, "denji")],
            "is_override_rotation": True,
        }
    ]
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.set_tulta_rotation_override(
            rotation_item_id=100,
            target_date="2026-08-26",
            member_names=[],
        )
    )

    # Pagoda deletes an override Item that has no member
    assert result["action"] == "cleared"
    assert fake.updated[0]["primary_override"][0]["members"] == []


def test_set_override_refuses_a_past_date(monkeypatch, rotation):
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    with pytest.raises(RuntimeError, match="already past"):
        tulta.set_tulta_rotation_override(
            rotation_item_id=100,
            target_date="2026-08-23",
            member_names=["denji"],
        )

    assert fake.updated == []


def test_set_override_does_nothing_for_an_unregistered_date(monkeypatch, rotation):
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.set_tulta_rotation_override(
            rotation_item_id=100,
            target_date="2026-08-26",
            member_names=[],
        )
    )

    assert result["action"] == "noop"
    assert fake.updated == []


def test_swap_members_overrides_only_the_affected_days(monkeypatch, rotation):
    schedule = {
        # denji is on call, so aki takes their place
        "2026-08-24": [{"name": "denji", "order": 1}, {"name": "power", "order": 2}],
        # aki is on call, so denji takes their place
        "2026-08-25": [{"name": "aki", "order": 1}, {"name": "himeno", "order": 2}],
        # both of them are on call, so they trade their order
        "2026-08-26": [{"name": "denji", "order": 1}, {"name": "aki", "order": 2}],
        # neither of them is on call, so this day is left alone
        "2026-08-27": [{"name": "power", "order": 1}, {"name": "himeno", "order": 2}],
    }
    fake = FakePagoda(rotation, schedule)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100,
            member_a="denji",
            member_b="aki",
            start_date="2026-08-24",
            end_date="2026-08-27",
        )
    )

    assert [x["date"] for x in result["swapped"]] == [
        "2026-08-24",
        "2026-08-25",
        "2026-08-26",
    ]
    assert result["swapped"][0]["after"] == ["aki", "power"]
    assert fake.updated[0]["primary_override"] == [
        {
            "id": 0,
            "date": "2026-08-24",
            "members": [{"id": 3, "name": "aki"}, {"id": 2, "name": "power"}],
            "is_override_rotation": True,
        },
        {
            "id": 0,
            "date": "2026-08-25",
            "members": [{"id": 1, "name": "denji"}, {"id": 4, "name": "himeno"}],
            "is_override_rotation": True,
        },
        {
            "id": 0,
            "date": "2026-08-26",
            "members": [{"id": 3, "name": "aki"}, {"id": 1, "name": "denji"}],
            "is_override_rotation": True,
        },
    ]


def test_swap_members_skips_past_days(monkeypatch, rotation):
    schedule = {
        "2026-08-23": [{"name": "denji", "order": 1}],
        "2026-08-24": [{"name": "denji", "order": 1}],
    }
    fake = FakePagoda(rotation, schedule)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100,
            member_a="denji",
            member_b="aki",
            start_date="2026-08-23",
            end_date="2026-08-24",
        )
    )

    assert result["skipped_past_dates"] == ["2026-08-23"]
    assert [x["date"] for x in result["swapped"]] == ["2026-08-24"]
    assert len(fake.updated[0]["primary_override"]) == 1


def test_swap_members_does_nothing_when_neither_is_on_call(monkeypatch, rotation):
    schedule = {"2026-08-24": [{"name": "makima", "order": 1}]}
    fake = FakePagoda(rotation, schedule)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    result = json.loads(
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100,
            member_a="denji",
            member_b="aki",
            start_date="2026-08-24",
            end_date="2026-08-24",
        )
    )

    assert result["swapped"] == []
    assert fake.updated == []


def test_swap_members_looks_up_an_outsider_only_once(monkeypatch, rotation):
    """A member that the rotation does not refer to yet has to be looked up.

    The lookup needs the whole Tulta contact Item list, so it must not be
    repeated for every affected date.
    """
    schedule = {
        "2026-08-24": [{"name": "denji", "order": 1}],
        "2026-08-25": [{"name": "denji", "order": 1}],
    }
    fake = FakePagoda(rotation, schedule)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    calls = []
    monkeypatch.setattr(
        tulta, "get_model_id", lambda **kwargs: calls.append(kwargs["search"]) or 20
    )
    monkeypatch.setattr(
        tulta,
        "get_item_list_api",
        lambda **kwargs: [Item(id=9, name="kobeni", schema={"id": 20, "name": "x"})],
    )

    result = json.loads(
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100,
            member_a="denji",
            member_b="kobeni",
            start_date="2026-08-24",
            end_date="2026-08-25",
        )
    )

    assert calls == [tulta.MODEL_TULTA_CONTACT]
    assert [x["after"] for x in result["swapped"]] == [["kobeni"], ["kobeni"]]
    assert [x["members"] for x in fake.updated[0]["primary_override"]] == [
        [{"id": 9, "name": "kobeni"}],
        [{"id": 9, "name": "kobeni"}],
    ]


def test_swap_members_reports_an_unknown_member(monkeypatch, rotation):
    schedule = {"2026-08-24": [{"name": "denji", "order": 1}]}
    fake = FakePagoda(rotation, schedule)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    monkeypatch.setattr(tulta, "get_model_id", lambda **kwargs: 20)
    monkeypatch.setattr(tulta, "get_item_list_api", lambda **kwargs: [])

    with pytest.raises(RuntimeError, match="named 'nobody'"):
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100,
            member_a="denji",
            member_b="nobody",
            start_date="2026-08-24",
            end_date="2026-08-24",
        )

    assert fake.updated == []


def test_swap_members_refuses_the_same_member(monkeypatch, rotation):
    fake = FakePagoda(rotation)
    fake.install(monkeypatch, today=date(2026, 8, 24))

    with pytest.raises(RuntimeError, match="same member"):
        tulta.swap_tulta_rotation_members(
            rotation_item_id=100, member_a="denji", member_b="denji"
        )


def test_update_warnings_report_what_pagoda_drops(monkeypatch, rotation):
    rotation["primary_override"] = [
        # an override of a past date is deleted by Pagoda on every update
        {
            "id": 401,
            "date": "2026-08-01",
            "members": [_member(1, "denji")],
            "is_override_rotation": True,
        },
        # an override without member is deleted by Pagoda as well
        {
            "id": 402,
            "date": "2026-08-30",
            "members": [],
            "is_override_rotation": False,
        },
    ]
    monkeypatch.setattr(tulta, "_today", lambda: date(2026, 8, 24))

    warnings = tulta._collect_update_warnings(rotation)

    assert len(warnings) == 2
    assert "2026-08-01" in warnings[0] and "already past" in warnings[0]
    assert "2026-08-30" in warnings[1] and "no member" in warnings[1]
