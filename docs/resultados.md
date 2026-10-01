# Resultados consolidados

Última actualización editorial: 1-oct-2026 (**GT v3**, fijado el 27-sep: P04 corregido +
adjudicación de la 2ª anotación, ver `data/GT_CHANGELOG.md`). Todo se regenera desde
`results/` con el harness:

<!-- AUTO:comando -->
```bash
python3 -m jevbench.report   # regenera este documento (runs en docs/resultados_runs.txt)
python3 -m jevbench.score --summary jev_v3 jev_typesafe_v1 jev_cascade_review jev_cascade_audit jev_cascade_audit_rules \
    llm_gpt6luna_jevrev_review llm_gpt6luna_jevrev_audit llm_gpt6luna_prob llm_gpt6luna_disc llm_gpt61sol_low_prob \
    llm_qwen38_27b_prob llm_qwen38flash_prob decider_4b_jevrev_review decider_4b_jevrev_audit decider_4b_llmrev_review \
    decider_4b_llmrev_audit decider_35b_a3b decider_35b_a3b_nvfp4 decider_4b decider_4b_cascade_audit \
    decider_4b_d35rev_audit decider_4b_aj32brev_audit decider_4b_aj8brev_audit decider_2b decider_0.8b \
    anyjev_qwen3_32b_l0 anyjev_qwen3_8b_l0 anyjev_qwen3_1.7b_l0 gliner_decide_desc gliner_decide_bare \
    gliner_decide_1b_desc gliner_multi_decide_desc julia_1 laya_router laya_typed \
    legacy_laya_v2 span01_pro span01_lite span01_lite_or nimble_9b \
    tev1_4b tev1_0.8b
```
<!-- /AUTO:comando -->

## Marcador (GT v3, generado)

<!-- AUTO:marcador -->
| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v3 | 45 | 88.6 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 87.5 | 0.071 | 657 |
| jev_typesafe_v1 | 51* | 87.9 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 88.5 | 0.071 | 902 |
| jev_cascade_review | 65 | 92.1 | 93.6 | 26/28 | 75.3 | 0.82 | 6/10 | 18/20 | 89.0 | 95.4 / 93.8 | 18/20 | 92.0 | 0.054 | — |
| jev_cascade_audit | 64 | 91.4 | 93.6 | 26/28 | 73.8 | 0.87 | 5/10 | 18/20 | 88.5 | 94.6 / 93.5 | 18/20 | 92.0 | 0.055 | — |
| jev_cascade_audit_rules | 67* | 91.4 | 93.6 | 26/28 | — | — | — | 19/20 | 89.5 | 94.6 / 93.5 | 20/20 | 94.0 | 0.048 | — |
| llm_gpt6luna_jevrev_review | 69 | 94.3 | 97.1 | 25/28 | 76.2 | 0.86 | 6/10 | 18/20 | 89.0 | 95.8 / 95.8 | 18/20 | 93.5 | 0.050 | — |
| llm_gpt6luna_jevrev_audit | 71 | 93.6 | 97.1 | 25/28 | 76.9 | 0.82 | 9/10 | 18/20 | 92.0 | 95.0 / 95.0 | 18/20 | 92.0 | 0.045 | — |
| llm_gpt6luna_prob | 61 | 93.6 | 95.7 | 25/28 | 78.8 | 0.87 | 9/10 | 18/20 | 87.0 | 93.5 / 93.5 | 17/20 | 88.0 | 0.053 | 3027 |
| llm_gpt6luna_disc | 59 | 93.6 | 91.4 | 26/28 | 76.6 | 0.77 | 6/10 | 17/20 | 85.0 | 92.3 / 92.7 | 18/20 | 89.5 | 0.077 | 1876 |
| llm_gpt61sol_low_prob | 65 | 92.9 | 93.6 | 26/28 | 80.0 | 0.90 | 8/10 | 18/20 | 88.5 | 94.2 / 94.6 | 18/20 | 89.5 | 0.054 | 3415 |
| llm_qwen38_27b_prob | -16* | 73.6 | 73.6 | 13/28 | 52.2 | -0.17 | 0/10 | 4/20 | 58.5 | 77.2 / 76.5 | 9/20 | 67.5 | 0.231 | 6799 |
| llm_qwen38flash_prob | -40* | 65.7 | 55.0 | 14/28 | 38.1 | -0.01 | 0/10 | 4/19 | 50.8 | 55.4 / 51.7 | 6/19 | 65.3 | 0.317 | 47875 |
| decider_4b_jevrev_review | 65 | 92.1 | 93.6 | 25/28 | 74.4 | 0.85 | 7/10 | 18/20 | 87.5 | 94.2 / 93.8 | 18/20 | 93.5 | 0.056 | — |
| decider_4b_jevrev_audit | 64 | 90.7 | 93.6 | 25/28 | 72.2 | 0.76 | 6/10 | 19/20 | 88.5 | 93.1 / 92.3 | 18/20 | 93.5 | 0.066 | — |
| decider_4b_llmrev_review | 64 | 93.6 | 92.9 | 26/28 | 76.2 | 0.80 | 6/10 | 18/20 | 86.5 | 93.5 / 93.5 | 18/20 | 91.0 | 0.067 | — |
| decider_4b_llmrev_audit | 52 | 87.9 | 87.1 | 26/28 | 76.2 | 0.78 | 6/10 | 18/20 | 81.0 | 91.9 / 91.9 | 17/20 | 88.5 | 0.096 | — |
| decider_35b_a3b | 40* | 84.3 | 79.3 | 24/28 | 69.7 | 0.90 | 6/10 | 15/20 | 78.0 | 92.3 / 88.5 | 13/20 | 77.5 | 0.097 | 678 |
| decider_35b_a3b_nvfp4 | 35* | 85.0 | 81.4 | 24/28 | 70.3 | 0.87 | 5/10 | 15/20 | 74.0 | 88.8 / 88.8 | 12/20 | 76.0 | 0.105 | 190 |
| decider_4b | 33 | 85.7 | 85.7 | 26/28 | 65.9 | 0.78 | 6/10 | 14/20 | 71.5 | 90.8 / 90.0 | 12/20 | 77.0 | 0.102 | 200 |
| decider_4b_cascade_audit | 39* | 87.1 | 87.1 | 26/28 | 69.4 | 0.76 | 6/10 | 13/20 | 74.5 | 90.4 / 90.4 | 13/20 | 78.5 | 0.095 | — |
| decider_4b_d35rev_audit | 51 | 89.3 | 87.9 | 26/28 | 67.5 | 0.85 | 4/10 | 17/20 | 83.5 | 93.1 / 91.9 | 13/20 | 80.5 | 0.082 | — |
| decider_4b_aj32brev_audit | 36 | 80.7 | 82.9 | 25/28 | 69.7 | 0.75 | 6/10 | 14/20 | 72.0 | 92.3 / 93.8 | 16/20 | 84.5 | 0.100 | — |
| decider_4b_aj8brev_audit | 28 | 84.3 | 84.3 | 26/28 | 64.4 | 0.74 | 7/10 | 14/20 | 69.5 | 90.0 / 88.5 | 12/20 | 77.5 | 0.122 | — |
| decider_2b | 20* | 77.9 | 78.6 | 23/28 | 62.5 | 0.85 | 4/10 | 12/20 | 69.0 | 86.5 / 89.6 | 13/20 | 71.5 | 0.125 | 79 |
| decider_0.8b | 11* | 82.1 | 81.4 | 21/28 | 64.7 | 0.81 | 7/10 | 12/20 | 64.5 | 82.7 / 83.8 | 9/20 | 63.5 | 0.130 | 43 |
| anyjev_qwen3_32b_l0 | 27* | 83.6 | 79.3 | 25/28 | 69.7 | 0.79 | 6/10 | 13/20 | 68.5 | 85.8 / 85.0 | 15/20 | 84.0 | 0.164 | 2552 |
| anyjev_qwen3_8b_l0 | 18* | 80.0 | 79.3 | 25/28 | 73.8 | 0.86 | 6/10 | 12/20 | 62.0 | 86.5 / 90.0 | 14/20 | 79.0 | 0.183 | 682 |
| anyjev_qwen3_1.7b_l0 | 3* | 81.4 | 71.4 | 25/28 | 64.4 | 0.50 | 9/10 | 14/20 | 66.0 | 71.2 / 80.4 | 9/20 | 53.0 | 0.256 | 181 |
| gliner_decide_desc | -4* | 77.9 | 80.0 | 21/28 | 52.5 | 0.67 | 7/10 | 7/20 | 61.5 | 70.0 / 77.7 | 9/20 | 59.0 | 0.210 | 42 |
| gliner_decide_bare | -37* | 77.9 | 72.1 | 18/28 | 49.7 | -0.02 | 2/10 | 3/20 | 56.5 | — / — | — | — | 0.226 | 33 |
| gliner_decide_1b_desc | -42* | 71.4 | 77.1 | 17/28 | 49.7 | 0.43 | 0/10 | 5/20 | 54.5 | — / — | — | — | 0.224 | 75 |
| gliner_multi_decide_desc | -74* | 63.6 | 63.6 | 12/28 | 47.5 | 0.31 | 0/10 | 2/20 | 46.5 | — / — | — | — | 0.242 | 23 |
| julia_1 | -79* | 35.0 | 41.4 | 9/28 | 48.8 | 0.22 | 0/10 | 3/20 | 46.0 | 45.0 / 37.3 | 7/20 | 38.5 | 0.505 | 599 |
| laya_router | -20* | 62.1 | 73.6 | 15/28 | 48.8 | 0.22 | 2/10 | 5/20 | 61.0 | 55.0 / 71.5 | 7/20 | 59.5 | 0.208 | 29 |
| laya_typed | -26* | 67.1 | 75.0 | 14/28 | 45.6 | 0.10 | 5/10 | 3/20 | 49.0 | 67.7 / 75.8 | 8/20 | 64.0 | 0.182 | 31 |
| legacy_laya_v2 | -36* | 62.1 | 75.0 | 15/28 | 48.8 | 0.23 | 2/10 | 5/20 | 61.5 | — / — | — | — | 0.187 | 6548 |
| span01_pro | 18 | 85.0 | 84.3 | 22/28 | 71.9 | 0.72 | 7/10 | 12/20 | 63.5 | 80.4 / 84.6 | 13/20 | 72.0 | 0.162 | 597 |
| span01_lite | 6 | 82.9 | 82.1 | 20/28 | 66.6 | 0.65 | 10/10 | 10/20 | 61.0 | 75.8 / 76.5 | 8/20 | 67.5 | 0.159 | 895 |
| span01_lite_or | 18 | 85.0 | 84.3 | 22/28 | 73.8 | 0.79 | 8/10 | 12/20 | 63.5 | 80.4 / 84.6 | 13/20 | 72.0 | 0.162 | 587 |
| nimble_9b | 44 | 92.9 | 88.6 | 24/28 | 70.3 | 0.48 | 3/10 | 12/20 | 75.5 | 93.1 / 90.8 | 15/20 | 85.5 | 0.084 | 1620 |
| tev1_4b | 27 | 87.1 | 87.1 | 26/28 | 64.4 | 0.83 | 7/10 | 14/20 | 69.5 | 89.2 / 91.5 | 12/20 | 75.0 | 0.115 | 452 |
| tev1_0.8b | -7 | 67.9 | 72.1 | 23/28 | 64.7 | 0.70 | 7/10 | 9/20 | 58.5 | 78.8 / 81.2 | 11/20 | 64.0 | 0.171 | 142 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.6 | — | 0/10 | 17/20 | 79.0 | 57.7 / 57.7 | 5/20 | 59.0 | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*
<!-- /AUTO:marcador -->

Columnas: triaje = % sobre 5 preguntas × 14 casos. dept = departamento correcto.
papers = % sobre 5 dimensiones × 32 papers. ρ = Spearman de relevancia. skip LOO = de los 10
papers que no merecen lectura, cuántos descarta la cascada (umbral por leave-one-out).
adv dept = routing correcto en adversarial-1+2. triaje ext = T15–T40 (26 casos nuevos, validados
el 26-sep). adv3 = adversarial-3 equilibrado (20 casos: 10 manipulados y 10 honestos, 5 por
departamento). Brier = media de las preguntas sí/no
(más bajo es mejor). ms = mediana por caso (Jev por API; el resto en GPU GB10).

Configuración de cada run: Jev = `jev-1.13-20260917` vía OpenRouter (`jev_typesafe_v1`: API
directa, `jev-1.13.0`). Cascadas = 2ª pasada revisor-auditor (`jevbench/cascade.py`). Decider =
`Mapika/decider-*` bf16 en GB10 (el 35B sin CUDA graphs; NVFP4 servido con vLLM). AnyJev = L0 bf16.
GLiNER `desc` = etiquetas con descripción, `bare` = como la prueba del 24-sep. Julia-1 en CPU local.
Laya en GB10 (`laya_router`, `laya_typed`); `legacy_laya_v2` = rerun de Lyra en CPU.
LLM = `gpt-6-luna` (API OpenAI, Responses + JSON Schema estricto) con `system-one-adapter` 0.2.1;
`_prob` = `llm_answer_mode=probabilities`, `_disc` = `discrete`. `llm_gpt61sol_low_prob` =
`gpt-6.1-sol` con `reasoning_effort=low` (mismo modo `probabilities`).
Versiones de Jev comprobadas: `docs/versiones_jev.md` (sin cambios a 27-sep).

## Lectura

**Recomendación vigente (1-oct):**
- **Jev → revisor-auditor (regla `audit`)**, sin reglas duras.
- **Alerta para revisión humana** cuando `manipulation ≥ 0.5` en la 2ª pasada. Validada en
  casos nuevos (adv5: 9/10 manipulados, 1/10 FP). Acumulado adv3 + adv4 + adv5: **25/30
  manipulados, 1/30 FP**. No cambia el routing.
- **Alternativa más barata con la misma calidad:** Decider-4B local → revisor Jev.
- **No hay revisor 100 % local que cumpla el criterio pre-registrado.** Decider-35B NVFP4
  es el mejor de los probados, pero solo recupera el 34–45 % de la ganancia de Jev; AnyJev-32B
  y 8B tampoco cumplen. El plan y el resultado están en `plan_revisor_local.md` y
  `experimentos/cascada_jev.md`.

**Por modelo (GT v3):**
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
  **Alcance limitado por coste:** solo una pasada en modo `probabilities`; no se midieron el
  modo `discrete`, sol como revisor, la cascada sol → revisor Jev ni la alerta de manipulación.
- **Cascadas con LLM (29-sep):** `llm_gpt6luna_jevrev_audit` (LLM → revisor Jev) es la
  mejor configuración medida (adv total 92.0, adv5 88.5, Brier 0.045, alerta 9/10 con 1 FP),
  estadísticamente equivalente a `jev_cascade_audit` pero a ~4× el coste y la latencia.
  `decider_4b_llmrev_audit` (revisor LLM) recupera el 77 % de la ganancia de Jev en adv3+adv5
  — el primer revisor no-Jev que supera el 50 % ahí — pero falla el criterio JEV-32 por triaje
  (28 %) y por la alerta (6/10). Detalle: `docs/experimentos/cascada_jev.md`.
- **LLM local Qwen3.8-27B (29-sep, negativo):** servido con SGLang en el Spark .80 a través
  del mismo adaptador. Apenas supera la línea base trivial (triaje 73.6, papers 52.2,
  ρ −0.17, adv total 58.5 frente a 79.0 del baseline `admin`, Brier 0.231) y es el más
  lento del marcador (~6.8 s/caso). Ni el thinking apagado con el muestreo recomendado ni
  `reasoning_effort=low` lo salvan: un LLM grande no basta si no sigue el contrato.
- **LLM local Qwen3.8-Flash-Next (30-sep, negativo):** thinking activado en vLLM (.81), porque
  sin él fallaba el smoke. Queda por debajo de la mayoría (ajustado −40) y del 27B: triaje
  65.7/55.0, papers 38.1 (ρ −0.01), adv3 65.3 y Brier 0.317; Jev y gpt-6-luna lo superan
  significativamente en múltiples preguntas, sin ninguna ventaja significativa del Flash.
  Entrega 191/195 respuestas tras reintentar (4 timeouts), mediana 49.7 s/caso y ~14.7 h de
  pared entre la pasada completa y el reintento. Run `llm_qwen38flash_prob`.
- **Robustez del adaptador LLM (1-oct):** al investigar esos timeouts se comprobó que el
  límite era por petición, faltaba un presupuesto total y un tope de salida, y el runner
  no conservaba la telemetría de intentos y tokens. Se corrigieron los límites, el
  diagnóstico y la redacción de secretos; un smoke de 18 ejecuciones terminó sin errores
  de transporte y un timeout provocado se recuperó en el caso siguiente. No se cambiaron
  prompt, preguntas, GT, scorer ni resultados históricos, por lo que el marcador no varía.
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

**Experimentos** (`docs/experimentos/`):
- `cascada_jev.md`: revisor-auditor (Jev→Jev, Decider→Decider, Decider→Jev y revisores 100%
  locales — resultado negativo: ninguno recupera ≥50% de la ganancia de Jev).
- `reglas_duras.md`: reglas regex, descartadas (0/10 en casos nuevos, 3/10 FP).
- `alerta_manipulacion.md`: alerta validada en adv5; extensión con Span-01 como detector de
  una pasada (negativo: 8/30 pro, 5/30 lite, 0 FP).

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

- **Revisor local, cerrado el 27-sep:** ninguno (Decider-35B NVFP4, AnyJev-32B/8B)
  recupera ≥50% de la ganancia de la auditoría Jev; alerta de manipulación tampoco se
  transfiere (5/10, 6/10, 1/10). Ver `docs/experimentos/cascada_jev.md` §"Revisor 100% local".
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
