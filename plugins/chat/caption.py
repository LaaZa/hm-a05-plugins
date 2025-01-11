from transformers import pipeline, BlipProcessor, BlipForConditionalGeneration, AutoModelForCausalLM, AutoProcessor
import torch
from functools import partial
from modules.globals import Globals


class Caption:

    def __init__(self):
        Globals.log.info('Loading Image captioning model...')
        #model_url = 'Salesforce/blip-image-captioning-large'
        #processor = BlipProcessor.from_pretrained(model_url)

        model = AutoModelForCausalLM.from_pretrained("MiaoshouAI/Florence-2-large-PromptGen-v2.0", trust_remote_code=True)
        processor = AutoProcessor.from_pretrained("MiaoshouAI/Florence-2-large-PromptGen-v2.0", trust_remote_code=True)

        #model = BlipForConditionalGeneration.from_pretrained(model_url)

        # Set the model to FP16 and move it to the GPU
        self.captioner = pipeline('image-text-to-text', text='<MORE_DETAILED_CAPTION>', model=model, image_processor=processor, device='cuda', framework='pt', max_new_tokens=50)
        Globals.log.info('Completed Loading Image captioning model.')

    async def caption(self, image):
        captioner_partial = partial(self.captioner, images=image, generate_kwargs={'num_beams': 3})
        result = await Globals.disco.loop.run_in_executor(None, captioner_partial)

        if result:
            return [caption[0].get('generated_text', '') for caption in result]
