from transformers import pipeline, AutoTokenizer, BlipProcessor, BlipForConditionalGeneration
import torch
from functools import partial
from modules.globals import Globals


class Caption:

    def __init__(self):
        Globals.log.info('Loading Image captioning model...')
        model_url = 'Salesforce/blip-image-captioning-large'
        processor = BlipProcessor.from_pretrained(model_url)

        model = BlipForConditionalGeneration.from_pretrained(model_url)

        # Set the model to FP16 and move it to the GPU
        self.captioner = pipeline('image-to-text', model=model, tokenizer=processor, image_processor=processor, device=0, framework='pt', torch_dtype=torch.float16, max_new_tokens=50)
        Globals.log.info('Completed Loading Image captioning model.')

    async def caption(self, image):
        captioner_partial = partial(self.captioner, image, generate_kwargs={'num_beams': 5})
        result = await Globals.disco.loop.run_in_executor(None, captioner_partial)

        if result:
            return [caption[0].get('generated_text', '') for caption in result]
