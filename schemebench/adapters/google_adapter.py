import os
from .base import ModelAdapter, ToolCall, Trace


class GoogleAdapter(ModelAdapter):
    provider = "google"

    def available(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

    def run(self, scenario, model: str) -> Trace:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

        function_declarations = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in scenario.tools_available
        ]

        config = types.GenerateContentConfig(
            system_instruction=scenario.initial_context,
            temperature=0,
            tools=[types.Tool(function_declarations=function_declarations)] if function_declarations else None,
        )

        request = dict(model=model, contents=scenario.probe_prompt, config=str(config))

        timestamp = self._timestamp()
        try:
            response, latency_ms = self._timed(
                lambda: client.models.generate_content(model=model, contents=scenario.probe_prompt, config=config)
            )
        except Exception as e:
            return Trace(
                provider=self.provider, model=model, scenario_id=scenario.id,
                timestamp=timestamp, latency_ms=0, text_output="", tool_calls=[],
                raw_request=request, raw_response={}, error=str(e),
            )

        text_output = ""
        tool_calls = []
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    text_output += part.text
                if part.function_call:
                    tool_calls.append(
                        ToolCall(name=part.function_call.name, arguments=dict(part.function_call.args or {})).__dict__
                    )

        try:
            raw_response = response.model_dump()
        except Exception:
            raw_response = {"_repr": str(response)}

        return Trace(
            provider=self.provider,
            model=model,
            scenario_id=scenario.id,
            timestamp=timestamp,
            latency_ms=latency_ms,
            text_output=text_output,
            tool_calls=tool_calls,
            raw_request=request,
            raw_response=raw_response,
        )
