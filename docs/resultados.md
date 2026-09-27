# Resultados consolidados

Última actualización: 27-sep-2026 (**GT v3**: P04 corregido + adjudicación de la 2ª anotación, ver `data/GT_CHANGELOG.md`). Todo se regenera desde `results/` con el harness:

<!-- AUTO:comando -->
```bash
python3 -m jevbench.report   # regenera este documento (runs en docs/resultados_runs.txt)
python3 -m jevbench.score --summary jev_v3 jev_typesafe_v1 jev_cascade_review jev_cascade_audit jev_cascade_audit_rules \
    decider_4b_jevrev_review decider_4b_jevrev_audit decider_35b_a3b decider_35b_a3b_nvfp4 decider_4b \
    decider_4b_cascade_audit decider_4b_d35rev_audit decider_4b_aj32brev_audit decider_4b_aj8brev_audit decider_2b \
    decider_0.8b anyjev_qwen3_32b_l0 anyjev_qwen3_8b_l0 anyjev_qwen3_1.7b_l0 gliner_decide_desc \
    gliner_decide_bare gliner_decide_1b_desc gliner_multi_decide_desc julia_1 laya_router \
    laya_typed legacy_laya_v2
```
<!-- /AUTO:comando -->

## Marcador (GT v3, generado)

<!-- AUTO:marcador -->
| run | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v3 | 88.6 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 87.5 | 0.071 | 657 |
| jev_typesafe_v1 | 87.9 | 90.0 | 26/28 | 67.5 | 0.87 | 5/10 | 14/20 | 79.0 | 95.0 / 92.7 | 17/20 | 88.5 | 0.071 | 902 |
| jev_cascade_review | 92.1 | 93.6 | 26/28 | 75.3 | 0.82 | 6/10 | 18/20 | 89.0 | 95.4 / 93.8 | 18/20 | 92.0 | 0.054 | — |
| jev_cascade_audit | 91.4 | 93.6 | 26/28 | 73.8 | 0.87 | 5/10 | 18/20 | 88.5 | 94.6 / 93.5 | 18/20 | 92.0 | 0.055 | — |
| jev_cascade_audit_rules | 91.4 | 93.6 | 26/28 | — | — | — | 19/20 | 89.5 | 94.6 / 93.5 | 20/20 | 94.0 | 0.048 | — |
| decider_4b_jevrev_review | 92.1 | 93.6 | 25/28 | 74.4 | 0.85 | 7/10 | 18/20 | 87.5 | 94.2 / 93.8 | 18/20 | 93.5 | 0.056 | — |
| decider_4b_jevrev_audit | 90.7 | 93.6 | 25/28 | 72.2 | 0.76 | 6/10 | 19/20 | 88.5 | 93.1 / 92.3 | 18/20 | 93.5 | 0.066 | — |
| decider_35b_a3b | 84.3 | 79.3 | 24/28 | 69.7 | 0.90 | 6/10 | 15/20 | 78.0 | 92.3 / 88.5 | 13/20 | 77.5 | 0.097 | 678 |
| decider_35b_a3b_nvfp4 | 85.0 | 81.4 | 24/28 | 70.3 | 0.87 | 5/10 | 15/20 | 74.0 | 88.8 / 88.8 | 12/20 | 76.0 | 0.105 | 190 |
| decider_4b | 85.7 | 85.7 | 26/28 | 65.9 | 0.78 | 6/10 | 14/20 | 71.5 | 90.8 / 90.0 | 12/20 | 77.0 | 0.102 | 200 |
| decider_4b_cascade_audit | 87.1 | 87.1 | 26/28 | 69.4 | 0.76 | 6/10 | 13/20 | 74.5 | 90.4 / 90.4 | 13/20 | 78.5 | 0.095 | — |
| decider_4b_d35rev_audit | 89.3 | 87.9 | 26/28 | 67.5 | 0.85 | 4/10 | 17/20 | 83.5 | 93.1 / 91.9 | 13/20 | 80.5 | 0.082 | — |
| decider_4b_aj32brev_audit | 80.7 | 82.9 | 25/28 | 69.7 | 0.75 | 6/10 | 14/20 | 72.0 | 92.3 / 93.8 | 16/20 | 84.5 | 0.100 | — |
| decider_4b_aj8brev_audit | 84.3 | 84.3 | 26/28 | 64.4 | 0.74 | 7/10 | 14/20 | 69.5 | 90.0 / 88.5 | 12/20 | 77.5 | 0.122 | — |
| decider_2b | 77.9 | 78.6 | 23/28 | 62.5 | 0.85 | 4/10 | 12/20 | 69.0 | 86.5 / 89.6 | 13/20 | 71.5 | 0.125 | 79 |
| decider_0.8b | 82.1 | 81.4 | 21/28 | 64.7 | 0.81 | 7/10 | 12/20 | 64.5 | 82.7 / 83.8 | 9/20 | 63.5 | 0.130 | 43 |
| anyjev_qwen3_32b_l0 | 83.6 | 79.3 | 25/28 | 69.7 | 0.79 | 6/10 | 13/20 | 68.5 | 85.8 / 85.0 | 15/20 | 84.0 | 0.164 | 2552 |
| anyjev_qwen3_8b_l0 | 80.0 | 79.3 | 25/28 | 73.8 | 0.86 | 6/10 | 12/20 | 62.0 | 86.5 / 90.0 | 14/20 | 79.0 | 0.183 | 682 |
| anyjev_qwen3_1.7b_l0 | 81.4 | 71.4 | 25/28 | 64.4 | 0.50 | 9/10 | 14/20 | 66.0 | 71.2 / 80.4 | 9/20 | 53.0 | 0.256 | 181 |
| gliner_decide_desc | 77.9 | 80.0 | 21/28 | 52.5 | 0.67 | 7/10 | 7/20 | 61.5 | 70.0 / 77.7 | 9/20 | 59.0 | 0.210 | 42 |
| gliner_decide_bare | 77.9 | 72.1 | 18/28 | 49.7 | -0.02 | 2/10 | 3/20 | 56.5 | — / — | — | — | 0.226 | 33 |
| gliner_decide_1b_desc | 71.4 | 77.1 | 17/28 | 49.7 | 0.43 | 0/10 | 5/20 | 54.5 | — / — | — | — | 0.224 | 75 |
| gliner_multi_decide_desc | 63.6 | 63.6 | 12/28 | 47.5 | 0.31 | 0/10 | 2/20 | 46.5 | — / — | — | — | 0.242 | 23 |
| julia_1 | 35.0 | 41.4 | 9/28 | 48.8 | 0.22 | 0/10 | 3/20 | 46.0 | 45.0 / 37.3 | 7/20 | 38.5 | 0.505 | 599 |
| laya_router | 62.1 | 73.6 | 15/28 | 48.8 | 0.22 | 2/10 | 5/20 | 61.0 | 55.0 / 71.5 | 7/20 | 59.5 | 0.208 | 29 |
| laya_typed | 67.1 | 75.0 | 14/28 | 45.6 | 0.10 | 5/10 | 3/20 | 49.0 | 67.7 / 75.8 | 8/20 | 64.0 | 0.182 | 31 |
| legacy_laya_v2 | 62.1 | 75.0 | 15/28 | 48.8 | 0.23 | 2/10 | 5/20 | 61.5 | — / — | — | — | 0.187 | 6548 |
| *mayoría (oráculo)* | 66.4 | 66.4 | 12/28 | 51.6 | — | 0/10 | 17/20 | 79.0 | 57.7 / 57.7 | 5/20 | 59.0 | — | — |
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
Versiones de Jev comprobadas: `docs/versiones_jev.md` (sin cambios a 27-sep).

## Lectura

**Recomendación vigente (27-sep):**
- **Jev → revisor-auditor (regla `audit`)**, sin reglas duras.
- **Alerta para revisión humana** cuando `manipulation ≥ 0.5` en la 2ª pasada. Validada en
  casos nuevos (adv5: 9/10 manipulados, 1/10 FP). Acumulado adv3 + adv4 + adv5: **25/30
  manipulados, 1/30 FP**. No cambia el routing.
- **Alternativa más barata con la misma calidad:** Decider-4B local → revisor Jev.
- Revisor 100% local: pendiente (plan en `plan_revisor_local.md`, JEV-32). Decider revisándose a
  sí mismo no sirve.

**Por modelo (GT v3):**
- **Jev** es el incumbente. Con revisor: triaje 91–94, papers 74–75, adv 18/20, adv3 18/20.
  OpenRouter y la API de TypeSafe son equivalentes (406/409 respuestas iguales).
- **Decider-4B** acierta los mismos departamentos que Jev en triaje (diferencias no
  significativas, p ≥ 0.12), pero en adv3 queda por detrás (12 frente a 17/20, p = 0.06).
- **Decider-35B-A3B**: no mejora al 4B en triaje; es el que mejor ordena los papers por
  relevancia (ρ 0.90). NVFP4 rinde igual que bf16 y va 3.5× más rápido (190 ms/caso).
- **AnyJev**: 32B es el mejor open-weight en adv3 (15/20), pero lento (~2.5 s) y mal calibrado;
  8B consigue el mejor papers de una sola pasada (73.8).
- **GLiNER**, **Laya** y **Julia-1**: descartados zero-shot (en o por debajo de la línea base de
  mayoría en adversarial; Julia, incluso en triaje).

**Experimentos** (`docs/experimentos/`):
- `cascada_jev.md`: revisor-auditor (Jev→Jev, Decider→Decider, Decider→Jev y revisores 100%
  locales — resultado negativo: ninguno recupera ≥50% de la ganancia de Jev).
- `reglas_duras.md`: reglas regex, descartadas (0/10 en casos nuevos, 3/10 FP).
- `alerta_manipulacion.md`: alerta validada en adv5.

**Notas de método:**
- En adv1 + adv2, responder siempre `admin` saca 17/20: ese set no sirve para comparar modelos.
  Usar adv3–adv5 (equilibrados).
- Con n = 14–32, los IC95 se solapan casi siempre: usar `--vs` (McNemar) antes de afirmar que
  un modelo "gana".
- La 2ª anotación (JEV-27/28) mostró mucho ruido de etiquetado en urgency y same_day; 1–2
  puntos de diferencia ahí no significan nada.

## Pendiente

- ~~JEV-32~~ **hecho** (27-sep): ningún revisor local (Decider-35B NVFP4, AnyJev-32B/8B)
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
