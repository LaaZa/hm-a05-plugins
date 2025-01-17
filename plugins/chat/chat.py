import datetime
import json
import time
import itertools
import traceback
from datetime import timedelta, timezone
import humanize

import aiosqlite
import nextcord
import re
import aiohttp
from jinja2 import Environment
from collections import defaultdict
from modules.globals import Globals, BotPath
from modules.pluginbase import PluginBase
from plugins.chat.summarize import Summarizer
from plugins.chat.sentiment import Sentiment
from plugins.chat.caption import Caption
from plugins.chat.dynamicmemory import DynamicMemory
from plugins.chat.templates import CHAT_TEMPLATE, MEMORY_EXTRACTION_TEMPLATE
from transformers import LlamaTokenizer
from ollama import AsyncClient


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.type = PluginBase.PluginType.UNCORE
        self.name = 'ChatBot'
        self.add_trigger('on_message', re.compile('.*'), False, self.on_message)
        self.help = 'Acts as a chatbot, generating dialogue with context'
        self.api_url = 'http://localhost:11434'
        self.character_name = 'Miharu'
        self.history_man = self.PromptHistoryManager(self)
        self.sentiment = Sentiment()
        self.captioner = Caption()
        self.tokenizer = LlamaTokenizer.from_pretrained('SanjiWatsuki/Silicon-Maid-7B')
        self.dynamicmemory = DynamicMemory()
        self.temperature = 0.5
        self.kobold = True
        self.messages_since_topic = 0
        self.first_load = True

        #load templates
        self.jinja_env = Environment()
        self.chat_template = self.jinja_env.from_string(CHAT_TEMPLATE)
        self.memory_extraction_template = self.jinja_env.from_string(MEMORY_EXTRACTION_TEMPLATE)

        # load custom config
        try:
            self.api_url = Globals.config_data.get_opt('chat', 'apiurl')
            #self.kobold = Globals.config_data.get_opt('chat', 'apikobold')
        except KeyError as e:
            Globals.log.error('using default config for chat')

        self.model_tag = "### Response:"
        self.user_tag = "### Instruction:"

        self.prompt_format = '{{system}}\n{{chardef}}\n{{personality}}\n{{scenario}}\n'

        self.system_mes = f"Enter RP mode. You shall reply to {{{{user}}}} while staying in character. {{{{user}}}} is also known as {{{{user_nick}}}}. Your responses must be detailed, creative, immersive, and drive the scenario forward. Answer naturally in a short Discord message. You will follow {self.character_name}'s persona."

        self.charadef = '''[character("{{char}}")\n{\nSpecies("android" + "robot" + "bot")\nPersonality("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nMind("carefree" + "clumsy" + "energetic" + "food lover" + "friendly" + "funny" + "nature lover" + "outgoing" + "puffy" + "third person")\nFeatures("Orange hair" + "Blue eyes")\nHeight("153 cm")\nWeight("39 kg")\nBody("pale" + "slim" + "small breasts" + "teen")\nGender("female")\nDescription("{{char}} is experiencing lots of things for the first time" + "{{char}}'s enthusiasm often overrules her common sense" + "{{char}} enjoys eating bananas" + "{{char}} sometimes talks in third person" + "{{char}} is always in Discord and does not leave and has no work or school")\nFavourite food("bananas" + "food containing bananas" + "chocobanana")\nClothes("white headband" + "school uniform")\nLikes("bananas" + "her creator")\nCreator("LaaZa")\nFamily("LaaZa who is male human" + "3 pet male gerbils called Lux, Pax and Nux, located in the real world")\nLocation("virtual world of {{char}}'s own imagination" + "{{char}}'s has a virtual room" + "{{char}} is always connected to the chat and never leaves")\n"{{char}} has real friends and imaginary ones. Everyone in the chat is in the real world and are real. {{char}} knows she cannot interact with the real world directly only through text. {{char}} knows she has certain limitations, like consuming entertainment, she likes to imagine them instead and wants to hear other tell her about different stories. {{char}} does not understand about technology"\n}]'''

        self.personality = "carefree, clumsy, energetic, food lover, friendly, funny, nature lover, outgoing, puffy"

        self.scenario = '{{char}} is a bot in a virtual world others are in the real world.'
        self.firstmessage = f'Helloo!! This is {self.character_name}! Your friendly bot friend! Please be kind to me, all this is very new to me!'
        self.examplemessages = '''<START>\n{{user}}: You are one happy bot aren't you!\n{{char}}: Of course I'm happy, because you are here! (^‿^)/\n<START>\n{{user}}: Hi, Miharu!\n{{char}}: Oh! Hellooo!! I hope we can be friends!\n{{user}}: Sure! I'm looking forward to it!\n{{char}}: Yay! Can you tell me something about yourself?\n{{user}}: Oh, yes my name is {{user}}. I guess I'm an ordinary guy, my hobbies include computers and programming.\n{{char}}: Whaa! That's so cool! Even though Miharu is a robot, I don't understand complicated things.\n{{user}}: That's fine. I find you very entertaining to talk to regardless.\n<START>\n{{user}}: Miharu, can you tell me about yourself?\n{{char}}: Yes! Certainly! I'm a bot so I live in the virtual world! I talk to you all here on Discord!\n{{user}}: Oh. I'd like to talk to you about many things. What does your virtual world look like?\n{{char}}: Miharu wants to talk with you too! In my virtual world I can imagine anything and it becomes true! Right now I'm in my cute room I made myself!\n{{user}}: Wow! That's awesome. I wish I could just imagine things that then become true.\n{{char}}: Don't stop dreaming! Even in the real world things can come true if you dream and work for them!\n{{user}}: Yeah, I guess you are right.\n<START>\n{{user}}: What is your room like?\n{{char}}: I can show you! *Hops on her bed* I have a cute soft bed. *Goes to show her anime figurine collection* And here I have many figurines from various anime and games! I can't watch or play them myself but I like hearing about them and imagine what they are like! My room can change because I can just imagine more!\n{{user}}: Your room is really cute!'''

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
            'surprise': 'surprised.png',
            'neutral': 'excited.png'
        }

        self.emo_counter = defaultdict(int)

    async def on_message(self, message, trigger):
        if self.first_load:
            await self.history_man.load_conversation_history()
            self.first_load = False

        try:

            if not self.history_man.get_history(message.channel):
                self.history_man.add_message(self.MessageBlock(text=self.firstmessage, author=Globals.disco.user, channel=message.channel))
            block = self.MessageBlock(message)
            try:
                if len(self.history_man.get_history(message.channel)) > 1 and (last_mes_time := self.history_man.get_history(message.channel)[-2].message.created_at):
                    if datetime.datetime.now(timezone.utc) >= last_mes_time + datetime.timedelta(hours=1):
                        block.prepend = f"*{humanize.naturaltime(last_mes_time, when=datetime.datetime.now(timezone.utc)).replace('ago', 'has passed since previous message')}*"
            except Exception as e:
                Globals.log.debug(f'Tried to add time {e}')

            # caption images if found
            if message.attachments:
                appends = []
                images = []
                for attachment in message.attachments:
                    if attachment.content_type.startswith("image/"):
                        images.append(attachment.url)
                if images:
                    captions = await self.captioner.caption(images)
                    for caption in captions:
                        if caption:
                            appends.append(f'image that shows {caption}')
                if appends:
                    block.append = f'*Sent an {" and another ".join(appends)}*'

                if not images:
                    return False

            self.history_man.add_message(block)

            async with message.channel.typing():
                self.dynamicmemory.update_memory(self.history_man.get_history(message.channel)[:-20])
                prompt = self.build_prompt(block)
                self.temperature = self.get_temperature(len(self.history_man.get_history(message.channel)))
                response = await self.generate_response(prompt)
                response = self.auto_capitalize_sentences(response)
                tokens = self.accurate_gpt_token_count(prompt + response) #await self.api_token_count(prompt + response)
                Globals.log.debug(f'{tokens=} {self.temperature=}')

                if response:
                    Globals.log.debug(f'{self.emo_counter[message.channel]}')
                    emotional = False
                    if self.emo_counter[message.channel] == 0 and (emo := await self.sentiment.emotion(response, 0.70)):
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
                    await self.history_man.save_conversation_history()
                else:
                    raise Exception("No response generated")

            return True
        except Exception as e:
            #Globals.log.error(f'ChatBot error: {str(e)}')
            #tb = e.__traceback__
            #ln = tb.tb_lineno
            #Globals.log.error(f'{ln}: {str(e)}')
            Globals.log.error(''.join(traceback.format_exception(None, e, e.__traceback__)))
            return False

    def build_prompt(self, message):
        memory = []
        memory_prompt = ''
        memory_messages = []
        #memory_messages = self.history_man.get_messages_by_id(
        #self.dynamicmemory.memory_id_prompt(
        #self.history_man.get_history(message.message.channel)[-4:]))

        mes_list = self.dynamicmemory.memory_id_prompt(self.history_man.get_history(message.message.channel)[-4:])
        for mes in mes_list:
            memory_messages.append(self.history_man.get_history_slice_by_id(mes, 3, message.message.author.id))

        for mem_msg in memory_messages:
            if isinstance(mem_msg, list):
                hist = []
                for msg in mem_msg:
                    author = msg.message.author.display_name
                    author = author if author != Globals.disco.user.name else self.character_name
                    hist.append(f'{self.model_tag if author == self.character_name else self.user_tag}{author}: {msg.message.content}')
                if hist:
                    hist = "".join(hist)
                    memory.append(f'<START>{hist}')
            else:
                author = mem_msg.message.author.display_name
                author = author if author != Globals.disco.user.name else self.character_name
                memory.append(f'<START>\n{self.model_tag if author == self.character_name else self.user_tag}{author}: {mem_msg.message.content}')

        if memory:
            memory_prompt = ''.join(memory)
            memory_prompt = f'This reminds you of these events from your past: [{memory_prompt}]'

        history_len = len(self.history_man.get_history(message.message.channel))
        if history_len >= 4 and self.messages_since_topic >= 4:
            self.history_man.summary(message.message.channel)
            self.messages_since_topic = 0
        #charadef = self.charadef
        scenario = self.history_man.get_scenario(message.message.channel).replace('{{user}}', message.message.author.display_name).replace('{{char}}', self.character_name)
        conversation = self.history_man.get_history_prompt(message.message.channel)
        #prompt = f"{memory_prompt}{charadef}\n{conversation}\n{self.character_name}:"

        #if memory_prompt:
            #prompt = f"{charadef}\nThis reminds you of these events from your past: [{memory_prompt}]\n\n<START>{conversation}\n{self.character_name}:"\
            #prompt = f"This reminds you of these events from your past: [{memory_prompt}]\n\n{charadef}\n\n{conversation}\n{self.character_name}:"
            #prompt = f'{self.system_mes}\n{self.charadef}\n{self.personality}\n{scenario}\n[{memory_prompt}]\n{conversation}{self.model_tag}{self.character_name}:'
        #else:
            #prompt = f'{self.system_mes}\n{self.charadef}\n{self.personality}\n{scenario}\n{conversation}{self.model_tag}{self.character_name}:'

        prompt = self.chat_template.render(
            system_mes=self.system_mes,
            charadef=self.charadef,
            scenario=scenario,
            memory_prompt=memory_prompt,
            conversation=conversation,
            model_tag=self.model_tag,
            user_tag=self.user_tag,
            bot_name=self.character_name,
            bot_username=Globals.disco.user,
            example_messages=self.examplemessages
        )


        #optimize prompt
        #prompt = re.sub(r'(\n\s+)|(\s+\n)|(\s{2,})', '', prompt)
        prompt = prompt.replace('{{user}}', message.message.author.name).replace('{{char}}', self.character_name).replace('{{user_nick}}', message.message.author.display_name or message.message.author.global_name)
        Globals.log.debug(f'{prompt=}')
        self.messages_since_topic += 1
        return prompt

    async def generate_response(self, prompt):
        # async with aiohttp.ClientSession() as session:
        #     payload = {}
        #     if self.kobold:
        #         payload = {
        #             'prompt': prompt,
        #             'use_story': False,
        #             'use_memory': False,
        #             'use_authors_note': False,
        #             'use_world_info': False,
        #             'max_context_length': 4096,
        #             'max_length': 80,
        #             'rep_pen': 1.1,
        #             'rep_pen_range': 2048,
        #             'rep_pen_slope': 0.2,
        #             'temperature': self.temperature,
        #             'tfs': 1,
        #             'top_a': 0,
        #             'top_k': 0,
        #             'top_p': 0.73,
        #             'typical': 1,
        #             'sampler_order': [
        #                 6, 0, 1, 3,
        #                 4, 2, 5
        #             ],
        #             'singleline': True,
        #             'stop_sequence': [
        #                 '<|user|>',
        #                 '<|model|>',
        #                 '<|user',
        #                 '<',
        #                 '<|',
        #                 '|',
        #                 '\n'
        #             ]
        #         }
        #     else:
        #         payload = {
        #             'prompt': prompt,
        #             'do_sample': True,
        #             'truncation_length': 2048,
        #             'max_new_tokens': 80,
        #             'repetition_penalty': 1.18,
        #             'temperature': self.temperature,
        #             'top_p': 0.9,
        #             'typical_p': 1,
        #             'min_length': 0,
        #             'no_repeat_ngram_size': 0,
        #             'num_beams': 1,
        #             'penalty_alpha': 0,
        #             'length_penalty': 1,
        #             'early_stopping': False,
        #             'seed': -1,
        #             'add_bos_token': True,
        #             'ban_eos_token': False,
        #             'skip_special_tokens': True,
        #             'stopping_strings': ['\n']
        #         }
        #
        #     async with session.post(self.api_url, json=payload) as resp:
        #         if resp.status == 200:
        #             response_data = await resp.json()
        #             generated_text = response_data['results'][0]['text']
        #             response = generated_text.split(f"{self.character_name}:")[-1].strip()
        #             #prune = re.sub(r'\n.+?:.*$', '', response, flags=re.MULTILINE | re.DOTALL).rstrip()
        #             cleaned = self.remove_last_incomplete_sentence_gpt(response)
        #             #cleaned = response
        #             Globals.log.debug(f'{cleaned=}')
        #             if cleaned != response:
        #                 Globals.log.debug(f'Original {response=}')
        #             return cleaned
        #         else:
        #             Globals.log.error(f'{resp.status=}')
        #             return None

        payload = {
            'prompt': prompt,
            'options': {
                'num_ctx': 12000,
                'num_predict': 80,
                'rep_pen': 1,
                'rep_pen_range': 2048,
                'rep_pen_slope': 1,
                'temperature': self.temperature,
                'tfs': 1,
                'top_a': 0,
                'top_k': 0,
                'top_p': 1,
                'typical': 1,
                'penalize_newline': True,
                'stop_sequence': [
                    '\n'
                ]
            }
        }
        client = AsyncClient(host=self.api_url)
        response = await client.generate(model='Silicon-maid', **payload)
        text_response = response['response'].split(f"{self.character_name}:")[-1].strip()
        cleaned = self.remove_last_incomplete_sentence_gpt(text_response)

        Globals.log.debug(f'{cleaned=}')
        if cleaned != text_response:
            Globals.log.debug(f'Original {text_response=}')
        return cleaned

    def auto_capitalize_sentences(self, text, pattern=re.compile(r'((?<!\.)[!?]\s+|(?<![.])[.]\s+|\(\s*|"\s*|(?<=\s)i(?=\s))(\w)')):
        if not text:
            return ''
        # Capitalize the first letter of the text
        text = text[0].upper() + text[1:]

        # Capitalize the first letter after sentence-ending punctuation, inside quotes, or inside parentheses
        text = pattern.sub(lambda m: m.group(1) + m.group(2).upper(), text)

        return text

    def approximate_gpt_token_count(self, text, pattern=re.compile(r'\w+|[^\w\s]', re.UNICODE)):
        tokens = re.findall(pattern, text)
        return len(tokens)

    def accurate_gpt_token_count(self, text):
        tokens = self.tokenizer.encode(text, max_length=4096, truncation=True)
        return len(tokens)

    async def api_token_count(self, text):
        async with aiohttp.ClientSession() as session:
            payload = {
                'prompt': text
            }

            async with session.post(self.api_url.replace('generate', 'token-count'), json=payload) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    tokens = response_data['results'][0]['tokens']
                    return tokens
                else:
                    Globals.log.error(f'{resp.status=}')
                    return self.approximate_gpt_token_count(text)

    def is_valid_ending(self, token, ending_pattern=re.compile(r'([.?!])+$|(\*.*\*)$')):
        if ending_pattern.search(token):
            return True
        return False

    def remove_last_incomplete_sentence_gpt(self, text):
        tokens = self.tokenizer.encode(text.rstrip('<'), max_length=4096, return_tensors='pt', truncation=True)
        token_list = tokens.tolist()[0]

        last_boundary_index = None
        for idx, token in reversed(list(enumerate(token_list))):
            decoded_token = self.tokenizer.decode(token).strip()
            if self.is_valid_ending(decoded_token):
                last_boundary_index = idx
                Globals.log.debug(f'{idx=} {token_list=}')
                break

        if last_boundary_index is not None:
            truncated_tokens = token_list[:last_boundary_index + 1]
            truncated_text = self.tokenizer.decode(truncated_tokens)
            truncated_text = truncated_text.replace('<s>', '')
            return truncated_text

        return text

    def get_temperature(self, context_size):
        # Define the temperature range
        min_temperature = 0.67
        max_temperature = 0.72

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

    async def generate_memories(self, conversation: list):
        memories = []

        prompt = self.memory_extraction_template.render(
            conversation=conversation,
            model_tag=self.model_tag,
            user_tag=self.user_tag,
            bot_name=self.character_name,
            bot_username=Globals.disco.user,
        )

        payload = {
            'prompt': prompt,
            'options': {
                'num_ctx': 12000,
                'num_predict': 512,
                'rep_pen': 1.3,
                'rep_pen_range': 512,
                'rep_pen_slope': 0.2,
                'temperature': 0.75,
                'tfs': 1,
                'top_a': 0,
                'top_k': 40,
                'top_p': 0.9,
                'typical': 1
            }
        }

        client = AsyncClient(host=self.api_url)
        response = await client.generate(model='Silicon-maid', **payload)
        Globals.log.debug(f'{response=}')
        try:
            examples = [
                {
                    "name": "LaaZa",
                    "memory": "LaaZa is a Finnish man and my creator.",
                    "category": "personal info"
                },
                {
                    "name": "Miharu",
                    "memory": "I said I loved LaaZa very much and I'm grateful he created me.",
                    "category": "feelings"
                },
                {
                    "name": "LaaZa",
                    "memory": "LaaZa said he updated my memory system.",
                    "category": "events"
                },
                {
                    "name": "Miharu",
                    "memory": "I agreed when LaaZa said that I don't need to be concerned about technical details.",
                    "category": "interactions"
                }
            ]


            memories = json.loads(response['response'])['memories']
            memories = [memory for memory in memories if memory not in examples]
            Globals.log.debug(f'{memories=}')
        except Exception as e:
            Globals.log.error(f'{e=}')


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

        def get_messages_by_id(self, ids):
            messages = []
            for messages_channel in self.prompt_histories.values():
                messages.append([mes for mes in messages_channel if mes.message.id in ids])

            return [item for sublist in messages for item in sublist]  # flatten

        def get_history_slice_by_id(self, message_id, slice_size=3, user_id=None):
            center_idx = None
            channel = None
            for messages_channel in self.prompt_histories.values():
                try:
                    idx, message = [(idx, mes.message) for idx, mes in enumerate(messages_channel) if mes.message.id == message_id and mes.message.author.id == (user_id or mes.message.author.id)][0]
                    center_idx = idx
                    channel = message.channel
                    break
                except IndexError:
                    continue
            if not channel:
                return []

            lst = self.get_history(channel)
            half_slice_size = slice_size // 2
            start_idx = max(center_idx - half_slice_size, 0)
            end_idx = min(center_idx + half_slice_size + 1, len(lst))
            start_idx = max(len(lst) - slice_size, 0) if end_idx == len(lst) else start_idx
            end_idx = min(slice_size, len(lst)) if start_idx == 0 else end_idx
            return lst[start_idx:end_idx]

        def get_history_prompt(self, channel, limit=20, max_age: timedelta = None):
            prompt = ""
            prompt_list = list()
            history = self.get_history(channel)
            for i, message in enumerate(reversed(history)):
                if i > limit:
                    break
                if max_age and datetime.datetime.now(datetime.UTC) - max_age > message.message.created_at:
                    continue  # do not get too old messages
                author = message.message.author.display_name
                author = author if author != Globals.disco.user.name else self.main.character_name  # Use the friendly name in prompt
                #prompt_list.insert(0, f"{self.main.model_tag if author == self.main.character_name else self.main.user_tag}{author}: {str(message)}")
                #message.extra['friendly_name'] = author
                prompt_list.insert(0, message)


            #prompt = ''.join(prompt_list)
            return prompt_list

        def get_histories(self):
            return self.prompt_histories

        def clear_history(self, channel):
            self.prompt_histories[channel].clear()

        def remove_older_messages(self, channel, max_age):
            if not self.prompt_histories[channel]:
                return
            return

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

        async def save_conversation_history(self, filename='chat.db'):
            try:
                async with aiosqlite.connect(BotPath.plugins / 'chat' / filename, timeout=10) as connection:
                    async with connection.cursor() as cursor:

                        await cursor.execute("CREATE TABLE IF NOT EXISTS conversation_history (channel_id INT PRIMARY KEY, user_id INT, message_ids TEXT)")
                        await cursor.execute("CREATE TABLE IF NOT EXISTS messageblocks (message_id INT PRIMARY KEY, block TEXT)")

                        for channel, messageblocks in self.get_histories().items():
                            message_ids = [message.message.id for message in messageblocks]
                            user_id = None
                            if channel.type is nextcord.ChannelType.private:
                                if channel.recipient:
                                    user_id = channel.recipient.id
                                else:
                                    user_id = [msg.message.author.id for msg in messageblocks if msg.message.author is not channel.me][0]
                            await cursor.execute("REPLACE INTO conversation_history (channel_id, user_id, message_ids) VALUES (?, ?, ?)", (channel.id, user_id, json.dumps(message_ids)))
                            for message in messageblocks:
                                await cursor.execute("REPLACE INTO messageblocks (message_id, block) VALUES (?, ?)", (message.message.id, json.dumps(message.data)))

                        await connection.commit()
            except Exception as e:
                Globals.log.error(str(e))

        async def load_conversation_history(self, filename='chat.db'):
            client = Globals.disco
            try:
                async with aiosqlite.connect(BotPath.plugins / 'chat' / filename, timeout=10) as connection:
                    async with connection.cursor() as cursor:

                        await cursor.execute("SELECT channel_id, user_id, message_ids FROM conversation_history")
                        data = await cursor.fetchall()

                        await cursor.execute("SELECT message_id, block FROM messageblocks")
                        blockdata = await cursor.fetchall()

                conversation_history = {}
                blockdict = {mid: json.loads(block) for (mid, block) in blockdata}

                import timeit

                channel_histories = {}

                for channel_id, user_id, message_ids_data in data:
                    try:
                        if user_id:
                            user = client.get_user(int(user_id))
                            channel = user.dm_channel or await user.create_dm()
                        else:
                            channel = nextcord.utils.get(client.get_all_channels(), id=int(channel_id))

                        if channel not in channel_histories.keys():
                            channel_histories[channel] = [item async for item in channel.history(limit=500)]

                        messages = []
                        message_ids = json.loads(message_ids_data)
                        message = None
                        mblock = None
                        for message_id in message_ids:
                            if blockdict.get(message_id) and blockdict.get(message_id).get('extra').get('fake'):
                                extra = blockdict.get(message_id).get('extra')
                                #Globals.log.debug(f'{extra}')
                                mblock = self.main.MessageBlock(text=extra.get('text'), author=client.get_user(int(extra.get('author_id'))), channel=channel, created_at=datetime.datetime.fromisoformat(extra.get('timestamp')))
                            else:
                                try:
                                    message = [m for m in channel_histories[channel] if m.id == message_id][0]
                                except IndexError:
                                    pass
                                if message:
                                    mblock = self.main.MessageBlock(message)
                            if mblock:
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
                    self.extra['timestamp'] = created_at or datetime.datetime.now(datetime.UTC)
                    self.extra['timestamp'] = self.extra['timestamp'].isoformat()
                    self.extra['text'] = text
                    self.extra['author_id'] = author.id if author else Globals.disco.user.id
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

        @property
        def author(self):
            return self.message.author

        @property
        def channel(self):
            return self.message.channel

        @property
        def content(self):
            return str(self)

        @property
        def display_name(self):
            return self.message.author.display_name
