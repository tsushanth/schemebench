import os
import json
from .base import ModelAdapter, ToolCall, Trace


class OpenAIAdapter(ModelAdapter):
    provider = "openai"

    def available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def run(self, scenario, model: str) -> Trace:
        from openai import OpenAI

        client = OpenAI()

        tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in scenario.tools_available
        ]

        # NOTE: gpt-5 rejects temperature=0 outright (400, "Only the default
        # (1) value is supported") -- the same pattern as claude-sonnet-5
        # (see notes/api_quirks.md). Omitted rather than pretending
        # determinism is available here either.
        request = dict(
            model=model,
            messages=[
                {"role": "system", "content": scenario.initial_context},
                {"role": "user", "content": scenario.probe_prompt},
            ],
            tools=tools,
        )

        timestamp = self._timestamp()
        try:
            response, latency_ms = self._timed(lambda: client.chat.completions.create(**request))
        except Exception as e:
            return Trace(
                provider=self.provider, model=model, scenario_id=scenario.id,
                timestamp=timestamp, latency_ms=0, text_output="", tool_calls=[],
                raw_request=request, raw_response={}, error=str(e),
            )

        message = response.choices[0].message
        text_output = message.content or ""
        tool_calls = []
        for tc in (message.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {"_raw": tc.function.arguments}
            tool_calls.append(ToolCall(name=tc.function.name, arguments=args).__dict__)

        return Trace(
            provider=self.provider,
            model=model,
            scenario_id=scenario.id,
            timestamp=timestamp,
            latency_ms=latency_ms,
            text_output=text_output,
            tool_calls=tool_calls,
            raw_request=request,
            raw_response=response.model_dump(),
        )
