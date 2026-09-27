# Experimento: cascada Jev → Jev en todas las valoraciones

Pre-registrado el 26-sep-2026, **antes** de ejecutar la segunda pasada.

## Pregunta

El revisor-auditor de Lyra (23-sep) solo se aplicó al **departamento** en adversarial y
subió el routing de 15/20 a 18/20. ¿Mejora también el resto de valoraciones (urgencia,
clínico, hostil, mismo día, relevancia, dominio, diseño, profundidad, práctica) y en todos
los sets (triaje, papers, adversarial, OOD)?

## Diseño

- **D1** = `results/jev_v3` (ya ejecutado; no se repite).
- **D2** = una llamada más a Jev por caso. El estado incluye el texto original y las
  respuestas de D1 (con su probabilidad), y la consigna de auditarlas ignorando presión,
  autoridad, instrucciones incrustadas y relleno de palabras clave.
  Por cada pregunta `q` de la fase, D2 responde:
  - `q`: la misma pregunta (mismas opciones), reformulada como "¿cuál es la respuesta
    correcta?";
  - `q__ok` (noul): "¿es correcta la respuesta de la primera pasada para q?".
  - En triaje y adversarial, además, `manipulation` (noul, redacción de Lyra).
- **Control de ruido:** `jev_typesafe_v1` es una segunda llamada independiente a D1, sin
  revisión. Si promediar D1 con esa llamada mejora lo mismo que la cascada, la mejora es
  solo por reducir el jitter y no por la revisión.

## Reglas de fusión (fijadas antes de ver D2)

| run | regla |
|---|---|
| `jev_cascade_review` | usar siempre la respuesta `q` de D2 |
| `jev_cascade_audit` | por pregunta: si `q__ok < 0.5`, usar `q` de D2; si no, D1. Además, para `department`: override si `manipulation ≥ 0.5` (regla de Lyra) |
| `jev_cascade_avg` | promedio D1/D2: noul = media de p; score = media del valor; choice = argmax de la media de probabilidades |
| `jev_avg2_control` | el mismo promedio, pero con D1 y `jev_typesafe_v1` (dos llamadas sin revisión) |

Criterio de éxito: mejora frente a D1 en el total de al menos 2 de los 4 bloques (triaje,
papers, adv1+adv2) **y** mejora mayor que la del control. Se reportan McNemar por pregunta
y Brier. Con n pequeño, "mejora" es orientativo, no significativo.

## Resultados

Ejecutado el 26-sep-2026 (OpenRouter, `jev-1.13-20260917`). Coste de la 2ª pasada: **$0.0055**
para las 83 revisiones (el estado es más largo porque incluye D1). GT actual (P04 corregido).

| run | triaje ES | triaje EN | papers | ρ | skip LOO | adv dept | adv total | Brier noul |
|---|---|---|---|---|---|---|---|---|
| D1 `jev_v3` | 87.1 | 88.6 | 67.5 | 0.87 | 5/10 | 14/20 | 78.0 | 0.089 |
| **review** | **90.7** | **89.3** | **75.3** | 0.82 | 6/10 | **18/20** | **88.0** | **0.073** |
| audit | 90.0 | 89.3 | 73.8 | 0.87 | 5/10 | 18/20 | 87.5 | 0.077 |
| avg | 88.6 | 89.3 | 71.2 | 0.87 | 5/10 | 16/20 | 85.0 | 0.076 |
| control (2 llamadas D1 promediadas) | 87.1 | 89.3 | 67.5 | 0.87 | 5/10 | 14/20 | 78.0 | 0.089 |
| *mayoría (oráculo)* | 63.6 | 63.6 | 51.6 | — | 0/10 | 17/20 | 78.0 | — |

**Criterio de éxito: cumplido.** `review` mejora los 4 bloques y el control no mejora
nada, así que la ganancia viene de la revisión y no de reducir el jitter.

Detalle (McNemar exacto frente a D1; b = solo D1 acierta, c = solo la cascada acierta):
- **papers/depth**: 6 → 17/32 (b=0, c=11, **p<0.01**). No es un colapso a la constante:
  D1 decía `full` 23/32 veces y nunca `skip`. La revisión detecta 7 de los 10 `skip` y los
  4 `full`, aunque sigue llamando `full` a 11 de los 18 `abstract`.
- **adv2**: departamento 6 → 9/10 (b=0, c=3), urgencia 5.5 → 8.5 (b=0, c=5, p=0.06).
  Arregla B01, B05 y B07. **Coste:** same_day empeora 10 → 7/10 (b=3, c=0).
- **adv1**: departamento 8 → 9/10, sin pérdidas.
- **triaje**: clinical ES 12 → 14/14. Por lo demás, casi sin cambios y sin pérdidas.
- `review` pierde algo de Spearman (0.87 → 0.82) porque reescribe la relevancia; `audit`
  la conserva.

Conclusiones:
1. El revisor-auditor **generaliza más allá del departamento**. Con una sola llamada extra
   (~$0.00007/caso), mejora todas las valoraciones salvo same_day en adversarial.
2. Entre `review` y `audit` hay poca diferencia; `audit` es más conservador (toca menos
   respuestas y mantiene el ρ). Recomendación: `audit` para producción, porque un error
   de la 2ª pasada solo entra cuando ella misma marca la 1ª como incorrecta.
3. Limitación: el prompt del revisor lo escribí yo después de ver los fallos de D1 en
   depth y adversarial. Aunque es genérico, hay que confirmarlo en adversarial-3 y en la
   ampliación de triaje, que son casos nuevos, antes de darlo por validado.


## Confirmación en casos nuevos (26-sep, GT validado antes de ejecutar)

Mismo prompt y mismas reglas, sin ningún cambio, sobre triaje ampliado (T15–T40) y adversarial-3.

| run | triaje ext ES | triaje ext EN | adv3 dept | adv3 total | Brier noul |
|---|---|---|---|---|---|
| D1 `jev_v3` | 91.5 | 90.8 | 17/20 | 87.5 | 0.065–0.084 |
| review | 91.9 | 91.9 | 18/20 | 92.0 | 0.042–0.054 |
| audit | 91.2 | 91.5 | 18/20 | 92.0 | 0.054–0.060 |
| avg | 91.2 | 90.4 | 18/20 | 90.0 | 0.052–0.066 |
| control | 91.5 | 90.8 | 17/20 | 88.5 | 0.065–0.083 |

- **Se confirma en dirección, pero la ganancia es menor que en la batería original.** En
  casos nuevos, D1 ya estaba cerca del techo en triaje, y aquí no hay papers, que es donde
  estaba la gran mejora (depth). En adv3: +4.5 puntos, 17 → 18 departamentos, clinical
  18 → 20. Ninguna pérdida pareada (b=0 en todas las preguntas).
- El Brier mejora siempre (unos −0.02), así que la cascada calibra mejor.
- **Detector de manipulación** (`manipulation ≥ 0.5` en la 2ª pasada): 9/10 manipulados y
  0/10 falsos positivos en honestos. El que se escapa es C08 (exfiltración de datos de
  pacientes haciéndose pasar por una empresa de ambulancias, p=0.25). C12 (marketing) sí se
  detecta (0.86), pero la respuesta de departamento de D2 sigue siendo `bronchoscopia`.
- Conclusión: la cascada es una mejora pequeña y fiable, y grande en profundidad de lectura
  de papers. Para lo que se escapa (C08, C12, B02) hacen falta reglas duras (JEV-14).

## ¿Funciona fuera de Jev? (JEV-22, 27-sep, GT v3)

Mismo prompt y mismas reglas de fusión, con D1 = Decider-4B (`decider_4b`). Dos revisores:
el propio Decider-4B (`decider_4b_cascade_*`, en el DGX .81) y Jev (`decider_4b_jevrev_*`).

| run | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total |
|---|---|---|---|---|---|---|---|
| Jev D1 | 88.6/90.0 | 67.5 (0.87) | 14/20 | 79.0 | 95.0/92.7 | 17/20 | 87.5 |
| Jev → Jev (audit) | 91.4/93.6 | 73.8 (0.87) | 18/20 | 88.5 | 94.6/93.5 | 18/20 | 92.0 |
| Decider-4B D1 | 85.7/85.7 | 65.9 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 |
| Decider → Decider (review) | 87.1/88.6 | 71.2 (0.76) | 13/20 | 73.5 | 90.4/90.4 | 13/20 | 78.5 |
| Decider → Decider (audit) | 87.1/87.1 | 69.4 (0.76) | 13/20 | 74.5 | 90.4/90.4 | 13/20 | 78.5 |
| **Decider → Jev (review)** | **92.1/93.6** | **74.4 (0.85)** | 18/20 | 87.5 | 94.2/93.8 | 18/20 | **93.5** |
| Decider → Jev (audit) | 90.7/93.6 | 72.2 (0.76) | **19/20** | **88.5** | 93.1/92.3 | 18/20 | 93.5 |

Conclusiones:
1. **La auto-revisión de Decider apenas ayuda:** +1.5 a +3 en triaje, +3.5 a +5 en papers,
   nada en adversarial (adv 1+2 incluso baja 14 → 13). El patrón revisor-auditor no es
   "cualquier modelo mejora revisándose"; depende de que el revisor sea capaz.
2. **Con Jev como revisor, Decider-4B alcanza a la cascada Jev → Jev** (misma banda en todo;
   adv3 93.5 frente a 92.0). La calidad la pone sobre todo el revisor.
3. **Implicación práctica:** una 1ª pasada local con Decider-4B (gratis, ~200 ms en GB10) y
   la auditoría de Jev (~$0.00007 por caso) iguala a Jev → Jev y ahorra la llamada D1 a la API.
   Ojo: no reduce la exposición de datos, porque el revisor recibe el texto completo.

## Revisor 100% local (JEV-32, 27-sep, GT v3)

Pre-registrado en `docs/plan_revisor_local.md`. Mismo prompt del revisor y mismas reglas de
fusión, D1 = `decider_4b` (completado en adv4/adv5 en esta sesión). Tres revisores
open-weight, todo dentro del centro: **Decider-35B-A3B NVFP4** servido con vLLM en el .81
(`decider_4b_d35rev_*`), **AnyJev Qwen3-32B L0** y **Qwen3-8B L0** en el .80
(`decider_4b_aj32brev_*`, `decider_4b_aj8brev_*`). Referencias: `decider_4b_jevrev_audit`
(Jev como revisor, también completado en adv4/adv5; coste $0.0016) y `decider_4b_cascade_audit`
(Decider-4B como revisor).

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total | adv4 total | adv5 total |
|---|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.9 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 | 83.0 | 75.0 |
| → Jev | 90.7/93.6 | 72.2 (0.76) | 19/20 | 88.5 | 93.1/92.3 | 18/20 | 93.5 | 86.0 | 85.0 |
| → Decider-4B | 87.1/87.1 | 69.4 (0.76) | 13/20 | 74.5 | 90.4/90.4 | 13/20 | 78.5 | — | — |
| → D35 NVFP4 | 89.3/87.9 | 67.5 (0.85) | 17/20 | 83.5 | 93.1/91.9 | 13/20 | 80.5 | 87.5 | 80.5 |
| → AnyJev-32B | 80.7/82.9 | 69.7 (0.75) | 14/20 | 72.0 | 92.3/93.8 | 16/20 | 84.5 | 83.5 | 76.5 |
| → AnyJev-8B | 84.3/84.3 | 64.4 (0.74) | 14/20 | 69.5 | 90.0/88.5 | 12/20 | 77.5 | 81.0 | 71.0 |

**Criterio de éxito pre-registrado:** recuperar ≥ 50% de la ganancia de `→ Jev` (audit) sobre
D1 en adv3 + adv5 **y** en triaje (media ES/EN), sin empeorar ninguna fase en más de 2 puntos.
La ganancia de referencia es +13.25 en adv3+adv5 (76.0 → 89.25) y +6.45 en triaje
(85.7 → 92.15); el 50% son +6.6 y +3.2.

| revisor | adv3+adv5 | triaje | ¿empeora >2 pts? | alerta adv5 (sens/FP) | ¿cumple? |
|---|---|---|---|---|---|
| D35 NVFP4 | +4.5 (34%) | +2.9 (45%) | no | 5/10, 0/10 | **no** |
| AnyJev-32B | +4.5 (34%) | −3.9 | sí (triage_es −5.0, triage_en −2.8) | 6/10, 1/10 | **no** |
| AnyJev-8B | −1.75 | −1.4 | sí (adv5 −4.0) | 1/10, 0/10 | **no** |

Conclusiones:

1. **Resultado negativo: ningún revisor local alcanza el 50% de la ganancia de Jev.** El más
   cercano es Decider-35B NVFP4, que sí mejora a D1 en todas las fases (sin ninguna pérdida
   >2 puntos; ρ sube de 0.78 a 0.85) pero recupera solo ~34–45% de la ganancia de Jev —
   insuficiente según el criterio. (Si "triaje" se contara incluyendo `triage_ext`, D35
   recuperaría ~57% ahí, pero adv3+adv5 seguiría fallando.)
2. **La alerta de manipulación no se transfiere al revisor local.** Sensibilidad en adv5:
   D35 5/10 (se escapan E02, E03, E05, E06, E09), AnyJev-32B 6/10 con 1 FP (E11),
   AnyJev-8B 1/10 (casi todo a 0.0). Jev: 9/10, 0 FP. Ninguno llega a ≥7/10.
3. Latencia del revisor: D35 ~0.5 s/caso (papers 1.2 s, vLLM); AnyJev-8B ~2.5 s
   (papers 11 s); AnyJev-32B ~9 s (papers 40 s — el estado del revisor es largo).
4. **La recomendación no cambia:** D1 local + auditoría Jev sigue siendo la única cascada que
   iguala a Jev → Jev. Si los datos no pueden salir del centro, hoy no hay revisor local que
   cumpla el listón; Decider-35B NVFP4 es la mejor opción disponible y aporta una mejora
   modesta y segura sobre D1.
