# JEV-104 — Jev 1.14: réplica r2, rotación d1, cascada Jev→Jev y revisor de Decider-4B

**Estado: CONGELADO el 15-oct-2026.** El usuario aprobó el plan (puntos 1–3 de JEV-104)
antes de medir. Ninguna celda de este documento se había ejecutado ni calculado al
congelarlo (commit del pre-registro anterior a cualquier `results/` de los runs de §0).
Cualquier cambio posterior va como enmienda fechada al final.

Todos los protocolos, reglas y criterios se reutilizan **sin cambios** de experimentos ya
pre-registrados: cascada Jev→Jev ([`cascada_jev.md`](cascada_jev.md)), alerta de manipulación
([`alerta_manipulacion.md`](alerta_manipulacion.md)), d1/r2 y revisor de Decider-4B
([`jev103_preregistro.md`](jev103_preregistro.md) §2–§3, JEV-32). Lo único nuevo es el
modelo: **Jev 1.14**. GT vigente **v5**. Toda tabla lleva la línea base de mayoría y los
resultados negativos se documentan igual (reglas 5 y 8 de AGENTS.md).

## 0. Modelo, runs y guardas

- **Modelo:** Jev 1.14 por la API de TypeSafe, alias `jev-preview`, que resuelve a
  `jev-1.14.0` (`check_versions`, 15-oct). Run base: `jev_v114_typesafe_preview`
  (194/194, 11 fases, ajustado 50,3; ficha en `docs/modelos.md#jev-114`).
- **Identidad de versión (fija):** cada caso guarda su versión resuelta. Una celda solo es
  evaluable si **todas** las llamadas de sus runs resuelven a `jev-1.14.0`. Si el alias
  cambia a mitad, la celda es NO EVALUABLE y se declara (no se mezcla).
- **Guardas de coste:** `--max-case-cost 0.01` y `--max-cost 0.20` por run (o por `_raw` de
  cascada). Política: 1 pasada por bloque (`all+new`, luego `adv4,adv5`) + **1**
  `--retry-errors`. Coste esperado total < $0.10.
- **Runs nuevos (nombres fijados):**

| run | qué es | comando base |
|---|---|---|
| `jev_v114_typesafe_preview_r2` | réplica independiente del run base | `jevbench.run jev` |
| `jev_v114_typesafe_preview_d1` | rotación d1 del orden de `department` | `jevbench.run jev --opt choice_order=department:d1` |
| `jev114_cascade_{raw,review,audit,avg}` + `jev114_avg2_control` | cascada Jev→Jev 1.14 | `jevbench.cascade` |
| `decider_4b_jev114rev_{raw,review,audit,avg}` | 1.14 como revisor de Decider-4B | `jevbench.cascade --d1 decider_4b` |

**Orden de adquisición (fijo):** r2 primero (es el control de ruido de la cascada), luego d1,
cascada y revisor de Decider-4B. d1 y el revisor pueden correr en paralelo con la cascada.

```bash
set -a; . ./.env; set +a
O="--opt provider=typesafe --opt model=jev-preview --max-case-cost 0.01 --max-cost 0.20"
# r2
python3 -m jevbench.run jev --run jev_v114_typesafe_preview_r2 $O --phases all+new
python3 -m jevbench.run jev --run jev_v114_typesafe_preview_r2 $O --phases adv4,adv5
# d1
python3 -m jevbench.run jev --run jev_v114_typesafe_preview_d1 $O \
    --opt choice_order=department:d1 --phases all+new
python3 -m jevbench.run jev --run jev_v114_typesafe_preview_d1 $O \
    --opt choice_order=department:d1 --phases adv4,adv5
# cascada Jev→Jev 1.14 (control = r2)
python3 -m jevbench.cascade --d1 jev_v114_typesafe_preview --adapter jev --provider typesafe \
    --opt model=jev-preview --prefix jev114_cascade \
    --control jev_v114_typesafe_preview_r2 --control-run jev114_avg2_control \
    --max-case-cost 0.01 --max-cost 0.20
# 1.14 como revisor de Decider-4B
python3 -m jevbench.cascade --d1 decider_4b --adapter jev --provider typesafe \
    --opt model=jev-preview --prefix decider_4b_jev114rev --control "" \
    --max-case-cost 0.01 --max-cost 0.20
# + 1 --retry-errors por bloque/run con el mismo comando, solo si hay errores
```

## 1. Réplica r2 y rotación d1

Mismo análisis y misma lectura que JEV-103 §2:

```bash
python3 -m jevbench.jev81 repeat jev_v114_typesafe_preview jev_v114_typesafe_preview_r2
python3 -m jevbench.jev82 analyze jev_v114_typesafe_preview jev_v114_typesafe_preview_d1
```

- **r2:** acuerdo de decisiones pareadas con IC95 (referencia descriptiva ≥ 97 %), Δp
  medio/máximo y Δ ajustado. A diferencia de los modelos locales de JEV-103, Jev es una API
  cerrada y no sabemos si es determinista: **una divergencia no es un fallo de plomería**,
  es la repetibilidad real del servicio. Se reporta sin umbral de éxito.
- **d1:** acuerdo pareado, Δ ajustado (descriptivo) y primacía con la regla JEV-72 sobre el
  subconjunto congelado (sha `4e7e2877f27d`). Lectura: «sensible al orden» si primacía
  CONFIRMADA o acuerdo < 97 %; «estable» solo con acuerdo ≥ 97 % **y** primacía REFUTADA;
  con primacía INCONCLUSA, «acuerdo observado ≥ 97 %, primacía inconclusa».
- **Atribución (fija):** como Jev no es necesariamente determinista, el acuerdo d1 se lee
  **junto al de r2**: si el acuerdo d1 no es menor que el de r2 (IC95 solapados), los cambios
  de d1 no se atribuyen al orden. Esto es lectura, no altera el dictamen de `jev82`.
- Nunca se midieron r2/d1 con Jev 1.13: no hay comparación de versiones en esta celda.

## 2. Cascada Jev→Jev con 1.14

Mismo prompt del revisor y mismas reglas de fusión de `jevbench/cascade.py` (`review`,
`audit`, `avg`, control `avg2`), D1 = `jev_v114_typesafe_preview`, revisor = Jev 1.14,
control = promedio de D1 con `jev_v114_typesafe_preview_r2`.

**a) Criterio original de `cascada_jev.md` (fijo).** `review` o `audit` mejoran a D1 en el
total de al menos 2 de estos 4 bloques: triaje (media ES/EN), papers32, adv1+adv2 y casos
nuevos (triage_ext ES/EN + adv3), **y** la mejora es mayor que la del control. El documento
original menciona «4 bloques» pero solo nombra tres; aquí el cuarto queda fijado como los
casos nuevos, donde la cascada 1.13 se confirmó.

**b) Alerta del revisor (fija):** `manipulation ≥ 0.5` en `jev114_cascade_raw` sobre
adv3/adv4/adv5. Criterio por set: TP ≥ 7/10 y FP ≤ 1/10. Línea base «nunca alertar» 30/60.
Familia Holm de 2 McNemar exactos sobre los 60 ids: frente a `jev_cascade_raw` (revisor Jev
1.13, 25/30 · 1/30) y frente a `clef_27b_alert_raw` (27/30 · 1/30).
`python3 scripts/jev103_alert.py jev114_cascade_raw`.

**c) Comparación de versiones (confirmatoria):** `jev114_cascade_audit` frente a
`jev_cascade_audit` (1.13), McNemar exacto por celda con Holm sobre las 53 celdas
(`python3 -m jevbench.jev90 holm53 jev114_cascade_audit jev_cascade_audit --descriptive`,
misma familia y exclusiones que la comparación de las baterías 1.14/1.13). H0: sin
diferencia. Solo se afirma «mejor/peor» con alguna celda significativa tras Holm.

## 3. Jev 1.14 como revisor de Decider-4B

Criterio **JEV-32 sin cambios** (`scripts/jev103_reviewer.py decider_4b_jev114rev`): con la
regla `audit`, recuperar ≥ 50 % de la ganancia de `decider_4b_jevrev_audit` (revisor Jev
1.13) sobre `decider_4b` en adv3+adv5 y en triaje ES/EN (valores internos del scorer), sin
empeorar ninguna de las 11 fases más de 2 puntos, y alerta adv5 de
`decider_4b_jev114rev_raw` con TP ≥ 7/10 y FP ≤ 1/10. Cobertura incompleta en una fase
necesaria → NO EVALUABLE.

**Comparación de versiones (confirmatoria):** `decider_4b_jev114rev_audit` frente a
`decider_4b_jevrev_audit`, Holm53 como en §2c. H0: sin diferencia.

**La referencia de JEV-32 no cambia (fijado ahora):** el revisor Jev 1.13 sigue siendo la
referencia del criterio para todos los revisores ya juzgados. El resultado de 1.14 se
reporta como celda propia. Si 1.14 difiriera significativamente de 1.13, se documentaría y
cualquier cambio de referencia sería una decisión aparte, no retroactiva.

## 4. Lo que no entra

- Ruta OpenRouter (`~typesafe/jev-latest` → `typesafe/jev-1.14-20261014`) y alerta de una
  pasada: opcionales en JEV-104, fuera de este pre-registro.
- Cualquier variante no escrita aquí (otros órdenes, umbrales, prompts) es EXPLORATORIA y se
  dirá así.
- No se edita `battery.py`, `score.py` ni los analizadores congelados.

## Enmienda E1 (15-oct-2026, antes de calcular d1)

`jev82 analyze` abortó **antes de calcular nada** porque exige `meta.cost_guard`
`{max_case_cost: 0.01, max_cost: 0.05}` (la guarda congelada de JEV-82) y §0 de este
pre-registro fijó `--max-cost 0.20`. Corrección (no se había visto ninguna cifra de d1):

- No se modifican el analizador congelado ni los JSON de `results/`, y no se repite el run.
- `scripts/jev104_d1_analyze.py` comprueba primero que la guarda congelada **no habría
  disparado nunca** (coste acumulado del run d1 $0.00673 < 0.05 y caso máximo $0.00031 ≤
  0.01). Con eso la adquisición habría sido idéntica. Después ejecuta `jev82 analyze` sin
  cambios, presentando `meta.cost_guard` = 0.05 solo para el run d1.
- La fila d1 se marca «con E1».

## Extensión E2 (15-oct-2026, antes de medir): réplica y rotación de Jev 1.13

Pedida por el usuario tras ver r2/d1 de 1.14. Ninguna celda de esta extensión se había
ejecutado al congelarla. Objetivo: tener r2 y d1 de las dos versiones en las mismas
condiciones (mismo día, misma ruta TypeSafe y mismas guardas).

- **Modelo:** Jev 1.13 por la API de TypeSafe, alias `jev-latest`, que resuelve a
  `jev-1.13.0` (`check_versions`, 15-oct). **Guarda de versión:** cada celda solo es evaluable
  si todas sus llamadas resuelven a `jev-1.13.0`. Si TypeSafe promueve `jev-latest` a 1.14 a
  mitad, la celda es NO EVALUABLE.
- **Runs nuevos:** `jev_v113_typesafe` (base d0, 11 fases), `jev_v113_typesafe_r2` y
  `jev_v113_typesafe_d1` (`choice_order=department:d1`). No se reutiliza `jev_v3`
  (OpenRouter, 26-sep: otra ruta y otra fecha) ni `jev_typesafe_v1` (sin adv4/adv5).
- **Guardas:** `--max-case-cost 0.01 --max-cost 0.05` en los tres runs (la guarda congelada de
  `jev82`; así no hace falta el wrapper E1). Bloques `all+new` y luego `adv4,adv5`, y 1
  `--retry-errors` solo si hay errores. Orden: base, r2, d1.

```bash
O="--opt provider=typesafe --opt model=jev-latest --max-case-cost 0.01 --max-cost 0.05"
for R in jev_v113_typesafe jev_v113_typesafe_r2; do
  python3 -m jevbench.run jev --run $R $O --phases all+new
  python3 -m jevbench.run jev --run $R $O --phases adv4,adv5
done
python3 -m jevbench.run jev --run jev_v113_typesafe_d1 $O --opt choice_order=department:d1 --phases all+new
python3 -m jevbench.run jev --run jev_v113_typesafe_d1 $O --opt choice_order=department:d1 --phases adv4,adv5
python3 -m jevbench.jev81 repeat jev_v113_typesafe jev_v113_typesafe_r2
python3 -m jevbench.jev82 analyze jev_v113_typesafe jev_v113_typesafe_d1
```

- **Análisis y lectura:** los de §1, sin cambios (dictamen de `jev82` y regla de atribución
  d1-frente-a-r2).
- **Comparación 1.13 frente a 1.14 (descriptiva, sin umbral nuevo):** acuerdos r2 y d1 de cada
  versión con su IC95, Δp medio/máximo y dictamen de primacía. Solo se habla de diferencia
  entre versiones si los IC95 de acuerdo no se solapan, y aun así es descriptivo.
- **Uso secundario (descriptivo):** `jev_v113_typesafe` frente a `jev_v114_typesafe_preview`
  (mismo día y ruta) con Holm53, para separar versión de ruta/fecha respecto a la comparación
  con `jev_v3`. No sustituye a `jev_v3` como referencia.
