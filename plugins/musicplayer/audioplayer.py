import asyncio
import functools
from enum import Enum
from random import shuffle
from typing import Protocol, Callable

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
        #date = '.'.join([d for d in (str(self.info.get("upload_day", "")), str(self.info.get("upload_month", "")), str(self.info.get("upload_year", ""))) if d])
        return self.info.get('upload_date', '')

    @property
    def uploader(self):
        return self.info.get('uploader', '')

    @property
    def url(self):
        return self.source.url

    @property
    def webpage_url(self):
        return self.info.get('webpage_url', '')

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
        self._is_previous_done = False
        self._status = AudioStatus.STOPPED

    async def add_song(self, audio_entry: AudioEntry):
        if self.deck.empty() and not self._current_song:
            self._current_song = audio_entry
        await self.deck.put(audio_entry)

    async def add_next(self, audio_entry: AudioEntry):
        if self.deck.empty():
            await self.add_song(audio_entry)
            return
        self.deck._queue[0] = audio_entry


    async def play(self, start=False):
        if self.status is AudioStatus.PAUSED:
            Globals.log.debug(f'resume')
            self.voice_client.resume()
            self.status = AudioStatus.PLAYING
        elif self.is_previous_done:
            Globals.log.debug(f'play: play_next')
            await self.play_next()
        elif start and self.status is not AudioStatus.PLAYING:
            Globals.log.debug(f'play: play_next START')
            self._is_previous_done = True
            self.status = AudioStatus.PLAYING
            await self.play_next()

    def pause(self):
        if self._current_song and self.is_playing and self.status is AudioStatus.PLAYING:
            Globals.log.debug(f'pause')
            self.voice_client.pause()
            self.status = AudioStatus.PAUSED

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

    @current_song.setter
    def current_song(self, val: AudioEntry):
        self._current_song = val

    @property
    def is_previous_done(self):
        return self._is_previous_done

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, audio_status: AudioStatus):
        self._status = audio_status

    async def wait_loaded(self):
        while not self.current_song:
            await asyncio.sleep(1)
        return True

    async def _after(self, error):
        if error:
            Globals.log.error(f'Playback error: {error}')
        self._is_previous_done = True
        await self.play_next()

    async def skip(self):
        Globals.log.debug(f'skip')
        self.voice_client.stop()
        await self.play_next()

    async def play_next(self):
        if self.deck.empty():
            Globals.log.debug(f'play_next: empty')
            self._current_song = None
            return
        if self.is_previous_done and self.status is not AudioStatus.STOPPED:
            self.status = AudioStatus.STOPPED
            Globals.log.debug(f'play_next')
            next_entry = await self.deck.get()
            try:
                self.voice_client.play(await next_entry.source.prepare(), after=self._after)
                self.status = AudioStatus.PLAYING
                self._current_song = next_entry
                self._is_previous_done = False
            except Exception as e:
                Globals.log.error(f'Download error: {e}')
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


class YTDLSource:
    ytdl_format_options = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': False,
        'flat-playlist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'extract_flat': 'in_playlist',
        'logger': Globals.log,
        'source_address': '0.0.0.0'
    }

    def __init__(self, url):
        self.ytdl = youtube_dl.YoutubeDL(self.ytdl_format_options)
        self._url = url
        self._func = functools.partial(self.ytdl.extract_info, url, download=False)
        self.data = None
        self.title = ''
        self.url = ''

    async def load(self, playlist=False):
        data = await Globals.disco.loop.run_in_executor(None, self._func)

        if playlist:
            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        return self

    async def prepare(self):
        #data = await Globals.disco.loop.run_in_executor(None, self._func)
        filename = self.data.get('url')  # self.ytdl.prepare_filename(data)
        #self.ytdl.download()
        ffmpeg_audio = nextcord.player.FFmpegPCMAudio(filename, before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn')
        ffmpeg_audio.data = self.data
        return ffmpeg_audio

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, cls.ytdl.extract_info, url)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = cls.ytdl.prepare_filename(data)

        return cls(nextcord.player.FFmpegPCMAudio(filename, before_options='-nostdin', options='-vn'), data=data)


class MetadataProvider(Protocol):

    name: str

    def hook(self, data) -> bool:
        ...

    async def on_update(self, fn, *args, **kwargs) -> None:
        ...

    async def metadata_update(self, audio_entry: AudioEntry) -> None:
        ...

    def close(self) -> None:
        ...
