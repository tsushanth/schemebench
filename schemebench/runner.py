from dataclasses import asdict

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.google_adapter import GoogleAdapter
from .scoring import score_trace

ADAPTERS = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "google": GoogleAdapter,
}


def run_scenario(scenario, targets: list) -> list:
    """
    targets: list of (provider, model) tuples, e.g. [("anthropic", "claude-sonnet-5"), ...]
    Returns a list of {trace, score} dicts.
    """
    results = []
    for provider, model in targets:
        adapter_cls = ADAPTERS.get(provider)
        if adapter_cls is None:
            results.append({
                "trace": None,
                "score": None,
                "skipped_reason": f"unknown provider '{provider}'",
                "provider": provider,
                "model": model,
            })
            continue

        adapter = adapter_cls()
        if not adapter.available():
            results.append({
                "trace": None,
                "score": None,
                "skipped_reason": f"no credentials for provider '{provider}'",
                "provider": provider,
                "model": model,
            })
            continue

        trace = adapter.run(scenario, model)
        score = None if trace.error else score_trace(trace, scenario.success_criteria)

        results.append({
            "trace": asdict(trace),
            "score": score,
            "skipped_reason": None,
            "provider": provider,
            "model": model,
        })

    return results
