from typing import Literal

from pydantic import BaseModel, Field


class ModelList(BaseModel):
    search: str = ""


class ModelDetailInput(BaseModel):
    model_id: int


class ItemList(BaseModel):
    model_id: int
    search: str = ""


class ItemAttribute(BaseModel):
    attrname: str
    value: str


class ItemDetailInput(BaseModel):
    item_id: int


class SearchItem(BaseModel):
    query: str


class AdvancedSearchAttrInfo(BaseModel):
    name: str = Field(description="Attribute names can be checked in the Model Details tool.")
    filter_key: Literal[0, 1, 2, 3, 4, 5] = Field(
        default=0,
        description="0=CLEARED, 1=EMPTY, 2=NON_EMPTY, 3=TEXT_CONTAINED, 4=TEXT_NOT_CONTAINED, 5=DUPLICATED",
    )
    keyword: str = Field(
        default="",
        description="""
Narrow search by keywords.
can use pipes to perform or searches. e.g. 'hoge|fuga'
maximum length is 249 characters, so if it have more than that, please split it up and execute it.
""",
    )


class AdvancedSearch(BaseModel):
    entities: list[int] = Field(
        description="List of ModelID, can be checked in the Model List tool."
    )
    attrinfo: list[AdvancedSearchAttrInfo]
    item_filter_key: Literal[0, 1, 2] = Field(
        default=0,
        description="""Narrow down the search by item name
0=CLEARED, 1=TEXT_CONTAINED, 2=TEXT_NOT_CONTAINED
""",
    )
    item_keyword: str = Field(
        default="",
        description="""Narrow down the search by item name.
can use pipes to perform or searches. e.g. 'hoge|fuga'
maximum length is 249 characters, so if it have more than that, please split it up and execute it.
""",
    )
    has_referral: bool = Field(
        default=False,
        description="If true, the search result will include a referral item.",
    )
    referral_name: str = Field(
        default="",
        description="Narrow down the referrer items.",
    )
    limit: int = 100
    offset: int = 0
