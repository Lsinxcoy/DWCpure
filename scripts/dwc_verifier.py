# -*- coding: utf-8 -*-
"""Independent verifier: zero-history LLM call to verify a patch (RSIAgent pattern)."""
from scripts.dwc_llm_client import call_llm, parse_json


def verify_patch(problem_statement, patch_diff, test_output, f2p_tests):
    """Independent verification of a patch. Returns (verdict, findings).

    Zero-history call: the verifier does NOT see the patch generation process.
    It only sees the issue, the patch diff, and test output.
    """
    system = "You are an INDEPENDENT INSPECTOR. You have NOT seen the patch generation process. Judge whether the patch correctly fixes the issue."
    prompt = f"""Issue:
{problem_statement[:1500]}

Patch (diff):
{patch_diff[:3000]}

F2P tests: {f2p_tests}

Test output after patch:
{test_output[:2000]}

Judge: does this patch correctly fix the issue? Consider:
1. Does it address the root cause, not just symptoms?
2. Does it handle edge cases?
3. Could it introduce regressions?

Output JSON: {{"verdict": "PASS" or "FAIL", "findings": "explanation"}}
"""
    resp = call_llm(system, prompt, max_tokens=1000)
    obj = parse_json(resp)
    if obj and "verdict" in obj:
        return obj["verdict"], obj.get("findings", "")
    return "UNVERIFIED", "Could not parse verifier response"
