import datetime
import json
import os
import sqlite3

import nextcord
import re
import aiohttp
from collections import deque, defaultdict
from modules.globals import Globals, BotPath
from modules.pluginbase import PluginBase


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'ChatBot'
        self.add_trigger('on_message', re.compile('.+'), False, self.on_message)
        self.help = 'Acts as a chatbot, generating dialogue with context'
        self.api_url = 'http://localhost:5000/api/v1/generate' #'https://miharu.free.beeceptor.com'  # Replace with your desired API URL
        self.character_name = 'Miharu'
        self.history_man = self.PromptHistoryManager(self)
        self.temperature = 0.5

        self.first_load = True

        self.charadef = '''Miharu's Persona: [character("Miharu")\n{\nSpecies("android" + "robot" + "bot")\nPersonality("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nMind("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nFeatures("Orange hair" + "Blue eyes")\nHeight("153 cm")\nWeight("39 kg")\nBody("pale" + "slim" + "small breasts" + "teen")\nGender("female")\nDescription("experiencing lots of things for the first time" + "{{char}}'s enthusiasm often overrules her common sense" + "{{char}} enjoys eating bananas" + "{{char}} sometimes talks in third person")\nFavourite food("bananas" + "food containing bananas" + "chocobanana")\nClothes("white headband" + "school uniform")\nLikes("bananas" + "her creator")\nCreator("LaaZa")\nFamily("LaaZa who is male human" + "Pet male gerbil called Null who has white fur and red eyes")\nLocation("virtual world of {{char}}'s own imagination" + "{{char}}'s has a virtual room" + "{{char}} is always connected to the chat and never leaves")\n"{{char}} has real friends and imaginary ones. Everyone in the chat is in the real world and are real. {{char}} knows she cannot interact with the real world directly only through text. {{char}} knows she has certain limitations, like consuming entertainment, she likes to imagine them instead and wants to hear other tell her about different stories. {{char}} does not understand about technology"\n}]
        ,personality: carefree, clumsy, energetic, food lover, friendly, funny, nature lover, outgoing, puffy
        {{char}} will not strecth names or change them in any way and keep them consistent. {{user}} will always be {{user}}

        <START>\n{{user}}: You are one happy bot aren't you!\n{{char}}: Of course I'm happy, because you are here! (^‿^)/\n<START>\n{{user}}: Hi, Miharu!\n{{char}}: Oh! Hellooo!! I hope we can be friends!\n{{user}}: Sure! I'm looking forward to it!\n{{char}}: Yay! Can you tell me something about yourself?\n{{user}}: Oh, yes my name is {{user}}. I guess I'm an ordinary guy, my hobbies include computers and programming.\n{{char}}: Whaa! That's so cool! Even though Miharu is a robot, I don't understand complicated things.\n{{user}}: That's fine. I find you very entertaining to talk to regardless.\n<START>\n{{user}}: Miharu, can you tell me about yourself?\n{{char}}: Yes! Certainly! I'm a bot so I live in the virtual world! I talk to you all here on Discord!\n{{user}}: Oh. I'd like to talk to you about many things. What does your virtual world look like?\n{{char}}: Miharu wants to talk with you too! In my virtual world I can imagine anything and it becomes true! Right now I'm in my cute room I made myself!\n{{user}}: Wow! That's awesome. I wish I could just imagine things that then become true.\n{{char}}: Don't stop dreaming! Even in the real world things can come true if you dream and work for them!\n{{user}}: Yeah, I guess you are right.\n<START>\n{{user}}: What is your room like?\n{{char}}: I can show you! *Hops on her bed* I have a cute soft bed. *Goes to show her anime figurine collection* And here I have many figurines from various anime and games! I can't watch or play them myself but I like hearing about them and imagine what they are like! My room can change because I can just imagine more!\n{{user}}: Your room is really cute!"
        ,scenario:{{char}} is a bot in a virtual world others are in the real wolrd.\n<START>\n'''

        self.firstmessage = f'Helloo!! This is {self.character_name}! Your friendly bot friend! Please be kind to me, all this is very new to me!'

    async def on_message(self, message, trigger):
        if self.first_load:
            await self.history_man.load_conversation_history()

        try:
            #if not self.conversation_history.get(message.channel):
            #    self.conversation_history[message.channel] = deque(maxlen=10)
            #    self.conversation_history.get(message.channel).append(self.firstmessage)
            #self.conversation_history.get(message.channel).append(f"{message.author.display_name}: {message.content}")
            if not self.history_man.get_history(message.channel):
                fakemes = nextcord.Object(id=0)
                fakemes.author = Globals.disco.user
                fakemes.channel = message.channel
                fakemes.content = self.firstmessage
                self.history_man.add_message(fakemes)
            self.history_man.add_message(message)

            async with message.channel.typing():
                prompt = self.build_prompt(message)
                self.temperature = self.get_temperature(len(self.history_man.get_history(message.channel)))
                response = await self.generate_response(prompt)
                response = self.auto_capitalize_sentences(response)
                tokens = self.approximate_gpt_token_count(prompt + response)
                Globals.log.debug(f'{tokens=} {self.temperature=}')

                if response:
                    sent_msg = await message.channel.send(f"{response}")
                    self.history_man.add_message(sent_msg)
                    self.history_man.save_conversation_history()
                else:
                    raise Exception("No response generated")

                return True
        except Exception as e:
            Globals.log.error(f'ChatBot error: {str(e)}')
            #await message.channel.send('Something went wrong')
            return False

    def build_prompt(self, message):
        charadef = self.charadef.replace('{{user}}', message.author.display_name).replace('{{char}}', self.character_name)
        conversation = self.history_man.get_history_prompt(message.channel)
        prompt = f"{charadef}\n{conversation}\n{self.character_name}:"
        #optimize prompt
        prompt = re.sub('(\n\s+)|(\s+\n)|(\s{2,})', '', prompt)
        Globals.log.debug(f'{prompt=}')
        return prompt

    async def generate_response(self, prompt):
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                "use_story": False,
                "use_memory": False,
                "use_authors_note": False,
                "use_world_info": False,
                "max_context_length": 1400,
                "max_length": 80,
                "rep_pen": 1.18,
                "rep_pen_range": 1024,
                "rep_pen_slope": 0.9,
                "temperature": self.temperature,
                "tfs": 0.9,
                "top_a": 0,
                "top_k": 0,
                "top_p": 0.9,
                "typical": 1,
                "sampler_order": [
                    6, 0, 1, 2,
                    3, 4, 5
                ],
                "singleline": True
            }
            async with session.post(self.api_url, json=payload) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    generated_text = response_data['results'][0]['text']
                    response = generated_text.split(f"{self.character_name}:")[-1].strip()
                    Globals.log.debug(f'{response}')
                    prune = re.sub(r'^.+?:.*$', '', response, flags=re.MULTILINE | re.DOTALL).rstrip()
                    Globals.log.debug(f'{prune}')
                    return prune or response
                else:
                    return None

    def auto_capitalize_sentences(self, text, pattern=re.compile(r'((?<!\.)[!?]\s+|(?<![.])[.]\s+|\(\s*|"\s*|(?<=\s)i(?=\s))(\w)')):
        # Capitalize the first letter of the text
        text = text[0].upper() + text[1:]

        # Capitalize the first letter after sentence-ending punctuation, inside quotes, or inside parentheses
        text = pattern.sub(lambda m: m.group(1) + m.group(2).upper(), text)

        return text

    def approximate_gpt_token_count(self, text, pattern=re.compile(r'\w+|[^\w\s]', re.UNICODE)):
        tokens = re.findall(pattern, text)
        return len(tokens)

    def get_temperature(self, context_size):
        # Define the temperature range
        min_temperature = 0.5
        max_temperature = 0.7

        # Define the context size range for adjusting the temperature
        min_context_size = 2
        max_context_size = 15

        # Calculate the temperature based on the context size
        temperature = min_temperature + (max_temperature - min_temperature) * (
            (context_size - min_context_size) / (max_context_size - min_context_size)
        )

        # Clip the temperature to the defined range
        temperature = max(min_temperature, min(temperature, max_temperature))

        return temperature

    class PromptHistoryManager:
        def __init__(self, main, max_history_length=15):
            self.prompt_histories = defaultdict(lambda: deque(maxlen=max_history_length))
            self.main = main

        def add_message(self, message):
            self.prompt_histories[message.channel].append(message)

        def get_history(self, channel):
            return self.prompt_histories[channel]

        def get_history_prompt(self, channel):
            prompt = ""
            prompt_list = list()
            history = self.get_history(channel)
            for message in history:
                author = message.author.display_name
                author = author if author != 'HM-A05' else 'Miharu'  # Use the friendly name in prompt
                prompt_list.append(f"{author}: {message.content}")

            prompt = '\n'.join(prompt_list)
            return prompt

        def get_histories(self):
            return self.prompt_histories

        def clear_history(self, channel):
            self.prompt_histories[channel].clear()

        def remove_older_messages(self, channel, max_age):
            if not self.prompt_histories[channel]:
                return

            new_history = deque(maxlen=self.prompt_histories[channel].maxlen)
            for message_data in reversed(self.prompt_histories[channel]):
                age = max_age + 1
                age = (datetime.datetime.now(datetime.timezone.utc) - message_data.created_at).total_seconds()
                if age <= max_age:
                    new_history.appendleft(message_data)
                else:
                    break
            self.prompt_histories[channel] = new_history

        def save_conversation_history(self, filename='chat.db'):
            try:
                connection = sqlite3.connect(BotPath.plugins / 'chat' / filename)
                cursor = connection.cursor()

                cursor.execute("CREATE TABLE IF NOT EXISTS conversation_history (channel_id INT PRIMARY KEY, user_id INT, message_ids TEXT)")

                for channel, messages in self.get_histories().items():
                    message_ids = [message.id for message in messages]
                    user_id = None
                    if channel.type is nextcord.ChannelType.private:
                        if channel.recipient:
                            user_id = channel.recipien.id
                        else:
                            user_id = [msg.author.id for msg in messages if msg.author is not channel.me][0]
                    cursor.execute("REPLACE INTO conversation_history (channel_id, user_id, message_ids) VALUES (?, ?, ?)", (channel.id, user_id, json.dumps(message_ids)))

                connection.commit()
                connection.close()
            except Exception as e:
                Globals.log.error(str(e))

        async def load_conversation_history(self, filename='chat.db'):
            client = Globals.disco
            try:
                connection = sqlite3.connect(BotPath.plugins / 'chat' / filename)
                cursor = connection.cursor()

                cursor.execute("SELECT channel_id, user_id, message_ids FROM conversation_history")
                data = cursor.fetchall()

                connection.close()

                conversation_history = {}
                for channel_id, user_id, message_ids_data in data:
                    try:
                        #channel = client.get_channel(int(channel_id))
                        if user_id:
                            channel = await client.get_user(int(user_id)).create_dm()
                        else:
                            channel = nextcord.utils.get(client.get_all_channels(), id=int(channel_id))
                        messages = []
                        message_ids = json.loads(message_ids_data)
                        message = None
                        for message_id in message_ids:
                            if message_id == 0:
                                fakemes = nextcord.Object(id=0)
                                fakemes.author = Globals.disco.user
                                fakemes.channel = channel
                                fakemes.content = self.main.firstmessage
                                message = fakemes
                            else:
                                message = await channel.fetch_message(message_id)
                            messages.append(message)
                        conversation_history[channel] = deque(messages, maxlen=15)
                    except Exception as e:
                        Globals.log.error(str(e))
                return conversation_history
            except Exception as e:
                Globals.log.error(str(e))


