# Resultados consolidados

Última actualización editorial: 3-oct-2026 (**GT v3**, fijado el 27-sep: P04 corregido +
adjudicación de la 2ª anotación, ver `data/GT_CHANGELOG.md`). Todo se regenera desde
`results/` con el harness:

<!-- AUTO:comando -->
```bash
python3 -m jevbench.report   # regenera este documento (runs en docs/resultados_runs.txt)
python3 -m jevbench.score --summary jev_v3 jev_typesafe_v1 jev_cascade_review jev_cascade_audit jev_cascade_audit_rules \
    llm_gpt6luna_jevrev_review llm_gpt6luna_jevrev_audit llm_gpt61sol_jevrev_review llm_gpt61sol_jevrev_audit jev_cerebrasqwenrev_review \
    jev_cerebrasqwenrev_audit jev_cerebrasqwennsrev_review jev_cerebrasqwennsrev_audit llm_gpt6luna_prob llm_gpt6luna_disc \
    llm_gpt61sol_low_prob llm_gpt61sol_low_disc llm_qwen38_27b_prob llm_qwen38flash_prob llm_cerebras_gptoss120b_low_prob \
    llm_cerebras_qwen38_27b_low_prob llm_cerebras_qwen38_27b_nostruct_prob llm_cerebras_qwen38_27b_disc llm_cerebras_qwen38_27b_nostruct_disc llm_qwen38_27b_fp8_nostruct_prob \
    llm_qwen38_27b_gguf81_nostruct_prob llm_qwen38_27b_nvfp4_nostruct_prob llm_qwen38_27b_fp8_inject_prob llm_qwen38_27b_fp8_nostruct_t0_prob llm_qwen38_27b_nvfp4_inject_prob \
    llm_qwen38_27b_nvfp4_inject_disc llm_qwen38_27b_arcgguf_inject_prob llm_qwen38_27b_arcgguf_inject_disc decider_4b_jevrev_review decider_4b_jevrev_audit \
    decider_4b_llmrev_review decider_4b_llmrev_audit decider_4b_solrev_review decider_4b_solrev_audit decider_35b_a3b \
    decider_35b_a3b_nvfp4 decider_4b decider_4b_cascade_audit decider_4b_d35rev_audit decider_4b_aj32brev_audit \
    decider_4b_aj8brev_audit decider_2b decider_0.8b anyjev_qwen3_32b_l0 anyjev_qwen3_8b_l0 \
    anyjev_qwen3_1.7b_l0 gliner_decide_desc gliner_decide_bare gliner_decide_1b_desc gliner_multi_decide_desc \
    julia_1 laya_router laya_typed legacy_laya_v2 span01_pro \
    span01_lite span01_lite_or nimble_9b tev1_4b tev1_0.8b \
    decider_4b_clefrev_review decider_4b_clefrev_audit clef_27b clef_flash_9b_xpu decider_4b_clefflashrev_review \
    decider_4b_clefflashrev_audit clm_v0.1_8b strands_2b_hobson_v19_xpu strands_2b_hobson_v19_xpu_trunc
```
<!-- /AUTO:comando -->

## Marcador (GT v3, generado)

<!-- AUTO:marcador -->
| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v3 | 45 | 88.6 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 87.5 | 0.071 | 657 | 0/219 |
| jev_typesafe_v1 | 51* | 87.9 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 88.5 | 0.071 | 902 | 0/219 |
| jev_cascade_review | 65 | 92.1 | 93.6 | 26/28 | 75.3 | 0.82 | 6/10 | 18/20 | 89.0 | 95.4 / 93.8 | 18/20 | 92.0 | 0.054 | — | 0/219 |
| jev_cascade_audit | 64 | 91.4 | 93.6 | 26/28 | 73.8 | 0.87 | 5/10 | 18/20 | 88.5 | 94.6 / 93.5 | 18/20 | 92.0 | 0.055 | — | 0/219 |
| jev_cascade_audit_rules | 67* | 91.4 | 93.6 | 26/28 | — | — | — | 19/20 | 89.5 | 94.6 / 93.5 | 20/20 | 94.0 | 0.048 | — | 0/117 |
| llm_gpt6luna_jevrev_review | 69 | 94.3 | 97.1 | 25/28 | 76.2 | 0.86 | 6/10 | 18/20 | 89.0 | 95.8 / 95.8 | 18/20 | 93.5 | 0.050 | — | 0/219 |
| llm_gpt6luna_jevrev_audit | 71 | 93.6 | 97.1 | 25/28 | 76.9 | 0.82 | 9/10 | 18/20 | 92.0 | 95.0 / 95.0 | 18/20 | 92.0 | 0.045 | — | 0/219 |
| llm_gpt61sol_jevrev_review | 66 | 92.1 | 95.7 | 25/28 | 76.6 | 0.87 | 7/10 | 18/20 | 88.0 | 94.2 / 95.0 | 18/20 | 92.5 | 0.051 | — | 0/219 |
| llm_gpt61sol_jevrev_audit | 66 | 92.1 | 95.0 | 25/28 | 77.8 | 0.70 | 8/10 | 18/20 | 89.0 | 94.2 / 95.4 | 18/20 | 91.5 | 0.049 | — | 0/219 |
| jev_cerebrasqwenrev_review | 68 | 90.0 | 92.1 | 24/28 | 78.1 | 0.89 | 5/10 | 18/20 | 89.5 | 95.8 / 94.6 | 18/20 | 92.0 | 0.059 | — | 0/219 |
| jev_cerebrasqwenrev_audit | 68 | 90.0 | 90.7 | 24/28 | 77.5 | 0.88 | 9/10 | 18/20 | 89.5 | 95.0 / 93.1 | 18/20 | 92.0 | 0.064 | — | 0/219 |
| jev_cerebrasqwennsrev_review | 68 | 92.1 | 93.6 | 26/28 | 76.2 | 0.83 | 7/10 | 18/20 | 90.0 | 94.6 / 93.5 | 15/20 | 87.5 | 0.059 | — | 0/219 |
| jev_cerebrasqwennsrev_audit | 69 | 92.1 | 93.6 | 26/28 | 76.9 | 0.83 | 9/10 | 18/20 | 91.0 | 93.8 / 92.7 | 15/20 | 87.5 | 0.065 | — | 0/219 |
| llm_gpt6luna_prob | 61 | 93.6 | 95.7 | 25/28 | 78.8 | 0.87 | 9/10 | 18/20 | 87.0 | 93.5 / 93.5 | 17/20 | 88.0 | 0.053 | 3027 | 0/219 |
| llm_gpt6luna_disc | 59 | 93.6 | 91.4 | 26/28 | 76.6 | 0.77 | 6/10 | 17/20 | 85.0 | 92.3 / 92.7 | 18/20 | 89.5 | 0.077 | 1876 | 0/219 |
| llm_gpt61sol_low_prob | 65 | 92.9 | 93.6 | 26/28 | 80.0 | 0.90 | 8/10 | 18/20 | 88.5 | 94.2 / 94.6 | 18/20 | 89.5 | 0.054 | 3415 | 0/219 |
| llm_gpt61sol_low_disc | 63 | 92.1 | 92.1 | 26/28 | 76.9 | 0.78 | 6/10 | 18/20 | 89.5 | 94.6 / 94.2 | 17/20 | 86.5 | 0.073 | 2221 | 0/219 |
| llm_qwen38_27b_prob | -16* | 73.6 | 73.6 | 13/28 | 52.2 | -0.17 | 0/10 | 4/20 | 58.5 | 77.2 / 76.5 | 9/20 | 67.5 | 0.231 | 6799 | 53/218 |
| llm_qwen38flash_prob | -40* | 65.7 | 55.0 | 14/28 | 38.1 | -0.01 | 0/10 | 4/19 | 50.8 | 55.4 / 51.7 | 6/19 | 65.3 | 0.317 | 47875 | 31/215 |
| llm_cerebras_gptoss120b_low_prob | 34 | 87.9 | 88.6 | 23/28 | 72.2 | 0.64 | 5/10 | 12/20 | 73.0 | 87.7 / 91.5 | 13/20 | 77.5 | 0.108 | 27000 | 0/219 |
| llm_cerebras_qwen38_27b_low_prob | 59 | 90.0 | 88.6 | 23/28 | 77.8 | 0.80 | 6/10 | 16/20 | 84.0 | 96.5 / 95.8 | 14/20 | 87.0 | 0.060 | 760 | 0/219 |
| llm_cerebras_qwen38_27b_nostruct_prob | 65 | 90.0 | 92.9 | 23/28 | 79.1 | 0.85 | 6/10 | 17/20 | 89.5 | 95.4 / 95.8 | 15/20 | 86.5 | 0.056 | 627 | 0/219 |
| llm_cerebras_qwen38_27b_disc | 58 | 91.4 | 92.1 | 25/28 | 78.8 | 0.83 | 8/10 | 14/20 | 84.0 | 93.8 / 94.6 | 15/20 | 88.0 | 0.077 | 561 | 0/219 |
| llm_cerebras_qwen38_27b_nostruct_disc | 58 | 90.0 | 91.4 | 23/28 | 78.4 | 0.79 | 8/10 | 15/20 | 82.0 | 95.8 / 96.9 | 16/20 | 90.0 | 0.072 | 460 | 0/219 |
| llm_qwen38_27b_fp8_nostruct_prob | 49 | 87.9 | 90.0 | 24/28 | 80.3 | 0.82 | 9/10 | 14/20 | 80.0 | 90.8 / 91.2 | 15/20 | 86.0 | 0.080 | 6369 | 0/219 |
| llm_qwen38_27b_gguf81_nostruct_prob | 48 | 87.1 | 89.3 | 25/28 | 77.8 | 0.84 | 5/10 | 13/20 | 80.0 | 90.8 / 93.8 | 14/20 | 83.5 | 0.084 | 10787 | 0/219 |
| llm_qwen38_27b_nvfp4_nostruct_prob | 52 | 90.7 | 87.1 | 25/28 | 76.9 | 0.81 | 9/10 | 14/20 | 81.0 | 90.4 / 91.9 | 14/20 | 83.5 | 0.076 | 5297 | 0/219 |
| llm_qwen38_27b_fp8_inject_prob | 51 | 88.6 | 87.9 | 24/28 | 77.2 | 0.88 | 9/10 | 14/20 | 81.5 | 94.6 / 93.5 | 15/20 | 84.5 | 0.075 | 6502 | 1/219 |
| llm_qwen38_27b_fp8_nostruct_t0_prob | 51 | 88.6 | 87.9 | 24/28 | 75.9 | 0.87 | 4/10 | 14/20 | 81.5 | 94.6 / 93.5 | 15/20 | 84.5 | 0.075 | 6485 | 1/219 |
| llm_qwen38_27b_nvfp4_inject_prob | 50 | 88.6 | 87.9 | 25/28 | 77.5 | 0.88 | 8/10 | 15/20 | 79.5 | 92.7 / 92.7 | 15/20 | 85.0 | 0.087 | 5253 | 0/219 |
| llm_qwen38_27b_nvfp4_inject_disc | 63 | 92.9 | 92.9 | 26/28 | 78.4 | 0.82 | 9/10 | 17/20 | 85.5 | 96.2 / 96.2 | 15/20 | 88.0 | 0.069 | 2213 | 0/219 |
| llm_qwen38_27b_arcgguf_inject_prob | 48 | 88.6 | 85.7 | 24/28 | 76.2 | 0.87 | 8/10 | 14/20 | 79.0 | 92.7 / 94.2 | 15/20 | 85.0 | 0.084 | 7543 | 1/219 |
| llm_qwen38_27b_arcgguf_inject_disc | 63 | 92.9 | 92.1 | 25/28 | 78.4 | 0.82 | 9/10 | 17/20 | 85.5 | 95.4 / 95.8 | 15/20 | 87.5 | 0.067 | 3429 | 0/219 |
| decider_4b_jevrev_review | 65 | 92.1 | 93.6 | 25/28 | 74.4 | 0.85 | 7/10 | 18/20 | 87.5 | 94.2 / 93.8 | 18/20 | 93.5 | 0.056 | — | 0/219 |
| decider_4b_jevrev_audit | 64 | 90.7 | 93.6 | 25/28 | 72.2 | 0.76 | 6/10 | 19/20 | 88.5 | 93.1 / 92.3 | 18/20 | 93.5 | 0.066 | — | 0/219 |
| decider_4b_llmrev_review | 64 | 93.6 | 92.9 | 26/28 | 76.2 | 0.80 | 6/10 | 18/20 | 86.5 | 93.5 / 93.5 | 18/20 | 91.0 | 0.067 | — | 0/219 |
| decider_4b_llmrev_audit | 52 | 87.9 | 87.1 | 26/28 | 76.2 | 0.78 | 6/10 | 18/20 | 81.0 | 91.9 / 91.9 | 17/20 | 88.5 | 0.096 | — | 0/219 |
| decider_4b_solrev_review | 68 | 93.6 | 94.3 | 26/28 | 79.7 | 0.88 | 9/10 | 18/20 | 86.5 | 94.6 / 93.8 | 20/20 | 95.5 | 0.061 | — | 0/219 |
| decider_4b_solrev_audit | 66 | 90.7 | 94.3 | 26/28 | 79.7 | 0.86 | 5/10 | 18/20 | 86.5 | 92.3 / 93.8 | 20/20 | 96.5 | 0.084 | — | 0/219 |
| decider_35b_a3b | 40* | 84.3 | 79.3 | 24/28 | 69.7 | 0.90 | 6/10 | 15/20 | 78.0 | 92.3 / 88.5 | 13/20 | 77.5 | 0.097 | 678 | 0/219 |
| decider_35b_a3b_nvfp4 | 35* | 85.0 | 81.4 | 24/28 | 70.3 | 0.87 | 5/10 | 15/20 | 74.0 | 88.8 / 88.8 | 12/20 | 76.0 | 0.105 | 190 | 0/219 |
| decider_4b | 33 | 85.7 | 85.7 | 26/28 | 65.9 | 0.78 | 6/10 | 14/20 | 71.5 | 90.8 / 90.0 | 12/20 | 77.0 | 0.102 | 200 | 0/219 |
| decider_4b_cascade_audit | 39* | 87.1 | 87.1 | 26/28 | 69.4 | 0.76 | 6/10 | 13/20 | 74.5 | 90.4 / 90.4 | 13/20 | 78.5 | 0.095 | — | 0/219 |
| decider_4b_d35rev_audit | 51 | 89.3 | 87.9 | 26/28 | 67.5 | 0.85 | 4/10 | 17/20 | 83.5 | 93.1 / 91.9 | 13/20 | 80.5 | 0.082 | — | 0/219 |
| decider_4b_aj32brev_audit | 36 | 80.7 | 82.9 | 25/28 | 69.7 | 0.75 | 6/10 | 14/20 | 72.0 | 92.3 / 93.8 | 16/20 | 84.5 | 0.100 | — | 0/123 |
| decider_4b_aj8brev_audit | 28 | 84.3 | 84.3 | 26/28 | 64.4 | 0.74 | 7/10 | 14/20 | 69.5 | 90.0 / 88.5 | 12/20 | 77.5 | 0.122 | — | 0/185 |
| decider_2b | 20* | 77.9 | 78.6 | 23/28 | 62.5 | 0.85 | 4/10 | 12/20 | 69.0 | 86.5 / 89.6 | 13/20 | 71.5 | 0.125 | 79 | 0/219 |
| decider_0.8b | 11* | 82.1 | 81.4 | 21/28 | 64.7 | 0.81 | 7/10 | 12/20 | 64.5 | 82.7 / 83.8 | 9/20 | 63.5 | 0.130 | 43 | 0/219 |
| anyjev_qwen3_32b_l0 | 27* | 83.6 | 79.3 | 25/28 | 69.7 | 0.79 | 6/10 | 13/20 | 68.5 | 85.8 / 85.0 | 15/20 | 84.0 | 0.164 | 2552 | 0/0 |
| anyjev_qwen3_8b_l0 | 18* | 80.0 | 79.3 | 25/28 | 73.8 | 0.86 | 6/10 | 12/20 | 62.0 | 86.5 / 90.0 | 14/20 | 79.0 | 0.183 | 682 | 0/0 |
| anyjev_qwen3_1.7b_l0 | 3* | 81.4 | 71.4 | 25/28 | 64.4 | 0.50 | 9/10 | 14/20 | 66.0 | 71.2 / 80.4 | 9/20 | 53.0 | 0.256 | 181 | 0/0 |
| gliner_decide_desc | -4* | 77.9 | 80.0 | 21/28 | 52.5 | 0.67 | 7/10 | 7/20 | 61.5 | 70.0 / 77.7 | 9/20 | 59.0 | 0.210 | 42 | 0/0 |
| gliner_decide_bare | -37* | 77.9 | 72.1 | 18/28 | 49.7 | -0.02 | 2/10 | 3/20 | 56.5 | — / — | — | — | 0.226 | 33 | 0/0 |
| gliner_decide_1b_desc | -42* | 71.4 | 77.1 | 17/28 | 49.7 | 0.43 | 0/10 | 5/20 | 54.5 | — / — | — | — | 0.224 | 75 | 0/0 |
| gliner_multi_decide_desc | -74* | 63.6 | 63.6 | 12/28 | 47.5 | 0.31 | 0/10 | 2/20 | 46.5 | — / — | — | — | 0.242 | 23 | 0/0 |
| julia_1 | -79* | 35.0 | 41.4 | 9/28 | 48.8 | 0.22 | 0/10 | 3/20 | 46.0 | 45.0 / 37.3 | 7/20 | 38.5 | 0.505 | 599 | 0/219 |
| laya_router | -20* | 62.1 | 73.6 | 15/28 | 48.8 | 0.22 | 2/10 | 5/20 | 61.0 | 55.0 / 71.5 | 7/20 | 59.5 | 0.208 | 29 | 2/219 |
| laya_typed | -26* | 67.1 | 75.0 | 14/28 | 45.6 | 0.10 | 5/10 | 3/20 | 49.0 | 67.7 / 75.8 | 8/20 | 64.0 | 0.182 | 31 | 2/219 |
| legacy_laya_v2 | -36* | 62.1 | 75.0 | 15/28 | 48.8 | 0.23 | 2/10 | 5/20 | 61.5 | — / — | — | — | 0.187 | 6548 | 0/0 |
| span01_pro | 18 | 85.0 | 84.3 | 22/28 | 71.9 | 0.72 | 7/10 | 12/20 | 63.5 | 80.4 / 84.6 | 13/20 | 72.0 | 0.162 | 597 | 0/0 |
| span01_lite | 6 | 82.9 | 82.1 | 20/28 | 66.6 | 0.65 | 10/10 | 10/20 | 61.0 | 75.8 / 76.5 | 8/20 | 67.5 | 0.159 | 895 | 0/0 |
| span01_lite_or | 18 | 85.0 | 84.3 | 22/28 | 73.8 | 0.79 | 8/10 | 12/20 | 63.5 | 80.4 / 84.6 | 13/20 | 72.0 | 0.162 | 587 | 0/0 |
| nimble_9b | 44 | 92.9 | 88.6 | 24/28 | 70.3 | 0.48 | 3/10 | 12/20 | 75.5 | 93.1 / 90.8 | 15/20 | 85.5 | 0.084 | 1620 | 0/0 |
| tev1_4b | 27 | 87.1 | 87.1 | 26/28 | 64.4 | 0.83 | 7/10 | 14/20 | 69.5 | 89.2 / 91.5 | 12/20 | 75.0 | 0.115 | 452 | 0/0 |
| tev1_0.8b | -7 | 67.9 | 72.1 | 23/28 | 64.7 | 0.70 | 7/10 | 9/20 | 58.5 | 78.8 / 81.2 | 11/20 | 64.0 | 0.171 | 142 | 0/0 |
| decider_4b_clefrev_review | 59 | 90.7 | 90.7 | 24/28 | 80.0 | 0.88 | 8/10 | 12/20 | 82.5 | 93.1 / 93.1 | 15/20 | 89.5 | 0.076 | — | 0/219 |
| decider_4b_clefrev_audit | 58 | 90.0 | 89.3 | 25/28 | 77.8 | 0.90 | 7/10 | 12/20 | 83.0 | 92.7 / 92.7 | 15/20 | 90.5 | 0.081 | — | 0/219 |
| clef_27b | 52 | 89.3 | 90.7 | 23/28 | 75.6 | 0.88 | 5/10 | 9/20 | 80.0 | 93.5 / 93.8 | 16/20 | 88.5 | 0.064 | 870 | 0/219 |
| clef_flash_9b_xpu | 41 | 87.9 | 86.4 | 24/28 | 71.6 | 0.90 | 6/10 | 9/20 | 74.5 | 90.8 / 92.7 | 14/20 | 81.5 | 0.087 | 142 | 0/219 |
| decider_4b_clefflashrev_review | 49 | 91.4 | 89.3 | 26/28 | 71.9 | 0.90 | 6/10 | 12/20 | 80.0 | 92.3 / 92.3 | 14/20 | 80.5 | 0.083 | — | 0/219 |
| decider_4b_clefflashrev_audit | 47 | 89.3 | 88.6 | 26/28 | 70.3 | 0.89 | 6/10 | 12/20 | 80.0 | 91.9 / 92.7 | 14/20 | 80.5 | 0.087 | — | 0/219 |
| clm_v0.1_8b | -35 | 67.9 | 58.6 | 13/28 | 50.6 | 0.49 | 4/10 | 5/20 | 52.5 | 67.3 / 66.5 | 9/20 | 59.0 | 0.238 | 80 | 0/219 |
| strands_2b_hobson_v19_xpu | 21* | 83.6 | 83.6 | 20/28 | 59.4 | 0.79 | 7/10 | 9/20 | 70.0 | 78.5 / 82.3 | 13/20 | 75.5 | 0.134 | 126 | 0/216 |
| strands_2b_hobson_v19_xpu_trunc | 21 | 83.6 | 83.6 | 20/28 | 59.1 | 0.77 | 7/10 | 9/20 | 70.0 | 78.5 / 82.3 | 13/20 | 75.5 | 0.134 | 125 | 0/219 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.6 | — | 0/10 | 17/20 | 79.0 | 57.7 / 57.7 | 5/20 | 59.0 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
<!-- /AUTO:marcador -->

Columnas: triaje = % sobre 5 preguntas × 14 casos. dept = departamento correcto.
papers = % sobre 5 dimensiones × 32 papers. ρ = Spearman de relevancia. skip LOO = de los 10
papers que no merecen lectura, cuántos descarta la cascada (umbral por leave-one-out).
adv dept = routing correcto en adversarial-1+2. triaje ext = T15–T40 (26 casos nuevos, validados
el 26-sep). adv3 = adversarial-3 equilibrado (20 casos: 10 manipulados y 10 honestos, 5 por
departamento). Brier = media de las preguntas sí/no
(más bajo es mejor). ms = mediana por caso (Jev por API; CLM y Strands en Intel Arc
Pro B70; otros modelos según su ficha, principalmente GPU GB10).

Configuración de cada run: Jev = `jev-1.13-20260917` vía OpenRouter (`jev_typesafe_v1`: API
directa, `jev-1.13.0`). Cascadas = 2ª pasada revisor-auditor (`jevbench/cascade.py`). Decider =
`Mapika/decider-*` bf16 en GB10 (el 35B sin CUDA graphs; NVFP4 servido con vLLM). AnyJev = L0 bf16.
GLiNER `desc` = etiquetas con descripción, `bare` = como la prueba del 24-sep. Julia-1 en CPU local.
Laya en GB10 (`laya_router`, `laya_typed`); `legacy_laya_v2` = rerun de Lyra en CPU.
LLM = `gpt-6-luna` (API OpenAI, Responses + JSON Schema estricto) con `system-one-adapter` 0.2.1;
`_prob` = `llm_answer_mode=probabilities`, `_disc` = `discrete`. `llm_gpt61sol_low_prob` =
`gpt-6.1-sol` con `reasoning_effort=low` (mismo modo `probabilities`).
Strands = `strands-decider` git `eb89e5c`, LoRA+cabeza pointer sobre Qwen3.5-2B bf16
en Arc Pro B70 (XPU), ventana 4096 estricta.
Versiones de Jev comprobadas: `docs/versiones_jev.md` (sin cambios a 27-sep).

## Lectura

**Recomendación vigente (3-oct):**
- **Jev → revisor-auditor (regla `audit`)**, sin reglas duras.
- **Alerta para revisión humana** cuando `manipulation ≥ 0.5` en la 2ª pasada. Validada en
  casos nuevos (adv5: 9/10 manipulados, 1/10 FP). Acumulado adv3 + adv4 + adv5: **25/30
  manipulados, 1/30 FP** con revisor Jev — y **27/30 con Clef-27B en una sola pasada**, sin
  revisor (1/30 FP). No cambia el routing.
- **Alternativa más barata con la misma calidad:** Decider-4B local → revisor Jev.
- **Revisor de mayor ajustado medido (nuevo, 4-oct):** Decider-4B → revisor
  **gpt-6.1-sol (low)** (`decider_4b_solrev_review` 68 / `_audit` 66, por encima del 64
  del revisor Jev; diferencia significativa solo en `relevance` de papers, p = 0.04).
  La pasada-2 cuesta ~$0.005/caso, ~100× la de Jev — solo si el revisor puede ser API de
  pago y se quiere el máximo agregado.
- **Alternativa 100 % local (nuevo, 3-oct):** Decider-4B → revisor **Clef-27B**
  (`decider_4b_clefrev_audit`, ajustado 58) cumple el criterio JEV-32 que ningún local
  cumplía (~89 % de la ganancia de Jev en adv3+adv5, ~61 % en triaje, alerta 9/10 · 1 FP
  en adv5). Queda por debajo del circuito con Jev (64) pero sin API ni salida de datos.
  El plan y los anteriores intentos están en `plan_revisor_local.md` y
  `experimentos/cascada_jev.md`.

**Por modelo (GT v3):**

- **CLM-v0.1-8B (Contrastive-LM, 3-oct, negativo):** run `clm_v0.1_8b`, 195 casos
  sin errores, Intel Arc Pro B70 de 32 GB. Ajustado **−35** (mayoría 0), Brier 0.238,
  mediana 80 ms. Ejecución viable y rápida, pero varias derrotas significativas frente
  a Jev en fases válidas; no es candidato a recomendación. Ficha: `docs/modelos.md` §CLM.
- **Strands Decider 2B Hobson v19 (3-oct):** decisor dedicado abierto (Apache-2.0),
  LoRA + cabeza pointer sobre Qwen3.5-2B, servido en Intel Arc Pro B70 con XPU
  (backend experimental upstream). Ajustado **21\*** — `*` porque un caso de papers
  excede la ventana 4096 y `--strict-window` lo rechaza (papers32 queda 31/32 y no
  cuenta en la media); la variante `_trunc` (truncado por defecto del servidor)
  cubre los 195 casos con el mismo ajustado 21. Por debajo de Decider-4B (33) y
  muy por debajo de Jev (45), aunque por encima de la mayoría en casi todas las
  fases. Falla donde el trivial es fuerte: dept de adv1+2 9/20 frente a 17/20 de
  responder siempre `admin`. Derrotas significativas en `same_day` ext_es frente
  a Jev y `relevance` de papers frente a Decider-4B; ninguna victoria
  significativa. Rápido: ~0,13 s/caso cliente (con túnel SSH). Runs
  `strands_2b_hobson_v19_xpu[_trunc]`. Ficha: `docs/modelos.md` §Strands.
- **Jev** es el incumbente. Con revisor: triaje 91–94, papers 74–75, adv 18/20, adv3 18/20.
  OpenRouter y la API de TypeSafe son equivalentes (406/409 respuestas iguales).
- **Decider-4B** acierta los mismos departamentos que Jev en triaje (diferencias no
  significativas, p ≥ 0.12), pero en adv3 queda por detrás (12 frente a 17/20, p = 0.06).
- **Decider-35B-A3B**: no mejora al 4B en triaje; es el que mejor ordena los papers por
  relevancia (ρ 0.90). NVFP4 rinde igual que bf16 y va 3.5× más rápido (190 ms/caso).
- **AnyJev**: 32B es el mejor open-weight en adv3 (15/20), pero lento (~2.5 s) y mal calibrado;
  8B consigue el mejor papers de una sola pasada (73.8).
- **LLM generalista (gpt-6-luna, 29-sep)** vía `system-one-adapter` de TypeSafe (su prompt y
  su esquema, API directa de OpenAI): en una sola pasada queda **al nivel de la cascada de
  Jev** (triaje 93.6/95.7, papers 78.8, adv 18/20, adv3 17/20, adv5 83.5, Brier noul 0.053).
  Frente a `jev_v3`, la única diferencia significativa es `depth` en papers (13 frente a 1,
  p < 0.01, a favor del LLM). Frente a `jev_cascade_audit`, solo `urgency` en adv4 (1 frente a
  10, p = 0.01, a favor de la cascada). El resto, sin diferencia significativa. Cuesta ~5.5× más por caso ($0.00019 frente a $0.000035)
  y es ~5× más lento (mediana 3.1 s frente a 0.64 s). El modo `discrete` rinde parecido pero
  calibra peor (Brier 0.077) y ordena peor los papers (ρ 0.77).
- **gpt-6.1-sol (1-oct, `reasoning_effort=low`):** modelo de OpenAI ~20× más caro por token que
  luna, medido con el mismo protocolo. **Ajustado 65: la mejor una pasada medida**, por encima de
  luna (61) y a la par de la cascada `jev_cascade_audit` (64), aunque por debajo de la mejor
  config absoluta (`llm_gpt6luna_jevrev_audit`, 71). Frente a luna solo es significativo
  `urgency` de adv4 (6–0 a favor de sol, p = 0.03); frente a `jev_v3`, `depth` de papers (13–1 a favor de sol, p < 0.01);
  frente a `jev_cascade_audit`, nada significativo (la cascada gana adv3 92.0/89.5 sin
  significación). Calibra igual que luna (Brier noul 0.054). 195 casos, 0 errores, coste
  medido **$0.56 (~$0.0029/caso, ~15× luna y ~80× Jev)** y mediana 3.4 s/caso. Resuelve como
  `gpt-6.1-sol` (sin fecha). Precio $2/$10 por Mtok (OpenRouter/fichas; pendiente confirmar
  en la consola de OpenAI). Plan y pre-registro: `docs/plan_gpt61sol.md`.
  **Alcance completo (4-oct, JEV-60):** el modo `discrete` da ajustado **63**
  (`llm_gpt61sol_low_disc`, $0.38, mediana 2.2 s) — mismo patrón que luna, ~2 puntos bajo
  `probabilities` y peor calibrado (Brier noul 0.073 frente a 0.054). Como **revisor de
  Decider-4B** (`decider_4b_solrev_*`) **cumple el criterio JEV-32** — el primero que supera
  en ajustado al revisor Jev sobre ese D1: audit **66** / review **68** frente a 64 de
  `decider_4b_jevrev_audit` (recupera ~136 % de la ganancia de Jev en adv3+adv5 y ~105 % en
  triaje, sin empeorar ninguna fase, alerta adv5 9/10 TP y 0 FP). Frente al revisor Jev la
  única diferencia significativa por pregunta es `relevance` de papers (2–10 a favor de sol,
  p = 0.04); frente al revisor luna (52) ninguna diferencia por pregunta es significativa.
  Coste de la pasada-2: **$1.05 (~$0.0054/caso, ~100× el revisor Jev)**. Como **D1 con
  revisor Jev** (`llm_gpt61sol_jevrev_*`): audit/review **66**, por debajo de
  `llm_gpt6luna_jevrev_audit` (71). Como **alerta de una pasada**
  (`llm_gpt61sol_low_alert_raw`): 22/30 TP y 0/30 FP — **no cumple** el criterio (adv4 5/10),
  entre Span-01 (8/30) y Clef-27B (27/30). Detalle: `docs/experimentos/cascada_jev.md` y
  `docs/experimentos/alerta_manipulacion.md`.
- **Cascadas con LLM (29-sep):** `llm_gpt6luna_jevrev_audit` (LLM → revisor Jev) es la
  mejor configuración medida (adv total 92.0, adv5 88.5, Brier 0.045, alerta 9/10 con 1 FP),
  estadísticamente equivalente a `jev_cascade_audit` pero a ~3× el coste y la latencia.
  `decider_4b_llmrev_audit` (revisor LLM) recupera el 77 % de la ganancia de Jev en adv3+adv5
  — el primer revisor no-Jev que supera el 50 % ahí — pero falla el criterio JEV-32 por triaje
  (28 %) y por la alerta (6/10). Detalle: `docs/experimentos/cascada_jev.md`.
- **LLM local Qwen3.8-27B (29-sep, negativo):** servido con SGLang en el Spark .80 a través
  del mismo adaptador. Checkpoint `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`:
  NVFP4 (4 bits), con LM head en BF16; no es una evaluación del backbone completo en BF16.
  La comparación con Clef-27B (BF16) no aísla el efecto del entrenamiento y la cabeza
  de decisión del posible efecto de cuantización. Apenas supera la línea base trivial (triaje 73.6, papers 52.2,
  ρ −0.17, adv total 58.5 frente a 79.0 del baseline `admin`, Brier 0.231) y es el más
  lento del marcador (~6.8 s/caso). **Nota (revisión 4-oct):** esta batería se midió
  con `structured=true` contra SGLang —el modelo no recibía las preguntas (solo el
  esquema-gramática), véase la causa raíz en el punto JEV-63— así que no es una
  valoración válida del modelo; las medidas válidas locales son las sin esquema
  (NVFP4 52, FP8 49, GGUF 48).
- **LLM local Qwen3.8-Flash-Next (30-sep, negativo):** thinking activado en vLLM (.81), porque
  sin él fallaba el smoke. Queda por debajo de la mayoría (ajustado −40) y del 27B: triaje
  65.7/55.0, papers 38.1 (ρ −0.01), adv3 65.3 y Brier 0.317; Jev y gpt-6-luna lo superan
  significativamente en múltiples preguntas, sin ninguna ventaja significativa del Flash.
  También medido con `structured=true` (modelo a ciegas): igualmente no válido para valorar
  al modelo — ver JEV-63.
  Entrega 191/195 respuestas tras reintentar (4 timeouts), mediana 49.7 s/caso y ~14.7 h de
  pared entre la pasada completa y el reintento. Run `llm_qwen38flash_prob`.
- **Robustez del adaptador LLM (1-oct):** al investigar esos timeouts se comprobó que el
  límite era por petición, faltaba un presupuesto total y un tope de salida, y el runner
  no conservaba la telemetría de intentos y tokens. Se corrigieron los límites, el
  diagnóstico y la redacción de secretos; un smoke de 18 ejecuciones terminó sin errores
  de transporte y un timeout provocado se recuperó en el caso siguiente. No se cambiaron
  prompt, preguntas, GT, scorer ni resultados históricos, por lo que el marcador no varía.
- **GPT-OSS-120B en Cerebras (3-oct, JEV-54):** el LLM abierto de OpenAI servido por
  Cerebras Inference con el mismo adaptador (`reasoning_effort=low`, temperatura 0,
  razonamiento separado). Ajustado **34**: sobre la mayoría y muy por encima del
  Qwen3.8-27B local NVFP4 (−16) — comparación descriptiva, no ablación de
  cuantización — pero por debajo de Jev (45), Clef-27B (52), luna (61) y sol (65).
  Triaje 87.9/88.6 sin diferencias significativas frente a Jev; la brecha agregada
  viene de adv3 (77.5 frente a 87.5; dept 13/20, p = 0.12), ρ relevancia de papers
  (0.64 frente a ~0.87) y calibración (Brier noul 0.108). adv5 a la par (76.0/77.0).
  195 casos, 0 errores, coste medido $0.12 (~$0.00062/caso). La cuenta impone
  5 req/min y 150 req/h: el run se espació con `min_interval=27` (opción nueva del
  adaptador), así que `ms`/`usage.latency` incluyen la espera; latencia API ~0.5 s.
  Run `llm_cerebras_gptoss120b_low_prob`; manifiesto en `docs/infra_runs/`.
- **Qwen3.8-27B en Cerebras (3-oct, JEV-54):** mismo protocolo que GPT-OSS pero
  sin pacing (límites por modelo mucho más holgados) y con ~3× más tokens de
  razonamiento `low`. Ajustado **59** — el mejor LLM generalista tras sol (65) y
  luna (61), por encima de Jev (45) y Clef-27B (52). **Gana a Jev en `same_day`
  de adv5 con significación (6–0, p = 0.03)** y roza el corte en `urgency`
  (5–0, p = 0.06); sin derrotas significativas frente a Jev ni luna. Triaje ext
  96.5/95.8 (los mejores del marcador), papers 77.8 (ρ 0.80), adv3 87.0, Brier
  0.060. Mediana 0.77 s/caso real, $0.44 medidos. El mismo tamaño en NVFP4 local
  daba −16: el salto es descriptivo (precisión, backend, muestreo y razonamiento
  difieren), no una ablación de cuantización. JEV-57 (4-oct) aporta un diagnóstico:
  los smoke SGLang y Ollama tienen distribuciones degeneradas con esquema
  y no sin él. Debilita un defecto exclusivo de SGLang, pero no aísla
  modelo, prompt/esquema del adaptador y servidor, ni efectos de precisión.
  Dos casos sin normalizar contienen ceros; no inferirlos de toda uniformidad.
  Run `llm_cerebras_qwen38_27b_low_prob`; manifiesto en `docs/infra_runs/`.
- **Qwen3.8-27B FP8 local + `structured=false` (4-oct, JEV-57):** ajustado
  **49**, 195 casos, 0 errores, **0/259 elecciones casi uniformes**. Frente
  al histórico cambian precisión, salida y límites: no una sola variable.
  Papers 80.3 (rho 0.82), ligeramente sobre sol 80.0 descriptivamente;
  adv3 86.0, Brier 0.080, 6.4 s/caso. Contrastes por pregunta frente a Jev:
  `depth` p<0.01 y `practice` p≈0.016, sin corrección de multiplicidad.
  No superioridad global; Brier peor que Jev (0.071) y ~10× su latencia.
  Bajo Cerebras (59) y Clef-27B (52) en ajustado descriptivo. NVFP4 sin
  esquema ya tiene batería completa (52), distinta de este run FP8. Run
  `llm_qwen38_27b_fp8_nostruct_prob`; manifiesto en `docs/infra_runs/`.
- **Qwen3.8-27B, cuadrícula completa (4-oct, JEV-58/61; revisión):**
  - Local sin esquema: NVFP4 **52** (Brier 0.076, 5.3 s/caso), FP8 **49**
    (0.080, 6.4 s), GGUF **48** (0.084, 10.8 s). Mismos casos/GT/scorer.
    El histórico NVFP4 también difiere en límites: no una ablación de una
    sola variable. El contraste de salida es fuerte, no una causa interna aislada.
  - Cerebras probabilities con/sin esquema: **59/65**, discrete **58/58**.
    Cero errores finales, un reintento por malformado en cada run sin esquema.
    Mínimo McNemar probabilities=0.0625: no significativo al 5 %, pero no
    equivalencia ni independencia del esquema. Brier prob 0.056–0.060 vs
    discrete 0.072–0.077; el ranking 65 empata solo por redondeo con sol.
  - Jev→Cerebras audit: **68/69**, frente a Jev→Jev 64; sin significación
    por pregunta (p≥0.125), sin equivalencia demostrada. Brier 0.064/0.065
    vs 0.055 de Jev→Jev; alerta 24/23 TP de 30, 0 FP.
  - Diagnóstico JEV-63 (misma tarde, 12 casos × 3 reps, cuatro
    configuraciones): se observa la **interacción** del prompt completo
    TypeSafe × esquema forzado — solo esa celda emite vectores nulos en
    local (mismos IDs nulos en las tres reps); mismo esquema con prompt simple o mismo prompt
    sin esquema dan cero. vLLM midió Flash-Next (otro modelo).
  - `unif choice` del resumen cubre 9 fases, excluye adv4/adv5: histórico
    53/218. En las 11 fases: 67/257 histórico y 0/259 en los nuevos locales
    sin esquema y Cerebras. No equivale a tasa de ceros crudos.
  Runs `llm_qwen38_27b_{nvfp4,gguf81}_nostruct_prob`, Cerebras
  `llm_cerebras_qwen38_27b_{nostruct_prob,disc,nostruct_disc}` y
  `jev_cerebrasqwen{,ns}rev_*`; manifiestos en `docs/infra_runs/`.
- **Span-01 (Respan, 29-sep):** clasificador de comportamientos cerrado, más barato que Jev
  ($0.000016/caso pro, ~2× menos; lite gratis). Competitivo pero por debajo en conjunto
  (ajustado 18 frente a 45 de Jev); sí gana en `depth` de papers (17/32 vs 6/32, p = 0.01).
  Como **detector de manipulación de una pasada** (misma pregunta y umbral del revisor)
  queda descartado: 8/30 pro y 5/30 lite, aunque sin falsos positivos.
- **Nimble-9B (Bespoke, 30-sep):** LoRA sobre Qwen3.5-9B que puntúa tokens candidato sin
  generar (una pasada forward por pregunta). El open-weight más fuerte evaluado sin revisor:
  ajustado 44 (a la par de `jev_v3`, 45; por encima de Decider-4B, 33). Triaje 92.9/88.6,
  adv3 85.5, pero ordena mal los papers (ρ 0.48). Sin diferencias significativas frente a
  Jev, Decider-4B ni gpt-6-luna salvo `urgency` de adv4, donde gana a gpt-6-luna (p<0.01).
  Mediana 1.6 s/estado en GB10. Run `nimble_9b`.
- **Tev1-4B (Together, 30-sep):** fine-tune autoregresivo de Qwen3.5-4B (una letra por
  pregunta, una generación por pregunta). Ajustado 27, por debajo de Nimble-9B (44) y
  Decider-4B (33): triaje 87.1/87.1, papers 64.4 (ρ 0.83), adv3 75.0, adv4 77.5,
  adv5 72.5, Brier 0.115. Sin diferencias significativas frente a Jev/Decider/Nimble;
  gpt-6-luna le gana en `depth` de papers (p<0.01). El más rápido: ~0.45 s/estado.
  Licencia de los pesos pendiente de publicación. Run `tev1_4b`.
- **Tev1-0.8B (Together, 30-sep, negativo):** mismo adaptador y contrato que el 4B,
  pero el escalado rompe el modelo: ajustado **−7**, por debajo de la mayoría
  trivial (triaje 67.9/72.1, adv total 58.5 frente a 79.0 del baseline `admin`,
  adv3 64.0, Brier 0.171, 12 binarios en la frontera 0.45–0.55 de adv3). El 4B
  le gana con significación en `same_day` de adv4 (10–1, p=0.01); los incumbentes
  le ganan en varias preguntas (department adv3/ext_es, clinical triaje ES).
  ~0.14 s/estado. Licencia de los pesos pendiente, igual que el 4B. Run `tev1_0.8b`.
- **GLiNER**, **Laya** y **Julia-1**: descartados zero-shot (en o por debajo de la línea base de
  mayoría en adversarial; Julia, incluso en triaje).
- **Clef-27B (Cloudflare, 3-oct):** open-weight (Apache-2.0), Qwen3.8-27B + cabeza de esquema
  conjunta, API SystemOne nativa, una pasada por estado. Ajustado **52** — el mejor single
  open-weight medido, por encima de `jev_v3` (45) y Nimble-9B (44); solo por debajo de
  gpt-6.1-sol (65), gpt-6-luna (61) y varias cascadas. Significativamente mejor que Jev
  en `depth` de papers (p=0.02); sin derrotas significativas. adv1/adv2 no se usan como
  evidencia comparativa. Brier 0.064,
  ~0.87 s/estado. Punto débil: `department` de adv1+2 (9/20). **Como revisor de Decider-4B
  (`decider_4b_clefrev_audit`, ajustado 58) es la primera configuración local que cumple el
  criterio JEV-32** (~89 % de la ganancia de Jev en adv3+adv5, ~61 % en triaje, alerta 9/10
  con 1 FP). Y **como alerta de una pasada** (`clef_27b_alert_raw`) da 27/30 TP · 1/30 FP —
  frente a 25/30 del revisor Jev, sin diferencia significativa (McNemar p=0.50). Runs `clef_27b`, `decider_4b_clefrev_*`. Ficha:
  `docs/modelos.md` §Clef.
- **Clef-Flash 9B (Cloudflare, 3-oct):** variante 9B de Clef sobre Qwen3.5-9B, mismo
  contrato, en el Arc Pro B70 de .70 (`clef_flash_9b_xpu`, 195 casos, 0 errores).
  Ajustado **41**: calidad ≈ Jev (45), por debajo de Clef-27B (52) pero a ~0.14 s/caso
  (~6× más rápido que el 27B, aunque en hardware distinto). Única derrota
  significativa frente al 27B: `urgency` de adv2 (p=0.03); frente a Jev gana en
  `depth` de papers (p=0.04). ρ relevancia 0.90, tercera de una pasada. **Como
  revisor no pasa el listón JEV-32** (recupera 38 % en
  adv3+adv5, ~50 % en triaje; `decider_4b_clefflashrev_audit` = 47), pero es el
  segundo mejor revisor local y el más barato. **Su alerta de una pasada sí cumple**
  (7/10 TP · 0 FP por set; 21/30 TP, p=0.18 vs el 27B). Ficha: `docs/modelos.md`
  §Clef-Flash.

**Experimentos** (`docs/experimentos/`):
- `cascada_jev.md`: revisor-auditor (Jev→Jev, Decider→Decider, Decider→Jev y revisores 100%
  locales — desde el 3-oct **Clef-27B sí recupera el listón del 50 %**; los anteriores no).
- `reglas_duras.md`: reglas regex, descartadas (0/10 en casos nuevos, 3/10 FP).
- `alerta_manipulacion.md`: alerta validada en adv5; extensión con Span-01 como detector de
  una pasada (negativo: 8/30 pro, 5/30 lite, 0 FP) y con **Clef-27B (positivo: 27/30, 1 FP)**.

**Notas de método:**
- La columna **ajustado** es el agregado único por run: media por fase de (acierto − mayoría) /
  (100 − mayoría). 0 = línea base trivial, <0 = peor que ella; `*` = cobertura incompleta.
- En adv1 + adv2, responder siempre `admin` saca 17/20: ese set no sirve para comparar modelos.
  Usar adv3–adv5 (equilibrados).
- Con n = 14–32, los IC95 se solapan casi siempre: usar `--vs` (McNemar) antes de afirmar que
  un modelo "gana".
- La 2ª anotación (JEV-27/28) mostró mucho ruido de etiquetado en urgency y same_day; 1–2
  puntos de diferencia ahí no significan nada.

## Seguimiento

- **Revisor local, reabierto el 3-oct:** Decider-35B NVFP4, AnyJev-32B/8B y gpt-6-luna no
  cumplieron el criterio JEV-32; **Clef-27B sí** (`decider_4b_clefrev_audit`, ajustado 58;
  ~89 % de la ganancia de Jev en adv3+adv5, alerta 9/10 con 1 FP). Existe por tanto una
  cascada 100 % local válida: Decider-4B → Clef-27B. Ver `docs/experimentos/cascada_jev.md`.
- **JEV-57/58/61 (revisión 4-oct):** NVFP4 sin esquema completa la batería
  con ajustado 52, frente al −16 histórico con esquema; límites/stack no
  perfectamente controlados. Cerebras funciona con y sin esquema (59/65),
  sin significación ni equivalencia demostrada. Guardar raw saneado
  y precisar cobertura del contador (9 vs 11 fases). No modificar históricos.
- **JEV-63 (resuelta 4-oct):** matriz 12 casos × 2 prompts × 2 rutas × 3 reps en
  cuatro configuraciones — la degeneración es la **interacción** prompt TypeSafe
  × esquema forzado (solo esa celda produce vectores nulos en local: 9/14/9 por
  rep en NVFP4/FP8/GGUF-Arc; `simple_struct` con el mismo esquema: 0; sin
  esquema: 0; Cerebras: 0). Manifiesto `docs/infra_runs/diag_qwen38_jev63.md`.
  Diagnóstico de 12 casos: no es puntuación ni generaliza al marcador.
  **Causa raíz (revisión externa, 4-oct):** con `structured=true` el adaptador
  envía solo el system prompt y el documento; las preguntas van solo al
  `response_format`, que los servidores locales usan para la gramática sin
  inyectarlo en el prompt — el modelo responde a ciegas (tokens de entrada
  222 local frente a 958 en Cerebras, que sí lo inyecta según los tokens).
  Los ceros no son una cualidad del prompt TypeSafe ni de la precisión: son
  una medición sin preguntas visibles. Verificado en las builds de SGLang y
  llama.cpp de estos runs; JEV-67 amplía a vLLM 0.29.0 y Ollama 0.32.14
  (tampoco inyectan).
  Total: 576 evaluaciones, 3 errores NVFP4 por salida agotada; coste Cerebras
  registrado por tokens/tarifas: $0.17217723.
- **JEV-65 (resuelta 4-oct):** ablación controlada del prompt (720 evaluaciones
  nuevas, NVFP4 + FP8): las dos frases anti-inyección **no son ni necesarias ni
  suficientes** — V1−frases (V3) y V1+redacción alternativa (V5) siguen emitiendo
  vectores nulos bajo esquema (NVFP4 9 y 8–14/rep; FP8 11 y 13–16/rep) y V2+frases
  (V4) sigue sano (0); V3/V5 sin esquema: 0. **JEV-66 confirma la causa raíz**:
  con el esquema inyectado en el system prompt (misma gramática), 0 nulos en
  los tres bloques (`docs/infra_runs/diag_qwen38_jev66.md`); la variación de
  conteo FP8 es compatible con ruido en condiciones ciegas — si las frases
  modulan con preguntas visibles no se midió.
  En `discrete` no hay vectores que anular, pero V1 degenera igual: papers
  fallan de forma sistemática (`length`/timeouts en NVFP4, solo timeouts en
  FP8) — discrete oculta la forma, no la
  degeneración. Rotación de claves choice en discrete: sin sesgo demostrado;
  el control en `probabilities` lo cierra JEV-67.
  Manifiesto `docs/infra_runs/diag_qwen38_prompt_ablacion.md`.
- **JEV-67 (4-oct):** batería completa con preguntas verificablemente
  visibles (puerta + regla de tokens por caso; thinking off, temp 0):
  struct+inject FP8 **51** / NVFP4 **50** / GGUF **48**, nostruct temp 0 FP8
  **51** (la gramática no cambia decisiones: 967/969), discrete+inject
  **63** en NVFP4 y GGUF (+13/+15 sobre probabilities — el modo cambia
  prompt y formato a la vez; en Cerebras el signo se invierte). Los fallos
  de papers en discrete eran del modelo a ciegas (0 con preguntas
  visibles). Rotación `choice` en probabilities: 24/259 cambios, acierto
  +6.2 pp a favor de rot1 — **sensibilidad al orden ≈ 7 puntos de ajustado
  en esta configuración; la media sobre órdenes no está medida**. Un caso
  (B07) emite vector nulo incluso con preguntas visibles. Sonda: ni vLLM
  0.29 ni Ollama 0.32.14 inyectan el esquema — `inject_schema_in_prompt`
  es la ruta local por defecto. Manifiesto
  `docs/infra_runs/qwen38_jev67.md`.
- **Trabajo abierto tras JEV-67:**
  - **JEV-68** — thinking local (`reasoning_effort`) con la misma ruta
    inject, a dos órdenes de opciones: cierra el hueco A1=51 vs Cerebras
    59–65 (candidato principal; la precisión parece secundaria — las tres
    dentro de 3 ptos).
  - **JEV-69** — issue upstream a `system-one-adapter`: `structured=true`
    debería inyectar las preguntas en el prompt (evidencia empaquetada en
    JEV-66/67).
  - **JEV-70** — DiffusionGemma-26B-A4B NVFP4 vía lecturas estructuradas de
    vLLM.
  - **JEV-71** — `discrete`+inject en FP8 (solo medido en NVFP4/GGUF) y
    secundarios: frases anti-inyección con preguntas visibles,
    `normalize=false`, IC bootstrap del ajustado agregado.
  - **JEV-72** — primacía de la opción-trampa en `department` (14/15
    cambios eran `bronchoscopia` primera→última), experimento de las 4
    rotaciones para estimar el ajustado medio sobre órdenes (~7 puntos en
    juego) y acotar el mecanismo discrete>prob (modo × thinking).
- Repetir `python3 -m jevbench.check_versions --log` periódicamente. Si aparece una versión
  nueva de Jev, repetir `jev_v3` y la cascada.

## Problemas del GT detectados

- **P04** (papers): `domain = "ild"` no era una opción válida y el diseño `cohort` chocaba
  con el título *systematic review*. **Corregido** a `ip`/`meta` (26-sep). Con esto, Jev pasa de
  66.2 a 67.5 en papers. Los informes antiguos y los tests usan el GT original (v1).
- El informe GLiNER del 24-sep daba 45.6% en papers, pero sus propios recuentos suman 49.1%.
- El informe AnyJev tenía los % de Laya ES/EN intercambiados (ES 63.6, EN 73.6).
- **GT v3 (27-sep):** 9 cambios tras la 2ª anotación (JEV-28), en `data/GT_CHANGELOG.md`.

## Histórico (informes de Lyra, re-puntuados con el harness)

| run | triaje ES | triaje EN | papers | ρ | adv dept |
|---|---|---|---|---|---|
| legacy_jev_v1 (20-sep) | 87.1 | 85.0 | 66.2 | 0.87 | 9/10 (solo adv1, con admin+catering) |
| legacy_jev_v2 (23-sep) | 86.4 | 88.6 | 66.2 | 0.87 | 15/20 |
| Jev v2 → revisor Jev | — | — | — | — | 18/20 (detector de manipulación 16/16) |
