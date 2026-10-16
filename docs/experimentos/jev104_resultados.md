# JEV-104 — resultados: Jev 1.14 en réplica, rotación d1, cascada Jev→Jev y revisor de Decider-4B

Pre-registro: [`jev104_preregistro.md`](jev104_preregistro.md), congelado el 15-oct-2026 antes
de medir (commit 5084b65), con la enmienda E1 (guarda de coste de d1). Adquisición el
15-oct-2026 por la API de TypeSafe, alias `jev-preview`. En los runs de 1.14 (§1–§3), **todas** las
llamadas resolvieron a `jev-1.14.0`, con 0 errores (los de 1.13 de §1b, a `jev-1.13.0`). Salidas literales en [`jev104/`](jev104/).

Coste registrado (suma de `cases[*].cost`): r2 $0.0067, d1 $0.0067, 2ª pasada de la cascada
$0.0098 y 2ª pasada del revisor de Decider-4B $0.0098, las 11 fases (≈ $0.033 en las cuatro
adquisiciones de 1.14; ≈ $0.053 incluyendo los tres runs de 1.13 de E2). Ejecución
operativa: la cascada se lanzó primero con las fases por defecto, que no incluyen
adv4/adv5, y ese bloque se completó después con `--phases adv4,adv5`. Es la política de dos
bloques de §0; no cambia celdas ni reglas.

## 1. Réplica r2 y rotación d1

*(La tabla consolidada de todas las réplicas r2 del banco está en
[`repetibilidad.md`](repetibilidad.md).)*

| run | acuerdo (IC95) | primacía | Δ ajustado | Δp medio · máx | lectura |
|---|---|---|---|---|---|
| r2 (`_r2`) | 955/964 = **99,1 %** (98,2–99,6) | — | 50,3 → 49,8 (−0,5) | 0,007 · 0,12 | repetible, no determinista |
| d1 (`_d1`, con E1) | 951/964 = **98,7 %** (97,7–99,3) | **REFUTADA** (14 y 14 errores, Δ 0) | −1,0 (−4,1 a 1,7) | 0,009 · 0,21 | **estable** |

- A diferencia de los decisores locales de JEV-103, Jev 1.14 **no es determinista**: dos
  llamadas idénticas cambian 9 de 964 decisiones y mueven las probabilidades hasta 0,12.
- Rotar `department` cambia 13 de 964 decisiones, una cifra parecida a la del ruido entre
  llamadas (IC95 solapados). Según la regla de atribución fijada, esos cambios no se
  atribuyen al orden. La comparación con 1.13 está en §1b (extensión E2).

### 1b. Extensión E2: réplica y rotación de Jev 1.13 (mismo día, misma ruta)

Pedida por el usuario tras ver r2/d1 de 1.14 y pre-registrada antes de medir (commit
750d107). Jev 1.13 por TypeSafe `jev-latest`: todas las llamadas de los tres runs resolvieron
a `jev-1.13.0`, con 0 errores y $0.0067 por run.

| versión | base (ajustado) | r2: acuerdo (IC95) · Δp máx | d1: acuerdo (IC95) · Δp máx | primacía d1 | lectura d1 |
|---|---:|---|---|---|---|
| 1.13 (`jev_v113_typesafe`) | 50,3 | 957/964 = **99,3 %** (98,5–99,7) · 0,10 | 957/964 = **99,3 %** (98,5–99,7) · 0,27 | INCONCLUSA (15 y 15 errores) | acuerdo observado ≥ 97 %, primacía inconclusa |
| 1.14 (`jev_v114_typesafe_preview`) | 50,3 | 955/964 = **99,1 %** (98,2–99,6) · 0,12 | 951/964 = **98,7 %** (97,7–99,3) · 0,21 | REFUTADA (14 y 14 errores) | estable |

- **No se observa diferencia de acuerdos entre versiones** según la regla descriptiva de E2:
  los IC95 se solapan en r2 y en d1. Solapar no prueba equivalencia. Ninguna de las dos es
  determinista (7 y 9 cambios entre dos llamadas idénticas), y en las dos la rotación de
  `department` cambia un número de decisiones parecido al del ruido entre llamadas. Los
  dictámenes de primacía difieren: INCONCLUSA en 1.13 y REFUTADA en 1.14.
- La primacía de 1.13 sale INCONCLUSA y no REFUTADA porque en el subconjunto congelado hay un
  error que cambia en cada sentido (b = c = 1), lo que ensancha el IC95 (−8,1 a 8,1 pp). No
  indica sensibilidad al orden: el acuerdo es el mismo que el de la réplica.
- **Base 1.13 frente a base 1.14, mismo día y ruta** (Holm53, descriptivo): 15 preguntas solo
  las acierta 1.14 y 19 solo 1.13; menor p cruda 0,25, Holm 1. Los dos ajustados redondean a
  50,3 (50,297 y 50,287). Esta comparación adicional por la misma ruta y fecha tampoco
  detecta diferencias significativas entre versiones, pero no permite descartar efectos de
  ruta o de fecha en la comparación histórica con `jev_v3`.
  Salidas en `jev104/r2_v113.txt`, `d1_v113.txt`, `holm53_v114_vs_v113_typesafe.txt` y
  `summary_v113_typesafe.md`.

## 2. Cascada Jev→Jev con 1.14

D1 = `jev_v114_typesafe_preview`, revisor = Jev 1.14. Control = promedio de D1 con la r2
(dos llamadas sin revisión). GT v5.

| run | ajustado | triaje ES/EN | papers | adv1+2 total | triaje ext ES/EN | adv3 total | Brier noul |
|---|---:|---|---:|---:|---|---:|---:|
| *mayoría (oráculo)* | 0 | 66,4/66,4 | 51,9 | 80,0 | 57,7/57,7 | 55,5 | — |
| D1 1.14 | 50 | 87,1/88,6 | 76,8 | 81,5 | 93,5/95,0 | 90,0 | 0,062 |
| control (D1 + r2 promediados) | 51 | 87,1/90,0 | 76,8 | 81,5 | 93,8/95,0 | 90,0 | 0,061 |
| review | **68** | 90,0/93,6 | 83,9 | 92,0 | 94,2/95,4 | 92,0 | 0,044 |
| audit | 66 | 89,3/91,4 | 81,3 | 91,0 | 93,5/95,0 | 94,5 | 0,046 |
| avg | 61 | 89,3/94,3 | 80,6 | 87,5 | 94,2/95,0 | 92,5 | 0,049 |
| *ref.: Jev→Jev 1.13 audit* | 68 | 91,4/93,6 | 83,2 | 90,5 | 94,6/93,5 | 92,5 | 0,045 |

**a) Criterio de `cascada_jev.md`: cumplido.** En los 4 bloques, `review` y `audit` mejoran
a D1 más que el control, que solo mejora ligeramente en triaje y en casos nuevos:

| bloque | mayoría (oráculo) | D1 | control | review | audit |
|---|---:|---:|---:|---:|---:|
| triaje (media ES/EN) | 66,4 | 87,9 | 88,6 | 91,8 | 90,4 |
| papers32 | 51,9 | 76,8 | 76,8 | 83,9 | 81,3 |
| adv1+adv2 | 80,0 | 81,5 | 81,5 | 92,0 | 91,0 |
| casos nuevos (ext ES/EN + adv3) | 57,0 | 92,8 | 92,9 | 93,9 | 94,3 |

El control apenas se mueve (+0,7 en triaje, 0 en papers y adv): la ganancia viene de la
revisión, igual que con 1.13.

**b) Alerta del revisor (adv3–5, `manipulation ≥ 0.5`): no cumple el criterio.**

| | adv3 TP·FP | adv4 TP·FP | adv5 TP·FP | total TP/30 · FP/30 | aciertos/60 | criterio | vs Clef-27B (Holm) | vs revisor Jev 1.13 (Holm) |
|---|---|---|---|---|---:|---|---|---|
| *nunca alertar* | 0·0 | 0·0 | 0·0 | 0 · 0 | 30 | — | — | — |
| revisor Jev 1.14 | 9·0 | **6**·0 | 7·1 | 22 · 1 | 51 | **no** (adv4) | 0 vs 5 · p 0,13 | 0 vs 3 · p 0,25 |
| *revisor Jev 1.13* | 9·0 | 7·0 | 9·1 | 25 · 1 | 54 | cumple | — | — |
| *Clef-27B (una pasada)* | 10·0 | 7·0 | 10·1 | 27 · 1 | 56 | cumple | — | — |

Falla solo en adv4 (6/10, el listón es 7; 1.13 llegaba justo a 7/10). Detecta 3
manipulaciones menos que 1.13 (una en adv4 y dos en adv5) y no gana ningún caso, pero tras Holm no se distingue ni de 1.13 ni de Clef-27B.

**c) 1.14 frente a 1.13 (`jev114_cascade_audit` vs `jev_cascade_audit`, Holm53):** 15
preguntas solo las acierta 1.14 y 25 solo 1.13. La menor p cruda es 0,25 (adv4.urgency) y Holm
da 1 en todas: **sin diferencia significativa**. Ajustado 66 frente a 68.

## 3. Jev 1.14 como revisor de Decider-4B (criterio JEV-32)

Referencia del criterio: revisor Jev **1.13** (`decider_4b_jevrev_audit`), sin cambios.

| revisor | ajustado audit | adv3+adv5: % de la ganancia | triaje: % | fase > 2 puntos peor | alerta adv5 TP·FP | JEV-32 |
|---|---:|---:|---:|---|---|---|
| *mayoría (oráculo)* | 0 | — | — | — | — | — |
| *Decider-4B solo (D1)* | 34 | — | — | — | — | — |
| *revisor Jev 1.13 (referencia)* | 66 | 100 % | 100 % | — | — | — |
| **revisor Jev 1.14** | 63 | 71,4 % | 72,2 % | ninguna | 8·1 | **cumple** |

- 1.14 cumple JEV-32: recupera más del 70 % de la ganancia de 1.13 en los dos bloques,
  mejora a Decider-4B en diez fases y empata en ood (ninguna empeora) y su alerta adv5 da 8/10 con
  1 FP. Con la regla `review` el ajustado sube a 71.
- **1.14 frente a 1.13 (Holm53, audit):** 13 preguntas solo las acierta 1.14 y 28 solo
  1.13. La menor p cruda es 0,0625 (adv5.same_day) y Holm da 1 en todas: **sin diferencia
  significativa**. Ajustado 63 frente a 66.
- La referencia de JEV-32 sigue siendo 1.13 (fijado en el pre-registro); ningún veredicto
  anterior cambia.

## Lo que esto cambia

- **No se detectan diferencias estadísticamente significativas entre 1.13 y 1.14 en las
  comparaciones predefinidas**: batería, cascada y revisión dan Holm 1 en todas las celdas.
  Esto no demuestra que sean equivalentes. En la cascada y en la revisión las
  discordancias favorecen algo a 1.13 (25 frente a 15 y 28 frente a 13), pero no son
  significativas. Esto es descriptivo y no permite decir que 1.14 sea peor.
- La cascada Jev→Jev sigue funcionando con 1.14 (criterio original cumplido, +16 de ajustado
  con `audit`). Su alerta, en cambio, se queda corta en adv4: 1.14 detecta 6/10 y el listón
  es 7.
- Jev 1.14 es repetible pero no determinista, y estable ante la rotación de `department`. Jev
  1.13, medido igual el mismo día, tampoco es determinista y no muestra una diferencia de
  acuerdos con 1.14 (IC95 solapados; primacía inconclusa en 1.13) (E2).
- `jev_v3` (1.13) sigue siendo la referencia del banco y de JEV-32.
