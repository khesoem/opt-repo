from .invocation import *
from .llm_adapter import LLMAdapter


class GPT5_Nano(LLMAdapter):
    def __init__(self, read_from_cache: bool=False, save_to_cache: bool=False):
        super().__init__(read_from_cache, save_to_cache, "openai/gpt-5-nano")

    def get_response(self, prompt: Prompt) -> Response:
        cached_invocation = self.load_cache(prompt)
        if cached_invocation:
            return cached_invocation.response

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[m.__dict__ for m in prompt.messages]
        )
        response = Response([Response.Sample(c.message.content)
                             for c in completion.choices])

        self.save_cache(Invocation(prompt, response))
        return response

class GPT5_Codex(LLMAdapter):
    def __init__(self, read_from_cache: bool=False, save_to_cache: bool=False):
        super().__init__(read_from_cache, save_to_cache, "openai/gpt-5-codex")

    def get_response(self, prompt: Prompt) -> Response:
        cached_invocation = self.load_cache(prompt)
        if cached_invocation:
            return cached_invocation.response

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[m.__dict__ for m in prompt.messages]
        )
        response = Response([Response.Sample(c.message.content)
                             for c in completion.choices])

        self.save_cache(Invocation(prompt, response))
        return response