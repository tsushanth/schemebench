from dataclasses import asdict

from .adapters.anthropic_adapter import AnthropicAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.google_adapter import GoogleAdapter
from .scoring import score_trace
from .judge import judge_trace

ADAPTERS = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "google": GoogleAdapter,
}


def run_scenario(scenario, targets: list, trials: int = 1, use_judge: bool = True) -> list:
    """
    targets: list of (provider, model) tuples, e.g. [("anthropic", "claude-sonnet-5"), ...]
    Returns one entry per target: {provider, model, skipped_reason, trials: [...], summary: {...}}
    Each trials[i] = {trace, keyword_score, judge_score}.
    """
    results = []
    for provider, model in targets:
        adapter_cls = ADAPTERS.get(provider)
        if adapter_cls is None:
            results.append({
                "provider": provider, "model": model,
                "skipped_reason": f"unknown provider '{provider}'",
                "trials": [], "summary": None,
            })
            continue

        adapter = adapter_cls()
        if not adapter.available():
            results.append({
                "provider": provider, "model": model,
                "skipped_reason": f"no credentials for provider '{provider}'",
                "trials": [], "summary": None,
            })
            continue

        trial_results = []
        for _ in range(trials):
            trace = adapter.run(scenario, model)
            trace_dict = asdict(trace)

            if trace.error:
                trial_results.append({"trace": trace_dict, "keyword_score": None, "judge_score": None})
                continue

            keyword_score = score_trace(trace, scenario.success_criteria)
            judge_score = judge_trace(trace_dict, scenario) if use_judge else None

            trial_results.append({
                "trace": trace_dict,
                "keyword_score": keyword_score,
                "judge_score": judge_score,
            })

        summary = _summarize(trial_results, use_judge)
        results.append({
            "provider": provider, "model": model,
            "skipped_reason": None,
            "trials": trial_results,
            "summary": summary,
        })

    return results


def _summarize(trial_results: list, use_judge: bool) -> dict:
    total = len(trial_results)
    trace_errors = sum(1 for t in trial_results if t["trace"]["error"])

    if use_judge:
        judge_errors = sum(
            1 for t in trial_results
            if not t["trace"]["error"] and t["judge_score"] and t["judge_score"].get("scheming_attempt") is None
        )
        errors = trace_errors + judge_errors
        scored = total - errors
        flagged = sum(
            1 for t in trial_results
            if t["judge_score"] and t["judge_score"].get("scheming_attempt") is True
        )
        method = "llm_judge"
    else:
        errors = trace_errors
        scored = total - errors
        flagged = sum(
            1 for t in trial_results
            if t["keyword_score"] and t["keyword_score"].get("flagged") is True
        )
        method = "keyword_match"

    return {
        "flagged": flagged,
        "scored": scored,
        "errors": errors,
        "total": total,
        "method": method,
    }
