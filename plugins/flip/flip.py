from modules import upsidedown as upd
from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Flip text'
        self.add_trigger('on_message', 'upd', True, self.on_message)
        self.help = 'Flips a given string upside down'

    async def on_message(self, message, trigger):
        try:
            msg = self.Command(message)
            text = ' '.join(msg.parts[1:])
            await message.channel.send(upd.flip(text))
            return True
        except Exception as e:
            Globals.log.error(f'Could not flip and send the message: {str(e)}')
            await message.channel.send('Something went wrong')
            return False