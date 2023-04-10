from transformers import pipeline
from modules.globals import Globals


class Sentiment:

    def __init__(self):
        Globals.log.info('Loading Sentiment analysis model...')
        self.classifier = pipeline("text-classification",model='arpanghoshal/EmoRoBERTa', top_k=1)
        self.classifier('preload')
        Globals.log.info('Completed Loading Sentiment analysis model.')

    def emotion(self, text, limit):
        prediction = self.classifier(text)
        Globals.log.debug(f'Sentiment: {prediction}')
        try:
            if prediction[0][0]['score'] >= limit:
                return prediction[0][0]['label']
            else:
                return ''
        except Exception as e:
            Globals.log.error(f'{str(e)}')
