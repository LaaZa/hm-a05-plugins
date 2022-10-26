import re
import struct

import aiohttp
import requests

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Music Player Icecast provider'
        self.help = ''

        try:
            Globals.pluginloader.plugins.get('musicplayer').register_metadata_provider(self.IcecastMetadataProvider())
            Globals.log.info(f'registered metadataprovider')
        except Exception as e:
            Globals.log.error(f'Could not register metadataprovider: {e}')


    class IcecastMetadataProvider:

        def __init__(self):
            self.name = 'Icecast'
            self._previous_np = ''
            self._streamname = ''

        async def metadata_update(self, audio_entry):
            await self._get_stream_info(audio_entry.url)
            audio_entry.info['title'] = self.api.np
            self._previous_np = self.api.np
            audio_entry.info['thumbnail'] = self.api.dj_image if not self.api.dj == 'Hanyuu-sama' else 'https://r-a-d.io/assets/logo_image_small.png'
            audio_entry.info['is_live'] = True
            audio_entry.info['name'] = f'{self._streamname or self.name}'

        async def on_update(self, fn, *args, **kwargs):
            Plugin.Jobs.add_interval_task(self, 'IcecastMetadataProvider', 10, self.on_update, fn, *args, **kwargs)

            if self._previous_np != self.api.np:
                await self.metadata_update(*args)
                await fn(*args, **kwargs)

        def hook(self, data):
            return self._test_icy(data.url)

        def _test_icy(self, url):
            try:
                if 'icy-metaint' in requests.head(url).headers.keys():
                    return True
            except Exception:
                return False

        async def _get_stream_info(self, url):
            info = {'title': '', 'name': ''}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={'Icy-MetaData': '1'}) as response:
                        metaint = int(response.headers['icy-metaint'])
                        for _ in range(1):
                            await response.content.read(metaint)
                            metadata_length = struct.unpack('B', await response.content.read(1))[0] * 16
                            metadata = await response.content.read(metadata_length)
                            metadata = metadata.rstrip(b'\0')

                            m = re.search(br"StreamTitle='([^']*)';", metadata)
                            if m:
                                title = m.group(1)
                                if title:
                                    info['title'] = title.decode('latin1')
                                    info['name'] = response.headers['icy-name']
                                    break
            except Exception:
                pass

            return info

        def close(self):
            Globals.log.debug('Closed')
            Plugin.Jobs.remove_interval_task(self, 'IcecastMetadataProvider')

        def __del__(self):
            self.close()