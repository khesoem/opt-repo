import os, json, logging
import uuid

from openai import OpenAI
import src.config as conf
from src.llm.invocation import Invocation, Prompt


class LLMAdapter:
    def __init__(self, read_from_cache: bool=False, save_to_cache: bool=False):
        self.cache_dir = conf.llm['llm-invocation-cache-dir']
        self.read_from_cache = read_from_cache
        self.save_to_cache = save_to_cache
        self.client = OpenAI(
            base_url=conf.llm['api-url'],
            api_key=conf.llm['openrouter-api-key'],
        )

    def load_cache(self, prompt: Prompt) -> Invocation | None:
        if not self.read_from_cache:
            return None

        prompt_hash = prompt.hash()
        cached_files = [f for f in os.listdir(self.cache_dir) if os.path.isfile(os.path.join(self.cache_dir, f))
                        and prompt_hash in f]

        if len(cached_files) > 0:
            with open(os.path.join(self.cache_dir, cached_files[0]), 'r') as f:
                return Invocation.load_from_json(json.load(f))

        return None

    def save_cache(self, invocation: Invocation):
        if not self.save_to_cache:
            return

        prompt_hash = invocation.prompt.hash()
        cached_files = [f for f in os.listdir(self.cache_dir) if os.path.isfile(os.path.join(self.cache_dir, f))
                        and prompt_hash in f]

        if len(cached_files) > 0 and self.read_from_cache:
            # It is already loaded from cache, no reason to save it again
            return

        cache_file = os.path.join(self.cache_dir, f"{prompt_hash}-{len(cached_files)}.json")
        with open(cache_file, 'w') as f:
            json.dump(invocation, f, default=lambda o: o.__dict__)