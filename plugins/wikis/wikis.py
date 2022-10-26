import asyncio
import re
from difflib import SequenceMatcher as SM

import aiohttp
import nextcord
import fandom
import fandom.error
import wikipedia
from bs4 import BeautifulSoup

from modules.globals import Globals
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    # plugin specific

    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'Wikipedia and Wikia'
        self.add_trigger('on_message', 'wiki', True, self.on_message_wikipedia)
        self.add_trigger('on_message', 'wikia', True, self.on_message_wikia)
        self.help = 'Query wikipedia and wikia'

    async def on_message_wikipedia(self, message, trigger):
        try:
            msg = self.Command(message)
            wiki = None
            if len(msg.parts) > 1:
                keyword = ' '.join(msg.parts[1:])
                wiki = wikipedia.page(keyword)
            else:
                wiki = wikipedia.random()[0]

        except wikipedia.exceptions.DisambiguationError as e:
            best_match = ''
            search = e.options
            options = list()
            for i, opt in enumerate(search):
                options.append(str(i + 1) + '. ' + opt)
            opts = '\n'.join(options)
            await message.channel.send(f'Try to be more specific. I found these though:\n{self.markdown(opts)}\nType any number above to get that article', delete_after=10)
            try:
                retry = await Globals.disco.wait_for(event='message', timeout=10, check=lambda m: m.channel == message.channel and m.author == message.author)
                best_match = search[int(retry.content) - 1]
                try:
                    await retry.delete()
                except (nextcord.Forbidden, nextcord.HTTPException):
                    pass
            except (ValueError, IndexError):
                return True
            except AttributeError:
                await message.channel.send('...well maybe it just doesn\'t exist, you suck at searching or I suck at finding... or maybe we just need more bananas.')
                return True
            except asyncio.TimeoutError:
                pass

            wiki = wikipedia.page(best_match)
        except wikipedia.exceptions.PageError:
            await message.channel.send('I didn\'t find anything on the Wikipedia about that. :<')
            return True

        text = f'{wikipedia.summary(wiki.title, 2)}'
        if len(text) > 400:
            text = f'{wikipedia.summary(wiki.title, 1)}'
        if len(text) > 400:
            text = f'{wikipedia.summary(wiki.title, 1)[:-3]}...'

        embed = nextcord.Embed(title=wiki.title, url=wiki.url.replace(' ', '_'), description='```' + text + '```', colour=nextcord.Colour.dark_blue())

        await message.channel.send(embed=embed)

        try:
            await message.delete()
        except (nextcord.Forbidden, nextcord.HTTPException):
            pass

        return True

        #except Exception as e:
         #   Globals.log.error(f'Could not search wikipedia: {str(e)}')
          #  return False

    async def on_message_wikia(self, message, trigger):
        try:
            msg = self.Command(message)
            wiki = None
            subwikia = msg.word(0)
            if len(msg.parts) > 2:
                keyword = ' '.join(msg.parts[2:])
                search = fandom.search(keyword, subwikia)
                best_match = tuple()
                test_disamb = False
                while True:
                    best_ratio = 0
                    best_match = tuple()
                    ratios = list()
                    for result in search:
                        result, i = result
                        if keyword.lower() in result.lower():
                            ratio = SM(None, keyword.lower(), result.lower()).ratio()
                            if ratio > best_ratio and ratio > 0.4:
                                best_ratio = ratio
                                best_match = (result, i)
                                ratios.append(ratio)
                            r = list(reversed(sorted(ratios)))

                            if len(r) > 1:
                                if r[0] - r[1] <= 0.2:
                                    best_match = tuple()

                            #print(f'{result=} {ratio=} {best_ratio=}')

                    if test_disamb and 'may refer to:' in fandom.page(pageid=int(best_match[1]), wiki=subwikia).summary:
                        search.remove(best_match)
                        test_disamb = False
                        continue
                    break

                try:
                    redirect_test = fandom.summary(keyword, subwikia)
                    if 'REDIRECT' in redirect_test:
                        best_match = redirect_test[9:]
                        #print(f'{best_match=}')
                except fandom.error.FandomError:
                    pass
                if not best_match:
                    #raise fandom.DisambiguationError(keyword, search)
                    options = list()
                    for i, opt in enumerate(search):
                        options.append(str(i + 1) + '. ' + opt[0])
                    opts = '\n'.join(options)
                    await message.channel.send(f'Try to be more specific. I found these though:\n{self.markdown(opts)}\nType any number above to get that article', delete_after=10)
                    try:
                        retry = await Globals.disco.wait_for(event='message', timeout=10, check=lambda m: m.channel == message.channel and m.author == message.author)
                        best_match = search[int(retry.content) - 1]
                        try:
                            await retry.delete()
                        except (nextcord.Forbidden, nextcord.HTTPException):
                            pass
                    except (ValueError, IndexError):
                        return True
                    except AttributeError:
                        await message.channel.send('...well maybe it just doesn\'t exist, you suck at searching or I suck at finding... or maybe we just need more bananas.')
                        return True
                    except asyncio.TimeoutError:
                        return True

                wiki = fandom.page(pageid=int(best_match[1]), wiki=subwikia)
            else:
                await message.channel.send('I didn\'t find anything on the Wikia about that. :<')
                return True

            '''
            text = f'**{wiki.title}**| {wiki.url}\n{fandom.summary(subwikia, wiki.title)}'
            text = self.markdown('\n'.join(re.findall(r'^.+\.', wiki.content[:1500], flags=re.M)))

            text = f'**{wiki.title}**\n{text}'
            
            if len(text) > 400:
                text = f'**{wiki.title}**| {wiki.url}\n{fandom.summary(subwikia ,wiki.title)}'
            if len(text) > 400:
                text = f'**{wiki.title}**| {wiki.url}\n{fandom.summary(subwikia, wiki.title)[:-3]}...'
            '''

            image = ''
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(wiki.url) as response:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        try:
                            image = soup.select_one('[class*="infobox"] img').attrs['src']
                            if not image.startswith('http'):
                                raise AttributeError
                        except AttributeError:
                            image = soup.find('meta', attrs={'property': 'og:image'}).attrs['content']
            except AttributeError:
                pass

            Globals.log.debug(f'Image url: {image}')

            text = wiki.plain_text[:2000]
            if not text:
                text = fandom.summary(wiki.title, subwikia)
            paragraph = re.findall(r'^.+\.', text, flags=re.M)
            if not paragraph:
                paragraph = [text, ]
            embed_long = nextcord.Embed(title=wiki.title, url=wiki.url.replace(' ', '_'), description='```' + '``````'.join(paragraph) + '```', colour=nextcord.Colour.teal())
            embed_short = nextcord.Embed(title=wiki.title, url=wiki.url.replace(' ', '_'), description='```' + paragraph[0] + '```', colour=nextcord.Colour.teal())
            if image:
                embed_long.set_image(url=image)
            embed_long.set_footer(text=re.search(r'(?:/)((?:[a-z0-9|-]+\.)*[a-z0-9|-]+\.[a-z]+)(?:/)', wiki.url).group(1))
            embed_short.set_footer(text=re.search(r'(?:/)((?:[a-z0-9|-]+\.)*[a-z0-9|-]+\.[a-z]+)(?:/)', wiki.url).group(1))

            if Globals.permissions.client_has_discord_permissions(('manage_messages',), message.channel):
                imsg = PluginBase.InteractiveMessage()
                await imsg.add_toggle('➕', '➖', imsg.edit, imsg.edit, tuple(), tuple(), {'embed': embed_long}, {'embed': embed_short})
                await imsg.send(message.channel, embed=embed_short)
            else:
                await message.channel.send(message.channel, embed=embed_long)

        except fandom.error.PageError:
            await message.channel.send('I didn\'t find anything on the Wikia about that. :<')
        except ValueError:
            await message.channel.send('I didn\'t find anything on the Wikia about that. :<')
        except fandom.error.FandomError as e:
            Globals.log.error(f'{e}')
            await message.channel.send('I didn\'t find anything :<')

        try:
            await message.delete()
        except (nextcord.Forbidden, nextcord.HTTPException):
            pass

        return True
