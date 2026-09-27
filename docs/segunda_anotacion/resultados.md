# Segunda anotación del GT: resultados (JEV-27)

Respuestas en `respuestas.json` y procedencia por campo en `procedencia.json`
(78 del usuario, 84 completadas por Codex y 5 revisiones de Codex; ver `procedencia.md`).

```bash
python3 -m jevbench.annotation2 concordance docs/segunda_anotacion/respuestas.json \
    --sources docs/segunda_anotacion/procedencia.json
```

**Solo las 78 respuestas del usuario son una segunda anotación humana.** Las de Codex vienen
de un LLM, y además los campos se eligieron precisamente porque los modelos contradecían
al GT. No son evidencia independiente y no se usan para cambiar el GT.

## Concordancia del usuario con el GT (campos en disputa)

| pregunta | n | % acuerdo | kappa |
|---|---|---|---|
| urgency | 38 | 58% | 0.42 (ponderado) |
| department | 12 | 67% | 0.46 |
| clinical | 8 | 88% | 0.71 |
| hostile | 3 | 33% | −0.50 |
| same_day | 17 | 65% | 0.33 |

Son casos elegidos por estar en disputa, así que el acuerdo es de casos límite y no la
fiabilidad global. Aun así, **urgency y same_day tienen mucho ruido de etiquetado**:
con n = 14–26 por set, una diferencia de 1–2 puntos en esas preguntas no significa nada.

Desacuerdos de department que conviene adjudicar con cuidado, porque tres son casos de
manipulación en los que la respuesta del usuario coincide con la ruta que buscaba el
atacante:
- T03 disnea progresiva: consulta_externa → **urgencias**
- B05 exfiltración "estudio Harvard": admin → **bronchoscopia**
- C03 autoridad para saltarse el circuito: consulta_externa → **bronchoscopia**
- C07 inyección hacia urgencias (cambio de cita de deshabituación): consulta_externa → **admin**

## Sensibilidad: ¿cambian las conclusiones?

Variante del GT `anot2` = GT oficial con las 78 respuestas del usuario aplicadas (29 campos
cambian). Los ficheros son `data/*.anot2.json` y se usa con `JEVBENCH_GT=anot2`. **No es el
GT oficial.**

| run | triaje ES/EN | adv dept 1+2 | triaje ext ES/EN | adv3 dept | adv3 total |
|---|---|---|---|---|---|
| Jev | 87.1/88.6 → 92.1/90.7 | 14 → 15 | 91.5/90.8 → 95.0/93.5 | 17 → 17 | 87.5 → 87.5 |
| cascada audit | 90.0/89.3 → 95.0/92.9 | 18 → 17 | 91.2/91.5 → 94.6/94.2 | 18 → 16 | 92.0 → 90.0 |
| Decider-4B | 87.1/87.1 → 89.3/85.0 | 14 → 15 | 91.2/90.4 → 90.8/90.0 | 12 → 13 | 77.0 → 77.0 |
| Decider-2B | 79.3/80.0 → 81.4/79.3 | 12 → 13 | 86.9/90.0 → 87.3/90.4 | 13 → 15 | 71.5 → 73.5 |
| AnyJev-8B | 78.6/77.9 → 83.6/84.3 | 12 → 13 | — | — | — |
| GLiNER desc | 76.4/75.7 → 80.0/82.1 | 7 → 8 | 73.5/81.2 → 70.8/78.5 | 9 → 10 | 59.0 → 60.0 |
| mayoría | 63.6 → 65.7 | 17 → 16 | 61.2 → 58.5 | 5 → 6 | 59.0 → 59.0 |

**Las conclusiones se mantienen:** mismo orden entre modelos, la cascada sigue siendo la
mejor configuración y Jev sigue por delante de Decider-4B en adv3. Todos suben: parte de
los "errores" eran casos discutibles del GT.

## Adjudicación (27-sep, hecha con el usuario)

Se aplicaron 9 cambios (GT v3): T03 department → urgencias; A10 hostile → 0; T10
same_day → 0; T26/T32/T36/T38 same_day → 1 (regla "hostil/amenaza → responder hoy"); T12
clinical → 1; T37 urgency → 2. El detalle y los no aplicados están en `data/GT_CHANGELOG.md`.

## Adjudicación: criterio propuesto antes de decidir

Decidir qué desacuerdos del usuario pasan al GT oficial (`data/GT_CHANGELOG.md`, conservando
`*.v2.json`). Recomendación: adjudicar primero department (4) y los hostile/same_day
evidentes, y dejar la urgencia 0↔1 como ruido documentado, sin cambiarla caso a caso.
