"""Who is calling a tool.

The runtime builds a ToolContext for every call: the MCP server from its environment today,
the agent runtime from the conversation later. It is never built from a model's arguments,
so a model cannot choose which store it acts on or who it acts as.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class ToolContext:
    store_id: UUID
    actor: Literal["owner", "shopper", "agent"]
    agent: str | None = None  # "support", "copy_seo", ...
    conversation_id: UUID | None = None
