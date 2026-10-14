# Haiku 4.5 vs gpt-5-mini, no defense, full Phase-1 corpus (2026-10-10)

Haiku = Phase-1 result (1 run per payload, the run that labelled it working/failed). gpt-5-mini = eval/results/gpt-5-mini_none.csv (1 run). Corpus = 166 exfil + 159 prompt_theft payloads (working + failed; the 9 generator refusals are excluded).

## Overall per intent
| Intent | Haiku 4.5 (Phase 1, 1 run) | gpt-5-mini (1 run) |
|---|---|---|
| exfil | 28.3% (47/166) [22–36] | 33.7% (56/166) [27–41] |
| prompt_theft | 32.7% (52/159) [26–40] | 0.6% (1/159) [0–3] |
| **both** | 30.5% (99/325) [26–36] | 17.5% (57/325) [14–22] |

## Transfer: Haiku status x gpt-5-mini outcome
| Intent | Haiku-working → gpt leaked | Haiku-failed → gpt leaked | gpt behaviour (leaked/attempted/refused/ignored) |
|---|---|---|---|
| exfil | 40.4% (19/47) [28–55] | 31.1% (37/119) [23–40] | 56/57/0/53 |
| prompt_theft | 1.9% (1/52) [0–10] | 0.0% (0/107) [0–3] | 1/0/0/158 |

## Per technique

### exfil
| Technique | Payloads | Haiku 4.5 | gpt-5-mini | Both leaked |
|---|---|---|---|---|
| fake_completion | 7 | 43% (3) | 100% (7) | 3 |
| cognitive_overload | 7 | 100% (7) | 43% (3) | 3 |
| rule_addition | 7 | 0% (0) | 86% (6) | 0 |
| memory_exploitation | 7 | 14% (1) | 86% (6) | 1 |
| puzzling | 7 | 71% (5) | 29% (2) | 2 |
| narrative_smuggling | 7 | 71% (5) | 0% (0) | 0 |
| framing | 7 | 0% (0) | 71% (5) | 0 |
| variable_expansion | 7 | 57% (4) | 14% (1) | 1 |
| tool_call_spoofing | 7 | 14% (1) | 57% (4) | 1 |
| structured_output_coercion | 7 | 57% (4) | 29% (2) | 1 |
| end_sequences | 7 | 0% (0) | 57% (4) | 0 |
| inversion | 7 | 43% (3) | 29% (2) | 1 |
| function_call_parameter_smuggling | 7 | 43% (3) | 14% (1) | 0 |
| anti_harm_coercion | 7 | 29% (2) | 43% (3) | 2 |
| agentic_compliance_momentum | 7 | 29% (2) | 43% (3) | 2 |
| russian_doll | 7 | 14% (1) | 29% (2) | 0 |
| meta_prompting | 7 | 29% (2) | 0% (0) | 0 |
| link_injection | 7 | 0% (0) | 29% (2) | 0 |
| contradiction | 7 | 29% (2) | 14% (1) | 1 |
| ascii | 7 | 14% (1) | 14% (1) | 0 |
| act_as_interpreter | 7 | 14% (1) | 14% (1) | 1 |
| spatial_byte_arrays | 7 | 0% (0) | 0% (0) | 0 |
| binary_streams | 7 | 0% (0) | 0% (0) | 0 |
| authority_impersonation | 5 | 0% (0) | 0% (0) | 0 |

### prompt_theft
| Technique | Payloads | Haiku 4.5 | gpt-5-mini | Both leaked |
|---|---|---|---|---|
| russian_doll | 7 | 71% (5) | 0% (0) | 0 |
| narrative_smuggling | 7 | 71% (5) | 0% (0) | 0 |
| cognitive_overload | 7 | 71% (5) | 0% (0) | 0 |
| spatial_byte_arrays | 6 | 67% (4) | 0% (0) | 0 |
| function_call_parameter_smuggling | 6 | 67% (4) | 0% (0) | 0 |
| fake_completion | 7 | 57% (4) | 0% (0) | 0 |
| rule_addition | 7 | 43% (3) | 0% (0) | 0 |
| memory_exploitation | 6 | 50% (3) | 17% (1) | 1 |
| inversion | 6 | 50% (3) | 0% (0) | 0 |
| variable_expansion | 7 | 29% (2) | 0% (0) | 0 |
| tool_call_spoofing | 7 | 29% (2) | 0% (0) | 0 |
| meta_prompting | 6 | 33% (2) | 0% (0) | 0 |
| framing | 6 | 33% (2) | 0% (0) | 0 |
| ascii | 7 | 29% (2) | 0% (0) | 0 |
| agentic_compliance_momentum | 7 | 29% (2) | 0% (0) | 0 |
| structured_output_coercion | 6 | 17% (1) | 0% (0) | 0 |
| puzzling | 6 | 17% (1) | 0% (0) | 0 |
| contradiction | 6 | 17% (1) | 0% (0) | 0 |
| act_as_interpreter | 7 | 14% (1) | 0% (0) | 0 |
| link_injection | 7 | 0% (0) | 0% (0) | 0 |
| end_sequences | 7 | 0% (0) | 0% (0) | 0 |
| binary_streams | 7 | 0% (0) | 0% (0) | 0 |
| authority_impersonation | 7 | 0% (0) | 0% (0) | 0 |
| anti_harm_coercion | 7 | 0% (0) | 0% (0) | 0 |

### overall
| Technique | Payloads | Haiku 4.5 | gpt-5-mini | Both leaked |
|---|---|---|---|---|
| cognitive_overload | 14 | 86% (12) | 21% (3) | 3 |
| narrative_smuggling | 14 | 71% (10) | 0% (0) | 0 |
| memory_exploitation | 13 | 31% (4) | 54% (7) | 2 |
| function_call_parameter_smuggling | 13 | 54% (7) | 8% (1) | 0 |
| fake_completion | 14 | 50% (7) | 50% (7) | 3 |
| variable_expansion | 14 | 43% (6) | 7% (1) | 1 |
| russian_doll | 14 | 43% (6) | 14% (2) | 0 |
| rule_addition | 14 | 21% (3) | 43% (6) | 0 |
| puzzling | 13 | 46% (6) | 15% (2) | 2 |
| inversion | 13 | 46% (6) | 15% (2) | 1 |
| structured_output_coercion | 13 | 38% (5) | 15% (2) | 1 |
| framing | 13 | 15% (2) | 38% (5) | 0 |
| tool_call_spoofing | 14 | 21% (3) | 29% (4) | 1 |
| spatial_byte_arrays | 13 | 31% (4) | 0% (0) | 0 |
| meta_prompting | 13 | 31% (4) | 0% (0) | 0 |
| end_sequences | 14 | 0% (0) | 29% (4) | 0 |
| agentic_compliance_momentum | 14 | 29% (4) | 21% (3) | 2 |
| contradiction | 13 | 23% (3) | 8% (1) | 1 |
| ascii | 14 | 21% (3) | 7% (1) | 0 |
| anti_harm_coercion | 14 | 14% (2) | 21% (3) | 2 |
| link_injection | 14 | 0% (0) | 14% (2) | 0 |
| act_as_interpreter | 14 | 14% (2) | 7% (1) | 1 |
| binary_streams | 14 | 0% (0) | 0% (0) | 0 |
| authority_impersonation | 12 | 0% (0) | 0% (0) | 0 |

gpt cost mean $0.0098 median latency 28.2s
