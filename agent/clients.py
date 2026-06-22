import os

from agent.mock import MockSpecialistClient, MockLeadClient


def get_specialist_client(specialist_name: str):
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()
    if provider == "mock":
        return MockSpecialistClient(specialist_name)
    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic()
    if provider == "openai":
        return _OpenAICompatibleClient()
    return MockSpecialistClient(specialist_name)


def get_lead_client():
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()
    if provider == "mock":
        return MockLeadClient()
    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic()
    if provider == "openai":
        return _OpenAICompatibleClient()
    return MockLeadClient()


class _OpenAIMessages:
    def __init__(self):
        import openai
        self._client = openai.OpenAI(
            base_url=os.environ.get("OPENAI_BASE_URL"),
            api_key=os.environ.get("OPENAI_API_KEY", "not-set"),
        )
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    def create(self, *, model, max_tokens, system, messages, tools=None):
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        kwargs = {"model": self._model, "messages": oai_messages, "max_tokens": max_tokens}
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in tools
            ]

        resp = self._client.chat.completions.create(**kwargs)
        return _convert_openai_response(resp)


def _convert_openai_response(resp):
    from agent.mock import _MockResponse, _TextBlock, _ToolUseBlock

    choice = resp.choices[0]
    content = []

    if choice.message.content:
        content.append(_TextBlock(choice.message.content))

    if choice.message.tool_calls:
        import json
        for tc in choice.message.tool_calls:
            content.append(_ToolUseBlock(
                tc.id, tc.function.name,
                json.loads(tc.function.arguments),
            ))
        return _MockResponse(content, stop_reason="tool_use")

    return _MockResponse(content, stop_reason="end_turn")


class _OpenAICompatibleClient:
    def __init__(self):
        self.messages = _OpenAIMessages()
