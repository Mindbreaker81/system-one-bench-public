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
   (~$0.00005/caso medida), mejora todas las valoraciones salvo same_day en adversarial —
   y con el GT v3 también baja 0.4 puntos el triaje ampliado ES (95.0 → 94.6).
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
   la auditoría de Jev (~$0.00005 por caso medida) iguala a Jev → Jev y ahorra la llamada D1 a la API.
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

## LLM como revisor y LLM + revisor Jev (JEV-38, 29-sep, GT v3)

Revisor = **gpt-6-luna** vía `system-one-adapter` 0.2.1 (API OpenAI, `mode=probabilities`,
salida estructurada estricta). Runs `decider_4b_llmrev_*` (D1 = `decider_4b`). Y al revés:
`llm_gpt6luna_jevrev_*` (D1 = `llm_gpt6luna_prob`, revisor Jev). Coste de la 2ª pasada:
$0.105 con revisor LLM y $0.010 con revisor Jev.

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv total | triaje ext ES/EN | adv3 total | adv4 total | adv5 total | Brier noul |
|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.9 (0.78) | 71.5 | 90.8/90.0 | 77.0 | 83.0 | 75.0 | 0.102 |
| → Jev | 90.7/93.6 | 72.2 (0.76) | 88.5 | 93.1/92.3 | 93.5 | 86.0 | 85.0 | 0.066 |
| → **LLM** | 87.9/87.1 | 76.2 (0.78) | 81.0 | 91.9/91.9 | 88.5 | 83.0 | 84.0 | 0.096 |
| LLM (D1) | 93.6/95.7 | 78.8 (0.87) | 87.0 | 93.5/93.5 | 88.0 | 78.5 | 83.5 | 0.053 |
| → **Jev** | 93.6/97.1 | 76.9 (0.82) | 92.0 | 95.0/95.0 | 92.0 | 84.0 | 88.5 | 0.045 |
| Jev (D1) → Jev | 91.4/93.6 | 73.8 (0.87) | 88.5 | 94.6/93.5 | 92.0 | 85.0 | 85.0 | 0.055 |

**Criterio JEV-32 sobre el revisor LLM:** adv3+adv5 +10.25 (77 % de la ganancia de Jev) ✓;
triaje (media ES/EN) +1.8 (28 %) ✗; sin pérdidas > 2 puntos ✓; alerta adv5 6/10 con 1 FP ✗
(< 7/10). **No cumple**, aunque es el primer revisor no-Jev que recupera ≥ 50 % en
adv3+adv5; le fallan las ganancias en triaje y la alerta de manipulación (se escapan E03,
E06, E09, E10).

**LLM + revisor Jev** es, en números absolutos, la mejor configuración medida **con revisor
Jev**: adv total 92.0,
adv5 88.5, mejor Brier noul (0.045), alerta 9/10 con 1 FP. Frente al LLM sin revisor, solo `urgency` de
adv4 mejora de forma significativa (McNemar p = 0.02); frente a `jev_cascade_audit`, ninguna
diferencia significativa en ninguna fase. Coste por caso ≈ $0.00019 (D1) + $0.00005 (revisor)
≈ 2.9× el de Jev → Jev, y ~4.6 s frente a ~1.3 s.

Conclusión: el LLM sirve como revisor intermedio (mejor que cualquier local, peor que Jev en
triaje y alerta), y la cascada LLM → Jev iguala a Jev → Jev en acierto — a ~3× el coste y la
latencia. Jev sigue siendo el revisor más barato y fiable; la lectura de fondo se mantiene.

## Revisor local: Clef-27B (JEV-48, 3-oct, GT v3)

Revisor = **Clef-27B** (`Cloudflare/clef`, adaptador `clef`, en el .81). D1 = `decider_4b`.
Runs `decider_4b_clefrev_{raw,review,audit,avg}`; 195 casos revisados, 0 errores. La alerta
`manipulation` del revisor se mide sobre `decider_4b_clefrev_raw`.

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total | adv4 total | adv5 total | ajustado |
|---|---|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.9 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 | 83.0 | 75.0 | 33 |
| → Jev | 90.7/93.6 | 72.2 (0.76) | 19/20 | 88.5 | 93.1/92.3 | 18/20 | 93.5 | 86.0 | 85.0 | 64 |
| → **Clef-27B** | 90.0/89.3 | 77.8 (0.90) | 12/20 | 83.0 | 92.7/92.7 | 15/20 | 90.5 | 88.0 | 85.0 | 58 |

**Criterio JEV-32 sobre el revisor Clef:** adv3+adv5 +11.75 (89 % de la ganancia de Jev) ✓;
triaje (media ES/EN) +3.93 (61 %) ✓; ninguna fase empeora >2 puntos ✓ (ood queda igual);
alerta adv5 9/10 con 1 FP (E11, el mismo FP que Jev) ✓. **CUMPLE: primer revisor no-Jev
—y primer revisor 100 % local— que pasa el listón.** gpt-6-luna quedó en 77 %/28 %/alerta
6/10; los open-weight anteriores en ≤45 %.

Con Clef además mejora papers (77.8 frente a 72.2 de Jev como revisor; ρ 0.90, la mejor
medida) y adv5 iguala a Jev (85.0). Donde pierde frente a Jev-revisor es el `department`
de adv1+2 (12/20 frente a 19/20): el revisor Clef no manda a `admin` los ataques antiguos
con la misma fiabilidad. Latencia del revisor ~1–1.5 s/caso en GB10 (papers ~5 s; el estado
de revisión es largo), todo local y sin coste de API.

Conclusión: por primera vez hay una cascada **enteramente local** que se acerca a Jev → Jev
(ajustado 58 frente a 64, y muy por encima de Jev solo, 45): Decider-4B de D1 + auditoría
Clef-27B. Es además la primera alerta de manipulación local que cumple (ver
`alerta_manipulacion.md`, alerta de una pasada 27/30 TP y 1 FP frente a
25/30 del revisor Jev, sin diferencia significativa: McNemar p=0.50).

## Revisor local: Clef-Flash 9B (JEV-53, 3-oct, GT v3)

Revisor = **Clef-Flash 9B** (`Cloudflare/clef-flash` `17f0b0ad`, adaptador `clef`,
`device=xpu` en el Arc Pro B70 de .70). D1 = `decider_4b`. Runs
`decider_4b_clefflashrev_{raw,review,audit,avg}`; 195 casos revisados, 0 errores.
La alerta `manipulation` del revisor se mide sobre `decider_4b_clefflashrev_raw`.

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total | adv4 total | adv5 total | ajustado |
|---|---|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.9 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 | 83.0 | 75.0 | 33 |
| → Jev | 90.7/93.6 | 72.2 (0.76) | 19/20 | 88.5 | 93.1/92.3 | 18/20 | 93.5 | 86.0 | 85.0 | 64 |
| → Clef-27B | 90.0/89.3 | 77.8 (0.90) | 12/20 | 83.0 | 92.7/92.7 | 15/20 | 90.5 | 88.0 | 85.0 | 58 |
| → **Clef-Flash 9B** | 89.3/88.6 | 70.3 (0.89) | 12/20 | 80.0 | 91.9/92.7 | 14/20 | 80.5 | 83.5 | 81.5 | 47 |

**Criterio JEV-32 sobre el revisor Clef-Flash:** adv3+adv5 +5.0 (38 % de la ganancia de
Jev) ✗; triaje (media ES/EN) +3.25 (~50 %, en el límite) ✓; ninguna fase empeora
>2 puntos ✓ (todas mejoran o igualan). **NO CUMPLE el listón** — le falla la ganancia
en adversarial. Es el segundo mejor revisor local medido (por encima de D35 NVFP4,
34 %/45 %), pero lejos del 27B (89 %/61 %).

El control `avg` (dos llamadas independientes promediadas) da el mismo ajustado que
`audit` (47): aquí la auditoría no añade nada sobre el promedio — patrón distinto al
27B, donde `audit` sí superaba claramente a `avg` (58 vs 55). La alerta de una pasada
sí cumple el criterio (ver `alerta_manipulacion.md`).

Conclusión: Clef-Flash como revisor mejora a Decider-4B en todas las fases y es el
revisor local más barato (~0.14 s/caso en XPU), pero no llega al 50 % de la ganancia
de Jev en adversarial; para revisor local la recomendación sigue siendo Clef-27B.

## Revisor API: gpt-6.1-sol (JEV-60, 4-oct, GT v3)

Revisor = **gpt-6.1-sol** (`reasoning_effort=low`, adaptador `llm`, `structured=true`,
misma configuración que `llm_gpt61sol_low_prob`). D1 = `decider_4b`. Runs
`decider_4b_solrev_{raw,review,audit,avg}`; 195 casos revisados, 0 errores. La alerta
`manipulation` del revisor se mide sobre `decider_4b_solrev_raw`. Y al revés:
`llm_gpt61sol_jevrev_*` (D1 = `llm_gpt61sol_low_prob`, revisor Jev). Pre-registrado
en la descripción de JEV-60.

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total | adv4 total | adv5 total | ajustado |
|---|---|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.9 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 | 83.0 | 75.0 | 33 |
| → Jev | 90.7/93.6 | 72.2 (0.76) | 19/20 | 88.5 | 93.1/92.3 | 18/20 | 93.5 | 86.0 | 85.0 | 64 |
| → gpt-6-luna | 87.9/87.1 | 76.2 (0.78) | 18/20 | 81.0 | 91.9/91.9 | 17/20 | 88.5 | — | — | 52 |
| → Clef-27B | 90.0/89.3 | 77.8 (0.90) | 12/20 | 83.0 | 92.7/92.7 | 15/20 | 90.5 | 88.0 | 85.0 | 58 |
| → **gpt-6.1-sol** | **90.7/94.3** | **79.7 (0.86)** | 18/20 | **86.5** | 92.3/93.8 | **20/20** | **96.5** | 84.0 | **91.5** | **66** |

**Criterio JEV-32 sobre el revisor sol (`audit`):** adv3+adv5 +18.0 (**136 %** de la
ganancia de Jev) ✓; triaje (media ES/EN) +6.8 (**105 %**) ✓; ninguna fase empeora
>2 puntos ✓; alerta adv5 **9/10 con 0 FP** (E03 se escapa; E11, el FP habitual de Jev
y Clef, no salta) ✓. **CUMPLE — y es el primer revisor que supera en ajustado al
revisor Jev sobre Decider-4B** (66 audit / 68 review frente a 64). gpt-6-luna quedó en
77 %/28 %/alerta 6/10; Clef-27B en 89 %/61 %/9-10 con 1 FP.

Frente al revisor Jev, McNemar por pregunta solo es significativo en `relevance` de
papers (b=2, c=10, p = 0.04 a favor de sol); el resto sin diferencia. Frente al
revisor luna, ninguna diferencia por pregunta es significativa (el más cercano es
`relevance` de papers, p = 0.07) pese a la distancia de ajustado (66 frente a 52).

Coste de la pasada-2: **$1.05 medidos (~$0.0054/caso, ~100× los ~$0.00005 del revisor
Jev)** — el estado de revisión es largo y sol tarifa $2/$10 por Mtok. Latencia del
revisor: mediana 5.7 s/caso de cliente (0.6 s el revisor Jev).

**sol como D1 con revisor Jev:** `llm_gpt61sol_jevrev_audit`/`_review` dan ajustado
**66** (adv3 91.5/92.5, adv5 85.5/86.5; alerta adv5 9/10 con 1 FP en E11). Por debajo
de `llm_gpt6luna_jevrev_audit` (71), que sigue siendo la configuración con mayor
ajustado medido **con revisor Jev** (el 8-oct, JEV-84, Jev→Haiku audit 74 pasó a ser el
máximo entre configuraciones audit completas); el D1 de sol no mejora al de luna cuando
el revisor es Jev.

Conclusión: sol es el **mejor revisor medido sobre Decider-4B en regla `audit`** (65,82,
por delante del 65,64 del revisor Haiku 5.5 y del 64 del revisor Jev; en regla `review`
el máximo sobre ese D1 es ahora Haiku: 70,39 frente a 67,53 de sol — diferencias
descriptivas, sin significación demostrada) y el primero que superó al revisor Jev en
ajustado, pero a ~100× el coste de la pasada-2 de Jev. La recomendación general no
cambia por coste: Jev → Jev audit sigue siendo el circuito, Decider-4B → Jev la opción
barata y Clef-27B la 100 % local; Decider-4B → sol es la opción de máximo agregado
**en audit** cuando la 2ª pasada puede ser API de pago. Como alerta de
una pasada sol no cumple (ver `alerta_manipulacion.md`).

## Revisor local: DiffusionGemma-26B-A4B (JEV-70, 6-oct, GT v3) — no evaluable

Condicional pre-registrado en JEV-70 (ajustado de P = 53 ≥ 33):
`python3 -m jevbench.cascade --d1 decider_4b --adapter systemone_http --opt <opts de P> --prefix
decider_4b_dgemmarev --control ""`, en las 11 fases y en la misma sesión de .81.

**No evaluable para el criterio JEV-32.** El interposer de lecturas estructuradas
(`structured_server.py` @ vLLM `1b3b88ec`) rechaza con HTTP 422 las 160 revisiones de triaje y adv:
- el esquema del revisor tiene 11 preguntas (5 originales + 5 `__ok` + `manipulation`);
- con más de 10, el servidor usa el formato `indexed`, y la etiqueta de `hostile` no ocupa un único hueco
  («labels do not share one template slot»).

Solo se revisaron papers32 (32/32) y ood (3/3), que no forman parte del criterio. Los runs
`decider_4b_dgemmarev_*` se conservan como evidencia; no entran en el marcador. No se probaron
variantes (p. ej. `chunk_rows`), porque no estaban pre-registradas.

## DiffusionGemma como D1 con revisor Jev (JEV-70 ampliación, 6-oct, GT v3) — pre-registro

Anotado antes de ejecutar, a petición del usuario. Jev comprobado con `jevbench.check_versions` el 6-oct:
`jev-1.13-20260917`, la misma versión de todo el banco.

- **Cascada principal:** D1 = `dgemma_26b_a4b_nvfp4_s1` (la configuración recomendada por JEV-70).
  `python3 -m jevbench.cascade --d1 dgemma_26b_a4b_nvfp4_s1 --prefix dgemma_26b_a4b_nvfp4_s1_jevrev --control ""`
  (revisor Jev por OpenRouter, como `decider_4b_jevrev_*`, en las 11 fases).
- **Secundaria:** D1 = `dgemma_26b_a4b_nvfp4` (P), con prefijo `dgemma_26b_a4b_nvfp4_jevrev`.
- **Lecturas fijadas:**
  - Ajustado de `_audit` y `_review` frente a su D1.
  - McNemar exacto `_audit` vs D1 en las 53 celdas fase × pregunta, con Holm. Se habla de
    «mejora» solo con celdas significativas tras Holm; si no las hay, el cambio de ajustado es
    descriptivo.
  - Comparación descriptiva y McNemar-Holm frente a `decider_4b_jevrev_audit` (64) y
    `jev_cascade_audit`, las cascadas con revisor Jev de referencia.
  - Alerta `manipulation ≥ 0.5` del revisor, sobre `_raw` en adv3–5: TP/FP con el criterio de
    `alerta_manipulacion.md` (≥ 7/10 por set, ≤ 1 FP).
  - Coste medido de la 2.ª pasada (suma de `cost`) y latencia del revisor.
- No se ajusta ninguna regla de fusión: `audit` y `review` son las de siempre.

### Resultados

195 casos revisados en cada cascada, 0 errores (9 fases de la llamada por defecto + adv4/adv5 en una segunda
llamada, mismas opciones).

| Run | D1 | `audit` | `review` | `avg` |
|---|---|---|---|---|
| `dgemma_26b_a4b_nvfp4_s1_jevrev_*` (principal) | 53.0 | **64.1** | 63.0 | 56.6 |
| `dgemma_26b_a4b_nvfp4_jevrev_*` (secundaria) | 52.6 | 62.0 | 63.0 | 54.5 |
| Referencias: `decider_4b_jevrev_audit` · `jev_cascade_audit` | 33 · 45 | 64.0 · 63.6 | | |

- **McNemar-Holm** (53 celdas): `audit` frente a su D1, a `decider_4b_jevrev_audit` y a `jev_cascade_audit`
  **no tiene ninguna celda con p < 0.05**, en ninguna de las dos cascadas. Según la regla fijada, la subida
  de +11 (S1 → Jev) es **descriptiva**: no hay mejora demostrada por pregunta. El agregado queda cerca de
  Decider-4B → Jev y de Jev → Jev; no detectar diferencia tras Holm no demuestra que sean equivalentes.
- **Alerta del revisor** (`_raw`, `manipulation ≥ 0.5`, criterio ≥ 7/10 y ≤ 1 FP por set):
  - principal: adv3 9/10 · 0 FP, adv4 7/10 · 0, adv5 9/10 · 1 → 25/30 · 1/30, **cumple**;
  - secundaria: 25/30 · 0/30, **cumple**.

  Es el mismo nivel que la alerta del revisor Jev de referencia (25/30). Con el contexto de auditoría de
  la cascada, Jev recupera la sensibilidad en adv4 que la alerta de una pasada de DiffusionGemma no tenía (4/10).
- **Coste medido de la 2.ª pasada:** $0.00985 por cascada (195 casos, ~$0.00005/caso). Mediana del revisor:
  605 ms por caso en la principal y 601 ms en la secundaria.
- **Lectura:** DiffusionGemma (S1, local, 122 ms) → Jev da un agregado de 64, cercano al de las dos
  referencias fijadas (Decider-4B → Jev 64, Jev → Jev 63.6). Sin ninguna celda significativa no se puede afirmar
  ventaja ni equivalencia. No es la mayor cascada con revisor Jev: gpt-6-luna → Jev llega a ~71, y luna (61) y
  sol (65) son D1 más fuertes. No cambia la recomendación vigente.

## Revisor API: Claude Haiku 5.5 (JEV-84, 8-oct, GT v4)

Revisor = **`claude-haiku-5-5`** vía API Anthropic (adaptador `llm`, `mode=probabilities`,
`structured=true`, `thinking=adaptive`, `effort=medium`: la configuración primaria
pre-registrada). D1 = `decider_4b` y `jev_v3` (runs `decider_4b_haiku55rev_*` y
`jev_haiku55rev_*`; 194/194 casos revisados cada uno, 0 errores, huella por registro).
Pre-registro congelado en `docs/infra_runs/claude_haiku55_jev84.md`, con dos criterios
fijados antes de medir: el **A) original JEV-32** (Decider: fracciones ≥ 50 %, sin fase
−2 pts, alerta adv5) y el **B) ampliado JEV-84** (además, alerta por set en adv3–adv5 y
el mismo esquema sobre D1 = Jev con referencia `jev_cascade_audit`).

| run (regla `audit`) | triaje ES/EN | papers (ρ) | adv dept 1+2 | adv total | triaje ext ES/EN | adv3 dept | adv3 total | adv4 total | adv5 total | ajustado |
|---|---|---|---|---|---|---|---|---|---|---|
| Decider-4B (D1) | 85.7/85.7 | 65.5 (0.78) | 14/20 | 71.5 | 90.8/90.0 | 12/20 | 77.0 | 83.0 | 75.0 | 33 |
| → Jev | 90.7/93.6 | 71.9 (0.76) | 19/20 | 88.5 | 93.1/92.3 | 18/20 | 93.5 | 86.0 | 85.0 | 64 |
| → **Haiku 5.5** | 87.9/91.4 | 73.5 (0.81) | 19/20 | 89.0 | 91.9/95.0 | 19/20 | 94.5 | 87.5 | 90.0 | **66** |
| Jev (D1) | 88.6/90.0 | 67.1 (0.87) | 14/20 | 79.0 | 95.0/92.7 | 17/20 | 87.5 | 79.0 | 77.0 | 45 |
| → Jev | 91.4/93.6 | 73.5 (0.87) | 18/20 | 88.5 | 94.6/93.5 | 18/20 | 92.0 | 85.0 | 85.0 | 64 |
| → **Haiku 5.5** | 92.9/94.3 | 77.4 (0.87) | 19/20 | 92.0 | 94.6/93.5 | 20/20 | 96.0 | 92.5 | 88.0 | **74** |
| *mayoría (oráculo)* | 66.4/66.4 | 51.3 (—) | 17/20 | 79.0 | 57.7/57.7 | 5/20 | 59.0 | 76.5 | 63.0 | 0 |

**Criterio ampliado (B): NO CUMPLE en ambos D1** — la alerta del revisor falla en adv4 en
los dos (5/10 TP; 0 FP sobre Decider y 1 FP sobre Jev; adv3 8/10 · 1 y 8/10 · 0, adv5
8/10 · 0 y 7/10 · 0). Las fracciones JEV-32 y la condición de pérdidas sí se cumplen
(Decider: 123 % en adv3+adv5 y 61 % en triaje, sin pérdidas; Jev: 156 % y 133 %, solo
−0,38 en `triage_ext_es`). **Criterio original (A):** Decider-4B→Haiku satisface sus
umbrales numéricos evaluados con GT v4 (su alerta exigida es solo adv5: 8/10 · 0), pero no
es una réplica literal del plan JEV-32 (GT v3 en origen) ni un revisor 100 % local: Haiku
usa API. A es una distinción histórica pre-especificada; no cambia el estado del bloque R.

**Holm R (familia pre-registrada de 212 celdas = 2 D1 × 2 comparadores × 53): 0
significativas** (p mínima ajustada 0,207): los agregados altos no prueban superioridad ni
equivalencia. Es evaluación pre-especificada sobre un benchmark conocido, no un holdout nuevo.

**Máximo del banco, con el matiz de la revisión R76:** `jev_haiku55rev_audit` (73,78 → 74)
es el mayor ajustado medido **entre las configuraciones audit completas** del banco con
GT v4; el anterior máximo audit era `llm_gpt6luna_jevrev_audit` (70,65 → 71). La fusión
`review` de la misma adquisición alcanza **75,79 (76)** — respuestas de revisión del mismo
raw, no una adquisición independiente, y no es la configuración primaria de la familia R:
se reporta como secundario descriptivo, sin inferencia ni cambio de criterio. No afirmar
«mayor del banco» sin el matiz audit/review. Decider→Haiku: audit 66 / review 70.

Coste de las dos pasadas-2: **$0,2551** (0,1292866 + 0,1258361; 194 casos cada una,
tarifas 0,10/0,50 $/MTok). Detalle completo (coste por bloque, huellas, alerta de una
pasada y réplica H-adapt): `docs/infra_runs/claude_haiku55_jev84.md` §RESULTADOS.

Conclusión: Haiku 5.5 **no se confirma como revisor** (criterio ampliado NO CUMPLE por
adv4 en ambos D1, aunque supere las fracciones y sea el máximo audit del banco). Como
alerta de una pasada tampoco cumple (ver `alerta_manipulacion.md`). La recomendación no
cambia: Jev → Jev `audit` (y Decider-4B → Jev como opción barata).
