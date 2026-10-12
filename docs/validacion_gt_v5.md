# GT v5 — revisión humana y efecto sobre resultados

El 11-oct-2026 el usuario completó la revisión de 88 campos: 83 principales
vigentes antes completados por Codex y cinco revisiones adicionales. En la
anotación inicial a ciegas hubo 51 acuerdos con GT v4 y 37 discrepancias;
la adjudicación humana posterior aplica 23 cambios y mantiene 14 etiquetas.
Se consultaron opiniones auxiliares de Cursor y Devin a petición del usuario,
reiniciando contexto y sin facilitar las etiquetas. La decisión final es humana.
La adjudicación asistida no constituye una segunda medición independiente de kappa.

La selección se centró en campos disputados, no es aleatoria ni exhaustiva.
Estos 88 campos tienen revisión humana documentada; no se afirma que todas
las etiquetas del banco estén revisadas por una persona. El resto conserva
su procedencia anterior; adv5 sigue validado por Claude por delegación.

El GT v5 mantiene los 194 casos, estados y preguntas. Cambian solo 23 etiquetas.
Copias completas de GT v4 en `data/*.v4.json`; cambios y justificaciones en
`data/GT_CHANGELOG.md`, procedencia por campo en `data/gt_v5_procedencia.json`.
No se repite inferencia ni se alteran probabilidades o respuestas guardadas.

## Repuntuación

Se repuntúan los 536 runs de decisión almacenados con ambos GT y el mismo
scorer. Las 21 fases auxiliares que carecen del contrato completo de decisión
se identifican aparte; no se inventan respuestas faltantes. La cobertura de
cada run se conserva. Las salidas originales (3492 JSON) mantienen sus hashes.
El marcador publicado usa su selección habitual de runs; los runs parciales
conservan su marca de cobertura incompleta.

El ajustado depende del acierto y de la línea base de mayoría del GT de cada
fase. Por tanto, los aumentos siguientes no representan mejoras del modelo:
sus respuestas son idénticas. No se compara directamente una cifra calculada
con v4 y otra con v5 como si fueran evaluaciones sobre las mismas etiquetas.

| Run | Ajustado GT v4 | Ajustado GT v5 | Cambio de puntuación |
|---|---|---|---|
| `jev_v3` | 45.38 | 49.28 | +3.90 |
| `jev_cascade_audit` | 63.62 | 67.63 | +4.01 |
| `decider_4b` | 33.32 | 33.84 | +0.52 |
| `clef_27b` | 52.04 | 55.77 | +3.74 |
| `llm_gpt61sol_low_prob` | 65.06 | 69.23 | +4.17 |
| `llm_haiku55_adapt_prob` | 69.29 | 72.95 | +3.66 |
| `jev_haiku55rev_audit` | 73.78 | 77.58 | +3.80 |
| `jev_ms_decision1` | 43.63 | 47.33 | +3.71 |
| Mayoría (oráculo) | 0.00 | 0.00 | 0.00 |

Los análisis confirmatorios cerrados antes de esta adjudicación conservan GT
v4 y sus auditorías declaran esa versión; son hechos históricos ligados a ese
cierre. Una réplica pre-registrada con GT v5
(`docs/experimentos/gt_v5_confirmatorio.md`, JEV-100) re-evalúa las mismas
hipótesis con criterios verbatim y es el veredicto confirmatorio vigente bajo
el GT actual: solo cambian dos ítems no primarios (P72 rango d0–d3, Holm
M4P1_vs_G4P1) y las discordancias de 4 celdas de jev90_holm53, sin cambio de
significación.

Publicación: la versión 2.0.0 se publica siguiendo
`docs/procedimientos/publicar-version.md` — commit y tag `v2.0.0` en el repo
privado, push con tags y snapshot saneado al espejo público. El sitio público
<https://system-one-bench.netlify.app/> se regenera y despliega solo con ese
push del privado. El artifact de Claude con la web resumen no se ha republicado:
el enlace existente no refleja esta versión.

## Verificación

Suite inicial: 834 comprobaciones, 80 omitidas por condiciones del entorno y
dos fallos corregidos durante esa ejecución. Se repitieron los bloques afectados
sobre el código final: DiffusionGemma 67/67 y exportación 17/17. Una corrida
completa posterior registró 836 comprobaciones con un error puntual ambiental
(`site/data/meta.json` ausente tras una regeneración del sitio interrumpida),
resuelto al regenerarla — bloques afectados 59/59; esa corrida no cuenta como
suite en verde. La suite completa final sobre el árbol de la versión termina
con exit 0: 822 comprobaciones, 80 omitidas por el entorno (los tests de
borradores ajenos, no versionados, estaban fuera del árbol). También pasan
GT v5 (4), auditorías (15), paridad ES/EN (28), sitio (33) y versión (2).
Las 12 auditorías verifican en privado y `python3 -m jevbench.publish` las
repite dentro del snapshot público antes de subirlo. Los 3492 JSON originales
mantienen sus hashes después de los tests.
