"""
Defender - Protects your community with automod features and
           empowers the staff and users you trust with
           advanced moderation tools
Copyright (C) 2020-present  Twentysix (https://github.com/Twentysix26/)
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import discord
from datetime import datetime

TITLE_TEXT = "Defender update"
FOOTER_TEXT = "\n\n*- Twentysix, creator of Defender*"
REPO_LINK = "https://github.com/Twentysix26/x26-Cogs"
SOCIALS = "\n\n[`x26.it`](https://x26.it) - [`Support me!`](https://www.patreon.com/Twentysix26)"
TAG = FOOTER_TEXT + SOCIALS
ANNOUNCEMENTS = {}


def _make_announcement_embed(content):
    return discord.Embed(color=discord.Colour.red(), title=TITLE_TEXT, description=content)


def get_announcements_text(*, only_recent=True):
    to_send = {}
    now = datetime.utcnow()

    for k, v in ANNOUNCEMENTS.items():
        ts = datetime.utcfromtimestamp(k)
        if only_recent is True and now > ts:  # The announcement is old
            continue
        to_send[k] = {"title": TITLE_TEXT, "description": v + TAG}

    return to_send


def get_announcements_embed(*, only_recent=True):
    to_send = {}
    now = datetime.utcnow()

    for k, v in ANNOUNCEMENTS.items():
        ts = datetime.utcfromtimestamp(k)
        if only_recent is True and now > ts:  # The announcement is old
            continue
        to_send[k] = _make_announcement_embed(v + TAG)

    return to_send
