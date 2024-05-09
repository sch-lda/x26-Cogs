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

from defender.enums import EmergencyMode
from ..abc import MixinMeta, CompositeMetaClass
from ..enums import Rank
from ..core.status import make_status
from ..core.cache import UserCacheConverter
from ..core.utils import utcnow
from ..exceptions import ExecutionError, InvalidRule
from ..core.announcements import get_announcements_embed
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.chat_formatting import error, pagify, box, inline, escape
from redbot.core import commands
from io import BytesIO
from inspect import cleandoc
from typing import Union
import emoji, pydantic, regex, yaml, sys, rapidfuzz # Debug info purpose
import logging
import asyncio
import fnmatch
import discord
import datetime
import tarfile

log = logging.getLogger("red.x26cogs.defender")

class StaffTools(MixinMeta, metaclass=CompositeMetaClass): # type: ignore

    @commands.group(aliases=["def"])
    @commands.guild_only()
    @commands.mod()
    async def defender(self, ctx: commands.Context):
        """Defender commands reserved to staff"""

    @defender.command(name="status")
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    async def defenderstatus(self, ctx: commands.Context):
        """Shows overall status of the Defender system"""
        pages = await make_status(ctx, self)
        await menu(ctx, pages, DEFAULT_CONTROLS)

    @defender.command(name="monitor")
    async def defendermonitor(self, ctx: commands.Context, *, keywords: str=""):
        """Shows recent events that might require your attention

        Can be filtered. Supports wildcards (* and ?)"""
        monitor = self.monitor[ctx.guild.id].copy()

        if not monitor:
            return await ctx.send("No recent events have been recorded.")

        if keywords:
            if "*" not in keywords and "?" not in keywords:
                keywords = f"*{keywords}*"
            keywords = keywords.lower()
            monitor = [e for e in monitor if fnmatch.fnmatch(e.lower(), keywords)]
            if not monitor:
                return await ctx.send("Filtering by those terms returns no result.")

        pages = list(pagify("\n".join(monitor), page_length=1300))

        if len(pages) == 1:
            await ctx.send(box(pages[0], lang="rust"))
        else:
            pages = [box(p, lang="rust") for p in pages]
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @defender.group(name="messages", aliases=["msg"])
    async def defmessagesgroup(self, ctx: commands.Context):
        """Access recorded messages of users / channels"""

    @defmessagesgroup.command(name="user")
    async def defmessagesgroupuser(self, ctx: commands.Context, user: UserCacheConverter):
        """Shows recent messages of a user"""
        author = ctx.author

        pages = await self.make_message_log(user, guild=author.guild, requester=author, pagify_log=True,
                                            replace_backtick=True)

        if not pages:
            return await ctx.send("No messages recorded for that user.")

        self.send_to_monitor(ctx.guild, f"{author} ({author.id}) accessed message history "
                                        f"of user {user} ({user.id})")

        if len(pages) == 1:
            await ctx.send(box(pages[0], lang="md"))
        else:
            pages = [box(p, lang="md") for p in pages]
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @defmessagesgroup.command(name="channel")
    async def defmessagesgroupuserchannel(self, ctx: commands.Context, channel: Union[discord.TextChannel, discord.Thread]):
        """Shows recent messages of a channel"""
        author = ctx.author
        if not channel.permissions_for(author).read_messages:
            self.send_to_monitor(ctx.guild, f"{author} ({author.id}) attempted to access the message "
                                            f"history of channel #{channel.name}")
            return await ctx.send("You do not have read permissions in that channel. Request denied.")

        pages = await self.make_message_log(channel, guild=author.guild, requester=author, pagify_log=True,
                                            replace_backtick=True)

        if not pages:
            return await ctx.send("No messages recorded in that channel.")

        self.send_to_monitor(ctx.guild, f"{author} ({author.id}) accessed the message history "
                                        f"of channel #{channel.name}")

        if len(pages) == 1:
            await ctx.send(box(pages[0], lang="md"))
        else:
            pages = [box(p, lang="md") for p in pages]
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @defmessagesgroup.command(name="exportuser")
    async def defmessagesgroupexportuser(self, ctx: commands.Context, user: UserCacheConverter):
        """Exports recent messages of a user to a file"""
        author = ctx.author

        _log = await self.make_message_log(user, guild=author.guild, requester=author)

        if not _log:
            return await ctx.send("No messages recorded for that user.")

        self.send_to_monitor(ctx.guild, f"{author} ({author.id}) exported message history "
                                        f"of user {user} ({user.id})")

        ts = utcnow().strftime("%Y-%m-%d")
        _log = "\n".join(_log)
        f = discord.File(BytesIO(_log.encode("utf-8")), f"{ts}-{user.id}.txt")

        await ctx.send(file=f)

    @defmessagesgroup.command(name="exportchannel")
    async def defmessagesgroupuserexportchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Exports recent messages of a channel to a file"""
        author = ctx.author
        if not channel.permissions_for(author).read_messages:
            return await ctx.send("You do not have read permissions in that channel. Request denied.")

        _log = await self.make_message_log(channel, guild=author.guild, requester=author)

        if not _log:
            return await ctx.send("No messages recorded in that channel.")

        self.send_to_monitor(ctx.guild, f"{author} ({author.id}) exported message history "
                                        f"of channel #{channel.name}")

        ts = utcnow().strftime("%Y-%m-%d")
        _log = "\n".join(_log)
        f = discord.File(BytesIO(_log.encode("utf-8")), f"{ts}-#{channel.name}.txt")

        await ctx.send(file=f)

    @defender.command(name="memberranks")
    async def defendermemberranks(self, ctx: commands.Context):
        """Counts how many members are in each rank"""
        ranks = {
            Rank.Rank1: 0,
            Rank.Rank2: 0,
            Rank.Rank3: 0,
            Rank.Rank4: 0,
        }

        async with ctx.typing():
            async for m in AsyncIter(ctx.guild.members, steps=2):
                if m.bot:
                    continue
                if m.joined_at is None:
                    continue
                rank = await self.rank_user(m)
                ranks[rank] += 1
        await ctx.send(box(f"Rank1: {ranks[Rank.Rank1]}\nRank2: {ranks[Rank.Rank2]}\n"
                    f"Rank3: {ranks[Rank.Rank3]}\nRank4: {ranks[Rank.Rank4]}\n\n"
                    f"For details about each rank see {ctx.prefix}defender status",
                    lang="yaml"))

    @defender.command(name="identify")
    @commands.bot_has_permissions(embed_links=True)
    async def defenderidentify(self, ctx, *, user: discord.Member):
        """Shows a member's rank + info"""
        em = await self.make_identify_embed(ctx.message, user)
        await ctx.send(embed=em)

    @defender.command(name="freshmeat")
    async def defenderfreshmeat(self, ctx, hours: int=24, *, keywords: str=""):
        """Returns a list of the new users of the day

        Can be filtered. Supports wildcards (* and ?)"""
        keywords = keywords.lower()
        msg = ""
        new_members = []
        x_hours_ago = ctx.message.created_at - datetime.timedelta(hours=hours)
        for m in ctx.guild.members:
            if m.joined_at is not None and m.joined_at > x_hours_ago:
                new_members.append(m)

        new_members.sort(key=lambda m: m.joined_at, reverse=True)

        if keywords:
            if "*" not in keywords and "?" not in keywords:
                keywords = f"*{keywords}*"
            keywords = keywords.lower()

        for m in new_members:
            if keywords:
                if not fnmatch.fnmatch(m.name.lower(), keywords):
                    continue
            join = m.joined_at.strftime("%Y/%m/%d %H:%M:%S")
            created = m.created_at.strftime("%Y/%m/%d %H:%M:%S")
            msg += f"J/C: {join}  {created} | {m.id} | {m}\n"

        pages = []
        for p in pagify(msg, delims=["\n"], page_length=1500):
            pages.append(box(p, lang="go"))

        if pages:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        else:
            await ctx.send("Nothing to show.")

    @defender.command(name="notifynew")
    async def defendernotifynew(self, ctx: commands.Context, hours: int):
        """Sends you a DM if a user younger than X hours joins

        Use 0 hours to disable notifications"""
        if hours < 0 or hours > 744: # I think a month is enough
            await ctx.send("Value must be between 1 and 744.")
            return

        await self.config.member(ctx.author).join_monitor_susp_hours.set(hours)
        async with self.config.guild(ctx.guild).join_monitor_susp_subs() as subs:
            if hours:
                if ctx.author.id not in subs:
                    subs.append(ctx.author.id)
            else:
                if ctx.author.id in subs:
                    subs.remove(ctx.author.id)

        await ctx.tick()

    @defender.command(name="emergency")
    async def defenderemergency(self, ctx: commands.Context, on_or_off: bool):
        """Manually engage or turn off emergency mode

        Upon activation, staff will be pinged and any module
        that is set to be active in emergency mode will be rendered
        available to helpers"""
        guild = ctx.guild
        author = ctx.author
        d_enabled = await self.config.guild(guild).enabled()
        if not d_enabled:
            return await ctx.send("Defender is currently not operational.")
        modules = await self.config.guild(ctx.guild).emergency_modules()
        if not modules:
            return await ctx.send("Emergency mode is disabled in this server.")

        alert_msg = (f"⚠️ Emergency mode manually engaged by `{author}` ({author.id}).\n"
                     f"The modules **{', '.join(modules)}** can now be used by "
                     "helper roles. To turn off emergency mode do "
                     f"`{ctx.prefix}defender emergency off`. Good luck.")
        emergency_mode = self.is_in_emergency_mode(guild)

        if on_or_off:
            if not emergency_mode:
                self.emergency_mode[guild.id] = EmergencyMode(manual=True)
                await self.send_notification(guild, alert_msg, title="Emergency mode",
                                             ping=True, jump_to=ctx.message)
                self.dispatch_event("emergency", guild)
            else:
                await ctx.send("Emergency mode is already ongoing.")
        else:
            if emergency_mode:
                del self.emergency_mode[guild.id]
                await self.send_notification(guild, "⚠️ Emergency mode manually disabled.",
                                             title="Emergency mode", jump_to=ctx.message)
            else:
                await ctx.send("Emergency mode is already off.")

    @defender.command(name="updates")
    async def defendererupdates(self, ctx: commands.Context):
        """Shows all the past announcements of Defender"""
        announcements = get_announcements_embed(only_recent=False)
        if announcements:
            announcements = list(announcements.values())
            await menu(ctx, announcements, DEFAULT_CONTROLS)
        else:
            await ctx.send("Nothing to show.")

