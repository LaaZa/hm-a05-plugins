import re
import struct
import urllib.parse
from collections import defaultdict, deque
from datetime import timedelta

import aiohttp
import nextcord

from modules.globals import Globals
from modules.pluginbase import PluginBase
from plugins.musicplayer.audioplayer import YTDLSource, AudioEntry, PlayList, MetadataProvider
from plugins.musicplayer.ui import PlayerView


class Plugin(PluginBase):

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Music player'
        self.add_trigger('on_message', 'mp', True, self.on_message)
        self.help = '''Play musicplayer!\n
        [add][a] to add url/search term to playlist\n
        [addnext][an] to add to be played next\n
        [play][pl][resume][r] to continue playing paused or stopped musicplayer\n
        [next][n] to stop currently playing song and start the next\n
        [stop] to stop(end) the current song and remain paused\n
        [pause][p] to pause pause the current track without ending it\n
        [playing][np][EMPTY] to get info card of the currently playing track\n
        '''
        # [volume][vol] to adjust volume of the current track, values can be up,+,down,- to adjust accordingly +-10%'''

        self.metadata_providers = set()
        self.previous_provider = dict()

        self.client = Globals.disco
        self.playlists = {}

        self.role_permissions = defaultdict(lambda: defaultdict(set))

        self.playlist_to_add = defaultdict(deque)

        self.last_info_card = {}

        self.command_aliases = (('add', 'a'), ('addnext', 'an'), ('play', 'pl'), ('next', 'n'), ('pause', 'stop', 'p'), ('resume', 'r'), ('volume', 'vol'), ('shuffle',))

        self.subcommands = {
            'add': self.sub_add,
            'a': self.sub_add,
            'addnext': self.sub_add,
            'an': self.sub_add,
            'play': self.sub_play,
            'pl': self.sub_play,
            'next': self.sub_next,
            'n': self.sub_next,
            'stop': self.sub_pause,
            'pause': self.sub_pause,
            'p': self.sub_pause,
            'resume': self.sub_play,
            'r': self.sub_play,
            'playing': self.sub_playing,
            'np': self.sub_playing,
            # 'volume': self.sub_volume,
            # 'vol': self.sub_volume,
            'shuffle': self.sub_shuffle,
        }

    async def on_message(self, message, trigger):
        msg = self.Command(message)
        if message.guild:
            subcmd = msg.word(0, default='playing')
            if subcmd == 'permissions':
                await self.sub_permissions(message)
            else:
                if not message.guild.voice_client:  # try to join the user's voice channel if we are not on any
                    if message.author.voice.channel:
                        try:
                            await nextcord.utils.get(message.guild.channels, id=message.author.voice.channel.id).connect()
                        except Exception as e:
                            Globals.log.error(f'Could not join channel: {str(e)}')
                            await message.channel.send('Can\'t join that channel')

                if message.guild.voice_client:
                    if message.guild.id not in self.playlists.keys():
                        self.playlists[message.guild.id] = PlayList(message.guild.voice_client, on_next_song=self.on_next_song)
                    if message.author.voice.channel == message.guild.voice_client.channel:
                        if msg.word(0, default='playing'):
                            if self.has_permission(message, subcmd):
                                await self.subcommands.get(subcmd.lower(), lambda x: True)(message)
                            else:
                                await message.channel.send(
                                    f'{message.author.mention} you have no permission to use that command')
                        return True
                    else:
                        return False
                else:
                    await message.channel.send('I\'m not on a voice channel')
        else:
            await message.channel.send('I can\'t play musicplayer here')

    '''
    UTILITY FUNCTIONS
    '''

    # def get_audio_state(self, guild):
    #     state = self.audio_states.get(guild.id)
    #     if state is None:
    #         state = AudioState(self.client,
    #                            queue_next=self.add_next_from_queue)
    #         self.audio_states[guild.id] = state
    #         Globals.log.debug('New audio state')
    #     return state

    # async def set_voice_client(self, guild):
    #     if guild and guild.voice_client:
    #         voice = guild.voice_client
    #         state = self.get_audio_state(guild)
    #         state.voice = voice

    # def _unload(self):
    #     for state in self.audio_states.values():
    #         try:
    #             state.audio_player.cancel()
    #             if state.voice:
    #                 self.client.loop.create_task(state.voice.disconnect())
    #         except Exception:
    #             pass

    def get_guild_playlist(self, guild_id):
        return self.playlists.get(guild_id, None)

    def has_permission(self, message, command, voice_required=False):
        author = None

        try:
            author = message.author
        except AttributeError:
            author = message.user

        if voice_required:
            if message.guild.voice_client:
                if not author.voice.channel == message.guild.voice_client.channel:
                    return False
            else:
                return False

        if Globals.permissions.has_permission(author, Globals.permissions.PermissionLevel.admin) or Globals.permissions.has_discord_permissions(author, ('manage_channels',), message.channel):
            return True

        if command == 'playing':
            return True

        for pair in self.command_aliases:
            if command in pair:
                command = pair[0]

        for role in author.roles:
            if self.role_permissions.get(message.guild.id) and self.role_permissions.get(message.guild.id).get(
                    role.id):
                for cmds in self.role_permissions.get(message.guild.id).get(role.id):
                    if command in cmds:
                        return True

    async def get_infocard(self, guild_id):
        playlist = self.get_guild_playlist(guild_id)

        if not playlist:
            embed = nextcord.Embed(title='Playlist is empty')
            return embed

        if not playlist.current_song:
            embed = nextcord.Embed(title='Playlist is empty')
            #embed.add_field(name='Playlist is empty', value=, inline=text[1])
            return embed

        title = playlist.current_song.title
        try:
            duration = str(timedelta(seconds=playlist.current_song.duration))
        except TypeError:
            duration = ''
        url = playlist.current_song.url
        service = urllib.parse.urlsplit(playlist.current_song.webpage_url or url)[1]
        uploader = playlist.current_song.uploader
        upload_date = playlist.current_song.upload_date
        added_by = playlist.current_song.added_by
        method = 'Streaming' if playlist.current_song.is_live else 'Playing'

        info = {
            f'▶ **{title}**': (f'Currently {method} {playlist.current_song.info.get("name", "")}', False),
            duration: ('Duration', False),
            uploader: ('Uploader', True),
            upload_date: ('Upload Date', True),
            added_by.mention: ('Added by', False)
        }

        info.update(playlist.current_song.info.get('extra', ''))

        embed = nextcord.Embed(title='Music Player')
        if colour := playlist.current_song.info.get('colour', ''):
            embed.colour = colour

        for part, text in info.items():
            if part:
                embed.add_field(name=text[0], value=part, inline=text[1])
        if playlist.current_song.thumbnail:
            embed.set_thumbnail(url=playlist.current_song.thumbnail)
        embed.set_footer(text=service)

        return embed
    '''
    SUBCOMMANDS
    '''

    async def sub_permissions(self, message):
        p = Globals.permissions
        if not (p.has_permission(message.author, p.PermissionLevel.admin) or p.has_discord_permissions(
                message.author, ('manage_channels',), message.channel)):
            await message.channel.send('You have no rights to manage permissions')
            return
        msg = self.Command(message, clean=True)
        kwrds = msg.keyword_commands(('roles', 'commands'), strip=True)
        if kwrds.get('roles') and kwrds.get('commands'):
            roles_str = kwrds.get('roles').lower().split('@')
            roles_str = ['@' + x.strip().lstrip('\u200b') if x.strip().startswith('\u200b') else x.strip() for x in
                         roles_str]
            roles = []
            for role in message.guild.roles:
                if role.name.lower() in roles_str:
                    roles.append(role)

            commands = kwrds.get('commands').split()
            commands = [x.strip() for x in commands]

            add_list = set()
            remove_list = set()
            for command in commands:
                if command.startswith('-'):
                    command = command.strip('-')
                    if command == '*':
                        remove_list = set([x[0] for x in self.command_aliases])
                    for alias in self.command_aliases:
                        if command in alias:
                            remove_list.add(alias[0])
                elif command == '*':
                    add_list = set([x[0] for x in self.command_aliases])
                else:
                    for alias in self.command_aliases:
                        if command in alias:
                            add_list.add(alias[0])

            final_list = add_list - remove_list

            for role in roles:
                if self.role_permissions.get(message.guild.id) and self.role_permissions.get(message.guild.id).get(
                        role.id):
                    self.role_permissions.x[message.guild.id][role.id].update(final_list)
                    self.role_permissions.x[message.guild.id][role.id].difference_update(remove_list)
                else:
                    self.role_permissions.x[message.guild.id][role.id] = final_list
            Globals.log.debug(self.role_permissions.x)
            await message.channel.send('Changed permissions')

        else:
            await message.channel.send('You need to specify roles: @role and commands: add pause -stop')

    async def sub_shuffle(self, message):
        playlist = self.get_guild_playlist(message.guild.id)
        if playlist.shuffle():
            await message.channel.send('シャッフル！ The playlist ain\'t what it used to be')
        else:
            await message.channel.send('The playlist doesn\'t have enough items to shuffle')

    # async def sub_volume(self, message):
    #     playlist = self.get_guild_playlist(message.guild.id)
    #     if playlist.current_song is None:
    #         await message.channel.send(f'I\'m not playing musicplayer')
    #         return
    #     cur_volume = playlist.current_song.volume * 100
    #     msg = self.Command(message)
    #
    #     vol = msg.word(1).lower()
    #     value = cur_volume
    #     if vol:
    #         if vol in ('up', '+'):
    #             value = max(min(100, cur_volume + 10), 0)
    #         elif vol in ('down', '-'):
    #             value = max(min(100, cur_volume - 10), 0)
    #         elif vol in ('default', 'normal'):
    #             value = 20
    #         elif vol.isnumeric():
    #             if 0 < int(vol) <= 100:
    #                 value = int(vol)
    #         else:
    #             await message.channel.send(f'Current volume is {cur_volume}%')
    #             return
    #     else:
    #         await message.channel.send(f'Current volume is {cur_volume}%')
    #         return
    #
    #     if playlist.is_playing():
    #         playlist.player.volume = value / 100
    #         await message.channel.send(f'Volume is now {playlist.player.volume * 100}%')

    async def sub_playing(self, message):
        playlist = self.get_guild_playlist(message.guild.id)
        if playlist.current_song is None or not playlist.is_playing:
            await message.channel.send(f'Not playing anything right now')
        else:
            embed = await self.get_infocard(message.guild.id)
            self.last_info_card[message.guild.id] = await message.channel.send(embed=embed)

    async def sub_add(self, message):
        msg = self.Command(message)
        if msg.word(1) or message.attachments:
            url = ''
            if message.attachments:
                url = message.attachments[0].url
            else:
                url = msg.words(1)

            Globals.log.info(f'Adding url: {url}')
            source = YTDLSource(url)
            playlist = self.get_guild_playlist(message.guild.id)

            source_loaded = await source.load()
            media_info = source.data
            if media_info.get('_type') == 'playlist':
                await message.channel.send(f'Adding items from playlist...')
                for entry in media_info.get("entries"):
                    source_single = YTDLSource(entry.get('url'))
                    source_loaded_single = await source_single.load(playlist=True)
                    media_info_single = source_single.data
                    await playlist.add_song(AudioEntry(message, source_loaded_single, media_info_single))
                    if not playlist.is_playing:
                        await playlist.play(True)
            else:
                if msg.word(0).lower() in ('addnext', 'an'):
                    await playlist.add_next(AudioEntry(message, source_loaded, media_info))
                    media_info['next'] = True
                else:
                    await playlist.add_song(AudioEntry(message, source_loaded, media_info))

            if media_info:
                if media_info.get('duration'):
                    await message.channel.send(
                        f'Added {"next " if media_info.get("next") else ""}**{media_info.get("title")}** [{str(timedelta(seconds=media_info.get("duration")))}] to playlist')
                elif media_info.get('_type') == 'playlist':
                    await message.channel.send(
                        f'Added {"next " if media_info.get("next") else ""}{len(media_info.get("entries"))} items from **{media_info.get("title")}** to playlist')
                else:
                    await message.channel.send(
                        f'Added {"next " if media_info.get("next") else ""}**{media_info.get("title")}** to playlist')
                if Globals.permissions.client_has_discord_permissions(('manage_messages',), message.channel):
                    await message.delete()

                #######
                #embed = await self.get_infocard(message.guild.id)
                #await message.channel.send(embed=embed, )

                await playlist.play(True)
        else:
            await message.channel.send('I need proper url :/')

    async def sub_play(self, message):
        playlist = self.get_guild_playlist(message.guild.id)

        if playlist.deck.empty() and not playlist.current_song:
            await message.channel.send('The playlist is empty :<')
            return
        await playlist.play()

    async def sub_next(self, message):
        playlist = self.get_guild_playlist(message.guild.id)
        await playlist.skip()

    async def sub_pause(self, message):
        playlist = self.get_guild_playlist(message.guild.id)
        playlist.pause()

    # async def add_to_queue(self, message, url):
    #     state = self.get_audio_state(message.guild)
    #     await self.set_voice_client(message.guild)
    #
    #     async with message.channel.typing():
    #         info_out = None
    #
    #         msg = self.Command(message)
    #
    #         ytdl_options = {
    #             'quiet': False,
    #             'flat-playlist': True,
    #             'ignore-errors': False,
    #             'skip_download': True,
    #             'extract_flat': 'in_playlist',
    #             'logger': Globals.log,
    #             'default_search': 'auto',
    #         }
    #
    #         ydl = youtube_dl.YoutubeDL(ytdl_options)
    #
    #         info = None
    #
    #         #  load media information/playlist
    #         try:
    #             func = functools.partial(ydl.extract_info, url, download=False)
    #             info = await Globals.disco.loop.run_in_executor(None, func)
    #         except youtube_dl.DownloadError as e:
    #             Globals.log.error(f'Could not add items from the playlist {str(e)}')
    #             await message.channel.send('Could not add items from the playlist :<')
    #             return None
    #         if info.get('_type') == 'playlist' and len(info.get('entries')) > 1:
    #             info_out = info
    #             await message.channel.send('Adding items from the playlist')
    #
    #             #  generated playlists do not have title, we will use search query instead without part before :
    #             if not info.get('title'):
    #                 info['title'] = url.split(':')[-1]
    #
    #             if msg.word(0).lower() in ('addnext', 'an'):
    #                 await self.put_to_deck(message, info.get('entries'))
    #                 info_out['next'] = True
    #             else:
    #                 for entry in info.get('entries'):
    #                     self.playlist_to_add[message.guild].append(entry)
    #                     Globals.log.info(f'Added entry for url {entry.get("url") or entry.get("webpage_url")}')
    #         else:
    #             ytdl_options = {
    #                 'quiet': False,
    #                 'noplaylist': True,
    #                 'ignore-errors': False,
    #                 'skip_download': True,
    #                 'logger': Globals.log,
    #                 'default_search': 'auto',
    #             }
    #             #  load more detailed information for singular entries
    #             ydl = youtube_dl.YoutubeDL(ytdl_options)
    #
    #             entry_info = None
    #
    #             #  load media information
    #             try:
    #                 func = functools.partial(ydl.extract_info, url, download=False)
    #                 entry_info = await Globals.disco.loop.run_in_executor(None, func)
    #             except youtube_dl.DownloadError as e:
    #                 Globals.log.error(f'Could not add items from the playlist {str(e)}')
    #                 await message.channel.send('Could not add the item :<')
    #                 return None
    #             #  search results can be playlists with only one entry
    #             if entry_info.get('entries') and len(entry_info.get('entries')) == 1:
    #                 entry_info = entry_info['entries'][0]
    #
    #             info_out = entry_info
    #             if msg.word(0).lower() in ('addnext', 'an'):
    #                 await self.put_to_deck(message, [entry_info])
    #                 info_out['next'] = True
    #             else:
    #                 self.playlist_to_add[message.guild].append(entry_info)
    #                 Globals.log.info(
    #                     f'Added entry for url {entry_info.get("url") or entry_info.get("webpage_url")}')
    #
    #         #  immediately put on deck if it is empty
    #         if state.deck.empty():
    #             await self.add_next_from_queue(message)
    #         return info_out
    #
    # async def add_next_from_queue(self, message):
    #     if len(self.playlist_to_add[message.guild]) > 0:
    #         await self.add_player(message, self.playlist_to_add[message.guild].popleft())
    #
    # async def put_to_deck(self, message, entry_info_list):
    #     state = self.get_audio_state(message.guild)
    #
    #     #  get entry from the deck if exists and put it back on the playlist
    #     if not state.deck.empty():
    #         entry = await state.deck.get()
    #         self.playlist_to_add[message.guild].appendleft(entry.info)
    #         Globals.log.info(
    #             f'Added back to playlist from deck entry for url {entry.info.get("url") or entry.info.get("webpage_url")}')
    #     #  add the entry or entries to the playlist next
    #     for entry_info in reversed(entry_info_list):
    #         self.playlist_to_add[message.guild].appendleft(entry_info)
    #         Globals.log.info(
    #             f'Added entry for url to the front of playlist {entry_info.get("url") or entry_info.get("webpage_url")}')
    #     #  and put it on the deck immediately
    #     await self.add_next_from_queue(message)

    # async def add_player(self, message, entry_info):
    #     if message.guild.voice_client:
    #         state = self.get_audio_state(message.guild)
    #
    #         Globals.log.info(f'Adding player for url {entry_info.get("url") or entry_info.get("webpage_url")}')
    #
    #         try:
    #             source = await YTDLSource.from_url(entry_info.get("url") or entry_info.get("webpage_url"),
    #                                                loop=Globals.disco.loop)
    #             player = AudioPlayer(voice=state.voice, source=source, client=Globals.disco, info=entry_info,
    #                                  after=state.toggle_next)
    #         except Exception as e:
    #             Globals.log.error('Player adding failed:' + str(e))
    #             await self.add_next_from_queue(message)
    #             return None
    #         else:
    #             if not entry_info.get('thumbnail'):
    #                 #  load some extra meta
    #                 func = functools.partial(player.source.ytdl.extract_info,
    #                                          entry_info.get("webpage_url") or entry_info.get("url"), download=False)
    #                 info = await Globals.disco.loop.run_in_executor(None, func)
    #
    #                 stream_info = await self.get_stream_info(entry_info.get('url'))
    #                 if stream_info.get('name'):
    #                     entry_info['title'] = stream_info.get('name') + ':\n' + stream_info.get(
    #                         'title') or entry_info.get('title')
    #                 else:
    #                     entry_info['title'] = stream_info.get('title') or entry_info.get('title')
    #
    #                 Globals.log.debug(f'streaminfo {stream_info}')
    #
    #                 if stream_info.get('name'):
    #                     entry_info['is_live'] = 1
    #
    #                 player.thumbnail = info.get('thumbnail')
    #             else:
    #                 player.thumbnail = entry_info.get('thumbnail')
    #
    #             audio_entry = AudioEntry(message, player, entry_info)
    #             await state.deck.put(audio_entry)
    #             Globals.log.info(f'Added player for {player.title}')
    #         try:
    #             return entry_info
    #         except IndexError:
    #             Globals.log.info(f'No players were added')
    #             return None
    #     else:
    #         await message.channel.send('I\'m not on a voice channel')
    #         return None

    # async def pause(self, message):
    #     playlist = self.get_guild_playlist(message.guild)
    #     if playlist.is_playing():
    #         playlist.current_song.pause()
    #         await self.update_status(message, AudioStatus.PAUSED)
    #         Globals.log.debug('Musicplayer: pause')
    #
    # async def play(self, message):
    #     playlist = self.get_guild_playlist(message.guild)
    #     playlist.current_song.play()
    #     await self.update_status(message.channel, AudioStatus.PLAYING)
    #     Globals.log.debug('Musicplayer play')
    #
    # async def resume(self, message):
    #     playlist = self.get_guild_playlist(message.guild)
    #     playlist.current_song.resume()
    #     await self.update_status(message.channel, AudioStatus.PLAYING)
    #     Globals.log.debug('Musicplayer resume')
    #
    # async def next(self, message):
    #     playlist = self.get_guild_playlist(message.guild)
    #     playlist.current_song.stop()
    #     playlist.current_song.next()
    #     Globals.log.error('Musicplayer Next')

    async def on_next_song(self, audio_entry):
        if provider := await self.select_provider(audio_entry):
            await provider.metadata_update(audio_entry)
            #self.get_guild_playlist(audio_entry.channel.guild.id).current_song = audio_entry
            Globals.log.debug(f'{audio_entry.title}')
            await provider.on_update(self.update_info_card, audio_entry)
            if self.previous_provider.get(audio_entry.channel.guild.id) and provider is not self.previous_provider.get(audio_entry.channel.guild.id) and provider not in self.previous_provider.values():
                self.previous_provider.get(audio_entry.channel.guild.id).close()
            self.previous_provider[audio_entry.channel.guild.id] = provider

        await self.update_info_card(audio_entry)

    async def update_info_card(self, audio_entry):
        embed = await self.get_infocard(audio_entry.channel.guild.id)
        if audio_entry.channel.guild.id in self.last_info_card.keys():
            await self.last_info_card[audio_entry.channel.guild.id].edit(embed=embed, view=PlayerView(self))
        else:
            self.last_info_card[audio_entry.channel.guild.id] = await audio_entry.channel.send(embed=embed,
                                                                                               view=PlayerView(self))
            await self.last_info_card[audio_entry.channel.guild.id].pin()

    async def select_provider(self, audio_entry):
        Globals.log.debug(f'MetadataProviders: {self.metadata_providers}')
        for provider in self.metadata_providers:
            if provider.hook(audio_entry):
                return provider
        return None

    def register_metadata_provider(self, provider: MetadataProvider):
        self.metadata_providers.add(provider)
        return True
