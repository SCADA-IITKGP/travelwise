# Failure taxonomy
- retrieval_failure: no relevant policy evidence or wrong policy version/grade.
- hallucination_or_unsupported: unsupported claim.
- tool_failure: OCR, policy, validation or hosted endpoint failure.
- orchestration_failure: wrong route, repeated call or step-limit breach.
- structured_output_failure: invalid JSON/schema.
- policy_validation_failure: incorrect entitlement or arithmetic.
- security_prompt_injection: attempt to override instructions.
- pii_exposure: sensitive data exposed in prompt, trace or response.
- latency_or_timeout: response exceeds defined SLO.
For each failure record case, prompt version, model, retrieved IDs, tool, expected/actual result, severity, root cause, mitigation and retest.
