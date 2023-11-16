import struct

import aiohttp
import requests
from bs4 import BeautifulSoup

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Music Player Nectarine provider'
        self.help = ''

        try:
            Globals.pluginloader.plugins.get('musicplayer').register_metadata_provider(self.NectarineMetadataProvider())
            Globals.log.info(f'registered metadataprovider')
        except Exception as e:
            Globals.log.error(f'Could not register metadataprovider: {e}')

    class NectarineMetadataProvider:

        def __init__(self):
            self.name = 'Nectarine'
            self._previous_np = ''
            self._streamname = ''
            self._np = ''

        async def metadata_update(self, audio_entry):
            info = await self._get_stream_info()
            self._np = info['title']
            audio_entry.info['title'] = info['title']
            self._previous_np = self._np
            audio_entry.info['thumbnail'] = ''
            audio_entry.info['is_live'] = True
            audio_entry.info['name'] = f'{self._streamname or self.name}'

        async def on_update(self, fn, *args, **kwargs):
            Plugin.Jobs.add_interval_task(self, 'NectarineMetadataProvider', 10, self.on_update, fn, *args, **kwargs)
            info = await self._get_stream_info()
            if self._previous_np != info['title']:
                await self.metadata_update(*args)
                await fn(*args, **kwargs)

        def hook(self, data):
            return 'scenestream' in data.url or 'necta' in data.url

        async def _get_stream_info(self):
            info = {'title': ''}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('https://www.scenestream.net/demovibes/') as response:
                        soup = BeautifulSoup(await response.text(), 'html.parser')

                        nowplaying_div = soup.find('div', attrs={'data-name': 'nowplaying'})
                        songname = nowplaying_div.find('span', class_='songname').find_all('a')
                        artistname = nowplaying_div.find_all('span', class_='artistname')
                        artists = [f':flag_{aname.img["title"]}: {aname.a.text.strip()}' for aname in artistname]
                        username = nowplaying_div.find('span', class_='username')
                        info['title'] = f'[{songname[0].img["title"]}] {songname[1].text}\n  by {", ".join(artists)}' + ('' if not username else f'\n\nRequested by:\n  :flag_{username.img["title"]}: {username.a.text}')

            except Exception as e:
                Globals.log.error(f'Could not get metadata: {e}')

            return info

        def close(self):
            Globals.log.debug('Closed')
            Plugin.Jobs.remove_interval_task(self, 'NectarineMetadataProvider')

        def __del__(self):
            self.close()