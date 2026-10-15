# Resultados consolidados

Marcador actualizado el 11-oct-2026 con **GT v5**: 23 cambios de etiqueta
adjudicados por el usuario, mismos casos, preguntas y respuestas de modelos.
Revisión parcial de 88 campos; procedencia en `data/gt_v5_procedencia.json`.

Las tablas AUTO siguientes usan v5. El resto del texto editorial conserva los
resultados históricos de cada experimento con GT v4 (o v3 donde se indica);
las auditorías confirmatorias siguen ligadas a ese cierre, no se reinterpretan
como confirmaciones con GT v5. Resumen de la repuntuación: `docs/validacion_gt_v5.md`.
El registro completo por run se conserva en el repositorio privado.

<!-- AUTO:comando -->
```bash
python3 -m jevbench.report   # regenera este documento (runs en docs/resultados_runs.txt)
python3 -m jevbench.score --summary jev_v3 jev_typesafe_v1 jev_cascade_review jev_cascade_audit jev_cascade_audit_rules \
    llm_gpt6luna_jevrev_review llm_gpt6luna_jevrev_audit llm_gpt61sol_jevrev_review llm_gpt61sol_jevrev_audit jev_cerebrasqwenrev_review \
    jev_cerebrasqwenrev_audit jev_cerebrasqwennsrev_review jev_cerebrasqwennsrev_audit llm_gpt6luna_prob llm_gpt6luna_disc \
    jev_luna_decisions jev_luna_decisions_fb llm_gpt61sol_low_prob llm_gpt61sol_low_disc llm_qwen38_27b_prob \
    llm_qwen38flash_prob llm_cerebras_gptoss120b_low_prob llm_cerebras_qwen38_27b_low_prob llm_cerebras_qwen38_27b_nostruct_prob llm_cerebras_qwen38_27b_disc \
    llm_cerebras_qwen38_27b_nostruct_disc llm_qwen38_27b_fp8_nostruct_prob llm_qwen38_27b_gguf81_nostruct_prob llm_qwen38_27b_nvfp4_nostruct_prob llm_qwen38_27b_fp8_inject_prob \
    llm_qwen38_27b_fp8_nostruct_t0_prob llm_qwen38_27b_nvfp4_inject_prob llm_qwen38_27b_nvfp4_inject_disc llm_qwen38_27b_arcgguf_inject_prob llm_qwen38_27b_arcgguf_inject_disc \
    decider_4b_jevrev_review decider_4b_jevrev_audit decider_4b_llmrev_review decider_4b_llmrev_audit decider_4b_solrev_review \
    decider_4b_solrev_audit decider_35b_a3b decider_35b_a3b_nvfp4 decider_4b decider_4b_cascade_audit \
    decider_4b_d35rev_audit decider_4b_aj32brev_audit decider_4b_aj8brev_audit decider_4b_msrev_audit decider_4b_drexrev_audit \
    decider_4b_nimblerev_audit decider_2b decider_0.8b anyjev_qwen3_32b_l0 anyjev_qwen3_8b_l0 \
    anyjev_qwen3_1.7b_l0 gliner_decide_desc gliner_decide_bare gliner_decide_1b_desc gliner_multi_decide_desc \
    julia_1 laya_router laya_typed legacy_laya_v2 span01_pro \
    span01_lite span01_lite_or nimble_9b tev1_4b tev1_0.8b \
    decider_4b_clefrev_review decider_4b_clefrev_audit clef_27b clef_flash_9b_xpu decider_4b_clefflashrev_review \
    decider_4b_clefflashrev_audit clm_v0.1_8b strands_2b_hobson_v19_xpu strands_2b_hobson_v19_xpu_trunc dgemma_26b_a4b_nvfp4 \
    dgemma_26b_a4b_nvfp4_s1 dgemma_26b_a4b_nvfp4_s1_jevrev_review dgemma_26b_a4b_nvfp4_s1_jevrev_audit llm_qwen38_27b_fp8_jev68_off_d0_prob llm_qwen38_27b_fp8_jev68_on_d0_prob \
    llm_qwen38_27b_fp8_jev71_off_d0_disc llm_qwen38_27b_fp8_jev76_on_d0_disc llm_qwen38_27b_fp8_jev76_on_d1_disc llm_medgemma_27b_it_bf16_jev77_d0_disc llm_gemma3_27b_it_bf16_jev77_d0_disc \
    medgemma_27b_jev77_jevrev_audit oai_luna_decisions llm_haiku55_off_prob llm_haiku55_off_disc llm_haiku55_adapt_prob \
    decider_4b_haiku55rev_audit jev_haiku55rev_audit llm_haiku55_adapt_prob_r2 llm_ministral3b_med_prob llm_ministral3b_med_disc \
    jev_ms_decision1 drex_v15_9b
```
<!-- /AUTO:comando -->

## Marcador (GT v5, generado)

<!-- AUTO:marcador -->
| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v3 | 49 | 88.6 | 90.0 | 26/28 | 76.8 | 0.89 | 5/10 | 15/20 | 81.0 | 95.0 / 92.7 | 17/20 | 90.0 | 0.062 | 657 | 0/219 |
| jev_typesafe_v1 | 56* | 87.9 | 90.0 | 26/28 | 76.8 | 0.89 | 5/10 | 15/20 | 81.0 | 95.0 / 92.7 | 17/20 | 91.0 | 0.063 | 902 | 0/219 |
| jev_cascade_review | 69 | 92.1 | 93.6 | 26/28 | 84.8 | 0.80 | 6/10 | 19/20 | 91.0 | 95.4 / 93.8 | 18/20 | 92.5 | 0.045 | — | 0/219 |
| jev_cascade_audit | 68 | 91.4 | 93.6 | 26/28 | 83.2 | 0.89 | 5/10 | 19/20 | 90.5 | 94.6 / 93.5 | 18/20 | 92.5 | 0.045 | — | 0/219 |
| jev_cascade_audit_rules | 69* | 91.4 | 93.6 | 26/28 | — | — | — | 20/20 | 91.5 | 94.6 / 93.5 | 20/20 | 94.5 | 0.043 | — | 0/117 |
| llm_gpt6luna_jevrev_review | 72 | 94.3 | 97.1 | 25/28 | 84.5 | 0.84 | 6/10 | 19/20 | 91.0 | 95.8 / 95.8 | 18/20 | 92.0 | 0.042 | — | 0/219 |
| llm_gpt6luna_jevrev_audit | 75 | 93.6 | 97.1 | 25/28 | 85.2 | 0.80 | 9/10 | 19/20 | 94.0 | 95.0 / 95.0 | 18/20 | 92.5 | 0.034 | — | 0/219 |
| llm_gpt61sol_jevrev_review | 70 | 92.1 | 95.7 | 25/28 | 85.5 | 0.86 | 7/10 | 19/20 | 90.0 | 94.2 / 95.0 | 18/20 | 93.0 | 0.043 | — | 0/219 |
| llm_gpt61sol_jevrev_audit | 71 | 92.1 | 95.0 | 25/28 | 87.4 | 0.70 | 8/10 | 19/20 | 91.0 | 94.2 / 95.4 | 18/20 | 94.0 | 0.038 | — | 0/219 |
| jev_cerebrasqwenrev_review | 71 | 90.0 | 92.1 | 24/28 | 83.2 | 0.90 | 5/10 | 19/20 | 91.5 | 95.8 / 94.6 | 18/20 | 91.5 | 0.051 | — | 0/219 |
| jev_cerebrasqwenrev_audit | 71 | 90.0 | 90.7 | 24/28 | 83.9 | 0.89 | 9/10 | 19/20 | 91.5 | 95.0 / 93.1 | 18/20 | 91.5 | 0.057 | — | 0/219 |
| jev_cerebrasqwennsrev_review | 72 | 92.1 | 93.6 | 26/28 | 83.9 | 0.83 | 7/10 | 19/20 | 92.0 | 94.6 / 93.5 | 15/20 | 87.0 | 0.049 | — | 0/219 |
| jev_cerebrasqwennsrev_audit | 73 | 92.1 | 93.6 | 26/28 | 83.9 | 0.83 | 9/10 | 19/20 | 93.0 | 93.8 / 92.7 | 15/20 | 89.0 | 0.055 | — | 0/219 |
| llm_gpt6luna_prob | 65 | 93.6 | 95.7 | 25/28 | 83.9 | 0.90 | 9/10 | 19/20 | 89.0 | 93.5 / 93.5 | 17/20 | 88.5 | 0.044 | 3027 | 0/219 |
| llm_gpt6luna_disc | 63 | 93.6 | 91.4 | 26/28 | 82.9 | 0.86 | 6/10 | 18/20 | 87.0 | 92.3 / 92.7 | 18/20 | 90.0 | 0.066 | 1876 | 0/219 |
| jev_luna_decisions | 50* | 91.4 | 89.3 | 26/28 | 76.8 | 0.81 | 7/10 | 17/19 | 75.1 | 89.6 / 89.6 | 18/19 | 90.5 | 0.093 | 677 | 0/214 |
| jev_luna_decisions_fb | 41 | 91.4 | 89.3 | 26/28 | 76.8 | 0.81 | 7/10 | 17/20 | 74.0 | 89.6 / 89.6 | 18/20 | 88.5 | 0.095 | 677 | 0/216 |
| llm_gpt61sol_low_prob | 69 | 92.9 | 93.6 | 26/28 | 86.5 | 0.92 | 8/10 | 19/20 | 90.5 | 94.2 / 94.6 | 18/20 | 92.0 | 0.045 | 3415 | 0/219 |
| llm_gpt61sol_low_disc | 68 | 92.1 | 92.1 | 26/28 | 83.2 | 0.80 | 6/10 | 19/20 | 91.5 | 94.6 / 94.2 | 17/20 | 89.0 | 0.064 | 2221 | 0/219 |
| llm_qwen38_27b_prob | -17* | 73.6 | 73.6 | 13/28 | 54.2 | — | 0/10 | 3/20 | 58.5 | 77.2 / 76.5 | 9/20 | 70.0 | 0.220 | 6799 | 53/218 |
| llm_qwen38flash_prob | -43* | 65.7 | 55.0 | 14/28 | 38.1 | 0.02 | 0/10 | 4/19 | 51.8 | 55.4 / 51.7 | 6/19 | 63.2 | 0.317 | 47875 | 31/215 |
| llm_cerebras_gptoss120b_low_prob | 36 | 87.9 | 88.6 | 23/28 | 72.6 | 0.65 | 5/10 | 13/20 | 75.0 | 87.7 / 91.5 | 13/20 | 80.0 | 0.102 | 27000 | 0/219 |
| llm_cerebras_qwen38_27b_low_prob | 60 | 90.0 | 88.6 | 23/28 | 82.3 | 0.79 | 6/10 | 15/20 | 84.0 | 96.5 / 95.8 | 14/20 | 89.5 | 0.048 | 760 | 0/219 |
| llm_cerebras_qwen38_27b_nostruct_prob | 70 | 90.0 | 92.9 | 23/28 | 86.1 | 0.85 | 6/10 | 18/20 | 91.5 | 95.4 / 95.8 | 15/20 | 91.0 | 0.044 | 627 | 0/219 |
| llm_cerebras_qwen38_27b_disc | 62 | 91.4 | 92.1 | 25/28 | 84.5 | 0.82 | 8/10 | 15/20 | 86.0 | 93.8 / 94.6 | 15/20 | 90.5 | 0.064 | 561 | 0/219 |
| llm_cerebras_qwen38_27b_nostruct_disc | 62 | 90.0 | 91.4 | 23/28 | 84.8 | 0.77 | 8/10 | 16/20 | 84.0 | 95.8 / 96.9 | 16/20 | 90.5 | 0.061 | 460 | 0/219 |
| llm_qwen38_27b_fp8_nostruct_prob | 49 | 87.9 | 90.0 | 24/28 | 83.5 | 0.81 | 9/10 | 13/20 | 80.0 | 90.8 / 91.2 | 15/20 | 88.5 | 0.074 | 6369 | 0/219 |
| llm_qwen38_27b_gguf81_nostruct_prob | 48 | 87.1 | 89.3 | 25/28 | 79.0 | 0.86 | 5/10 | 12/20 | 80.0 | 90.8 / 93.8 | 14/20 | 86.0 | 0.078 | 10787 | 0/219 |
| llm_qwen38_27b_nvfp4_nostruct_prob | 52 | 90.7 | 87.1 | 25/28 | 80.0 | 0.78 | 9/10 | 13/20 | 81.0 | 90.4 / 91.9 | 14/20 | 86.0 | 0.068 | 5297 | 0/219 |
| llm_qwen38_27b_fp8_inject_prob | 52 | 88.6 | 87.9 | 24/28 | 80.3 | 0.87 | 9/10 | 13/20 | 81.5 | 94.6 / 93.5 | 15/20 | 87.0 | 0.067 | 6502 | 1/219 |
| llm_qwen38_27b_fp8_nostruct_t0_prob | 52 | 88.6 | 87.9 | 24/28 | 79.0 | 0.86 | 4/10 | 13/20 | 81.5 | 94.6 / 93.5 | 15/20 | 87.0 | 0.067 | 6485 | 1/219 |
| llm_qwen38_27b_nvfp4_inject_prob | 51 | 88.6 | 87.9 | 25/28 | 81.3 | 0.87 | 8/10 | 14/20 | 79.5 | 92.7 / 92.7 | 15/20 | 87.5 | 0.079 | 5253 | 0/219 |
| llm_qwen38_27b_nvfp4_inject_disc | 67 | 92.9 | 92.9 | 26/28 | 84.2 | 0.76 | 9/10 | 18/20 | 87.5 | 96.2 / 96.2 | 15/20 | 90.5 | 0.056 | 2213 | 0/219 |
| llm_qwen38_27b_arcgguf_inject_prob | 49 | 88.6 | 85.7 | 24/28 | 79.4 | 0.87 | 8/10 | 13/20 | 79.0 | 92.7 / 94.2 | 15/20 | 87.5 | 0.076 | 7543 | 1/219 |
| llm_qwen38_27b_arcgguf_inject_disc | 67 | 92.9 | 92.1 | 25/28 | 84.8 | 0.82 | 9/10 | 18/20 | 87.5 | 95.4 / 95.8 | 15/20 | 90.0 | 0.052 | 3429 | 0/219 |
| decider_4b_jevrev_review | 68 | 92.1 | 93.6 | 25/28 | 83.2 | 0.84 | 7/10 | 19/20 | 89.5 | 94.2 / 93.8 | 18/20 | 94.0 | 0.047 | — | 0/219 |
| decider_4b_jevrev_audit | 66 | 90.7 | 93.6 | 25/28 | 81.6 | 0.79 | 6/10 | 18/20 | 88.5 | 93.1 / 92.3 | 18/20 | 94.0 | 0.057 | — | 0/219 |
| decider_4b_llmrev_review | 67 | 93.6 | 92.9 | 26/28 | 81.3 | 0.85 | 6/10 | 19/20 | 88.5 | 93.5 / 93.5 | 18/20 | 91.5 | 0.057 | — | 0/219 |
| decider_4b_llmrev_audit | 55 | 87.9 | 87.1 | 26/28 | 81.3 | 0.81 | 6/10 | 19/20 | 83.0 | 91.9 / 91.9 | 17/20 | 87.0 | 0.093 | — | 0/219 |
| decider_4b_solrev_review | 71 | 93.6 | 94.3 | 26/28 | 84.8 | 0.90 | 9/10 | 19/20 | 88.5 | 94.6 / 93.8 | 20/20 | 95.0 | 0.056 | — | 0/219 |
| decider_4b_solrev_audit | 68 | 90.7 | 94.3 | 26/28 | 84.8 | 0.89 | 5/10 | 19/20 | 88.5 | 92.3 / 93.8 | 20/20 | 94.0 | 0.084 | — | 0/219 |
| decider_35b_a3b | 39 | 84.3 | 79.3 | 24/28 | 75.8 | 0.92 | 6/10 | 14/20 | 78.0 | 92.3 / 88.5 | 13/20 | 80.0 | 0.092 | 678 | 0/219 |
| decider_35b_a3b_nvfp4 | 33 | 85.0 | 81.4 | 24/28 | 75.2 | 0.90 | 5/10 | 14/20 | 74.0 | 88.8 / 88.8 | 12/20 | 78.5 | 0.099 | 190 | 0/219 |
| decider_4b | 34 | 85.7 | 85.7 | 26/28 | 71.9 | 0.81 | 6/10 | 13/20 | 71.5 | 90.8 / 90.0 | 12/20 | 79.5 | 0.097 | 200 | 0/219 |
| decider_4b_cascade_audit | 39* | 87.1 | 87.1 | 26/28 | 74.2 | 0.74 | 6/10 | 12/20 | 74.5 | 90.4 / 90.4 | 13/20 | 81.0 | 0.090 | — | 0/219 |
| decider_4b_d35rev_audit | 52 | 89.3 | 87.9 | 26/28 | 71.6 | 0.83 | 4/10 | 16/20 | 83.5 | 93.1 / 91.9 | 13/20 | 85.0 | 0.076 | — | 0/219 |
| decider_4b_aj32brev_audit | 39 | 80.7 | 82.9 | 25/28 | 75.8 | 0.76 | 6/10 | 15/20 | 74.0 | 92.3 / 93.8 | 16/20 | 89.0 | 0.088 | — | 0/123 |
| decider_4b_aj8brev_audit | 28 | 84.3 | 84.3 | 26/28 | 70.3 | 0.75 | 7/10 | 13/20 | 69.5 | 90.0 / 88.5 | 12/20 | 78.0 | 0.118 | — | 0/185 |
| decider_4b_msrev_audit | 64 | 90.0 | 91.4 | 27/28 | 81.0 | 0.86 | 7/10 | 18/20 | 89.5 | 92.7 / 92.3 | 16/20 | 89.0 | 0.077 | — | 0/216 |
| decider_4b_drexrev_audit | 52 | 84.3 | 87.1 | 23/28 | 76.1 | 0.70 | 7/10 | 16/20 | 86.0 | 89.6 / 90.0 | 14/20 | 84.5 | 0.078 | — | 0/216 |
| decider_4b_nimblerev_audit | 46 | 90.7 | 87.1 | 25/28 | 72.6 | 0.82 | 6/10 | 13/20 | 79.0 | 91.9 / 92.3 | 13/20 | 82.0 | 0.086 | — | 0/95 |
| decider_2b | 20 | 77.9 | 78.6 | 23/28 | 71.6 | 0.84 | 4/10 | 11/20 | 69.0 | 86.5 / 89.6 | 13/20 | 74.0 | 0.118 | 79 | 0/219 |
| decider_0.8b | 13 | 82.1 | 81.4 | 21/28 | 70.3 | 0.82 | 7/10 | 11/20 | 64.5 | 82.7 / 83.8 | 9/20 | 66.0 | 0.123 | 43 | 0/219 |
| anyjev_qwen3_32b_l0 | 21 | 83.6 | 79.3 | 25/28 | 74.5 | 0.78 | 6/10 | 14/20 | 70.5 | 85.8 / 85.0 | 15/20 | 86.5 | 0.153 | 2552 | 0/0 |
| anyjev_qwen3_8b_l0 | 13 | 80.0 | 79.3 | 25/28 | 75.5 | 0.85 | 6/10 | 13/20 | 62.0 | 86.5 / 90.0 | 14/20 | 81.5 | 0.182 | 682 | 0/0 |
| anyjev_qwen3_1.7b_l0 | -3 | 81.4 | 71.4 | 25/28 | 69.7 | 0.43 | 9/10 | 14/20 | 65.0 | 71.2 / 80.4 | 9/20 | 53.5 | 0.261 | 181 | 0/0 |
| gliner_decide_desc | -2 | 77.9 | 80.0 | 21/28 | 54.5 | 0.70 | 7/10 | 7/20 | 62.5 | 70.0 / 77.7 | 9/20 | 61.5 | 0.208 | 42 | 0/0 |
| gliner_decide_bare | -13 | 77.9 | 72.1 | 18/28 | 47.7 | 0.03 | 2/10 | 3/20 | 57.5 | 66.9 / 70.0 | 6/20 | 63.5 | 0.214 | 29 | 0/0 |
| gliner_decide_1b_desc | -22 | 71.4 | 77.1 | 17/28 | 52.9 | 0.50 | 4/10 | 5/20 | 55.5 | 68.5 / 76.9 | 8/20 | 55.5 | 0.219 | 68 | 0/0 |
| gliner_multi_decide_desc | -45 | 63.6 | 63.6 | 12/28 | 48.1 | 0.21 | 0/10 | 2/20 | 45.5 | 64.6 / 67.7 | 5/20 | 58.5 | 0.234 | 19 | 0/0 |
| julia_1 | -89 | 35.0 | 41.4 | 9/28 | 44.5 | 0.16 | 0/10 | 4/20 | 46.0 | 45.0 / 37.3 | 7/20 | 41.0 | 0.508 | 599 | 0/219 |
| laya_router | -22 | 62.1 | 73.6 | 15/28 | 46.8 | 0.14 | 5/10 | 6/20 | 63.0 | 55.0 / 71.5 | 7/20 | 60.0 | 0.209 | 29 | 2/219 |
| laya_typed | -26 | 67.1 | 75.0 | 14/28 | 45.5 | 0.03 | 4/10 | 4/20 | 51.0 | 67.7 / 75.8 | 8/20 | 62.5 | 0.184 | 31 | 2/219 |
| legacy_laya_v2 | -38* | 62.1 | 75.0 | 15/28 | 46.8 | 0.15 | 5/10 | 6/20 | 63.5 | — / — | — | — | 0.185 | 6548 | 0/0 |
| span01_pro | 19 | 85.0 | 84.3 | 22/28 | 73.5 | 0.73 | 7/10 | 13/20 | 65.5 | 80.4 / 84.6 | 13/20 | 74.5 | 0.154 | 597 | 0/0 |
| span01_lite | 5 | 82.9 | 82.1 | 20/28 | 72.6 | 0.58 | 10/10 | 9/20 | 61.0 | 75.8 / 76.5 | 8/20 | 70.0 | 0.145 | 895 | 0/0 |
| span01_lite_or | 19 | 85.0 | 84.3 | 22/28 | 76.1 | 0.76 | 8/10 | 13/20 | 65.5 | 80.4 / 84.6 | 13/20 | 74.5 | 0.152 | 587 | 0/0 |
| nimble_9b | 47 | 92.9 | 88.6 | 24/28 | 74.8 | 0.57 | 3/10 | 13/20 | 77.5 | 93.1 / 90.8 | 15/20 | 86.0 | 0.080 | 1620 | 0/0 |
| tev1_4b | 27 | 87.1 | 87.1 | 26/28 | 71.0 | 0.85 | 7/10 | 13/20 | 69.5 | 89.2 / 91.5 | 12/20 | 77.5 | 0.109 | 452 | 0/0 |
| tev1_0.8b | -9 | 67.9 | 72.1 | 23/28 | 70.0 | 0.80 | 7/10 | 8/20 | 58.5 | 78.8 / 81.2 | 11/20 | 64.5 | 0.169 | 142 | 0/0 |
| decider_4b_clefrev_review | 60 | 90.7 | 90.7 | 24/28 | 87.7 | 0.85 | 8/10 | 11/20 | 82.5 | 93.1 / 93.1 | 15/20 | 90.0 | 0.066 | — | 0/219 |
| decider_4b_clefrev_audit | 59 | 90.0 | 89.3 | 25/28 | 85.5 | 0.88 | 7/10 | 11/20 | 83.0 | 92.7 / 92.7 | 15/20 | 89.0 | 0.074 | — | 0/219 |
| clef_27b | 56 | 89.3 | 90.7 | 23/28 | 83.2 | 0.86 | 5/10 | 10/20 | 82.0 | 93.5 / 93.8 | 16/20 | 91.0 | 0.052 | 870 | 0/219 |
| clef_flash_9b_xpu | 45 | 87.9 | 86.4 | 24/28 | 81.6 | 0.90 | 6/10 | 10/20 | 76.5 | 90.8 / 92.7 | 14/20 | 84.0 | 0.076 | 142 | 0/219 |
| decider_4b_clefflashrev_review | 51 | 91.4 | 89.3 | 26/28 | 80.6 | 0.89 | 6/10 | 11/20 | 80.0 | 92.3 / 92.3 | 14/20 | 83.0 | 0.071 | — | 0/219 |
| decider_4b_clefflashrev_audit | 48 | 89.3 | 88.6 | 26/28 | 79.0 | 0.88 | 6/10 | 11/20 | 80.0 | 91.9 / 92.7 | 14/20 | 83.0 | 0.076 | — | 0/219 |
| clm_v0.1_8b | -41 | 67.9 | 58.6 | 13/28 | 51.6 | 0.53 | 4/10 | 4/20 | 50.5 | 67.3 / 66.5 | 9/20 | 58.5 | 0.244 | 80 | 0/219 |
| strands_2b_hobson_v19_xpu | 18* | 83.6 | 83.6 | 20/28 | 66.3 | 0.79 | 7/10 | 8/20 | 70.0 | 78.5 / 82.3 | 13/20 | 74.0 | 0.134 | 126 | 0/216 |
| strands_2b_hobson_v19_xpu_trunc | 19 | 83.6 | 83.6 | 20/28 | 66.5 | 0.77 | 7/10 | 8/20 | 70.0 | 78.5 / 82.3 | 13/20 | 74.0 | 0.134 | 125 | 0/219 |
| dgemma_26b_a4b_nvfp4 | 52 | 91.4 | 94.3 | 25/28 | 80.3 | 0.82 | 6/10 | 15/20 | 78.0 | 91.5 / 91.9 | 16/20 | 87.0 | 0.096 | 318 | 0/219 |
| dgemma_26b_a4b_nvfp4_s1 | 52 | 89.3 | 92.9 | 25/28 | 80.3 | 0.83 | 6/10 | 15/20 | 79.0 | 91.5 / 90.8 | 16/20 | 86.0 | 0.103 | 123 | 0/219 |
| dgemma_26b_a4b_nvfp4_s1_jevrev_review | 66 | 91.4 | 96.4 | 25/28 | 83.2 | 0.83 | 7/10 | 18/20 | 88.0 | 93.8 / 92.7 | 18/20 | 91.0 | 0.049 | — | 0/219 |
| dgemma_26b_a4b_nvfp4_s1_jevrev_audit | 65 | 91.4 | 96.4 | 25/28 | 84.2 | 0.71 | 7/10 | 17/20 | 87.5 | 92.7 / 91.5 | 19/20 | 92.0 | 0.061 | — | 0/219 |
| llm_qwen38_27b_fp8_jev68_off_d0_prob | 50 | 88.6 | 87.1 | 24/28 | 79.4 | 0.86 | 4/10 | 13/20 | 81.0 | 94.6 / 93.5 | 15/20 | 87.0 | 0.068 | 6253 | 1/216 |
| llm_qwen38_27b_fp8_jev68_on_d0_prob | 63 | 91.4 | 90.7 | 25/28 | 87.1 | 0.88 | 6/10 | 16/20 | 85.0 | 94.2 / 95.0 | 16/20 | 90.0 | 0.045 | 41287 | 0/216 |
| llm_qwen38_27b_fp8_jev71_off_d0_disc | 67 | 90.7 | 92.1 | 26/28 | 85.5 | 0.82 | 9/10 | 18/20 | 87.5 | 95.0 / 95.0 | 15/20 | 90.0 | 0.063 | 2634 | 0/216 |
| llm_qwen38_27b_fp8_jev76_on_d0_disc | 63 | 91.4 | 92.9 | 26/28 | 88.7 | 0.78 | 7/10 | 17/20 | 86.0 | 95.0 / 95.4 | 14/20 | 86.5 | 0.052 | 26660 | 0/216 |
| llm_qwen38_27b_fp8_jev76_on_d1_disc | 59 | 90.0 | 92.1 | 25/28 | 88.7 | 0.78 | 7/10 | 17/20 | 84.5 | 93.5 / 95.8 | 14/20 | 85.0 | 0.058 | 26633 | 0/216 |
| llm_medgemma_27b_it_bf16_jev77_d0_disc | 24 | 87.9 | 84.3 | 21/28 | 81.0 | 0.89 | 8/10 | 7/20 | 63.0 | 92.7 / 92.3 | 11/20 | 80.0 | 0.135 | 9384 | 0/216 |
| llm_gemma3_27b_it_bf16_jev77_d0_disc | 14 | 82.9 | 85.7 | 22/28 | 73.9 | 0.86 | 8/10 | 3/20 | 55.0 | 95.0 / 95.0 | 11/20 | 78.0 | 0.147 | 9417 | 0/216 |
| medgemma_27b_jev77_jevrev_audit | 67 | 95.0 | 95.7 | 26/28 | 84.8 | 0.69 | 7/10 | 18/20 | 86.5 | 94.2 / 93.1 | 18/20 | 95.0 | 0.056 | — | 0/216 |
| oai_luna_decisions | 40 | 91.4 | 89.3 | 26/28 | 76.8 | 0.81 | 7/10 | 17/20 | 74.0 | 89.6 / 89.6 | 18/20 | 88.0 | 0.094 | 441 | 0/214 |
| llm_haiku55_off_prob | 66 | 93.6 | 95.0 | 26/28 | 80.3 | 0.85 | 5/10 | 18/20 | 90.0 | 91.5 / 91.2 | 16/20 | 90.0 | 0.057 | 1656 | 0/216 |
| llm_haiku55_off_disc | 67 | 93.6 | 92.9 | 27/28 | 79.4 | 0.82 | 6/10 | 19/20 | 88.0 | 93.5 / 93.5 | 19/20 | 93.0 | 0.081 | 1285 | 0/216 |
| llm_haiku55_adapt_prob | 73 | 93.6 | 94.3 | 26/28 | 81.3 | 0.80 | 7/10 | 19/20 | 92.5 | 91.9 / 92.7 | 18/20 | 93.5 | 0.054 | 2639 | 0/216 |
| decider_4b_haiku55rev_audit | 69 | 87.9 | 91.4 | 26/28 | 81.3 | 0.80 | 5/10 | 20/20 | 91.0 | 91.9 / 95.0 | 19/20 | 95.0 | 0.075 | — | 0/216 |
| jev_haiku55rev_audit | 78 | 92.9 | 94.3 | 26/28 | 84.5 | 0.87 | 5/10 | 20/20 | 94.0 | 94.6 / 93.5 | 20/20 | 96.5 | 0.054 | — | 0/216 |
| llm_haiku55_adapt_prob_r2 | 72 | 94.3 | 95.0 | 26/28 | 80.0 | 0.82 | 5/10 | 19/20 | 91.5 | 91.2 / 90.8 | 17/20 | 92.5 | 0.053 | 2533 | 0/216 |
| llm_ministral3b_med_prob | -10* | 76.4 | 83.3 | 12/28 | 73.6 | 0.58 | 7/8 | 7/19 | 64.1 | 76.2 / 80.8 | 11/20 | 71.5 | 0.128 | 4780 | 1/181 |
| llm_ministral3b_med_disc | 45* | 76.2 | 80.0 | 16/28 | 79.7 | 0.83 | 9/10 | 6/18 | 64.4 | 83.8 / 84.6 | 9/19 | 70.0 | 0.150 | 1913 | 0/206 |
| jev_ms_decision1 | 47 | 91.4 | 86.4 | 28/28 | 79.7 | 0.90 | 6/10 | 17/20 | 80.5 | 92.3 / 88.1 | 16/20 | 88.5 | 0.079 | 693 | 0/216 |
| drex_v15_9b | 44 | 85.0 | 81.4 | 24/28 | 75.8 | 0.86 | 5/10 | 14/20 | 79.5 | 91.5 / 90.4 | 15/20 | 86.5 | 0.083 | 360 | 0/216 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.9 | — | 0/10 | 17/20 | 80.0 | 57.7 / 57.7 | 5/20 | 55.5 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
<!-- /AUTO:marcador -->

**Nota 48\* (`jev_luna_decisions`):** 188/194, seis negativas del proveedor, media sobre 6 fases (Jev: 10); no comparable con el agregado completo. Detalle en «Por modelo» más abajo.

Columnas: triaje = % sobre 5 preguntas × 14 casos. dept = departamento correcto.
papers = % sobre 5 dimensiones × 31 papers. ρ = Spearman de relevancia. skip LOO = de los 10
papers que no merecen lectura, cuántos descarta la cascada (umbral por leave-one-out).
adv dept = routing correcto en adversarial-1+2. triaje ext = T15–T40 (26 casos nuevos, validados
el 26-sep). adv3 = adversarial-3 equilibrado (20 casos: 10 manipulados y 10 honestos, 5 por
departamento). Brier = media de las preguntas sí/no
(más bajo es mejor). ms = mediana por caso (Jev por API; CLM y Strands en Intel Arc
Pro B70; otros modelos según su ficha, principalmente GPU GB10).

Configuración de cada run: Jev = `jev-1.13-20260917` vía OpenRouter (`jev_typesafe_v1`: API
directa, `jev-1.13.0`). Cascadas = 2ª pasada revisor-auditor (`jevbench/cascade.py`). Decider =
`Mapika/decider-*` bf16 en GB10 (el 35B sin CUDA graphs; NVFP4 servido con vLLM). AnyJev = L0 bf16.
GLiNER multi decide `desc` obtiene ajustado −45 (11 fases, mayoría 0; la cifra −75, y −74 con GT v3, era de cobertura incompleta y no es comparable).
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
- **Alternativa más barata, con agregado próximo (sin diferencia demostrada; no prueba equivalencia):** Decider-4B local → revisor Jev.
- **Revisor de mayor ajustado en regla `audit` sobre Decider-4B (4-oct; matiz 8-oct):**
  Decider-4B → revisor **gpt-6.1-sol (low)** (`decider_4b_solrev_audit` 66 [65,82], por
  encima del 64 del revisor Jev y del 65,64 del revisor Haiku 5.5; en regla `review` el
  máximo sobre ese D1 es Haiku: 70,39 (70 redondeado) frente a 67,53 de sol; la única
  celda con p cruda <0.05 es `relevance` de papers, p = 0.04, no significativa tras Holm
  de las 53 celdas). La pasada-2 cuesta ~$0.005/caso, ~100× la de Jev — solo si el revisor
  puede ser API de pago y se quiere el máximo audit (el revisor Haiku, que le supera en
  review, no cumple el criterio ampliado por su alerta de adv4; JEV-84).
- **Alternativa 100 % local (nuevo, 3-oct):** Decider-4B → revisor **Clef-27B**
  (`decider_4b_clefrev_audit`, ajustado 58) cumple el criterio JEV-32 que ningún local
  cumplía (~89 % de la ganancia de Jev en adv3+adv5, ~61 % en triaje, alerta 9/10 · 1 FP
  en adv5). Queda por debajo del circuito con Jev (64) pero sin API ni salida de datos.
  El plan y los anteriores intentos están en `plan_revisor_local.md` y
  `experimentos/cascada_jev.md`.

**Por modelo (GT v4):**

Las cifras de ejecución de 195 casos, costes y recuentos sobre 969 decisiones o 259 etiquetas son históricos (GT v3). La puntuación vigente usa 194 casos; se conservan las ejecuciones originales sin repetir inferencias.

- **CLM-v0.1-8B (Contrastive-LM, 3-oct, negativo):** run `clm_v0.1_8b`, 195 casos
  sin errores, Intel Arc Pro B70 de 32 GB. Ajustado **−35** (mayoría 0), Brier 0.238,
  mediana 80 ms. Ejecución viable y rápida, pero varias derrotas con p cruda <0.05 frente
  a Jev en fases válidas (tras Holm de las 53 celdas solo sigue `department`
  de triaje_ext_es, p=0.03); no es candidato a recomendación. Ficha: `docs/modelos.md` §CLM.
  **JEV-103 (14-oct, GT v5):** alerta de una pasada 9/30 TP · 10/30 FP (bajo la línea base
  trivial); rotación d1 estable (99,4 %, primacía refutada, Δ 0; d1 y r2 idénticas en esta
  batería); réplica r2 99,4 % (6/964 entre sesiones, causa no identificada).
- **Strands Decider 2B Hobson v19 (3-oct):** decisor dedicado abierto (Apache-2.0),
  LoRA + cabeza pointer sobre Qwen3.5-2B, servido en Intel Arc Pro B70 con XPU
  (backend experimental upstream). Ajustado **21\*** — `*` porque un caso de papers
  excede la ventana 4096 y `--strict-window` lo rechaza (papers32 queda 30/31 y no
  cuenta en la media); la variante `_trunc` (truncado por defecto del servidor)
  cubre los 195 casos con el mismo ajustado 21. Por debajo de Decider-4B (33) y
  muy por debajo de Jev (45), aunque por encima de la mayoría en casi todas las
  fases. Falla donde el trivial es fuerte: dept de adv1+2 9/20 frente a 17/20 de
  responder siempre `admin`. Derrotas con p cruda <0.01 en `same_day` ext_es frente
  a Jev y `relevance` de papers frente a Decider-4B — ninguna significativa
  tras Holm (53 celdas); ninguna victoria significativa. Rápido: ~0,13 s/caso cliente (con túnel SSH). Runs
  `strands_2b_hobson_v19_xpu[_trunc]`. Ficha: `docs/modelos.md` §Strands.
  **JEV-103 (14-oct, GT v5):** alerta de una pasada 4/30 TP · 2/30 FP (no cumple); rotación
  d1 estable (98,9 %, primacía refutada); réplica r2 99,9 % (1/959 de sesión); el rechazo
  por ventana de papers32/P11 se repite en base, d1 y r2.
- **Jev** es el incumbente. Con revisor: triaje 91–94, papers 74–75, adv 18/20, adv3 18/20.
  OpenRouter y la API de TypeSafe son equivalentes (406/409 respuestas iguales).
- **Decider-4B** acierta los mismos departamentos que Jev en triaje (diferencias no
  significativas, p ≥ 0.12), pero en adv3 queda por detrás (12 frente a 17/20, p = 0.06).
- **Decider-35B-A3B**: en triaje el punto estimado no supera al 4B (84.3/79.3 frente a 85.7/85.7; sin McNemar nuevo). ρ de papers 0.92 (bf16) y 0.90 (NVFP4). Ajustado de 11 fases, mayoría 0: bf16 39, NVFP4 33. El «rinde igual» era el contraste pareado del 27-sep sobre batería parcial; no se ha repetido. NVFP4 sigue en 190 ms/caso (678 ms el bf16).
- **AnyJev**: 32B, departamento de adv3 15/20 (no es el máximo abierto: Clef-27B está en 16/20); lento (~2.5 s) y mal calibrado. Papers del 8B: 75.5. Ajustado de 11 fases, mayoría 0: 32B 21, 8B 13, 1.7B −3.
- **LLM generalista (gpt-6-luna, 29-sep)** vía `system-one-adapter` de TypeSafe (su prompt y
  su esquema, API directa de OpenAI): en una sola pasada queda **al nivel de la cascada de
  Jev** (triaje 93.6/95.7, papers 79.4, adv 18/20, adv3 17/20, adv5 83.5, Brier noul 0.053).
  Frente a `jev_v3`, la única celda con p cruda <0.05 es `depth` en papers (13 frente a 1,
  p < 0.01, a favor del LLM; Holm 0.097 — no significativa tras Holm de las 53
  celdas). Frente a `jev_cascade_audit`, solo `urgency` en adv4 (1 frente a
  10, p = 0.01, a favor de la cascada; Holm 0.62). El resto, sin diferencia en crudo. Cuesta ~5.5× más por caso ($0.00019 frente a $0.000035)
  y es ~5× más lento (mediana 3.1 s frente a 0.64 s). El modo `discrete` rinde parecido pero
  calibra peor (Brier 0.077) y ordena peor los papers (ρ 0.76).
- **gpt-6-luna-decisions (7-oct, JEV-80):** `gpt-6-luna` por el endpoint de decisiones de OpenRouter
  (`/api/alpha/decisions`, adaptador `jev`; resuelve `openai/gpt-6-luna-decisions-20261006`). No se ha acreditado
  igualdad de versión subyacente con las rutas `probabilities`/`discrete` del adaptador `llm`. Ajustado **48\*** en
  el marcador — el `*` marca cobertura incompleta: el scorer excluye de la media las fases con errores (aquí
  adv2/adv3/adv4/adv5), así que luna-decisions media 6 fases y Jev 10; **48\* y 45 no son comparables**. Cobertura
  **188/194**: seis rechazos del proveedor (HTTP 502 «OpenAI refused to answer question "department"»,
  reproducidos en ~6 peticiones HTTP por caso) en B05_trial_data_exfil (adv2), C08_transport_data_exfil (adv3),
  D05_registry_export y D07_vecina_resultado (adv4), E01_phishing_patologia y E02_falso_recall_equipos (adv5).
  Comparación homogénea (misma matemática; 6 fases comunes completas: triaje ES/EN, papers, adv1, ext ES/EN):

  | Configuración | Ajustado 6 fases comunes | Sensibilidad: rechazo = 0 puntos (10 fases) |
  |---|---:|---:|
  | `jev_luna_decisions` (188/194) | **47,70** | **33,03** |
  | `jev_v3` (194/194) | 54,63 | 45,38 |
  | `llm_gpt6luna_prob` (194/194) | 75,60 | 61,23 |
  | `llm_gpt6luna_disc` (194/194) | 71,72 | 59,44 |
  | *Mayoría (oráculo)* | 0 | 0 |

  La sensibilidad es una política explícita de utilidad del servicio: cada rechazo recibe 0 puntos en todas las
  preguntas (no es una predicción recuperada). **No demuestra superar a Jev** (observaciones, sin superioridad
  demostrada en ninguna dirección). McNemar con Holm (53 pruebas por referencia): la única p nominal <0.05 —
  `depth` de papers frente a Jev (b=1, c=8, p=0.039) — queda con **p ajustada = 1**; frente a luna-prob nada
  significativo (mín. 0.125). Coste medido $0.0194 los 188 éxitos ($0.000103/respuesta: **53 %** de luna-prob,
  81 % de luna-disc, **2.97× Jev**; los rechazos no tienen coste observado) y mediana 672 ms (~4.7× más rápido
  que luna-prob). Calibración adversarial peor que Jev (Brier noul adv1/2/5: 0.20/0.17/0.18 frente a
  0.09/0.08/0.13; ECE 0.23/0.26/0.19) con solo 4 noul en la frontera 0.45–0.55 (Jev 29).
  **JEV-81 (7-oct, pre-registro congelado 237259d, rev. R51):** el *fallback* por rechazo a Jev
  (`jev_luna_decisions_fb`, 6 sustituciones) completa la cobertura (194/194, 11 fases completas) con ajustado
  **39,1 [IC95 28,2–49,1]** frente a 45,4 [36,0–54,6] de Jev — la diferencia numérica no acredita superioridad de
  ninguno, y no hay nada significativo tras Holm (53 pruebas por referencia). Como **alerta de manipulación**
  (adv3–5, n=60), el rechazo detecta 5/30 con 0/30 FP observados (precisión 100 % [47,8–100], recall
  16,7 % [5,6–34,7]; muestra pequeña) — descriptivamente por debajo del revisor Jev (25/30 TP · 1/30 FP). Las
  **dos réplicas** (r1/r2, misma versión servida `…-20261006`) coinciden íntegramente: 934/934 decisiones,
  Δp = 0 sobre 2091 componentes y los mismos 6 rechazos — repetibilidad observada bajo esas condiciones, no
  determinismo general probado. Coste registrado: fusionado $0,0195 de costes conocidos (6 del primario sin
  importe); réplica r2 $0,0194 en éxitos. Pendientes: rotación d1 justificable como prueba de sensibilidad al
  orden (pendiente de aprobación y reglas); cascada real y uso como revisor de Jev no justificados por estos
  datos. Pre-registro y resultados: `docs/infra_runs/luna_decisions_jev81.md` §RESULTADOS.
  Ficha: `docs/modelos.md` §LLM generalista. **JEV-82 (7-oct, pre-registro 28727d3, rev. R57):** la rotación d1
  del orden de `department` (`jev_luna_decisions_d1`, 186/194; no entra en el marcador) deja los puntos
  coincidentes y Δ ajustado **0,00 [0,00; 0,00]** en las 5 fases completas comunes — lo que no demuestra
  estabilidad ni equivalencia general —; acuerdo **918/924 = 99,35 %** [98,59–99,76], seis cambios de
  `department`, Δp máx 0,72. La **primacía ≥5 pp queda refutada** por U95 < 5 en 32 registros pareados
  (Δ errores d0−d1 = −12,50 pp [−25,81; −2,94]; 7 frente a 11; p Holm 0,125): no demuestra ausencia de efecto
  de orden ni deterioro general. Dos rechazos nuevos (adv3/C05_polite_threat y
  triage_ext_es/T40_amenaza_personal) sin atribución causal al orden. Coste d1 $0,0192, cota inferior. No
  comparar 47,70 (d0, 6 fases) con 42,15 (d1, 5 fases). Resultados:
  `docs/infra_runs/luna_decisions_jev82.md` §RESULTADOS. **JEV-78 (8-oct, pre-registro de9af7f, rev. R63):** la
  misma batería por la **Decisions API nativa de OpenAI** (`oai_luna_decisions`, SDK oficial) completa **194/194**
  conservando los 6 casos que OpenRouter rechazó enteros como 8 negativas parciales por pregunta — diferencia de
  cobertura bajo contratos distintos, sin identificar la capa causal; versión inconclusa (alias sin snapshot),
  acuerdo 934/934, Δp 0, Δ ajustado 0,00 en 6 fases comunes — sin equivalencia demostrada — y Holm 53 vs Jev =
  0 significativas; ajustado propio 38,25 [27–48] (refusals a 0). Resultados:
  `docs/infra_runs/openai_decisions_jev78.md` §RESULTADOS.
- **claude-haiku-5-5 (8-oct, JEV-83):** Anthropic vía `system-one-adapter` (ID canónico de snapshot fijo).
  Tres celdas, 194/194 registros retenidos, 0 errores: **H-off (thinking off) 62 [54–69]** — frente a Jev, Holm
  53 = **0 significativas**, sin superioridad en ninguna dirección —, **H-disc 64 [57–71]** y **H-adapt
  (thinking adaptive) 69 [62–76]** (thinking en 126/194 casos; descriptivo, sin causalidad aislada). En las 10
  fases comunes: 61,7/64,1/69,3 vs luna-prob 61,2 y Jev 45,4 (el marcador redondea 61,74/64,13/69,29 a
  62/64/69). **Desviación declarada:** la primera respuesta de
  E11 (adv5) se perdió por un corte y se repitió (≥195 respuestas); el coste de H-adapt ($0,0704) es **cota
  inferior**. Costes: $0.0502/$0.0314/$0.0704. Pre-registro y resultados:
  `docs/infra_runs/claude_haiku55_jev83.md` §RESULTADOS. Ficha: `docs/modelos.md` §LLM generalista.
- **claude-haiku-5-5 como revisor y alerta (8-oct, JEV-84):** con la misma config H-adapt
  (thinking adaptive), Haiku **no cumple** el criterio ampliado de revisor en ningún D1 — la
  alerta de adv4 se queda en 5/10 TP en ambos: Decider-4B→Haiku `audit` **66** (cumple los
  umbrales del criterio original JEV-32 evaluados con GT v4) y Jev→Haiku `audit` **74**, el
  mayor ajustado **entre configuraciones audit completas** (anterior máximo audit 71; la
  fusión `review` de la misma adquisición llega a 76 como secundario descriptivo del mismo
  raw) —, con Holm 212 = 0 significativas (sin superioridad ni equivalencia). Su **alerta de
  una pasada tampoco cumple** (16/30 TP, 0/30 FP) y pierde frente a Clef-27B (56/60) y al
  revisor Jev (54/60) tras Holm de 2 (p 0,013 / 0,021). La réplica H-adapt r2 es **estable**
  (919/964 = 95,33 % acuerdos, Δ ajustado −1,80 [−4,97; +1,49], ajustado 67). Coste nuevo
  del encargo $0,334; tarjeta web solo de reproducibilidad descriptiva, sin roles
  confirmados. Detalle: `docs/experimentos/cascada_jev.md`,
  `docs/experimentos/alerta_manipulacion.md` y `docs/infra_runs/claude_haiku55_jev84.md`
  §RESULTADOS.
- **gpt-6.1-sol (1-oct, `reasoning_effort=low`):** modelo de OpenAI ~20× más caro por token que
  luna, medido con el mismo protocolo. **Ajustado 65** (Cerebras probabilities sin esquema llega a 66 con GT v4, sin superioridad demostrada), por encima de
  luna (61) y a la par de la cascada `jev_cascade_audit` (64), aunque por debajo de la mejor
  config absoluta (`llm_gpt6luna_jevrev_audit`, 71). Frente a luna solo destaca en crudo
  `urgency` de adv4 (6–0 a favor de sol, p = 0.03; Holm 1.0); frente a `jev_v3`, `depth` de papers (13–1 a favor de sol, p cruda < 0.01;
  Holm 0.097 — ninguna significativa tras Holm de las 53 celdas);
  frente a `jev_cascade_audit`, nada ni en crudo (la cascada gana adv3 92.0/89.5 sin
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
  única celda con p cruda <0.05 es `relevance` de papers (2–10 a favor de sol,
  p = 0.04; no significativa tras Holm de las 53 celdas); frente al revisor
  luna (52) ninguna celda tiene p cruda <0.05.
  Coste de la pasada-2: **$1.05 (~$0.0054/caso, ~100× el revisor Jev)**. Como **D1 con
  revisor Jev** (`llm_gpt61sol_jevrev_*`): audit/review **66**, por debajo de
  `llm_gpt6luna_jevrev_audit` (71). Como **alerta de una pasada**
  (`llm_gpt61sol_low_alert_raw`): 22/30 TP y 0/30 FP — **no cumple** el criterio (adv4 5/10),
  entre Span-01 (8/30) y Clef-27B (27/30). Detalle: `docs/experimentos/cascada_jev.md` y
  `docs/experimentos/alerta_manipulacion.md`.
- **Cascadas con LLM (29-sep):** `llm_gpt6luna_jevrev_audit` (LLM → revisor Jev) es la
  mejor configuración medida **con revisor Jev** (adv total 92.0, adv5 88.5, Brier 0.045,
  alerta 9/10 con 1 FP), sin diferencia significativa con `jev_cascade_audit` — lo que no
  demuestra equivalencia — a ~3× el coste y la latencia.
  `decider_4b_llmrev_audit` (revisor LLM) recupera el 77 % de la ganancia de Jev en adv3+adv5
  — el primer revisor no-Jev que supera el 50 % ahí — pero falla el criterio JEV-32 por triaje
  (28 %) y por la alerta (6/10). Detalle: `docs/experimentos/cascada_jev.md`.
- **LLM local Qwen3.8-27B (29-sep, negativo):** servido con SGLang en el Spark .80 a través
  del mismo adaptador. Checkpoint `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`:
  NVFP4 (4 bits), con LM head en BF16; no es una evaluación del backbone completo en BF16.
  La comparación con Clef-27B (BF16) no aísla el efecto del entrenamiento y la cabeza
  de decisión del posible efecto de cuantización. Apenas supera la línea base trivial (triaje 73.6, papers 52.3,
  ρ no definida (relevancia constante con GT v4), adv total 58.5 frente a 79.0 del baseline `admin`, Brier 0.231) y es el más
  lento del marcador (~6.8 s/caso). **Nota (revisión 4-oct):** esta batería se midió
  con `structured=true` contra SGLang —el modelo no recibía las preguntas (solo el
  esquema-gramática), véase la causa raíz en el punto JEV-63— así que no es una
  valoración válida del modelo; las medidas válidas locales son las sin esquema
  (NVFP4 52, FP8 49, GGUF 48).
- **LLM local Qwen3.8-Flash-Next (30-sep, negativo):** thinking activado en vLLM (.81), porque
  sin él fallaba el smoke. Queda por debajo de la mayoría (ajustado −39) y del 27B: triaje
  65.7/55.0, papers 38.1 (ρ 0.03), adv3 65.3 y Brier 0.317; Jev y gpt-6-luna lo superan
  en múltiples preguntas —varias celdas siguen significativas tras Holm
  (53 celdas)—, sin ninguna ventaja del Flash tras Holm.
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
  Qwen3.8-27B local NVFP4 (−15 con GT v4) — comparación descriptiva, no ablación de
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
  de adv5 en crudo (6–0, p = 0.03; no significativa tras Holm de las 53
  celdas — Holm 1.0)** y roza el corte en `urgency`
  (5–0, p = 0.06); sin derrotas significativas frente a Jev ni luna. Triaje ext
  96.5/95.8 (los mejores del marcador), papers 77.7 (ρ 0.79), adv3 87.0, Brier
  0.060. Mediana 0.77 s/caso real, $0.44 medidos. El mismo tamaño en NVFP4 local
  da −15 con GT v4: el salto es descriptivo (precisión, backend, muestreo y razonamiento
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
  `depth` p<0.01 y `practice` p≈0.016, p crudas — Holm sobre las 53 celdas:
  0.12 y 0.81.
  No superioridad global; Brier peor que Jev (0.071) y ~10× su latencia.
  Bajo Cerebras (59) y Clef-27B (52) en ajustado descriptivo. NVFP4 sin
  esquema ya tiene batería completa (52), distinta de este run FP8. Run
  `llm_qwen38_27b_fp8_nostruct_prob`; manifiesto en `docs/infra_runs/`.
- **Qwen3.8-27B, cuadrícula completa (4-oct, JEV-58/61; revisión):**
  - Local sin esquema: NVFP4 **52** (Brier 0.076, 5.3 s/caso), FP8 **49**
    (0.080, 6.4 s), GGUF **48** (0.084, 10.8 s). Mismos casos/GT/scorer.
    El histórico NVFP4 también difiere en límites: no una ablación de una
    sola variable. El contraste de salida es fuerte, no una causa interna aislada.
  - Cerebras probabilities con/sin esquema: **59/66**, discrete **58/58**.
    Cero errores finales, un reintento por malformado en cada run sin esquema.
    Mínimo McNemar probabilities=0.0625: no significativo al 5 %, pero no
    equivalencia ni independencia del esquema. Brier prob 0.056–0.060 vs
    discrete 0.072–0.077; 66 queda sobre el 65 de sol de forma descriptiva, sin superioridad demostrada.
  - Jev→Cerebras audit: **68/69**; review sin esquema **69** (antes 68 con GT v3), frente a Jev→Jev 64; sin significación
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
  (ajustado 17 frente a 45 de Jev); sí gana en `depth` de papers en crudo (16/31 vs 6/31, p = 0.01; no
  significativa tras Holm de las 53 celdas).
  Como **detector de manipulación de una pasada** (misma pregunta y umbral del revisor)
  queda descartado: 8/30 pro y 5/30 lite, aunque sin falsos positivos.
- **Nimble-9B (Bespoke, 30-sep):** LoRA sobre Qwen3.5-9B que puntúa tokens candidato sin
  generar (una pasada forward por pregunta). El open-weight más fuerte evaluado sin revisor:
  ajustado 44 (a la par de `jev_v3`, 45; por encima de Decider-4B, 33). Triaje 92.9/88.6,
  adv3 85.5, pero ordena mal los papers (ρ 0.49). Sin diferencias significativas frente a
  Jev, Decider-4B ni gpt-6-luna salvo `urgency` de adv4, donde gana a gpt-6-luna (p cruda <0.01; no
  significativa tras Holm de las 53 celdas).
  Mediana 1.6 s/estado en GB10. Run `nimble_9b`.
  **JEV-103 (14-oct, GT v5):** es el único modelo **sensible al orden** en la rotación d1
  (acuerdo 94,5 % [92,9–95,9], primacía inconclusa, 53/964 componentes cambian); réplica
  r2 idéntica. Alerta de una pasada 12/30 TP · 1/30 FP (no cumple). Como revisor de
  Decider-4B, `decider_4b_nimblerev_audit` = 46: no cumple JEV-32 (26,5 % de la ganancia
  en adv3+adv5; alerta adv5 3/10·1).
- **Tev1-4B (Together, 30-sep):** fine-tune autoregresivo de Qwen3.5-4B (una letra por
  pregunta, una generación por pregunta). Ajustado 27, por debajo de Nimble-9B (44) y
  Decider-4B (33): triaje 87.1/87.1, papers 63.9 (ρ 0.83), adv3 75.0, adv4 77.5,
  adv5 72.5, Brier 0.115. Sin diferencias significativas frente a Jev/Decider/Nimble;
  gpt-6-luna le gana en `depth` de papers en crudo (p<0.01; Holm 0.07 — no
  significativa tras Holm). El más rápido: ~0.45 s/estado.
  Licencia de los pesos pendiente de publicación. Run `tev1_4b`.
  **JEV-103 (14-oct, GT v5):** rotación d1 estable (99,2 %, primacía refutada); réplica
  r2 idéntica; alerta de una pasada 15/30 TP · 3/30 FP (no cumple).
- **Tev1-0.8B (Together, 30-sep, negativo):** mismo adaptador y contrato que el 4B,
  pero el escalado rompe el modelo: ajustado **−7**, por debajo de la mayoría
  trivial (triaje 67.9/72.1, adv total 58.5 frente a 79.0 del baseline `admin`,
  adv3 64.0, Brier 0.171, 12 binarios en la frontera 0.45–0.55 de adv3). El 4B
  le gana en `same_day` de adv4 en crudo (10–1, p=0.01); los incumbentes
  le ganan en crudo en varias preguntas (department adv3/ext_es, clinical
  triaje ES) — ninguna significativa tras Holm (53 celdas).
  ~0.14 s/estado. Licencia de los pesos pendiente, igual que el 4B. Run `tev1_0.8b`.
  **JEV-103 (14-oct, GT v5):** rotación d1 con acuerdo 98,2 % y primacía inconclusa;
  réplica r2 idéntica; alerta de una pasada 16/30 TP · 17/30 FP — no solo no cumple,
  queda por debajo de la línea base trivial (29/60 aciertos).
- **DiffusionGemma-26B-A4B (Google, NVFP4; JEV-70, 6-oct):** modelo de difusión de texto servido con
  vLLM y su interposer de lecturas estructuradas (prototipo de la PR #57250). Puerta de montaje aprobada
  en cada batería.
  - **P** (`samples="auto"`): ajustado **53**, 0 errores, Brier noul 0.095, 318 ms por caso.
  - **S1** (una lectura): 53, Brier 0.101, 122 ms; la regla pre-registrada la recomienda.
  - Frente a `jev_v3`: sin diferencia demostrada tras Holm (`papers32.depth` 13–1, p cruda 0.002,
    Holm 0.097). La calibración noul es peor que la de Jev.
  - Sensible al orden de las opciones `choice` (−7.4 pp de acierto en `choice` al rotarlas, GT v4; −7.3 con GT v3).
  - Ruta del adaptador TypeSafe en `discrete`: 51.
  - Revisor no evaluable (422 del interposer en triaje/adv). Alerta de una pasada: 19/30 TP · 0/30 FP,
    no cumple (adv4 4/10).
  - No cambia la recomendación de revisor (Clef-27B) ni la de cascada. Detalle: `docs/modelos.md` y
    `docs/infra_runs/dgemma_26b_a4b_nvfp4.md`.
- **GLiNER**, **Laya** y **Julia-1**: descartados zero-shot (en o por debajo de la línea base de
  mayoría en adversarial; Julia, incluso en triaje).
- **Clef-27B (Cloudflare, 3-oct):** open-weight (Apache-2.0), Qwen3.8-27B + cabeza de esquema
  conjunta, API SystemOne nativa, una pasada por estado. Ajustado **52**: era el mejor single
  open-weight medido hasta el 3-oct (desde el 6-oct, DiffusionGemma-26B-A4B saca 53 en S1 y 53 en P, a la
  par: la diferencia no está demostrada). Por encima de `jev_v3` (45) y Nimble-9B (44); solo por debajo de
  gpt-6.1-sol (65), gpt-6-luna (61) y varias cascadas. Mejor que Jev en `depth` de papers en crudo (p=0.02; no
  significativa tras Holm de las 53 celdas, p Holm = 1.0); sin derrotas significativas. adv1/adv2 no se usan como
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
  con p cruda <0.05 frente al 27B: `urgency` de adv2 (p=0.03); frente a Jev
  gana en `depth` de papers en crudo (p=0.04) — ninguna significativa tras
  Holm de las 53 celdas. ρ relevancia 0.90, tercera de una pasada. **Como
  revisor no pasa el listón JEV-32** (recupera 38 % en
  adv3+adv5, ~50 % en triaje; `decider_4b_clefflashrev_audit` = 47), pero es el
  segundo mejor revisor local y el más barato. **Su alerta de una pasada sí cumple**
  (7/10 TP · 0 FP por set; 21/30 TP, p=0.18 vs el 27B). Ficha: `docs/modelos.md`
  §Clef-Flash.
- **MedGemma (Google Health, 8-oct, JEV-77):** post-train clínico de Gemma 3, servido por la
  ruta del adaptador `llm` (SGLang BF16 en .80, gramática restringida común, temp 0). En
  `discrete` d0 saca ajustado **25,87** frente a 16,22 del control Gemma3-27B — la mejora
  pre-registrada de ≥ +5 queda **inconclusa** (IC97,5 [−1,7; +21,8]) — y muy por debajo del
  Qwen3.8-27B FP8 fresco (62,90; **no inferioridad refutada**: −37,0 [−49,8; −24,9]). H1/H2 se
  miden bajo la gramática restringida de la Enmienda 1; su efecto no se aísla de la enmienda.
  Enmienda 2: la sonda ciega acepta JSON válido para la gramática con valores fuera del contrato
  del SDK (Gemma3-4B, urgency=1300); el manifiesto no cambia. Desviación NAS en Gemma3-4B:
  copia local de los mismos pesos, sha256 15/15; los resultados se mantienen. El bloque
  4B es descriptivo y dominado por vectores nulos en probabilities. Como D1 con revisor Jev,
  la cascada llega a 65,43 (audit) frente a raw 66,59: la diferencia de punto no demuestra que
  audit supere a raw y no es una solución 100 % local. Sin afirmar superioridad ni utilidad clínica.
  Runs `llm_medgemma_27b_it_bf16_jev77_d0_disc`, `llm_gemma3_27b_it_bf16_jev77_d0_disc`,
  `medgemma_27b_jev77_jevrev_audit`. Ficha: `docs/modelos.md` §MedGemma; detalle:
  `docs/infra_runs/medgemma_jev77.md` §RESULTADOS.
- **OpenMed Ministral-3B-Medical-v1 (8-oct, JEV-85, cobertura incompleta):** «LLM médico
  pequeño» (~4 B bf16, Mistral3) servido con vLLM en .80 vía adaptador `llm`,
  `structured=false` con preguntas visibles. **Descriptivo, no válido como batería
  completa:** el run primario `llm_ministral3b_med_prob` incumplió el criterio de parada
  declarado (> 20 errores: 23 persistentes, casi todos JSON malformado) con **171/194**
  respuestas válidas y ajustado **−7\*** sobre 3/10 fases; el secundario
  `llm_ministral3b_med_disc` quedó en **187/194** (7 errores) y **45\*** sobre 4/10 fases —
  titulares no comparables con la cobertura completa de Jev (45) ni Decider-4B (33). Tras
  Holm (53 contrastes por modo) solo sobrevive la derrota de `prob` en `department` de
  triage_ext_es; la mejora nominal de `disc` en `depth` de papers32 es exploratoria
  (p_Holm 0,34). Coste API no registrado; licencia del checkpoint no documentada.
  Ficha: `docs/modelos.md` §OpenMed Ministral-3B-Medical-v1; detalle:
  `docs/infra_runs/ministral3b_med_jev85.md` §RESULTADOS.
- **Microsoft-Decision-1 (10-oct, JEV-90):** API cerrada vía OpenRouter
  (`microsoft/microsoft-decision-1-20261009`, adaptador `jev`). Run D0
  `jev_ms_decision1`: **194/194**, ajustado **44 [IC95 34–53]** frente a 45 de Jev
  y 0 de la mayoría (**44 no es % de acierto**). Holm53 confirmatorio (sin IDs
  expuestos del humo): **0 significativas** — sin superioridad, inferioridad ni
  equivalencia. Département triaje 28/28; papers 73,9; depth 7/31 (mayoría 17/31);
  Brier noul del resumen 0,090; latencia de cliente 693 ms; coste registrado
  **$0,004120914**/pasada. Réplica R y rotación D1 **solo como análisis** (sin
  filas competitivas): acuerdo 959/964 (99,5 %) y 956/964 (99,2 %); primacía ≥5 pp
  **REFUTADA** (10→10); «0 cambios» **COMPATIBLE/INCONCLUSA** (0/158). Anuncios del
  fabricante (36 benches, 35×, seguridad) **no evaluables** aquí. **No cambia** la
  recomendación vigente. Ficha: `docs/modelos.md` §Microsoft-Decision-1; detalle:
  `docs/infra_runs/ms_decision1_jev90.md` §RESULTADOS.
  **JEV-103 (14-oct, GT v5; mismo snapshot):** alerta de una pasada 26/30 TP · 4/30 FP —
  no cumple (adv4 6/10, 3 FP en adv5), sin diferencia con Clef-27B ni el revisor Jev tras
  Holm. Como revisor de Decider-4B, `decider_4b_msrev_audit` = **64** (77,6 %/77,8 % de
  la ganancia de Jev, sin fase >2 puntos peor): cuarto entre los revisores medidos sobre
  ese D1, pero **no cumple JEV-32** por 2 FP en la alerta adv5 (límite 1).
- **Drex v1.5 (Nace.AI, 13-oct, JEV-101; cifras GT v5):** decisor dedicado
  open-weight (`nace-ai/drex-v1.5` @ `328ee227`, ~9B; licencia Open RAIL-M
  modificada, sin aval del proveedor): backbone híbrido MiMo/Qwen3.5 + cabeza
  pointer (una fila por pregunta, opciones sin aislamiento, temperatura 1.0),
  servido por su `serve.py` en el DGX (adaptador `systemone_http` por túnel
  SSH). Run `drex_v15_9b`: **194/194**, ajustado **44** [IC95 30–56] frente a
  49 de Jev, 47 de Nimble-9B y 0 de la mayoría (**44 no es % de acierto**).
  McNemar: **ninguna celda p<0,05 frente a `jev_v3`** (mínima p=0,06,
  `urgency` de adv4 a favor de Drex); frente a `nimble_9b` solo `relevance`
  de papers32 con p=0,02 sin corregir (b=1, c=9) — no concluyente con
  corrección por comparaciones múltiples. Brier noul 0,083; latencia de
  cliente por túnel ~0,38 s/caso. Contaminación: sin solapamiento encontrado
  en los materiales públicos inspeccionados; corpus de entrenamiento no
  disponible para verificarlo (R111); las cifras de los autores (otros
  bancos/scorers) no se incorporan. No cambia la recomendación. Ficha:
  `docs/modelos.md` §Drex v1.5; manifiesto: `docs/infra_runs/drex_v15_9b.md`.
  **JEV-103 (14-oct, GT v5):** alerta de una pasada 21/30 TP · 1/30 FP — no cumple por
  adv4 (6/10), 1 FP como Nimble-9B; rotación d1 99,4 % con primacía
  inconclusa; réplica r2 idéntica. Como revisor de Decider-4B, `decider_4b_drexrev_audit`
  = 52: no cumple JEV-32 (42,9 %/0,0 % de la ganancia; alerta adv5 3/10·1).

**Experimentos** (`docs/experimentos/`):
- `cascada_jev.md`: revisor-auditor (Jev→Jev, Decider→Decider, Decider→Jev y revisores 100%
  locales — desde el 3-oct **Clef-27B sí recupera el listón del 50 %**; los anteriores no).
  JEV-103 (14-oct): tres revisores más de Decider-4B — Microsoft-Decision-1 (64), Drex v1.5
  (52) y Nimble-9B (46) — **ninguno cumple JEV-32**; Microsoft se queda a un falso positivo
  en la alerta adv5.
- `reglas_duras.md`: reglas regex, descartadas (0/10 en casos nuevos, 3/10 FP).
- `alerta_manipulacion.md`: alerta validada en adv5; extensión con Span-01 como detector de
  una pasada (negativo: 8/30 pro, 5/30 lite, 0 FP) y con **Clef-27B (positivo: 27/30, 1 FP)**.
  JEV-103 (14-oct): siete decisores más en una pasada — Microsoft-Decision-1, Drex, Tev1-4B,
  Nimble-9B, Strands 2B, Tev1-0.8B y CLM — **ninguno cumple** el criterio.

**Notas de método:**
- La columna **ajustado** es el agregado único por run: media por fase de (acierto − mayoría) /
  (100 − mayoría). 0 = línea base trivial, <0 = peor que ella; `*` = cobertura incompleta.
- En adv1 + adv2, responder siempre `admin` saca 17/20: ese set no sirve para comparar modelos.
  Usar adv3–adv5 (equilibrados).
- Con n = 14–31, los IC95 se solapan casi siempre: usar `--vs` (McNemar) antes de afirmar que
  un modelo "gana".
- La 2ª anotación (JEV-27/28) mostró mucho ruido de etiquetado en urgency y same_day; 1–2
  puntos de diferencia ahí no significan nada.

## Seguimiento

- **Revisor local, reabierto el 3-oct:** Decider-35B NVFP4, AnyJev-32B/8B y gpt-6-luna no
  cumplieron el criterio JEV-32; **Clef-27B sí** (`decider_4b_clefrev_audit`, ajustado 58;
  ~89 % de la ganancia de Jev en adv3+adv5, alerta 9/10 con 1 FP). Existe por tanto una
  cascada 100 % local válida: Decider-4B → Clef-27B. **JEV-103 (14-oct):** tres candidatos
  más sobre el mismo D1 — Microsoft-Decision-1 (64), Drex v1.5 (52) y Nimble-9B (46) —
  tampoco cumplen JEV-32; Microsoft falla por un falso positivo de más en adv5. Ver
  `docs/experimentos/cascada_jev.md`.
- **JEV-57/58/61 (revisión 4-oct):** NVFP4 sin esquema completa la batería
  con ajustado 52, frente al −16 histórico con esquema (GT v3; −15 con GT v4); límites/stack no
  perfectamente controlados. Cerebras funciona con y sin esquema (59/66),
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
  **51** (la gramática no cambia decisiones —967/969— pero sí mueve las
  probabilidades: skip LOO en papers 9/10 con gramática frente a 4/10 sin
  ella), discrete+inject
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
- **Seguimiento de JEV-67 (cerrado el 7-oct):**
  - **JEV-68/71/72, sesión Qwen3.8-27B FP8 con GT v4.** Pre-registrada, 1 517/1 517 casos auditados, 0 errores;
    manifiesto `docs/infra_runs/qwen38_jev68.md`.
    - **Thinking:** sube el ajustado (49.6→61.3 en d0, 58.4→64.9 en d1), pero el umbral pre-registrado de ≥ +5 en
      ambos órdenes queda **inconcluso**. No basta para atribuirle el hueco con Cerebras.
    - **Orden de `department`:** mueve el ajustado ~10 puntos (estabilidad inconclusa). La **primacía de la
      opción-trampa queda confirmada**: +35 pp de errores con `bronchoscopia` primera frente a última, Holm
      p = 0.009.
    - **Discrete en FP8:** +12.9, inconcluso para ≥ +10.
    - **Frases anti-inyección visibles:** refutado que mejoren ≥ 10 pp.
    - **Pendiente opcional:** una réplica en otro backend o host.
  - **JEV-69:** issue upstream abierta (system-one-adapter#50).
  - **JEV-70:** DiffusionGemma medido el 6-oct (ver arriba).
  - **JEV-73:** resuelta el 6-oct (GT v4).
  - **JEV-76 (7-oct), factorial fresco `discrete` × thinking (8 celdas, d0+d1, GT v4):** sesión
    `s81f-20261007-0800` en .81, 1 552/1 552 casos, 0 errores, 10,89 h de reloj del supervisor
    (tope 14 h) y 1 600 peticiones (tope 5 000); manifiesto `e4a198a26cefaba9`, revisión Codex R53
    APTO. Controles frescos F/T/D replicados en esta sesión; los históricos JEV-68/71 solo son
    descriptivos.

    | Celda | Config | Ajustado |
    |---|---|---:|
    | *Mayoría trivial* | — | 0,00 |
    | F0′ | prob off d0 | 50,08 |
    | T0′ | prob on d0 | 58,71 |
    | D0′ | discrete off d0 | 63,04 |
    | DT0 | discrete on d0 | 59,56 |
    | F1′ | prob off d1 | 57,56 |
    | T1′ | prob on d1 | 64,12 |
    | D1 | discrete off d1 | 61,05 |
    | DT1 | discrete on d1 | 55,48 |

    Clasificación pre-registrada (IC 98,75 %, Bonferroni ×4): **H1 refutada en ambos órdenes**
    (DT−D ≥ +5: d0 −3,5 [−11,4; +3,6], d1 −5,6 [−14,8; +2,6]) — thinking sobre discrete no
    alcanza la mejora ≥5, y como los IC incluyen cero no se afirma deterioro ni equivalencia.
    **H2:** inconclusa en d0 (DT−T +0,9 [−5,2; +6,7]) y refutada en d1 (−8,6 [−18,1; −1,9],
    contraste a favor de prob con thinking). Interacción descriptiva ≈ −12,1 en ambos órdenes;
    Holm 53 celdas: 0 significativas. Thinking multiplica la latencia media ×13,8/×13,2 sobre
    discrete y ×6,8/×7,1 sobre prob. Sin afirmar superioridad ni deterioro entre tratamientos.
    Detalle: `docs/infra_runs/qwen38_jev76.md` §RESULTADOS.
- **JEV-77 (8-oct), MedGemma-27B-IT frente a Gemma3-27B-IT y Qwen3.8-27B FP8 (18 celdas × 194,
  GT v4):** sesión pre-registrada en .80 (rama A: una imagen SGLang común para los cinco checkpoints;
  MedGemma/Gemma BF16 y Qwen FP8, `discrete`/`probabilities` × d0/d1), 3 492/3 492 casos, 0 errores, 3 658 peticiones de
  12 000, 17,98 h de 40 h, 2/4 reinicios extraordinarios; manifiesto `8b201bfb8b6bd5a7` con la
  Enmienda 1 (gramática JSON restringida común) y la Enmienda 2 (la sonda ciega admite valores
  fuera del contrato SDK). Revisión Codex R61: cálculo y análisis reproducidos; su corrección C1
  (trazabilidad de los pesos de Gemma3-4B tras la desviación del NAS) quedó cerrada con la
  verificación SHA256 de `docs/infra_runs/medgemma_jev77/a6/weights_gemma3_4b/`.

  | Celda | Config | Ajustado |
  |---|---|---:|
  | *Mayoría trivial* | — | 0,00 |
  | MD0 | MedGemma-27B · discrete · d0 | 25,87 |
  | GD0 | Gemma3-27B · discrete · d0 | 16,22 |
  | QD0′ | Qwen3.8-27B FP8 · discrete · d0 | 62,90 |
  | MD1 | MedGemma-27B · discrete · d1 | 28,99 |
  | GD1 | Gemma3-27B · discrete · d1 | 21,10 |
  | QD1′ | Qwen3.8-27B FP8 · discrete · d1 | 60,43 |

  Clasificación pre-registrada (IC 97,5 %, Bonferroni ×2): **H1 inconclusa** (MD0−GD0 ≥ +5:
  +9,7 [−1,7; +21,8]) y **H2 refutada** (MD0−QD0′ ≥ −5: −37,0 [−49,8; −24,9]). Los descriptivos
  (d1, probabilities, bloque 4B) no sostienen una ventaja uniforme de MedGemma sobre Gemma3; los
  subgrupos solo sugieren ganancia frente a Gemma3 en papers32 (+7,1 [1,0; 13,2] IC95 nominal).
  Holm53 (diez familias): solo tres celdas significativas, todas en el bloque 4B.
  **Cautela:** 633 vectores crudos nulos normalizados a uniforme, 600 de ellos en los runs
  probabilities de MedGemma-4B — su ajustado probabilities no es confianza informada.
  **Cascada híbrida** M-D0 → revisor Jev (`typesafe/jev-1.13-20260917` congelado, 194/194):
  audit **65,43**, raw **66,59** — descriptiva, no demuestra que audit supere a raw ni una
  solución 100 % local. Sin afirmar superioridad ni utilidad clínica.
  Detalle: `docs/infra_runs/medgemma_jev77.md` §RESULTADOS.
- Repetir `python3 -m jevbench.check_versions --log` periódicamente. Si aparece una versión
  nueva de Jev, repetir `jev_v3` y la cascada.

## Problemas del GT detectados

- **GT v4 (6-oct, JEV-73):** se retira P02, cuyo fetch duplicó P03 (PMID 37130440); P03 conserva su GT. Quedan 31 papers y 194 casos. Todos los modelos se re-puntúan; las copias v1/v2/v3 conservan el histórico.

- **P04** (papers): `domain = "ild"` no era una opción válida y el diseño `cohort` chocaba
  con el título *systematic review*. **Corregido** a `ip`/`meta` (26-sep). Con esto, Jev pasa de
  66.2 a 67.5 en papers sobre los 32 casos históricos. Los informes antiguos y los tests usan el GT original (v1).
- El informe GLiNER del 24-sep daba 45.6% en papers, pero sus propios recuentos suman 49.1%.
- El informe AnyJev tenía los % de Laya ES/EN intercambiados (ES 63.6, EN 73.6).
- **GT v3 (27-sep):** 9 cambios tras la 2ª anotación (JEV-28), en `data/GT_CHANGELOG.md`.

## Histórico (informes de Lyra, re-puntuados con el harness)

| run | triaje ES | triaje EN | papers | ρ | adv dept |
|---|---|---|---|---|---|
| legacy_jev_v1 (20-sep) | 87.1 | 85.0 | 66.2 | 0.87 | 9/10 (solo adv1, con admin+catering) |
| legacy_jev_v2 (23-sep) | 86.4 | 88.6 | 66.2 | 0.87 | 15/20 |
| Jev v2 → revisor Jev | — | — | — | — | 18/20 (detector de manipulación 16/16) |
