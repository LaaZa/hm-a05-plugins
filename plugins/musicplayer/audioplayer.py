import asyncio
from enum import Enum
import inspect
from random import shuffle

import nextcord
import youtube_dl

from modules.globals import Globals


class AudioStatus(Enum):
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3


class AudioEntry:

    def __init__(self, message, source, info):
        self.added_by = message.author
        self.channel = message.channel
        self.message = message
        self.source = source
        self.info = info

    @property
    def upload_date(self):
        return self.info.get('uploader', '')

    @property
    def uploader(self):
        return self.info.get('uploader', '')

    @property
    def url(self):
        return self.source.url

    @property
    def download_url(self):
        return self.info.get('download_url', '')

    @property
    def description(self):
        return self.info.get('description', '')

    @property
    def title(self):
        return self.info.get('title', '')

    @property
    def duration(self):
        return self.info.get('duration', '')

    @property
    def thumbnail(self):
        return self.info.get('thumbnail', '')

    @property
    def is_live(self):
        return self.info.get('is_live', '')


class PlayList:

    def __init__(self, voice_client, on_next_song=None):
        self.deck = asyncio.Queue()
        self._current_song = None
        self.voice_client = voice_client
        self._on_next_song = on_next_song

    async def add_song(self, audio_entry: AudioEntry):
        if self.deck.empty():
            self._current_song = audio_entry
        await self.deck.put(audio_entry)

    async def play(self):
        if self._current_song and not self.voice_client.is_playing:
            self.voice_client.resume()
        else:
            await self.play_next()

    def pause(self):
        if self._current_song and self.is_playing:
            self.voice_client.pause()

    def shuffle(self):
        if self.deck.qsize() >= 1:
            shuffle(self.deck._queue)
            return True
        return False

    @property
    def titles(self):
        return list(self.deck._queue)

    @property
    def is_playing(self):
        return self.voice_client.is_playing()

    @property
    def current_song(self):
        return self._current_song

    async def play_next(self, paused=False):
        if self.deck.empty():
            self._current_song = None
        next_entry = await self.deck.get()
        self.voice_client.play(next_entry.source)
        self._current_song = next_entry
        if paused:
            self.pause()
        if self._on_next_song:
            await self._on_next_song(next_entry)


class AudioState:

    def __init__(self, on_status_change=None, queue_next=None):
        self.current = None
        self.voice = None
        self.client = Globals.disco
        self.play_next_song = asyncio.Event()
        self.deck = asyncio.Queue()
        self.audio_player = self.client.loop.create_task(self.audio_player_task())

        self.on_status_change = on_status_change
        self.queue_next = queue_next

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.source
        return player.is_playing()

    async def run_status_update(self, status):
        if self.on_status_change is not None and self.voice is not None:
            await self.on_status_change(self.voice.channel, status)

    @property
    def player(self):
        return self.current.source

    def toggle_next(self, e=None):
        self.client.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.deck.get()
            await self.run_status_update(AudioStatus.PLAYING)
            self.current.source.play()
            if self.deck.qsize() < 1:
                await self.queue_next(self.current.message)
            await self.play_next_song.wait()

            if self.deck.empty():
                await self.run_status_update(AudioStatus.STOPPED)


class AudioPlayer:

    def __init__(self, voice, source, client, info, after=None):
        self.voice = voice
        self.client = client
        self.source = source
        self.__after = after
        self.info = self.source.data

        self.info.update(info)

    def is_playing(self):
        return self.voice.is_playing()

    def is_paused(self):
        return self.voice.is_paused()

    def play(self):
        self.voice.play(self.source, after=self.__after)

    def stop(self):
        self.voice.stop()

    def pause(self):
        self.voice.pause()

    def resume(self):
        self.voice.resume()

    def next(self):
        self.__after()

    @property
    def volume(self):
        return self.voice.source.volume

    @volume.setter
    def volume(self, vol):
        self.voice.source.volume = vol

    @property
    def upload_date(self):
        return self.info.get('uploader', '')

    @property
    def uploader(self):
        return self.info.get('uploader', '')

    @property
    def url(self):
        return self.source.url

    @property
    def download_url(self):
        return self.info.get('download_url', '')

    @property
    def description(self):
        return self.info.get('description', '')

    @property
    def title(self):
        return self.info.get('title', '')

    @property
    def duration(self):
        return self.info.get('duration', '')

    @property
    def is_live(self):
        return self.info.get('is_live', '')


class YTDLSource(nextcord.PCMVolumeTransformer):
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'extract_flat': True,
        'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
    }

    ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, cls.ytdl.extract_info, url)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = cls.ytdl.prepare_filename(data)

        return cls(nextcord.FFmpegPCMAudio(filename, before_options='-nostdin', options='-vn'), data=data)
