import time

import nextcord

from modules.globals import Globals
from modules.pluginbase import PluginBase
from plugins.radio.radioapi import RadioAPI


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'R/a/dio'
        self.add_trigger('on_message', 'radio', True, self.on_message)
        self.help = 'Get info from R/a/dio'

        self.radio = RadioAPI()
        self.last_dj = ''
        self.last_np = ''
        self.auto_query_list = {'dj': {}, 'np': {}}
        self.last_update = None

        try:
            Globals.pluginloader.plugins.get('musicplayer').register_metadata_provider(self.RadioMetadataProvider())
            Globals.log.info(f'registered metadataprovider')
        except Exception as e:
            Globals.log.error(f'Could not register metadataprovider: {e}')

    async def on_message(self, message, trigger):
        await self.radio.update()
        self.last_update = time.time()
        
        msg = self.Command(message)

        if msg.word(0) == 'np' or not msg.word(0):

            embed = nextcord.Embed(title='R/a/dio')
            embed.add_field(name='Now playing', value=self.radio.np)
            embed.set_thumbnail(url='https://r-a-d.io/assets/logo_image_small.png')
            await message.channel.send(embed=embed)
            self.last_np = self.radio.np
            if msg.word(1) == 'notify':
                if self.Jobs.add_interval_task(self, 'np' + str(message.channel.id), 10, self.autoquery, message, 'np'):
                    await message.channel.send('I\'ll tell you when the song changes')
                else:
                    self.Jobs.remove_interval_task(self, 'np' + str(message.channel.id))
                    await message.channel.send('Okay, I won\'t be notifying about song changes')
            return True
        elif msg.word(0) == 'dj':
            embed = nextcord.Embed(title='R/a/dio', colour=self.radio.dj_color)
            embed.add_field(name='Current DJ', value=self.radio.dj)
            embed.set_thumbnail(url=self.radio.dj_image)
            await message.channel.send(embed=embed)
            self.last_dj = self.radio.dj
            if msg.word(1) == 'notify':
                if self.Jobs.add_interval_task(self, 'dj' + str(message.channel.id), 10, self.autoquery, message, 'dj'):
                    await message.channel.send('I\'ll tell you when the DJ changes')
                else:
                    self.Jobs.remove_interval_task(self, 'dj' + str(message.channel.id))
                    await message.channel.send('Okay, I won\'t be notifying about DJ changes')
            return True
        elif msg.word(0) == 'next':
            embed = nextcord.Embed(title='Next On R/a/dio')
            embed.add_field(name=self.radio.queue_track(0), value=f'in { self.radio.queue_time(0)}')
            embed.set_thumbnail(url='https://r-a-d.io/assets/logo_image_small.png')
            await message.channel.send(embed=embed)
            return True
        elif msg.word(0) == 'queue':
            embed = nextcord.Embed(title='R/a/dio Coming Up')
            for i, track in enumerate(self.radio.queue):
                if self.radio.queue_is_request(i):
                    embed.add_field(name=self.radio.queue_track(i), value=f'in {self.radio.queue_time(i)}', inline=False)
                else:
                    embed.add_field(name=self.radio.queue_track(i), value=f'in {self.radio.queue_time(i)}', inline=False)
            await message.channel.send(embed=embed)
            return True
        else:
            return False

    async def autoquery(self, message, querytype):
        if time.time() - self.last_update >= 10:
            await self.radio.update()
            self.last_update = time.time()

        if querytype == 'dj' and self.last_dj != self.radio.dj:
            embed = nextcord.Embed(title='R/a/dio', colour=self.radio.dj_color)
            embed.add_field(name='New DJ', value=self.radio.dj)
            embed.set_thumbnail(url=self.radio.dj_image)
            await message.channel.purge(limit=20, check=self.__purge_check_dj)
            await message.channel.send(embed=embed)
            self.last_dj = self.radio.dj
        elif querytype == 'np' and self.last_np != self.radio.np:
            embed = nextcord.Embed(title='R/a/dio')
            embed.add_field(name='Now playing', value=self.radio.np)
            embed.set_thumbnail(url='https://r-a-d.io/assets/logo_image_small.png')
            await message.channel.purge(limit=20, check=self.__purge_check_np)
            await message.channel.send(embed=embed)
            self.last_np = self.radio.np

    def __purge_check_np(self, m):
        try:
            return m.author == Globals.disco.user and m.embeds[0]['title'] == 'R/a/dio' and m.embeds[0]['fields'][0]['name'] == 'Now playing'
        except Exception:
            return False

    def __purge_check_dj(self, m):
        try:
            return m.author == Globals.disco.user and m.embeds[0]['title'] == 'R/a/dio' and m.embeds[0]['fields'][0]['name'] in ('New DJ', 'Current DJ')
        except Exception:
            return False

    class RadioMetadataProvider:

        def __init__(self):
            self.name = 'R/a/dio'
            self.api = RadioAPI()
            self._previous_np = ''

        async def metadata_update(self, audio_entry):
            await self.api.update()
            audio_entry.info['title'] = self.api.np
            self._previous_np = self.api.np
            audio_entry.info['thumbnail'] = self.api.dj_image if not self.api.dj == 'Hanyuu-sama' else 'https://r-a-d.io/assets/logo_image_small.png'
            audio_entry.info['is_live'] = True
            audio_entry.info['name'] = f'{self.name} with {self.api.dj}'
            audio_entry.info['webpage_url'] = 'https://r-a-d.io/'
            audio_entry.info['colour'] = self.api.dj_color
            audio_entry.info['extra'] = {

            }

            queue = []

            for i, track in enumerate(self.api.queue):
                if self.api.queue_is_request(i):
                    queue.append(f'▢ **{self.api.queue_track(i)} `in {self.api.queue_time(i)}`**')
                else:
                    queue.append(f'▢ {self.api.queue_track(i)} `in {self.api.queue_time(i)}`')

            audio_entry.info['extra'].update({
                '\n\n'.join(queue): ('Coming Up', False)
            })

        async def on_update(self, fn, *args, **kwargs):
            Plugin.Jobs.add_interval_task(self, 'RadioMetadataProvider', 10, self.on_update, fn, *args, **kwargs)
            await self.api.update()
            if self._previous_np != self.api.np:
                await self.metadata_update(*args)
                await fn(*args, **kwargs)

        def hook(self, data):
            return 'r-a-d.io' in data.info.get('url', '')

        def close(self):
            Globals.log.debug('Closed')
            Plugin.Jobs.remove_interval_task(self, 'RadioMetadataProvider')

        def __del__(self):
            self.close()
