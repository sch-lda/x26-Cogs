"""In-memory expiry counters used for repeated-event throttling."""

import asyncio
from collections import defaultdict, deque
from datetime import timedelta
from typing import Union

import discord

from .utils import utcnow


MAX_HEATPOINTS = 100
_heat_store: dict[int, dict[str, "HeatLevel"]] = defaultdict(dict)


class HeatLevel:
    __slots__ = ("guild_id", "key", "_heat_points")

    def __init__(self, guild_id: int, key: Union[str, int]):
        self.guild_id = guild_id
        self.key = str(key)
        self._heat_points = deque(maxlen=MAX_HEATPOINTS)

    def increase(self, duration: timedelta):
        self._heat_points.append(utcnow() + duration)

    def _expire(self):
        now = utcnow()
        self._heat_points = deque((point for point in self._heat_points if point > now), maxlen=MAX_HEATPOINTS)

    def __len__(self):
        self._expire()
        count = len(self._heat_points)
        if not count:
            _heat_store[self.guild_id].pop(self.key, None)
        return count


def get_custom_heat(guild: discord.Guild, key: str) -> int:
    key = key.lower()
    level = _heat_store[guild.id].get(key)
    return len(level) if level else 0


def increase_custom_heat(guild: discord.Guild, key: str, duration: timedelta):
    key = key.lower()
    level = _heat_store[guild.id].get(key)
    if level is None:
        level = _heat_store[guild.id][key] = HeatLevel(guild.id, key)
    level.increase(duration)


async def remove_stale_heat():
    for guild_store in list(_heat_store.values()):
        for level in list(guild_store.values()):
            len(level)
        await asyncio.sleep(0)
