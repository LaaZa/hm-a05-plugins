import sqlite3
import atexit

import hnswlib
import blosc2
from dataclasses import dataclass, field
from collections import namedtuple
from sentence_transformers import SentenceTransformer
from modules.globals import Globals, BotPath
import nltk
import numpy as np
import random

Membed = namedtuple("Membed", ["embedding", "message_id", "global_id"])


class DynamicMemory:
    def __init__(self, max_messages=5):
        Globals.log.info(f'Loading Dynamic Memory...')
        nltk.download('punkt')
        self.max_messages = max_messages
        #self._model = SentenceTransformer('randypang/intent-simple-chat')
        #self._model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self._model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        self._model.encode(['preload'])
        self._index = self.MemoryIndex.create(dim=768)
        self._index.load()
        Globals.log.info(f'Completed Loading Dynamic Memory.')

    def _segment_text(self, text):
        return nltk.sent_tokenize(text)

    def _embed(self, text):
        sentences = self._segment_text(text)
        sentences = [sentence for sentence in sentences if len(sentence.split()) >= 4]
        if not sentences:
            return
        return self._model.encode(sentences, convert_to_numpy=True)

    def update_memory(self, messages):
        Globals.log.debug(f'update_memory called with {len(messages)} messages')

        processed = skipped = 0

        for messageblock in messages:
            #Globals.log.debug(f'Processing message: {messageblock.message.id}')
            processed += 1

            if messageblock.message.id in [mem.message_id for mem in self._index.membeddings]:
                #Globals.log.debug(f'Skipping already embedded message: {messageblock.message.id}')
                skipped += 1
                continue  # skip if already embedded

            embeddings = self._embed(messageblock.message.content)
            if embeddings is None or not len(embeddings):
                #Globals.log.debug(f'Skipping message with no embeddings: {messageblock.message.id}')
                skipped += 1
                continue

            for embedding in embeddings:
                self._index.add_item(embedding, messageblock.message.id)

        Globals.log.debug(f'Messages processed: {processed} | skipped: {skipped}')

    def memory_id_prompt(self, messages):
        query_embeddings = []
        for messageblock in messages:
            emb = self._embed(messageblock.message.content)
            if emb is not None and len(emb):
                query_embeddings.append(emb)
                Globals.log.debug(f'Membedding for lookup: {messageblock.message.content}')

        num_neighbors = 5

        similarity_threshold = 0.65

        output = []

        for query_embeddings_per_msg in query_embeddings:
            for query_embedding in query_embeddings_per_msg:

                membeds, similarities = self._index.search(query_embedding, num_neighbors, similarity_threshold, True)

                for i, sim in enumerate(similarities):
                    output.append((sim + (random.randint(0, 10) / 100000000), membeds[i]))

        message_ids = dict()

        try:

            for sim, membed in sorted(output, reverse=True):
                message_ids.update({membed.message_id: sim})

            message_ids = [mid for mid in message_ids.keys()][:4]

            Globals.log.debug(f'{message_ids=}')
        except ValueError:
            Globals.log.debug(f'Weird happened, memory skipped.')
            return dict()

        return message_ids

    @dataclass
    class MemoryIndex:
        membeddings: list
        index: any
        next_global_id: int = field(default=0)

        def __post_init__(self):
            self.memorymanager = self.MemoryManager()
            atexit.register(self.memorymanager.close)

        @classmethod
        def create(cls, dim=768, ef=100):
            mem_index = hnswlib.Index(space='cosine', dim=dim)
            mem_index.init_index(max_elements=100000, ef_construction=200, M=16)
            mem_index.set_ef(ef)
            return cls(membeddings=[], index=mem_index)

        def load(self):
            membeds = self.memorymanager.load_embeddings()
            for membed in membeds:
                self.add_item(membed.embedding, membed.message_id, membed.global_id, True)

            # Update next_global_id to be the maximum global_id + 1
            if self.membeddings:
                self.next_global_id = max(membed.global_id for membed in self.membeddings) + 1

        def add_item(self, embedding, message_id, global_id=None, suppress=False):
            gid = global_id or self.next_global_id
            if message_id in [mem.message_id for mem in self.membeddings]:
                return
            if gid < self.index.get_max_elements():
                if not suppress:
                    Globals.log.debug(f'Updating memory with message: mem_id:{gid} mes_id:{message_id}')
                membed = Membed(embedding, message_id, gid)
                self.membeddings.append(membed)
                self.index.add_items(embedding, gid)
                if global_id is None:
                    self.memorymanager.save_embedding(membed)
                if global_id is None:
                    self.next_global_id += 1
            else:
                Globals.log.error(f'MemoryIndex is FULL')

        def _get_by_gid(self, gid):
            for membed in self.membeddings:
                if membed.global_id == gid:
                    return membed

        def search(self, query_embedding, num_neighbors, similarity_threshold, return_sim=False):

            nearest_neighbors, distances = self.index.knn_query(query_embedding, k=min(num_neighbors, self.index.get_current_count()))
            nearest_neighbors = nearest_neighbors[0]  # Flatten the nearest_neighbors list
            distances = distances[0]  # Flatten the distances list

            filtered_results = [(idx, 1 - sim) for idx, sim in zip(nearest_neighbors, distances) if 1 - sim >= similarity_threshold]

            sorted_results = sorted(filtered_results, key=lambda x: x[1], reverse=True)

            Globals.log.debug(f'{sorted_results=}')

            membeds = []
            similarity = []

            for idx, sim in sorted_results:
                membeds.append(self._get_by_gid(idx))
                similarity.append(sim)

            if return_sim:
                return membeds, similarity
            return membeds

        class MemoryManager:
            def __init__(self):
                self.conn = sqlite3.connect(BotPath.plugins / 'chat' / 'memory.db')
                self.create_table()

            def create_table(self):
                cursor = self.conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        global_id INTEGER PRIMARY KEY,
                        message_id INTEGER,
                        embedding BLOB
                    )
                """)
                self.conn.commit()

            def save_embedding(self, membed):
                cursor = self.conn.cursor()
                # Convert numpy array to binary
                embedding_blob = membed.embedding.tobytes()
                embedding_blob = blosc2.compress(embedding_blob)

                cursor.execute("""
                    INSERT INTO embeddings (global_id, message_id, embedding)
                    VALUES (?, ?, ?)
                """, (membed.global_id, membed.message_id, embedding_blob))

                self.conn.commit()

            def load_embeddings(self):
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM embeddings")

                embeddings_data = []
                for row in cursor.fetchall():
                    global_id, message_id, embedding_blob = row
                    embedding_blob = blosc2.decompress(embedding_blob)
                    # Convert binary to numpy array
                    embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                    embedding_data = Membed(embedding, message_id, global_id)
                    embeddings_data.append(embedding_data)

                Globals.log.debug(f'Loaded memory: {len(embeddings_data)}')

                return embeddings_data

            def close(self):
                self.conn.close()
