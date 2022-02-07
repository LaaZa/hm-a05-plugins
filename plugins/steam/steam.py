import json

import aiohttp

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Steam'
        self.add_trigger('on_message', 'steam', True, self.on_message)
        self.help = 'Checks the status of Steam, Steam community and Dota 2/CSGO GCs'

    async def on_message(self, message, trigger):
        try:
            async with aiohttp.ClientSession(loop=Globals.disco.loop) as session:
                async with session.get('https://steamgaug.es/api/v2', headers={'User-Agent': ' Mozilla/5.0 (Windows NT 5.1; rv:5.0) Gecko/20100101 Firefox/40.0'}) as resp:
                    data = await resp.text()
            data = json.loads(data)
            status = 'Steam is up' if data['ISteamClient']['online'] else 'Steam is down'
            community = 'Community is up' if data['SteamCommunity']['online'] else 'Community is down'
            gc = 'Dota 2 game coordinator is up' if data['ISteamGameCoordinator']['570']['online'] else 'Dota 2 game coordinator is down.'
            csgc = 'CSGO game coordinator is up' if data['ISteamGameCoordinator']['730']['online'] else 'CSGO game coordinator is down.'
            await message.channel.send(f'{status}\n{community}\n{gc}\n{csgc}')
        except Exception as e:
            Globals.log.error(f'Could not get Steam status: {str(e)}')
            await message.channel.send('Something went wrong')
            return False

