from typing import Callable, Type

from mcp.types import PromptArgument
from pydantic import BaseModel


class PagodaCert(BaseModel):
    endpoint: str
    token: str


class PromptHandler(BaseModel):
    handler: Callable
    desc: str
    args: list[PromptArgument]


class ToolHandler(BaseModel):
    handler: Callable
    desc: str
    input_schema: Type[BaseModel]
