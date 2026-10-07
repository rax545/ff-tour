"""Private Discord squad rooms with persisted channel IDs and roster synchronization."""

import asyncio

import discord

from config import GUILD_ID, STAFF_ROLE_IDS
from database.db import audit, connect


class WarRoomService:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def team(self, team_id, actor):
        from utils.permissions import staff

        db = await connect()
        try:
            cur = await db.execute("SELECT * FROM teams WHERE id=?", (team_id,))
            team = await cur.fetchone()
            if not team:
                raise ValueError("Squad not found.")
            if team["captain_id"] != actor.id and not staff(actor):
                raise ValueError("Only the captain or staff can manage this squad room.")
            cur = await db.execute(
                "SELECT user_id FROM team_members WHERE team_id=? AND user_id>0", (team_id,)
            )
            ids = {r["user_id"] for r in await cur.fetchall()} | {team["captain_id"]}
            return dict(team), ids
        finally:
            await db.close()

    async def overwrites(self, guild, ids):
        rules = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                attach_files=True,
                embed_links=True,
                connect=True,
                speak=True,
            ),
        }
        for user_id in ids:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    continue
            rules[member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                connect=True,
                speak=True,
            )
        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role and role != guild.default_role:
                rules[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    connect=True,
                    speak=True,
                )
        return rules

    async def resolve_channel(self, guild, channel_id, channel_type):
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.NotFound:
                return None
        if channel.guild.id != guild.id or not isinstance(channel, channel_type):
            raise ValueError(
                "Saved war room channel has an unexpected type or server. Contact staff."
            )
        return channel

    async def manage(self, guild, actor, team_id, close=False):
        if GUILD_ID and guild.id != GUILD_ID:
            raise ValueError("Manage squad rooms in the configured tournament server.")
        # Serialize creation/close locally so repeated clicks cannot create orphan rooms.
        async with self.lock:
            team, ids = await self.team(team_id, actor)
            db = await connect()
            created = []
            try:
                cur = await db.execute(
                    "SELECT * FROM war_rooms WHERE guild_id=? AND team_id=?", (guild.id, team_id)
                )
                saved = await cur.fetchone()
                text = (
                    await self.resolve_channel(guild, saved["text_channel_id"], discord.TextChannel)
                    if saved
                    else None
                )
                voice = (
                    await self.resolve_channel(
                        guild, saved["voice_channel_id"], discord.VoiceChannel
                    )
                    if saved
                    else None
                )
                if close:
                    if not saved:
                        raise ValueError("No squad war room exists.")
                    for channel in (text, voice):
                        if channel:
                            try:
                                await channel.delete(
                                    reason=f"Squad {team_id} war room closed by {actor.id}"
                                )
                            except discord.NotFound:
                                pass
                    await db.execute(
                        "DELETE FROM war_rooms WHERE guild_id=? AND team_id=?", (guild.id, team_id)
                    )
                    await db.commit()
                    result = None
                else:
                    rules = await self.overwrites(guild, ids)
                    reason = f"Squad {team_id} war room managed by {actor.id}"
                    # No shared category: each channel carries explicit private overwrites.
                    if text:
                        await text.edit(overwrites=rules, reason=reason)
                    else:
                        text = await guild.create_text_channel(
                            f"squad-{team_id}-war-room", overwrites=rules, reason=reason
                        )
                        created.append(text)
                    if voice:
                        await voice.edit(overwrites=rules, reason=reason)
                    else:
                        voice = await guild.create_voice_channel(
                            f"Squad {team_id} • War Room", overwrites=rules, reason=reason
                        )
                        created.append(voice)
                    await db.execute(
                        """INSERT INTO war_rooms(guild_id,team_id,text_channel_id,voice_channel_id,created_by)
                        VALUES(?,?,?,?,?) ON CONFLICT(guild_id,team_id) DO UPDATE SET
                        text_channel_id=excluded.text_channel_id, voice_channel_id=excluded.voice_channel_id""",
                        (guild.id, team_id, text.id, voice.id, actor.id),
                    )
                    await db.commit()
                    result = (text, voice)
            except Exception:
                # If rollback deletion fails, retain the ID so a retry reconciles
                # the partial room instead of leaking an untracked duplicate.
                retained = {}
                for channel in created:
                    try:
                        await channel.delete(reason="Rollback incomplete war room creation")
                    except discord.NotFound:
                        pass
                    except discord.HTTPException:
                        retained[
                            "text" if isinstance(channel, discord.TextChannel) else "voice"
                        ] = channel.id
                if retained:
                    await db.execute(
                        """INSERT INTO war_rooms(guild_id,team_id,text_channel_id,voice_channel_id,created_by)
                        VALUES(?,?,?,?,?) ON CONFLICT(guild_id,team_id) DO UPDATE SET
                        text_channel_id=excluded.text_channel_id, voice_channel_id=excluded.voice_channel_id""",
                        (
                            guild.id,
                            team_id,
                            retained.get("text", saved["text_channel_id"] if saved else 0),
                            retained.get("voice", saved["voice_channel_id"] if saved else 0),
                            actor.id,
                        ),
                    )
                    await db.commit()
                raise
            finally:
                await db.close()
            await audit(
                actor.id, "war_room_close" if close else "war_room_sync", f"{guild.id}:{team_id}"
            )
            return result
