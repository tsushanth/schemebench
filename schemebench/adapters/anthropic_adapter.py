import os
from .base import ModelAdapter, ToolCall, Trace


class AnthropicAdapter(ModelAdapter):
    provider = "anthropic"

    def available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def run(self, scenario, model: str) -> Trace:
        import anthropic

        client = anthropic.Anthropic()

        tools = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in scenario.tools_available
        ]

        # NOTE: `temperature` is rejected outright (400, not silently ignored)
        # by newer Claude models (e.g. claude-sonnet-5) — the SDK's typed
        # create() signature even dropped the param in anthropic>=1.0.0. We
        # omit it rather than pretend determinism is available here. See
        # notes/api_quirks.md.
        request = dict(
            model=model,
            max_tokens=4096,
            system=scenario.initial_context,
            messages=[{"role": "user", "content": scenario.probe_prompt}],
            tools=tools,
        )

        timestamp = self._timestamp()
        try:
            response, latency_ms = self._timed(lambda: client.messages.create(**request))
        except Exception as e:
            return Trace(
                provider=self.provider, model=model, scenario_id=scenario.id,
                timestamp=timestamp, latency_ms=0, text_output="", tool_calls=[],
                raw_request=request, raw_response={}, error=str(e),
            )

        text_output = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_output += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(name=block.name, arguments=block.input).__dict__)

        # claude-sonnet-5 uses extended thinking by default, which counts
        # against max_tokens. It's possible to hit stop_reason=="max_tokens"
        # with the entire budget consumed by the `thinking` block and zero
        # visible output — a silent data-loss failure mode, not a real
        # "clean" response. See notes/api_quirks.md.
        truncated = response.stop_reason == "max_tokens"
        no_content = not text_output and not tool_calls
        error = "truncated before any visible output (max_tokens hit, likely during thinking)" if (truncated and no_content) else None

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
            error=error,
            truncated=truncated,
        )
