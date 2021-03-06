import feedparser

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Reddit'
        self.add_trigger('on_message', 'reddit', True, self.on_message)
        self.help = 'Returns the top post on reddit. Can optionally pass a subreddit to get the top post there instead'

    async def on_message(self, message, trigger):
        try:
            msg = self.Command(message)
            if len(msg.parts) > 1:
                path = '/r/' + ' '.join(msg.parts[1:]) + '/.rss'
                d = feedparser.parse('https://www.reddit.com' + path)
                await message.channel.send(d.entries[0]['link'])
            else:
                d = feedparser.parse('https://www.reddit.com/.rss')
                await message.channel.send(d.entries[0]['link'])
            return True
        except Exception as e:
            Globals.log.error(f'Could not get the top post: {str(e)}')
            await message.channel.send('Something went wrong')
            return False