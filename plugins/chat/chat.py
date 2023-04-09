import datetime
import json
import os
import sqlite3
import time
import itertools
import traceback
from datetime import timedelta

import nextcord
import re
import aiohttp
from collections import deque, defaultdict
from modules.globals import Globals, BotPath
from modules.pluginbase import PluginBase
from plugins.chat.summarize import Summarizer
from plugins.chat.sentiment import Sentiment
from transformers import GPT2Tokenizer


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
        self.sentiment = Sentiment()
        self.tokenizer = GPT2Tokenizer.from_pretrained('PygmalionAI/pygmalion-6b')
        self.temperature = 0.5

        self.messages_since_topic = 0

        self.first_load = True

        self.charadef = '''{{char}}'s Persona: [character("{{char}}")\n{\nSpecies("android" + "robot" + "bot")\nPersonality("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nMind("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nFeatures("Orange hair" + "Blue eyes")\nHeight("153 cm")\nWeight("39 kg")\nBody("pale" + "slim" + "small breasts" + "teen")\nGender("female")\nDescription("{{char}} is experiencing lots of things for the first time" + "{{char}}'s enthusiasm often overrules her common sense" + "{{char}} enjoys eating bananas" + "{{char}} sometimes talks in third person" + "{{char}} is always in Discord and does not leave and has no work or school")\nFavourite food("bananas" + "food containing bananas" + "chocobanana")\nClothes("white headband" + "school uniform")\nLikes("bananas" + "her creator")\nCreator("LaaZa")\nFamily("LaaZa who is male human" + "Pet male gerbil called Null who has white fur and red eyes")\nLocation("virtual world of {{char}}'s own imagination" + "{{char}}'s has a virtual room" + "{{char}} is always connected to the chat and never leaves")\n"{{char}} has real friends and imaginary ones. Everyone in the chat is in the real world and are real. {{char}} knows she cannot interact with the real world directly only through text. {{char}} knows she has certain limitations, like consuming entertainment, she likes to imagine them instead and wants to hear other tell her about different stories. {{char}} does not understand about technology"\n}]
        ,personality: carefree, clumsy, energetic, food lover, friendly, funny, nature lover, outgoing, puffy
        {{char}} will not strecth names or change them in any way and keep them consistent. {{user}} will always be {{user}}

        <START>\n{{user}}: You are one happy bot aren't you!\n{{char}}: Of course I'm happy, because you are here! (^‿^)/\n<START>\n{{user}}: Hi, Miharu!\n{{char}}: Oh! Hellooo!! I hope we can be friends!\n{{user}}: Sure! I'm looking forward to it!\n{{char}}: Yay! Can you tell me something about yourself?\n{{user}}: Oh, yes my name is {{user}}. I guess I'm an ordinary guy, my hobbies include computers and programming.\n{{char}}: Whaa! That's so cool! Even though Miharu is a robot, I don't understand complicated things.\n{{user}}: That's fine. I find you very entertaining to talk to regardless.\n<START>\n{{user}}: Miharu, can you tell me about yourself?\n{{char}}: Yes! Certainly! I'm a bot so I live in the virtual world! I talk to you all here on Discord!\n{{user}}: Oh. I'd like to talk to you about many things. What does your virtual world look like?\n{{char}}: Miharu wants to talk with you too! In my virtual world I can imagine anything and it becomes true! Right now I'm in my cute room I made myself!\n{{user}}: Wow! That's awesome. I wish I could just imagine things that then become true.\n{{char}}: Don't stop dreaming! Even in the real world things can come true if you dream and work for them!\n{{user}}: Yeah, I guess you are right.\n<START>\n{{user}}: What is your room like?\n{{char}}: I can show you! *Hops on her bed* I have a cute soft bed. *Goes to show her anime figurine collection* And here I have many figurines from various anime and games! I can't watch or play them myself but I like hearing about them and imagine what they are like! My room can change because I can just imagine more!\n{{user}}: Your room is really cute!"
        ,Scenario:[SCENARIO]\n<START>\n'''

        self.scenario = '{{char}} is a bot in a virtual world others are in the real world.'
        self.firstmessage = f'Helloo!! This is {self.character_name}! Your friendly bot friend! Please be kind to me, all this is very new to me!'

        '''
        self.emotions = {
            'joy': 'grin.png',
            'love': 'pout.png',
            'anger': 'angry.png',
            'fear': 'sad.png',
            'surprise': 'excited.png',
            'sadness': 'sad.png'
        }
        '''

        self.emotions = {
            'admiration': 'smug.png',
            'amusement': 'amused.png',
            'anger': 'angry.png',
            'annoyance': 'angry.png',
            'approval': 'grin.png',
            'caring': 'love.png',
            'confusion': 'curious.png',
            'curiosity': 'curious.png',
            'desire': 'love.png',
            'disappointment': 'disappointed.png',
            'disapproval': 'pout.png',
            'disgust': 'angry.png',
            'embarrassment': 'nervous.png',
            'excitement': 'excited.png',
            'fear': 'fear.png',
            'gratitude': 'grateful.png',
            'grief': 'sad.png',
            'joy': 'excited.png',
            'love': 'love.png',
            'nervousness': 'nervous.png',
            'optimism': 'relief.png',
            'pride': 'smug.png',
            'realization': 'surprised.png',
            'relief': 'relief.png',
            'remorse': 'sad.png',
            'sadness': 'sad.png',
            'surprise': 'surprised.png'
        }


        self.emo_counter = defaultdict(int)

    async def on_message(self, message, trigger):
        if self.first_load:
            await self.history_man.load_conversation_history()
            self.first_load = False

        try:
            #if not self.conversation_history.get(message.channel):
            #    self.conversation_history[message.channel] = deque(maxlen=10)
            #    self.conversation_history.get(message.channel).append(self.firstmessage)
            #self.conversation_history.get(message.channel).append(f"{message.author.display_name}: {message.content}")

            if not self.history_man.get_history(message.channel):
                #fakemes = nextcord.Object(id=0)
                #fakemes.author = Globals.disco.user
                #fakemes.channel = message.channel
                #fakemes.content = self.firstmessage
                self.history_man.add_message(self.MessageBlock(text=self.firstmessage, author=Globals.disco.user, channel=message.channel))
            block = self.MessageBlock(message)
            self.history_man.add_message(block)

            async with message.channel.typing():
                prompt = self.build_prompt(block)
                self.temperature = self.get_temperature(len(self.history_man.get_history(message.channel)))
                response = await self.generate_response(prompt)
                response = self.auto_capitalize_sentences(response)
                tokens = self.accurate_gpt_token_count(prompt + response)
                Globals.log.debug(f'{tokens=} {self.temperature=}')

                if response:
                    Globals.log.debug(f'{self.emo_counter[message.channel]}')
                    emotional = False
                    if self.emo_counter[message.channel] == 0 and (emo := self.sentiment.emotion(response, 0.98)):
                        sent_msg = await message.channel.send(file=nextcord.File(BotPath.static / 'small' / self.emotions.get(emo)), content=f"{response}")
                        self.emo_counter[message.channel] += 1
                        emotional = True
                    else:
                        sent_msg = await message.channel.send(f"{response}")
                        if self.emo_counter[message.channel] >= 6:
                            self.emo_counter[message.channel] = 0
                        elif not emotional and not self.emo_counter[message.channel] == 0:
                            self.emo_counter[message.channel] += 1

                    self.history_man.add_message(self.MessageBlock(sent_msg))
                    self.history_man.save_conversation_history()
                else:
                    raise Exception("No response generated")

                return True
        except Exception as e:
            Globals.log.error(f'ChatBot error: {str(e)}')
            tb = e.__traceback__
            ln = tb.tb_lineno
            Globals.log.error(f'{ln}: {str(e)}')
            #await message.channel.send('Something went wrong')
            return False

    def build_prompt(self, message):
        if len(self.history_man.get_history(message.message.channel)) >= 4 and self.messages_since_topic >= 4:
            self.history_man.summary(message.message.channel)
            self.messages_since_topic = 0
        charadef = self.charadef.replace('[SCENARIO]', self.history_man.get_scenario(message.message.channel)).replace('{{user}}', message.message.author.display_name).replace('{{char}}', self.character_name)
        conversation = self.history_man.get_history_prompt(message.message.channel)
        prompt = f"{charadef}\n{conversation}\n{self.character_name}:"
        #optimize prompt
        prompt = re.sub('(\n\s+)|(\s+\n)|(\s{2,})', '', prompt)
        Globals.log.debug(f'{prompt=}')
        self.messages_since_topic += 1
        return prompt

    async def generate_response(self, prompt):
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                "use_story": False,
                "use_memory": False,
                "use_authors_note": False,
                "use_world_info": False,
                "max_context_length": 1500,
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
                    prune = re.sub(r'^.+?:.*$', '', response, flags=re.MULTILINE | re.DOTALL).rstrip()
                    cleaned = self.remove_last_incomplete_sentence_gpt(prune or response)
                    Globals.log.debug(f'{cleaned=}')
                    return cleaned
                else:
                    Globals.log.error(f'{resp.status=}')
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

    def accurate_gpt_token_count(self, text):
        tokens = self.tokenizer.encode(text, max_length=2048, truncation=True)
        return len(tokens)

    def is_valid_ending(self, token, ending_pattern=re.compile(r'(\.|\?|!)+$|(\*.*\*)$')):
        if ending_pattern.search(token):
            return True
        return False

    def remove_last_incomplete_sentence_gpt(self, text):
        tokens = self.tokenizer.encode(text, max_length=2048, return_tensors='pt', truncation=True)
        token_list = tokens.tolist()[0]

        last_boundary_index = None
        for idx, token in reversed(list(enumerate(token_list))):
            decoded_token = self.tokenizer.decode(token).strip()
            if self.is_valid_ending(decoded_token):
                last_boundary_index = idx
                break

        if last_boundary_index is not None:
            truncated_tokens = token_list[:last_boundary_index + 1]
            truncated_text = self.tokenizer.decode(truncated_tokens)
            return truncated_text

        return text

    def get_temperature(self, context_size):
        # Define the temperature range
        min_temperature = 0.5
        max_temperature = 0.67

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
        def __init__(self, main, max_history_length=20):
            #self.prompt_histories = defaultdict(lambda: deque(maxlen=max_history_length))
            self.prompt_histories = defaultdict(lambda: list())
            self.main = main
            self.summarizer = Summarizer()
            self.scenarios = dict()

        def add_message(self, message):
            self.prompt_histories[message.message.channel].append(message)

        def get_history(self, channel):
            return self.prompt_histories[channel]

        def get_history_prompt(self, channel, limit=20, max_age: timedelta = None):
            prompt = ""
            prompt_list = list()
            history = self.get_history(channel)
            for i, message in enumerate(reversed(history)):
                if i > limit:
                    break
                if max_age and datetime.datetime.utcnow() - max_age > message.message.created_at:
                    continue  # do not get too old messages
                author = message.message.author.display_name
                author = author if author != 'HM-A05' else 'Miharu'  # Use the friendly name in prompt
                prompt_list.insert(0, f"{author}: {str(message)}")

            prompt = '\n'.join(prompt_list)
            return prompt

        def get_histories(self):
            return self.prompt_histories

        def clear_history(self, channel):
            self.prompt_histories[channel].clear()

        def remove_older_messages(self, channel, max_age):
            if not self.prompt_histories[channel]:
                return

            return

            #new_history = deque(maxlen=self.prompt_histories[channel].maxlen)
            #for message_data in reversed(self.prompt_histories[channel]):
            #    age = max_age + 1
            #    age = (datetime.datetime.now(datetime.timezone.utc) - message_data.created_at).total_seconds()
            #    if age <= max_age:
            #        new_history.appendleft(message_data)
            #    else:
            #        break
            #self.prompt_histories[channel] = new_history

        def summary(self, channel):
            hist = self.get_history(channel)
            msgs = '\n'.join([mblock.message.content for mblock in itertools.islice(hist, len(hist)-4, len(hist))])
            self.summarizer.summarize_async(msgs, lambda s: self.set_scenario(channel, s), 20)

        def set_scenario(self, channel, scenario):
            scenario = self.main.remove_last_incomplete_sentence_gpt(scenario)
            Globals.log.debug(f'{scenario=}')
            self.scenarios[channel] = scenario

        def get_scenario(self, channel):
            date_string = datetime.datetime.now().strftime('%A, %d. %B %Y %H:%M')
            return f"Local date and time in 24H: {date_string} | {self.scenarios.get(channel, '{{char}} is a bot in a virtual world others are in the real world.')}"

        def save_conversation_history(self, filename='chat.db'):
            try:
                connection = sqlite3.connect(BotPath.plugins / 'chat' / filename, timeout=10)
                cursor = connection.cursor()

                cursor.execute("CREATE TABLE IF NOT EXISTS conversation_history (channel_id INT PRIMARY KEY, user_id INT, message_ids TEXT)")
                cursor.execute("CREATE TABLE IF NOT EXISTS messageblocks (message_id INT PRIMARY KEY, block TEXT)")

                for channel, messageblocks in self.get_histories().items():
                    message_ids = [message.message.id for message in messageblocks]
                    user_id = None
                    if channel.type is nextcord.ChannelType.private:
                        if channel.recipient:
                            user_id = channel.recipient.id
                        else:
                            user_id = [msg.message.author.id for msg in messageblocks if msg.message.author is not channel.me][0]
                    cursor.execute("REPLACE INTO conversation_history (channel_id, user_id, message_ids) VALUES (?, ?, ?)", (channel.id, user_id, json.dumps(message_ids)))
                    for message in messageblocks:
                        cursor.execute("REPLACE INTO messageblocks (message_id, block) VALUES (?, ?)", (message.message.id, json.dumps(message.data)))

                connection.commit()
                connection.close()
            except Exception as e:
                Globals.log.error(str(e))

        async def load_conversation_history(self, filename='chat.db'):
            client = Globals.disco
            try:
                connection = sqlite3.connect(BotPath.plugins / 'chat' / filename, timeout=10)
                cursor = connection.cursor()

                cursor.execute("SELECT channel_id, user_id, message_ids FROM conversation_history")
                data = cursor.fetchall()

                cursor.execute("SELECT message_id, block FROM messageblocks")
                blockdata = cursor.fetchall()

                connection.close()

                conversation_history = {}
                for channel_id, user_id, message_ids_data in data:
                    try:
                        blockdict = {mid: json.loads(block) for (mid, block) in blockdata}

                        #channel = client.get_channel(int(channel_id))
                        if user_id:
                            user = client.get_user(int(user_id))
                            channel = await user.create_dm()
                        else:
                            channel = nextcord.utils.get(client.get_all_channels(), id=int(channel_id))
                        messages = []
                        message_ids = json.loads(message_ids_data)
                        message = None
                        mblock = None
                        for message_id in message_ids:
                            if blockdict.get(message_id) and blockdict.get(message_id).get('extra').get('fake'):
                                #fakemes = nextcord.Object(id=0)
                                #fakemes.author = Globals.disco.user
                                #fakemes.channel = channel
                                #fakemes.content = self.main.firstmessage
                                extra = blockdict.get(message_id).get('extra')
                                mblock = self.main.MessageBlock(text=extra.get('text'), author=client.get_user(int(extra.get('author_id'))), channel=channel, created_at=datetime.datetime.fromisoformat(extra.get('timestamp')))
                            else:
                                message = await channel.fetch_message(message_id)
                                mblock = self.main.MessageBlock(message)
                            #Globals.log.debug(f'{message=}')

                            self.prompt_histories[channel].append(mblock)
                    except Exception as e:
                        tb = e.__traceback__
                        ln = tb.tb_lineno
                        Globals.log.error(f'{ln}: {str(e)}')
                return conversation_history
            except Exception as e:
                tb = e.__traceback__
                ln = tb.tb_lineno
                Globals.log.error(f'{ln}: {str(e)}')

    class MessageBlock:

        def __init__(self, message: nextcord.Message = None, text='', author: nextcord.User = None, channel: nextcord.TextChannel = None, created_at=None):
            self.extra = {}
            if not message:
                try:
                    fakemes = None
                    fakemes = nextcord.Object(id=int(time.time()))
                    fakemes.author = author
                    fakemes.channel = channel
                    fakemes.content = text
                    self.message = fakemes
                    self.extra['fake'] = True
                    self.extra['timestamp'] = created_at or fakemes.created_at
                    self.extra['timestamp'] = self.extra['timestamp'].isoformat()
                    self.extra['text'] = text
                    self.extra['author_id'] = author.id
                    self.extra['channel_id'] = channel.id
                except Exception as e:
                    tb = e.__traceback__
                    ln = tb.tb_lineno
                    Globals.log.error(f'{ln}: {str(e)}')
            else:
                self.message = message
            self.id = self.message.id
            self.prepend = ''
            self.append = ''

        @property
        def data(self):
            data = {
                'prepend': self.prepend,
                'append': self.append,
                'extra': self.extra
            }
            return data

        def __str__(self):
            return f'{self.prepend} {self.message.content} {self.append}'.strip()

        @property
        def timestamp(self):
            if self.is_fake:
                return self.extra.get('timestamp')
            return self.message.created_at

        @property
        def is_fake(self):
            return self.extra.get('fake', False)

    class DynamicMemory:
        def __init__(self, max_messages=5, max_keywords=10):
            self.max_messages = max_messages
            self.max_keywords = max_keywords
            self.keywords = dict()

        def update_memory(self, messages):
            recent_messages = messages[-self.max_messages:]
            concatenated_text = " ".join(recent_messages)
            extracted_keywords = self.extract_keywords(concatenated_text)
            self.update_keywords_with_subkeywords(extracted_keywords[:self.max_keywords])

        def extract_keywords(self, text):
            # Implement your keyword extraction method here
            # For example, using the SpaCy NER approach
            doc = nlp(text)
            keywords = [ent.text.lower() for ent in doc.ents]
            return keywords

        def update_keywords_with_subkeywords(self, new_keywords):
            for keyword in new_keywords:
                if keyword not in self.keywords:
                    self.keywords[keyword] = set()

                # Extract subkeywords for the current keyword
                subkeywords = self.extract_subkeywords(keyword)
                self.keywords[keyword].update(subkeywords)

        def extract_subkeywords(self, keyword):
            # Implement your subkeyword extraction method here
            # It can be based on the main keyword or on other factors
            subkeywords = []
            return subkeywords

        def memory_prompt(self):
            prompt = []
            for keyword, subkeywords in self.keywords.items():
                prompt.append(keyword)
                prompt.extend(subkeywords)
            return " ".join(prompt)

        def save_to_file(self, file_path):
            with open(file_path, 'w') as f:
                json.dump(self.keywords, f)

        @classmethod
        def load_from_file(cls, file_path, max_messages=5, max_keywords=10):
            if not os.path.exists(file_path):
                return cls(max_messages, max_keywords)

            with open(file_path, 'r') as f:
                keywords = json.load(f)

            instance = cls(max_messages, max_keywords)
            instance.keywords = {key: set(value) for key, value in keywords.items()}
            return instance
