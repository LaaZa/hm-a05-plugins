from annoy import AnnoyIndex
from sentence_transformers import SentenceTransformer
from modules.globals import Globals
import nltk
import numpy as np


class DynamicMemory:
    def __init__(self, max_messages=5):
        Globals.log.info(f'Loading Dynamic Memory...')
        nltk.download('punkt')
        self.max_messages = max_messages
        self.membeddings = list()
        self._model = SentenceTransformer('randypang/intent-simple-chat')
        self._annoyin = AnnoyIndex(768, "angular")
        Globals.log.info(f'Completed Loading Dynamic Memory.')

    def _segment_text(self, text):
        return nltk.sent_tokenize(text)

    def _embed(self, text):
        sentences = self._segment_text(text)
        sentences = [sentence for sentence in sentences if len(sentence.split()) >= 4]
        if not sentences:
            return
        return self._model.encode(sentences, convert_to_numpy=True)

    def _build_annoy_index(self):
        self._annoyin = AnnoyIndex(768, "angular")
        for i, (embedding, _) in enumerate(self.membeddings):
            self._annoyin.add_item(i, embedding)
        self._annoyin.build(10)

    def update_memory(self, messages):
        updated = False
        for messageblock in messages:
            #if messageblock.message.id in [mem[1] for mem in self.membeddings]:
            #    continue  # skip if already embedded
            #Globals.log.debug(f'Updating memory with message: {messageblock.message.id}')
            embeddings = self._embed(messageblock.message.content)
            if embeddings is None or not len(embeddings):
                continue
            for embedding in embeddings:
                self.membeddings.append((embedding, messageblock.message.id))
                updated = True

            if updated:
                self._build_annoy_index()

    def memory_id_prompt(self, messages):
        query_embeddings = []
        for messageblock in messages:
            emb = self._embed(messageblock.message.content)
            if emb is not None and len(emb):
                query_embeddings.append(emb)
                Globals.log.debug(f'Membedding for lookup: {messageblock.message.content}')

        num_neighbors = 5

        similarity_threshold = 0.7

        output = []

        for query_embeddings_per_msg in query_embeddings:
            for query_embedding in query_embeddings_per_msg:

                nearest_neighbors, distances = self._annoyin.get_nns_by_vector(query_embedding, num_neighbors, include_distances=True)
                Globals.log.debug(f'{nearest_neighbors} {distances} - {query_embedding=}')
                #  convert to cosine similarity 0 - 1.0
                similarity_scores = [1 - dist / 2 for dist in distances]

                filtered_results = [(idx, sim) for idx, sim in zip(nearest_neighbors, similarity_scores) if sim >= similarity_threshold]

                sorted_results = sorted(filtered_results, key=lambda x: x[1], reverse=True)

                for idx, sim in sorted_results:
                    Globals.log.debug(f"Index: {idx}, Similarity: {sim}")

                    output.append(self._annoyin.get_item_vector(idx))

        message_ids = set()

        for emb in output:
            for embed, m_id in self.membeddings:
                if np.array_equal(emb, embed):
                    message_ids.add(m_id)

        Globals.log.debug(f'{message_ids=}')

        return message_ids
