import nextcord

from modules.globals import Globals, BotPath
from modules.pluginbase import PluginBase

import aiohttp
import json
import base64
import io

class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Stable Diffusion'
        self.add_trigger('on_message', 'sd', True, self.on_message)
        self.add_trigger('on_message', 'sds', True, self.on_message)
        self.help = 'Generates images using sdapi'
        try:
            self.api_url = Globals.config_data.get_opt('stabeldiffusion', 'api_url')
        except:
            self.api_url = 'http://127.0.0.1:7860'

        self.prompts = {}

    async def on_message(self, message, trigger):
        try:
            msg = self.Command(message)
            if len(msg.parts) > 1:
                async with message.channel.typing():
                    await self.load_prompts()
                    file = await self.render(msg.parts[1:], trigger == 'sds')
                    if file:
                        await message.channel.send(file=file)
                    else:
                        raise
            else:
                pass
            return True
        except Exception as e:
            Globals.log.error(f'SD error: {str(e)}')
            await message.channel.send('Something went wrong')
            return False

    async def render(self, prompt, sfw=False):

        format = {
            'f:portrait': (576, 768),
            'f:portraitw': (640, 768),
            'f:landscape': (768, 576),
            'f:landscapet': (768, 640),
            'f:big': (768, 768)
        }

        w, h = format.get(prompt[0], (512, 512))

        if prompt[0] in format.keys():
            prompt.pop(0)

        prompt = ' '.join(prompt)

        for p, r in self.prompts.items():
            prompt = prompt.replace(p, r)

        reqbody = {
          "prompt": str(prompt),
          "styles": [
            "Everything Quality"
          ],
          "seed": -1,
          "sampler_name": "DPM++ SDE Karras",
          "batch_size": 1,
          "n_iter": 1,
          "steps": 20,
          "cfg_scale": 7,
          "width": w,
          "height": h
        }

        if sfw:
            reqbody.update({"script_args": [True, True],
                            "script_name": "CensorScript"})

        #Globals.log.debug(f'{reqbody=}')

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url + '/sdapi/v1/txt2img', json=reqbody) as resp:
                respjson = await resp.json()
                img_b64 = respjson['images'][0]
                with io.BytesIO() as f:
                    img = base64.b64decode(img_b64)
                    f.write(img)
                    f.seek(0)
                    file = nextcord.File(f, filename=img_b64[:8] + '.png')
            return file

    async def load_prompts(self):
        try:
            with open(BotPath.get_file_path(BotPath.plugins / 'stablediffusion', 'prompts.json'), 'r') as f:
                data = f.read()
                try:
                    json_data = json.loads(data)
                    if isinstance(json_data, dict):
                        self.prompts = json_data
                        return True
                    else:
                        raise ValueError
                except ValueError:
                    Globals.log.error('Prompt file not properly formatted -> skipped')
                    return False
        except FileNotFoundError:
            Globals.log.error('Prompt file does not exist')