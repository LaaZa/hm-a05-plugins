from transformers import pipeline, AutoTokenizer
from optimum.onnxruntime import ORTModelForSequenceClassification
from modules.globals import Globals


class Sentiment:

    def __init__(self):
        Globals.log.info('Loading Sentiment analysis model...')
        model_id = "SamLowe/roberta-base-go_emotions-onnx"
        file_name = "onnx/model_quantized.onnx"


        model = ORTModelForSequenceClassification.from_pretrained(model_id, file_name=file_name)
        tokenizer = AutoTokenizer.from_pretrained(model_id)

        self.classifier = pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=1)
        self.classifier('preload')
        Globals.log.info('Completed Loading Sentiment analysis model.')

    async def emotion(self, text, limit):

        prediction = await Globals.disco.loop.run_in_executor(None, self.classifier, text)
        Globals.log.debug(f'Sentiment: {prediction}')
        try:
            if prediction[0][0]['score'] >= limit:
                return prediction[0][0]['label']
            else:
                return ''
        except Exception as e:
            Globals.log.error(f'{str(e)}')
