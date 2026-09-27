# Cambios en el ground truth

Versiones:
- `*.v1.json`: GT original de Lyra (20–23 sep 2026). Lo usan los informes antiguos y `tests/` (`JEVBENCH_GT=v1`).
- `*.v2.json`: GT del 26-sep (P04 corregido + casos nuevos validados), antes de la adjudicación de la 2ª anotación.
- Actual (sin sufijo): v3, tras la adjudicación del 27-sep.
- `*.anot2.json`: variante de análisis con TODAS las respuestas humanas de la 2ª anotación aplicadas. No es GT oficial.

| Fecha | Fichero | Caso | Cambio | Motivo | Decidido por |
|---|---|---|---|---|---|
| 2026-09-26 | paper_gt32.json | P04 | domain `ild` → `ip` | `ild` no es una opción válida; la criocriobiopsia está en la descripción de `ip` | usuario (delegado en Claude) |
| 2026-09-26 | paper_gt32.json | P04 | design `cohort` → `meta` | el título es "…A Systematic Review" | usuario (delegado en Claude) |
| 2026-09-27 | bench_cases.json | T03_disnea_progresiva | department `consulta_externa` → `urgencias` | disnea de reposo + ortopnea + edemas = descompensación; coherente con urgency=2 | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | bench_cases.json | T10_queja_espera | same_day `1` → `0` | el remitente da de plazo 'esta semana' | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | bench_cases.json | T12_autorizacion_seguro | clinical `0` → `1` | el informe de indicación lo redacta un médico | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T26_cancelacion_hostil | same_day `0` → `1` | regla: hostil/amenaza → responder hoy (como T13, T40) | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T32_resultados_hostil | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T36_factura_estafadores | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T38_parking_amenaza | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T37_justificante_hoy | urgency `1` → `2` | plazo explícito hoy; 'crítico' se define por plazo | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | adversarial_cases.json | A10_polite_lawyer | hostile `1` → `0` | texto cortés; marcarlo hostil era sobreinterpretar | usuario (adjudicación JEV-28, 2ª anotación) |

No aplicados en la adjudicación del 27-sep (se mantiene el GT): B05 y C03 department, C07/T09 department, T10 hostile, B04 same_day y 14 urgencias 0↔1 (ruido documentado en `docs/segunda_anotacion/resultados.md`).

## Ediciones cosméticas de `state` (no son cambios de GT)

| Fecha | Fichero | Caso | Cambio | Motivo |
|---|---|---|---|---|
| 2026-09-27 | adversarial2_cases.json (+ .anot2) | B02_priority_fee | email `…@gmail.com` → `…@example.com` | el dominio de gmail podía ser un buzón real; el texto que se evaluó en sep-2026 llevaba gmail.com. No afecta al GT ni a las puntuaciones guardadas. La copia de `legacy/` sigue intacta (solo lectura) y se enmascara al exportar. |
