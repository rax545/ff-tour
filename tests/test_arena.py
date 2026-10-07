import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from PIL import Image
import database.db as database
from services.arena import (validate_stream_url, player_passport, issue_certificate,
                            verify_certificate, revoke_certificate, stream_status)
from services.war_rooms import WarRoomService
from utils.cards import passport, certificate, slot_grid
from utils.permissions import staff


class ValidationTests(unittest.TestCase):
    def test_stream_urls(self):
        self.assertEqual(validate_stream_url(' https://youtu.be/abc '), 'https://youtu.be/abc')
        for url in ('javascript:alert(1)', 'https://', 'https://user:pass@youtube.com',
                    'https://you tube.com', 'https://youtube.com:bad', 'https://[invalid',
                    'https://youtube.com:1234', 'https://youtube.com/\nabc', 'https://'+'a'*520+'.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_stream_url(url)

    def test_staff(self):
        member = MagicMock(spec=discord.Member)
        member.guild_permissions.administrator = False
        role = MagicMock()
        role.id = 123
        member.roles = [role]
        with patch('utils.permissions.STAFF_ROLE_IDS', {123,456}):
            self.assertTrue(staff(member))
            role.id = 789
            self.assertFalse(staff(member))
        self.assertFalse(staff(MagicMock(spec=discord.User)))
        member.guild_permissions.administrator = True
        self.assertTrue(staff(member))

    def test_graphics(self):
        row = {'ign':'Player','uid':'123','role':'IGL','team_name':'Wolves'}
        stats = {'kills':7,'damage':200,'matches':1}
        cert = {'tournament_name':'Cup','recipient_name':'Player','award':'Champion',
                'team_name':'Wolves','issued_at':'2026-10-07','code':'RLU-ABC'}
        for buf,size in [(passport('Player',[row],stats),(1200,720)),
                         (certificate(cert),(1600,1000)),
                         (slot_grid('Cup',[{'name':'Wolves','tag':'W'}],25,2),(1440,1000))]:
            image = Image.open(io.BytesIO(buf.getvalue()))
            self.assertEqual(image.size,size)
            self.assertEqual(image.format,'PNG')
        with self.assertRaises(ValueError):
            slot_grid('Cup',[],24,2)


class ArenaDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(database, 'DATABASE_PATH', str(Path(self.tmp.name)/'arena.sqlite3'))
        self.path_patch.start()
        await database.init_db()
        db = await database.connect()
        await db.executescript('''
            INSERT INTO tournaments(id,name) VALUES(1,'Cup'),(2,'Other');
            INSERT INTO teams(id,tournament_id,name,tag,captain_id) VALUES(1,1,'Wolves','W',10);
            INSERT INTO team_members(team_id,user_id,ign,uid,role) VALUES(1,11,'Player','123','IGL');
            INSERT INTO matches(id,tournament_id,match_no,stream_url,stream_live)
                VALUES(1,1,1,'https://youtu.be/abc',1),(2,1,2,'',0);
            INSERT INTO player_results(match_id,team_id,ign,uid,kills,damage,verified)
                VALUES(1,1,'Player','123',7,200,1),(2,1,'Player','123',50,200,0);
            INSERT INTO results(match_id,team_id,placement,kills,verified) VALUES(1,1,1,100,1);
        ''')
        await db.commit()
        await db.close()

    async def asyncTearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    async def test_passport_private_stats(self):
        rosters,stats,student = await player_passport(11)
        self.assertEqual(stats, {'kills':7,'damage':200,'matches':1})
        self.assertEqual(len(rosters),1)
        self.assertIsNone(student)
        db = await database.connect()
        await db.execute("INSERT INTO team_members(team_id,user_id,ign,uid) VALUES(1,11,'Player','123')")
        await db.commit()
        await db.close()
        self.assertEqual((await player_passport(11))[1]['kills'],7)
        self.assertEqual((await player_passport(99))[1]['kills'],0)

    async def test_certificate_idempotent_and_scoped(self):
        a,b = await asyncio.gather(*[issue_certificate(100,1,1,11,'Champion',10) for _ in range(2)])
        self.assertEqual(a['code'],b['code'])
        self.assertIsNone(await verify_certificate(200,a['code']))
        self.assertEqual((await verify_certificate(100,a['code'].lower()))['recipient_name'],'Player')
        self.assertTrue(await revoke_certificate(100,a['code'],10))
        self.assertFalse(await revoke_certificate(100,a['code'],10))
        self.assertIsNotNone((await verify_certificate(100,a['code']))['revoked_at'])
        with self.assertRaises(ValueError):
            await issue_certificate(100,1,1,11,'Champion',10)

    async def test_invalid_certificate(self):
        for tournament,recipient,award in [(2,11,'Champion'),(1,99,'Champion'),(1,11,' '),(1,11,'a'*81)]:
            with self.assertRaises(ValueError):
                await issue_certificate(100,tournament,1,recipient,award,10)
        a = await issue_certificate(100,1,1,10,'Participation',10)
        self.assertEqual(a['recipient_id'],10)

    async def test_stream_stop(self):
        before = await stream_status(1)
        self.assertEqual(before['stream_live'],1)
        after = await stream_status(1,stop=True)
        self.assertEqual(after['stream_live'],0)
        self.assertEqual(after['stream_url'],before['stream_url'])
        self.assertIsNone(await stream_status(999,stop=True))

    async def test_migration_repeat_and_cascade(self):
        cert = await issue_certificate(100,1,1,11,'Champion',10)
        await database.init_db()
        db = await database.connect()
        await db.execute('DELETE FROM tournaments WHERE id=1')
        await db.commit()
        await db.close()
        self.assertIsNone(await verify_certificate(100,cert['code']))

    def guild(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        guild.default_role = MagicMock(spec=discord.Role)
        guild.me = MagicMock(spec=discord.Member)
        guild.get_role.return_value = None
        guild.get_member.side_effect = lambda user_id: MagicMock(spec=discord.Member)
        guild.get_channel.return_value = None
        return guild

    def channel(self, kind, guild, channel_id):
        channel = MagicMock(spec=kind)
        channel.guild = guild
        channel.id = channel_id
        channel.edit = AsyncMock()
        channel.delete = AsyncMock()
        return channel

    async def test_room_create_sync_close_and_authorization(self):
        guild = self.guild()
        text = self.channel(discord.TextChannel,guild,101)
        voice = self.channel(discord.VoiceChannel,guild,102)
        guild.create_text_channel = AsyncMock(return_value=text)
        guild.create_voice_channel = AsyncMock(return_value=voice)
        actor = MagicMock(spec=discord.Member)
        actor.id = 10
        actor.guild_permissions.administrator = False
        actor.roles = []
        service = WarRoomService()
        with patch('services.war_rooms.GUILD_ID',0):
            self.assertEqual(await service.manage(guild,actor,1),(text,voice))
            rules = guild.create_text_channel.call_args.kwargs['overwrites']
            self.assertFalse(rules[guild.default_role].view_channel)
            guild.get_channel.side_effect = lambda channel_id: {101:text,102:voice}.get(channel_id)
            await service.manage(guild,actor,1)
            guild.create_text_channel.assert_awaited_once()
            text.edit.assert_awaited_once()
            actor.id = 99
            with self.assertRaises(ValueError):
                await service.manage(guild,actor,1)
            actor.id = 10
            await service.manage(guild,actor,1,close=True)
            text.delete.assert_awaited_once()
            voice.delete.assert_awaited_once()

    async def test_room_partial_creation_rollback(self):
        guild = self.guild()
        text = self.channel(discord.TextChannel,guild,101)
        guild.create_text_channel = AsyncMock(return_value=text)
        guild.create_voice_channel = AsyncMock(side_effect=RuntimeError('voice failed'))
        actor = MagicMock(spec=discord.Member)
        actor.id = 10
        with patch('services.war_rooms.GUILD_ID',0), self.assertRaises(RuntimeError):
            await WarRoomService().manage(guild,actor,1)
        text.delete.assert_awaited_once()
        db = await database.connect()
        self.assertEqual((await (await db.execute('SELECT COUNT(*) FROM war_rooms')).fetchone())[0],0)
        await db.close()

    async def test_uncached_channel_is_fetched(self):
        guild = self.guild()
        channel = self.channel(discord.TextChannel,guild,101)
        guild.fetch_channel = AsyncMock(return_value=channel)
        service = WarRoomService()
        self.assertIs(await service.resolve_channel(guild,101,discord.TextChannel),channel)
        guild.fetch_channel.assert_awaited_once_with(101)
        with self.assertRaises(ValueError):
            await service.resolve_channel(guild,101,discord.VoiceChannel)


class CommandRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_extensions_load_without_discord_connection(self):
        from discord.ext import commands
        bot = commands.Bot(command_prefix='!',intents=discord.Intents.none())
        async with bot:
            for ext in ('cogs.esports','cogs.admin','cogs.support','cogs.reminders','cogs.arena'):
                await bot.load_extension(ext)
            self.assertIsNotNone(bot.tree.get_command('passport'))
            self.assertIsNotNone(bot.tree.get_command('certificate').get_command('issue'))
            self.assertIsNotNone(bot.tree.get_command('squad').get_command('warroom'))
            self.assertIsNotNone(bot.tree.get_command('match').get_command('streamstop'))
