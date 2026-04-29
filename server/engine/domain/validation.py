"""Pydantic models for validating game data at load time."""
from pydantic import BaseModel, Field
from typing import Optional


class RoomModel(BaseModel):
    id: str
    name: str
    description: str
    zone: str = "default"
    room_type: str = "indoor"
    base_temp_f: int = 70
    exits: dict[str, str] = {}
    items: list[str] = []
    is_campfire: bool = False
    recruitable_npc_ids: list[str] = []


class ItemModel(BaseModel):
    id: str
    name: str
    type: str
    weight: int = 0
    value: int = 0
    description: str = ""
    effect_type: Optional[str] = None
    effect_params: dict = {}


class NPCModel(BaseModel):
    template_id: str
    name: str
    class_type: str = "warrior"
    level: int = 1
    hp: int = 10
    max_hp: int = 10
    is_recruitable: bool = False
    darkvision: bool = False
