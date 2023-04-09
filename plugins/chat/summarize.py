import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import threading
from modules.globals import Globals


class Summarizer:
    def __init__(self):
        Globals.log.info('Loading Summarization model...')
        self.tokenizer = AutoTokenizer.from_pretrained("philschmid/bart-large-cnn-samsum")
        self.model = AutoModelForSeq2SeqLM.from_pretrained("philschmid/bart-large-cnn-samsum")
        Globals.log.info('Completed Loading Summarization model.')

    def summarize(self, text, callback, tokens=200):
        # Summarize the text
        input_ids = self.tokenizer.encode(text, return_tensors="pt", max_length=512, truncation=True)

        # Generate the summary (on CPU)
        with torch.no_grad():
            summary_ids = self.model.generate(
                input_ids,
                max_new_tokens=tokens,  # Adjust the maximum length of the summary
                num_beams=5,  # Increase the number of beam search branches
                min_length=10
            )

        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)

        # Call the callback function with the generated summary
        callback(summary)

    def summarize_async(self, text, callback, tokens=200):
        # Start the summarization in a separate thread
        threading.Thread(target=self.summarize, args=(text, callback, tokens)).start()
