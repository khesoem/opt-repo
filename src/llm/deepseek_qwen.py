from .invocation import *
from .llm_adapter import LLMAdapter


class DeepseekR1Qwen3(LLMAdapter):

    def get_response(self, prompt: Prompt) -> Response:
        cached_invocation = self.load_cache(prompt)
        if cached_invocation:
            return cached_invocation.response

        completion = self.client.chat.completions.create(
            model="deepseek/deepseek-r1-0528-qwen3-8b",
            messages=[m.__dict__ for m in prompt.messages]
        )
        response = Response([Response.Sample(c.message.content)
                             for c in completion.choices])

        self.save_cache(Invocation(prompt, response))
        return response