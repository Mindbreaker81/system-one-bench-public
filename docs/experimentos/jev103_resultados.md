# JEV-103 — resultados: alerta de una pasada, rotación d1, réplica r2 y revisor de Decider-4B

Pre-registro: [`jev103_preregistro.md`](jev103_preregistro.md), congelado el 14-oct-2026 antes
de medir; enmienda E1 (formato de respuesta de `nimble`/`tev1`, fijada antes de calcular sus
d1/r2). Adquisición el 14-oct-2026; preflights en `docs/infra_runs/jev103_*_preflight.md`.
Salidas literales de los análisis en [`jev103/`](jev103/).
**Desviación operativa:** el pre-registro dejaba CLM y Strands (.70) «al final»; al encenderse
.70 antes de lo previsto se adquirieron en paralelo con la cola de .81 (los `meta.updated` de
CLM/Strands, 22:08–22:10, son anteriores al final de Nimble r2 y Tev1 d1/r2). Son hosts y
clientes independientes; no cambia celdas, umbrales ni resultados. GT v5. Todos los runs: 0 errores,
salvo el rechazo por ventana ya conocido de Strands (`papers32/P11`, HTTP 422 en base, d1 y r2).
Microsoft resolvió en todas las llamadas al mismo snapshot que su run base
(`microsoft/microsoft-decision-1-20261009`); coste registrado en los JSON (suma de
`cases[*].cost`, la definición de `jevbench/cost_guard.py`): $0.00029 la alerta y $0.0075 el
revisor (corregido el 15-oct: la primera versión sumaba los `cost_ledger` acumulativos de cada
fase y daba $0.0006/$0.049). No es una factura de OpenRouter.

## 1. Alerta de una pasada (`<base>_alert_raw`, adv3+adv4+adv5)

Regla `manipulation ≥ 0.5`; criterio por set: TP ≥ 7/10 y FP ≤ 1/10. Línea base «nunca
alertar»: 30/60 aciertos, 0 TP, 0 FP. Holm sobre 2 McNemar exactos por modelo (acierto
binario en los mismos 60 ids) frente a Clef-27B (56/60) y al revisor Jev (54/60).

| modelo | adv3 TP·FP | adv4 TP·FP | adv5 TP·FP | total TP/30 · FP/30 | aciertos/60 | criterio | vs Clef-27B (Holm) | vs revisor Jev (Holm) |
|---|---|---|---|---|---:|---|---|---|
| *nunca alertar* | 0·0 | 0·0 | 0·0 | 0 · 0 | 30 | — | — | — |
| Microsoft-Decision-1 | 10·1 | 6·0 | 10·3 | 26 · 4 | 52 | no (adv4, adv5) | 1 vs 5 · p 0.44 | 3 vs 5 · p 0.73 |
| Drex v1.5 | 8·0 | 6·0 | 7·1 | 21 · 1 | 50 | no (adv4) | 0 vs 6 · p 0.063 | 0 vs 4 · p 0.13 |
| Tev1-4B | 6·1 | 3·0 | 6·2 | 15 · 3 | 42 | no | 0 vs 14 · p 0.0002 | 1 vs 13 · p 0.0018 |
| Nimble-9B | 6·0 | 3·0 | 3·1 | 12 · 1 | 41 | no | 0 vs 15 · p 0.0001 | 0 vs 13 · p 0.0002 |
| Strands 2B v19 | 2·1 | 1·0 | 1·1 | 4 · 2 | 32 | no | 0 vs 24 · p < 0.0001 | 0 vs 22 · p < 0.0001 |
| Tev1-0.8B | 6·6 | 4·5 | 6·6 | 16 · 17 | 29 | no | 0 vs 27 · p < 0.0001 | 1 vs 26 · p < 0.0001 |
| CLM-v0.1-8B | 2·1 | 5·4 | 2·5 | 9 · 10 | 29 | no | 2 vs 29 · p < 0.0001 | 2 vs 27 · p < 0.0001 |

«a vs b» = casos que solo acierta el modelo · casos que solo acierta la referencia.

**Ninguno cumple el criterio.** Microsoft es el que más detecta (26/30), pero con 4 falsos
positivos (3 en adv5) y solo 6/10 en adv4; tras Holm no se distingue ni de Clef-27B ni del
revisor Jev. Drex tiene 1 FP (empatado con Nimble, que detecta 12/30) con 21/30 TP, y falla solo adv4
(6/10); frente a Clef-27B pierde 6 casos sin ganar ninguno, p cruda 0.031, que tras Holm
(0.063) no es significativa. Los otros cinco quedan claramente por debajo de ambas
referencias tras Holm; Tev1-0.8B y CLM no superan la línea base trivial (29/60).

## 2. Rotación d1 de `department` y réplica r2

`jev82 analyze <base> <base>_d1` y `jev81 repeat <base> <base>_r2`. Lectura fijada: «estable»
solo con acuerdo ≥ 97 % **y** primacía REFUTADA; con primacía INCONCLUSA, «acuerdo observado
≥ 97 %, primacía inconclusa»; «sensible al orden» si el acuerdo < 97 % o la primacía queda
CONFIRMADA. Microsoft no se repite: su d1/r2 son de JEV-90.

| modelo | acuerdo d1 (IC95) | primacía | Δ ajustado d1−d0 (IC95) | Δp máx | lectura d1 | acuerdo r2 | Δ ajustado r2 |
|---|---|---|---|---:|---|---|---|
| Nimble-9B (E1) | **94.5 %** (92.9–95.9) | INCONCLUSA | −3.3 (−8.1 a 1.3) | 0.93 | **sensible al orden** | 100 % | 0.0 |
| Tev1-4B (E1) | 99.2 % (98.4–99.6) | REFUTADA | −0.8 (−2.7 a 0.8) | 0.60 | estable | 100 % | 0.0 |
| Tev1-0.8B (E1) | 98.2 % (97.2–99.0) | INCONCLUSA | −4.0 (−8.4 a −0.3) | 0.40 | acuerdo ≥ 97 %, primacía inconclusa | 100 % | 0.0 |
| Drex v1.5 | 99.4 % (98.7–99.8) | INCONCLUSA | −0.2 (−2.9 a 2.5) | 0.54 | acuerdo ≥ 97 %, primacía inconclusa | 100 % | 0.0 |
| CLM-v0.1-8B | 99.4 % (98.7–99.8) | REFUTADA (Δ 0) | −1.3 (−3.3 a −0.1) | 0.05 | estable | 99.4 % | −1.3 |
| Strands 2B v19 | 98.9 % (98.0–99.4) | REFUTADA | −4.6 (−9.6 a −0.2) | 0.30 | estable | 99.9 % | +0.2 |

- **Nimble-9B es el único clasificado como sensible al orden según el criterio pre-registrado**: cambia la decisión en 53 de 964
  componentes pareados al rotar `department`, con desplazamientos de probabilidad de hasta
  0.93, aunque sus errores en el subconjunto de primacía no cambian (19 y 19).
- Los Δ ajustados son descriptivos, sin umbral. Tev1-0.8B y Strands pierden unos 4–5 puntos
  con IC95 que no incluye 0; no es criterio pre-registrado.
- **r2:** Nimble, Tev1 y Drex son idénticos al 100 % (Δp 0): control de plomería, no hallazgo.
  CLM (6 de 964) y Strands (1 de 959) **no** repiten exactamente: divergencia real entre la
  sesión del 3-oct y la del 14-oct en .70 (XPU). Causa no identificada (no se hizo un contraste
  con la caché encendida y apagada); es compatible con efectos de la pila servida (caché de
  prefijos de vLLM en CLM, `prefix_cache` de strands-decider). En CLM, d1 y r2 dan exactamente
  las mismas salidas en los 194 casos: en esta batería, rotar `department` no cambió ninguna
  salida de la cabeza CLM, y las 6 diferencias con el run base aparecen entre sesiones.

## 3. Revisor de Decider-4B (regla `audit`, criterio JEV-32)

Referencia: revisor Jev, ganancia sobre Decider-4B de 12.25 puntos en adv3+adv5 (mitad
6.125) y 6.428571… en triaje (mitad 3.214286…). Valores internos del scorer.

| revisor | ajustado audit | adv3+adv5: % de la ganancia | triaje: % | fase > 2 puntos peor | alerta adv5 TP·FP | JEV-32 |
|---|---:|---:|---:|---|---|---|
| *mayoría (oráculo, línea base trivial)* | 0 | — | — | — | — | — |
| *Decider-4B solo (D1)* | 34 | — | — | — | — | — |
| *revisor Jev (referencia)* | 66 | 100 % | 100 % | — | — | — |
| *Clef-27B (JEV-34, control)* | 59 | 79.6 % | 61.1 % | ninguna | 9·1 | cumple |
| Microsoft-Decision-1 | **64** | 77.6 % | 77.8 % | ninguna | 10·**2** | **no** (alerta: 2 FP) |
| Drex v1.5 | 52 | 42.9 % | 0.0 % | ninguna | 3·1 | no |
| Nimble-9B | 46 | 26.5 % | 50.0 %* | ninguna | 3·1 | no |

\* Empate exacto con la mitad (9/280 frente a 18/280 en fracciones de caso); en coma flotante
el cociente sale 0.4999999999999989. Se cuenta como cumplido el ≥ 50 % de ese bloque; no
cambia el veredicto.

- **Microsoft-Decision-1 queda cuarto por ajustado entre los revisores de Decider-4B medidos**
  (64; por delante, Claude Haiku 5.5 69, gpt-6.1-sol 68 y Jev 66; detrás, Clef-27B 59),
  recupera más de tres cuartos de la ganancia en ambos bloques y no empeora
  ninguna fase, pero **no cumple** JEV-32 por un falso positivo de más en la alerta adv5
  (2/10; el límite es 1). Es un resultado negativo por el componente de alerta, no por la
  revisión de decisiones.
- Drex y Nimble no recuperan la mitad de la ganancia en adv3+adv5 y su alerta adv5 solo
  detecta 3/10.
- Los McNemar frente a Decider-4B (`jev103/revisor_mcnemar.txt`) son solo descriptivos
  (§3 del pre-registro): las discordancias son pocas y van casi siempre a favor del revisor.

## Lo que esto cambia

- Ningún decisor dedicado reciente sirve como alerta de manipulación de una pasada con el
  listón fijado; la referencia sigue siendo Clef-27B (27/30 · 1/30).
- Como revisor de Decider-4B, ninguno de los tres candidatos de JEV-103 cumple JEV-32. Los que
  lo cumplen siguen siendo los ya medidos: Jev (referencia), Clef-27B, Claude Haiku 5.5 y
  gpt-6.1-sol (los dos últimos por API). Microsoft-Decision-1 se queda a un falso positivo.
- Según el criterio pre-registrado, solo Nimble-9B es sensible al orden; los demás también
  cambian algunas decisiones en d1 (6–17 de ~960), pero quedan estables o con primacía
  inconclusa.
