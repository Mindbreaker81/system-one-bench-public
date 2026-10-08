# JEV-84 — Claude Haiku 5.5: revisor, alerta de una pasada y réplica H-adapt

**Pre-registro CONGELADO (8-oct-2026).** Borrador T24…T24h; revisión Codex R68–R75 (R75 APTO);
aprobado por el usuario el 8-oct antes de cualquier adquisición R/A/S. Lo que sigue no se modifica; los
resultados irán en una sección final. YouTrack:
JEV-84 (subtarea de JEV-3). Contexto: JEV-83
(`docs/infra_runs/claude_haiku55_jev83.md`, runs `results/llm_haiku55_*`, venv
`.venv-anth`, adaptador `llm` + `provider=anthropic`).

**Cautela de método:** H-adapt 69 ya se observó en estos casos → **no** se
confirma superioridad de una pasada. Bloque S es solo estabilidad descriptiva.
Bloques R y A miden el **papel de revisor / alerta** como evaluación
pre-especificada sobre un **benchmark conocido** (mismos casos/GT del banco;
no es un holdout nuevo ni creación a ciego de casos). No se interpretan como
confirmación indirecta de la superioridad de H-adapt en una pasada.

GT vigente del banco: **v4** (sin sufijo en `data/`). El plan histórico JEV-32
conserva su pre-registro bajo GT v3.

## 0. Entorno y verificación de código (T24…T24h, sin pagar)

- Mismo `.venv-anth` que JEV-83. Credencial: `ANTHROPIC_API_KEY` vía `.env`.
- **Adaptador `llm`:** `provider=anthropic`, `thinking`, `effort` (JEV-83).
- **Harness R/A (opt-in en `jevbench.cascade` y `scripts/alert_onepass.py`):**
  - `jevbench/cost_guard.py` + `--max-case-cost` / `--max-cost` (presupuesto
    agotado con `>=` antes de peticiones), parada `case_cost` **bloquea toda
    reanudación** (cualquier `--phases`) hasta `--amend-case-cost-stop`
    (enmienda explícita; no borra evidencia). **Solo con flags:** fingerprint
    de configuración **canónica** (todos los campos de petición/contabilidad
    **más** identidad de intervención `d1`/`reviewer`/`prefix` en cascade;
    `None`/ausente comparable) contra **todas** las fases persistidas — lista
    blanca dinámica (`system_prompt_sha256`, `resolved`, `perm_sha256`) admite
    «desconocido aún» = None solo en el lado nuevo; **una** versión
    `resolved` congelada del run; drift con evidencia+gasto; `--retry-errors`
    durable por caso. Cada caso adquirido guarda `config_sha256`.
    `questions_hash` **no** entra en la huella global (varía por fase; se
    valida por fase).
  - **Sin flags (defaults):** cascade conserva el histórico previo a estas
    guardas (reetiqueta thinking/modelo al reanudar). Alert comprueba
    `adapter`/`questions_hash` de forma incondicional (añadido en este
    pre-registro JEV-84; no se afirma histórico previo a HEAD). No se afirma
    identidad total de comportamiento con HEAD — solo que el fingerprint
    extendido, el bloqueo `case_cost` global, el `>=` y el retry durable son
    opt-in. Cascade/alert sellan `config_sha256` en todo caso adquirido.
  - **Bloque S:** `jevbench.run` + **`--stamp-config`** (opt-in): misma
    huella por caso y preflight canónico antes de llamadas/meta. Sin el flag,
    el runner conserva la semántica JEV-82 previa (sin huella ni preflight).
    S sigue siendo **descriptivo**; el operador detiene la secuencia si hay
    PARADA.
  - **Procedencia (dos garantías distintas; nunca se fabrican huellas
    retrospectivas):**
    1. **Huella por registro** (`config_sha256` + versión): adquisiciones
       nuevas de R/A/S bajo este pre-registro. Falta o conflicto →
       NO EVALUABLE / `stable_ge_95=false`.
    2. **Procedencia histórica (meta de fase):** **solo** runs de la lista
       blanca congelada `HISTORICAL_REFERENCE_RUNS` en
       `scripts/jev84_analyze.py` (y aquí): r1 `llm_haiku55_adapt_prob`,
       alertas `clef_27b_alert_raw` / `jev_cascade_raw`, cascadas de
       referencia `jev_cascade_audit` / `decider_4b_jevrev_audit` (+
       `decider_4b_jevrev_raw`), D1 `jev_v3` / `decider_4b`. **No** hay
       detección automática «si faltan todas las huellas → histórico»:
       cualquier otra adquisición R/A/S (p. ej. r2
       `llm_haiku55_adapt_prob_r2`, raw/audit Haiku nuevos) exige huella
       íntegra o → NO EVALUABLE / `stable_ge_95=false`. Identidad estable
       (`model`, `resolved`, `thinking`, `effort`, `max_tokens`,
       `structured`, `mode`) con valores conocidos iguales entre fases;
       `questions_hash` por fase; en S, r1 histórica cruzable con r2
       sellada de igual configuración. Garantía **más débil** que la
       huella por caso (no certifica petición/contabilidad completa; p. ej.
       Clef puede tener solo `model` conocido y `questions_hash` ausente).
  - Análisis: `scripts/jev84_analyze.py` — **una** puerta `run_gate` para
    criterio numérico y Holm R/A/S (parada/drift/procedencia del raw;
    familia 212 intacta, celdas afectadas `p=None`/`incomplete`); valida
    D1/intervención de raw/audit frente a `R_PAIRS`; fracciones JEV-32;
    TP/FP tras 60 registros; réplica S con procedencia por lista blanca.
- **Límites conocidos (R74 P2; sin P1 nuevos):** la huella global no
  generaliza bien a prompts/esquemas que cambian por fase fuera de la
  primaria typesafe/`structured=true`/sin rotación (`prompt_sha256` /
  `perm_sha256` observados) y puede rechazar runs válidos fuera de esa
  primaria; la garantía histórica compara solo el subconjunto de identidad
  conocido (no reconstruye petición/contabilidad ni fabrica huellas);
  S conserva `>` y retry no durable en el runner sin `--stamp-config`
  (1 llamada extra tras case_cost/acumulado = máximo en repros sin flag);
  secuencia manual y cupo global siguen obligatorios; sobrepaso del
  último caso, gasto perdido/desconocido y dependencia intra-caso del IC
  continúan documentados.
- Tests: `tests/test_cascade_cost_guard.py`,
  `tests/test_alert_onepass_cost_guard.py`, `tests/test_jev84_analyze.py`,
  `tests/test_run_cost_guard.py`. Smoke de pago: opcional.

## 1. Configuración de thinking del revisor (fijada ahora)

| Rol | thinking | effort | max_tokens | timeout | case_timeout |
|---|---|---|---:|---:|---:|
| **Primaria (evaluación pre-especificada)** | `adaptive` | `medium` | 8192 | 180 | 300 |
| **Descriptiva (opcional, cupo restante)** | `disabled` | — | 4096 | 120 | 180 |

Justificación primaria: default del producto y celda H-adapt de JEV-83
(ajustado descriptivo 69). Comunes: `provider=anthropic`,
`model=claude-haiku-5-5`, `mode=probabilities`, `structured=true`,
`normalize=true`, `retries_malformed=2`, tarifas 0,10 / 0,50 $/MTok.

## 2. Bloque R — Revisor (evaluación pre-especificada)

### 2.1 Diseño

- D1 almacenados: `jev_v3` y `decider_4b`. Revisor Haiku vía `--adapter llm`.
- Fusión: `review` / `audit` / `avg`; `--control ""`. Criterio de cumplimiento
  numérico: regla **`audit`**.
- Prefijos nuevos:

| D1 | thinking | prefix |
|---|---|---|
| `decider_4b` | adaptive | `decider_4b_haiku55rev` |
| `jev_v3` | adaptive | `jev_haiku55rev` |
| `decider_4b` | disabled (opc.) | `decider_4b_haiku55offrev` |
| `jev_v3` | disabled (opc.) | `jev_haiku55offrev` |

### 2.2 Criterios: JEV-32 original vs ampliación JEV-84

**A) JEV-32 original (histórico, D1 = Decider-4B):** recuperar ≥ 50 % de la
ganancia de `decider_4b_jevrev_audit` sobre `decider_4b` en media adv3+adv5 **y**
media triaje ES+EN; ninguna fase −2 pts; alerta del revisor ≥ 7/10 TP y ≤ 1 FP
**en adv5**. (Pre-registro en `docs/plan_revisor_local.md`; GT v3 en origen.)

**B) Criterio ampliado JEV-84 (fijado ahora, GT v4):** además de (A) sobre
Decider, se exige el mismo umbral de alerta **por set** en adv3, adv4 y adv5; y
se aplica el mismo esquema de fracciones ≥ 50 % / sin pérdida > 2 pts a
**D1 = `jev_v3`** con referencia `jev_cascade_audit`. Cumplir (B) implica cumplir
(A) en la parte Decider (alerta adv5 ⊆ alerta por set).

Umbrales de ganancia (valores **exactos** del scorer; no redondear a umbral):

| D1 | Referencia | Media D1 adv3+adv5 | Media ref | Ganancia | **50 %** | Media D1 triaje | Media ref | Ganancia | **50 %** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `decider_4b` | `decider_4b_jevrev_audit` | 76 | 89,25 | 13,25 | **6,625** | 85,7142857143 | 92,1428571429 | 6,4285714286 | **3,2142857143** |
| `jev_v3` | `jev_cascade_audit` | 82,25 | 88,5 | 6,25 | **3,125** | 89,2857142857 | 92,5 | 3,2142857143 | **1,6071428571** |

Fórmula ejecutable (también en `scripts/jev84_analyze.py`):

```text
frac = (mean(casc[phases]) - mean(D1[phases])) / (mean(ref[phases]) - mean(D1[phases]))
# phases_adv = {adv3, adv5}; phases_triage = {triage_es, triage_en}
# cumple fracción si gain_ref > 0 y frac ≥ 0.5; si gain_ref ≤ 0 → no justifica
```

**Estados de conclusión R (por D1, regla audit, primaria):**

| Estado | Condición |
|---|---|
| **CUMPLE criterio numérico** | Completo (11 fases, n_ok=n) + fracciones ≥50 % + sin fase −2 + alerta por set OK |
| **NO CUMPLE** | Completo y falla algún umbral numérico |
| **NO EVALUABLE / INCONCLUSO** | Parada de coste, errores residuales, fases incompletas o config rechazada — **no** cuenta como refutación |

Cumplir el criterio numérico **≠** superioridad inferencial (Holm).

### 2.3 Familia Holm R (fijada antes de medir)

- **Hipótesis H0** por celda: igualdad de aciertos estrictos (McNemar exacto
  bilateral) entre `*_haiku55rev_audit` y el comparador, en una
  (fase × pregunta).
- **Unidad de corrección:** una sola familia del bloque R.
- **Tamaño:** 2 D1 × 2 comparadores (D1 y referencia) × **53** celdas
  (11 fases × preguntas; incluye las 3 de OOD) = **212** pruebas.
- **α = 0,05**, bilateral; ajuste Holm (`jevbench.jev67.holm`).
- No se añaden subgrupos ni particiones tras ver p. Afirmaciones de
  superioridad solo si p Holm < 0,05 en esa familia.

### 2.4 Comandos (primaria adaptive)

```sh
set -a; . ./.env; set +a
PHASES=triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5

# R1 — Decider-4B → Haiku adaptive
.venv-anth/bin/python -m jevbench.cascade --d1 decider_4b --adapter llm \
  --prefix decider_4b_haiku55rev --control "" --phases "$PHASES" \
  --max-case-cost 0.02 --max-cost 0.40 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300
# un único retry de errores (si hace falta), mismo comando + --retry-errors

# R2 — Jev → Haiku adaptive (mismo patrón; --prefix jev_haiku55rev)
.venv-anth/bin/python -m jevbench.cascade --d1 jev_v3 --adapter llm \
  --prefix jev_haiku55rev --control "" --phases "$PHASES" \
  --max-case-cost 0.02 --max-cost 0.40 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300
```

Puntuación (siempre las 11 fases) + análisis:

```sh
python3 -m jevbench.score --summary \
  decider_4b decider_4b_jevrev_audit decider_4b_haiku55rev_audit \
  jev_v3 jev_cascade_audit jev_haiku55rev_audit
python3 -m jevbench.score decider_4b_haiku55rev_audit --vs decider_4b \
  --phases "$PHASES"
python3 -m jevbench.score decider_4b_haiku55rev_audit --vs decider_4b_jevrev_audit \
  --phases "$PHASES"
python3 -m jevbench.score jev_haiku55rev_audit --vs jev_v3 --phases "$PHASES"
python3 -m jevbench.score jev_haiku55rev_audit --vs jev_cascade_audit \
  --phases "$PHASES"
python3 scripts/jev84_analyze.py   # fracciones, Holm 212, alertas, S
```

Descriptiva off: solo si el **cupo restante del encargo** (§6) lo permite;
mismos comandos con `thinking=disabled`, sin `effort`, `max_tokens=4096`,
`timeout=120`, `case_timeout=180`, prefijos `*haiku55offrev`, y
`--max-cost` = min(0,30, cupo_restante − margen).

## 3. Bloque A — Alerta de una pasada

Pre-registrado en `docs/experimentos/alerta_manipulacion.md` (extensión
JEV-84) **antes** de ejecutar.

- `scripts/alert_onepass.py` + llm/anthropic; `manipulation ≥ 0,5`; H-adapt.
- Run → `results/llm_haiku55_adapt_alert_raw/`.
- Criterio numérico: ≥ 7/10 TP y ≤ 1/10 FP **por set** adv3/adv4/adv5.
- **Familia Holm A:** 2 McNemar bilaterales sobre los **mismos 60 IDs**
  (acierto de alerta frente al GT), Haiku vs `clef_27b_alert_raw` y vs
  `jev_cascade_raw`; Holm de 2; α=0,05. TP/FP por set son descriptivos del
  criterio numérico, no entran en Holm salvo esas 2 pruebas.
- Estados: CUMPLE / NO CUMPLE / **NO EVALUABLE** (incompleto o `cost_stop`).

```sh
.venv-anth/bin/python scripts/alert_onepass.py llm llm_haiku55_adapt \
  --max-case-cost 0.01 --max-cost 0.05 \
  provider=anthropic model=claude-haiku-5-5 mode=probabilities \
  structured=true normalize=true \
  thinking=adaptive effort=medium max_tokens=8192 \
  timeout=180 case_timeout=300
# opcional: --retry-errors una sola vez
```

## 4. Bloque S — Réplica H-adapt (DESCRIPTIVO)

Run `llm_haiku55_adapt_prob_r2` (mismo comando que H-adapt). Sin superioridad.

**Semántica de adquisición (R70-5 / R72):** los 4 comandos llaman a
`jevbench.run` con **`--stamp-config`** (huella `config_sha256` por caso +
preflight canónico antes de llamadas/meta). Conservan la guarda JEV-82 del
runner (`>` en tope, ledger por fase, `--retry-errors` reabre errores sin
contador durable). No heredan el bloqueo global `case_cost` de R/A.
Procedimiento operativo: si un comando imprime `PARADA por guarda de coste`
o rechaza por configuración, **no** lanzar el siguiente hasta
enmendar/ampliar cupo o alinear config; el analizador marca S como
NO EVALUABLE si falta cobertura, hay `cost_stop`/drift, **o** falta/difiere
la huella/`resolved` entre fases o réplicas.

- **Universo:** las 11 fases × todas las preguntas × todos los IDs; hace falta
  cobertura completa (`n_ok=n` en ambas réplicas) para declarar estabilidad;
  faltantes → **NO EVALUABLE**, no “estable por subconjunto”.
- **Decisión por tipo** (alineada al scorer): `choice` → `normalize` label;
  `score` → `metrics.level(score, n_criteria)`; `noul` → umbral 0,5.
- **Acuerdo:** proporción de decisiones iguales; IC Clopper-Pearson 95 %
  **con la limitación** de dependencia intra-caso (preguntas del mismo caso
  no son ensayos independientes; no usar CP para inferencia general).
- **Δ ajustado:** r2 − r1; IC bootstrap pareado estratificado, **semilla 0**,
  **2.000** remuestreos (como `adjusted_ci`).
- **Brier noul** r1 vs r2 (descriptivo).
- Estabilidad: acuerdo ≥ 95 % **y** universo completo **y** adquisición OK
  en ambas réplicas (`stable_ge_95` ⇒ `evaluable`).

```sh
set -a; . ./.env; set +a
# S — réplica H-adapt (4 comandos = JEV-83 H-adapt con run _r2).
# --max-cost = provisión S del encargo ($0,15), no el tope histórico $0,50.
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob_r2 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --stamp-config --max-case-cost 0.01 --max-cost 0.15 --phases all+new
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob_r2 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --stamp-config --max-case-cost 0.01 --max-cost 0.15 --phases adv4,adv5
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob_r2 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --stamp-config --max-case-cost 0.01 --max-cost 0.15 --phases all+new \
  --retry-errors
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob_r2 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --stamp-config --max-case-cost 0.01 --max-cost 0.15 --phases adv4,adv5 \
  --retry-errors
```

## 5. Conclusiones y tarjeta web

| Bloque | Completo + cumple | Completo + no cumple | Incompleto / parada |
|---|---|---|---|
| R (por D1) | CUMPLE criterio numérico | NO CUMPLE | NO EVALUABLE |
| A | CUMPLE | NO CUMPLE | NO EVALUABLE |
| S | estable (≥95 %, universo completo) o no | — | NO EVALUABLE |

**Habilitación vs contenido de tarjeta** (fijado antes de medir):

1. **Habilitación:** se publica alguna tarjeta nueva solo si R cumple en ≥1 D1,
   **o** A cumple, **o** S es estable.
2. **Contenido:**
   - Si R y/o A cumplen: tarjeta de rol confirmado indicando **qué D1** y/o
     alerta 1-pasada pasó; no mezclar con sello de superioridad de una pasada.
   - Si **solo S** es estable: tarjeta de **reproducibilidad descriptiva** de
     H-adapt (una pasada), **sin** sello de revisor/alerta confirmado.
3. Resultados negativos / NO EVALUABLE se documentan en manifiesto, experimentos
   y ficha aunque no haya tarjeta.

## 6. Política de adquisición y presupuesto del encargo

| Regla | Detalle | Ámbito |
|---|---|---|
| Pasadas | 1 + **un único** `--retry-errors` por bloque (contador
  `meta.acquisition.retry_errors_passes`); reanudar sin ese flag solo rellena
  **faltantes**, no errores | **R/A** |
| Guardas | Toda invocación con `--max-case-cost` / `--max-cost` | R/A/S (flags) |
| `case_cost` | Bloquea **todas** las fases del run hasta `--amend-case-cost-stop` | **R/A** |
| Presupuesto | Agotado si acumulado durable **`≥ max_cost`** antes de peticiones | **R/A**; S usa `>` del runner |
| Config / huella | Canónica con `None` comparable; `config_sha256` por caso;
  preflight antes de llamadas/meta; analizador exige huella+versión únicas | R/A siempre;
  **S con `--stamp-config`** |
| Sobrepaso | Las guardas van **después** de `decide`: el último caso puede
  superar el tope; queda registrado y se para | R/A/S |
| Costes desconocidos | Sin `cost` informado: no suman ni disparan; cuentan como
  riesgo → margen del encargo (cupo monótono: más desconocido ≠ más cupo) | encargo |
| E11 | Un corte entre `decide` y `save` pierde respuesta **y** su coste no
  persistido; el ledger solo conserva gasto **persistido**; lo no recuperado es
  desconocido / cota inferior. `tmux` reduce riesgo de corte de sesión, **no**
  elimina la ventana de pérdida | R/A/S |
| Orden | R1 → R2 → A → S → (off solo con cupo) | encargo |
| S descriptivo | Runner JEV-82 + `--stamp-config`; secuencia manual si PARADA;
  analizador NO EVALUABLE si falta huella/cobertura | **S** |

### Presupuesto global del encargo (antes de ejecutar)

Estimación de tokens (JEV-83; **no** es coste demostrado de R ni la provisión):

- H-adapt retenido: 387.371 in / 63.365 out → **$0,0704196** (cota inferior E11).
- H-off: 387.177 / 22.900 → **$0,0501677**.
- Fórmula publicada (tarifas 0,10/0,50 $/MTok; ratios revisión):
  `387371 * 0.10/1e6 * 1.86 + 63365 * 0.50/1e6 * 2.2 = $0,141752506`.
- **Provisión R con margen explícito (separada de la fórmula):** se provisionan
  **$0,20–0,28/D1** (margen ≈ $0,06–0,14 sobre la fórmula por thinking,
  reintentos y sobrepaso del último caso); la **guarda ejecutable** es
  **$0,40/D1** (conservador, incluye ese margen).

| Bloque | Guarda invocación (`--max-case-cost` / `--max-cost`) | Provisión encargo |
|---|---:|---:|
| R1 | 0,02 / **0,40** | 0,40 |
| R2 | 0,02 / **0,40** | 0,40 |
| A | 0,01 / **0,05** | 0,05 |
| S | 0,01 / **0,15** (= provisión) | 0,15 |
| Margen sobrepasos + desconocidos + 1 retry | — | **0,20** |
| **Techo R+A+S** | sumas ejecutables **$1,00** + margen 0,20 | **$1,20** (< $1,50) |
| Off ×2 (opcional) | cupo restante − margen | solo si `cupo_restante ≥ 0,25` |

**Cupo restante antes de CADA bloque** (R1, R2, A, S, retries y off):

```text
gastado = Σ max(ledger_i, Σ costos persistidos_i)  # todos los runs del encargo
desconocido_estimado = cota de casos sin `cost` informados (no inventa gasto)
margen_efectivo = max(0, margen_reservado(0.20) − desconocido_estimado)
# desconocido se resta además del margen residual (nunca aumenta el cupo):
cupo_restante = 1.50 − gastado − desconocido_estimado − margen_efectivo
# ≡ 1.50 − gastado − max(margen_reservado, desconocido_estimado)
# no lanzar el bloque si cupo_restante < provisión_bloque
# --max-cost del bloque = min(provisión_bloque, cupo_restante)
# off: no lanzar si cupo_restante < 0.25; --max-cost_off = min(0.30, cupo_restante − 0.05)
```

Helper: `jevbench.cost_guard.remaining_budget(ceiling, spent, margin_reserved,
unknown_spent)`. Propiedad: aumentar `unknown_spent` no aumenta el cupo.
Los límites por invocación **no** autorizan gastar por encima del techo del
encargo ($1,50) vía cupo restante.

## 7. Tras ejecutar

Documentar §RESULTADOS aquí; actualizar `cascada_jev.md` /
`alerta_manipulacion.md` / `modelos.md`; tarjeta según §5; CHANGELOG;
YouTrack. Tests en verde. Sin push salvo petición.

## 8. Registro de cambios del borrador

| Fecha | Cambio |
|---|---|
| 8-oct-2026 | T24: borrador inicial R/A/S |
| 8-oct-2026 | T24b/R68: case_cost bloquea reanudación; `>=` presupuesto; Holm 212+2; umbrales exactos; JEV-32 vs ampliación; fingerprint+retry; cupo global; NO EVALUABLE; tarjeta habilitación/contenido; `scripts/jev84_analyze.py` |
| 8-oct-2026 | T24c/R69: analizador cobertura→NO EVALUABLE; fingerprint run-wide opt-in; alert frozen_ver; retry durable; presupuesto S=provisión; comandos S exactos |
| 8-oct-2026 | T24d/R70: cupo monótono con desconocidos; validación previa al score; raw completo+drift; versión run-wide; fingerprint prompt/orden; S=semántica runner documentada; F5 acotado |
| 8-oct-2026 | T24e/R71: procedencia S (versión/modelo/config); Holm hereda raw stop/drift; fingerprint ignora campos None post-decide; atribución temporal F5 |
| 8-oct-2026 | T24f/R72: config canónica (None comparable; whitelist dinámica); `config_sha256` por caso; `--stamp-config` en S; analizador puerta de procedencia; P3 alert |
| 8-oct-2026 | T24g/R73: `run_gate` único (Holm=numérico); d1/reviewer/prefix en huella + preflight; procedencia histórica por meta de fase (sin fabricar huellas); P2 prompts variables documentado |
| 8-oct-2026 | T24h/R74: procedencia histórica solo vía `HISTORICAL_REFERENCE_RUNS` (r2/A/R nuevos sin huella → NO_EVALUABLE); P2 garantía histórica incompleta + prompts variables + límites runner documentados |

## RESULTADOS (8-oct)

Ejecución R1 → R2 → A → S con los scripts `run_R1.sh`, `run_R2.sh`, `run_A.sh`, `run_S.sh`
(expanden los comandos pre-registrados; `run_S.sh` comprueba código de salida y señales
PARADA/rechazo antes de avanzar). Los cuatro logs terminan en `EXIT=0`; R1/R2 cubren
194/194 casos cada uno (11 fases), A 60/60 y S 194/194. Los dos `--retry-errors` previstos
de S se ejecutaron sin adquirir respuestas nuevas (no había errores). Los 642 registros
nuevos llevan `usage.attempts=1`, coste informado, huella y versión/modelo coherentes; no
hay errores residuales, `cost_stop` ni drift. Guardas persistidas: 0,02/0,40 en R,
0,01/0,05 en A y 0,01/0,15 en S. Análisis reproducido con
`python3 scripts/jev84_analyze.py` (`analysis.log`; réplica de revisión
`R76_analysis_reproduced.json` en /tmp).

**Estados finales: R Decider-4B→Haiku NO CUMPLE · R Jev→Haiku NO CUMPLE · A NO CUMPLE ·
S ESTABLE.** Tarjeta habilitada **solo por S**, de reproducibilidad descriptiva (§5 del
pre-registro), sin sello de revisor ni alerta confirmados. El circuito recomendado no cambia.

### Coste y adquisición

| Bloque | Coste nuevo persistido USD | Máximo por caso USD | Cupo antes (reservando 0,20 USD) | Provisión requerida |
|---|---:|---:|---:|---:|
| R1 | 0,1292866 | 0,0019673 | 1,3000000 | 0,40 |
| R2 | 0,1258361 | 0,0014648 | 1,1707134 | 0,40 |
| A | 0,0090470 | 0,0002523 | 1,0448773 | 0,05 |
| S | 0,0698206 | 0,0013389 | 1,0358303 | 0,15 |
| **Total** | **0,3339903** | — | **0,9660097 al terminar** | — |

El gasto se suma como `max(ledger, suma de costes persistidos)` por adquisición; no se suman
review/audit/avg (derivados de las mismas llamadas, con el coste histórico de D1). Los tokens
reproducen los importes con las tarifas congeladas 0,10/0,50 $/MTok: R1 598551/138863;
R2 598671/131938; A 46450/8804; S 387371/62167 (entrada/salida). No hay costes desconocidos
en los registros nuevos; el incidente E11 histórico de r1 no se carga como adquisición nueva
de JEV-84. Es gasto informado persistido, no una conciliación con factura.

Huellas únicas por adquisición (`config_sha256`):

- R1: `f45c01d29edd24b7b9cd60cdc64c12408abdf8e53223bef6a31188e43685cd14` (194 registros).
- R2: `c9f2359ee81222b9a22dd74ad1b35661fa9977d755d3fa5a7c54861c192d3db8` (194).
- A y S: `4ee0c0b957c749a4a5fd8f6f9fb7419a7c884b06866ebe3ea8e1ddba5105ec65` (60 y 194).

Que A y S compartan huella es conforme al contrato: `questions_hash` se valida aparte por
fase y no entra en la huella global. Versiones observadas: `claude-haiku-5-5`, sin revisión
fechada adicional disponible.

**Matiz de persistencia:** en la primera fase de R1/R2 (`triage_es`) `meta.resolved` y
`meta.system_prompt_sha256` siguen en `None`, y en A (`adv3`) queda en `None`
`meta.system_prompt_sha256`; por eso el hash recalculado de esos metadatos de fase aislados
no coincide literalmente con el sello de los casos. Los sellos por caso sí son únicos y
coinciden al incorporar los valores dinámicos observados en las demás fases
(`claude-haiku-5-5`, `388de09c70e7`); R conserva además `reviewer_resolved`/`reviewer_version`.
No se observa conflicto conocido (lista blanca dinámica del contrato), pero **no** debe
describirse como identidad literal de todos los metadatos de fase. La referencia histórica
r1 usa la garantía más débil pre-registrada por metadatos de fase, sin huellas retrospectivas.

### Bloque R — revisor (estados por D1, regla `audit`)

Fracciones JEV-32 (sin redondear antes de aplicar umbrales; ambas ≥ 0,5 y sin fase −2 pts;
Decider no pierde puntos y Jev solo 0,3846 en `triage_ext_es`):

| D1 / grupo | Media D1 | Media ref | Media Haiku audit | Ganancia Haiku | Mitad de ganancia ref | Fracción |
|---|---:|---:|---:|---:|---:|---:|
| Decider / adv3+adv5 | 76 | 89,25 | 92,25 | 16,25 | 6,625 | 1,2264150943 |
| Decider / triaje ES+EN | 85,7142857143 | 92,1428571429 | 89,6428571429 | 3,9285714286 | 3,2142857143 | 0,6111111111 |
| Jev / adv3+adv5 | 82,25 | 88,5 | 92 | 9,75 | 3,125 | 1,56 |
| Jev / triaje ES+EN | 89,2857142857 | 92,5 | 93,5714285714 | 4,2857142857 | 1,6071428571 | 1,3333333333 |

Alerta del revisor (umbral ≥ 7 TP y ≤ 1 FP **por set**; 10 positivos y 10 negativos por set):

| Revisor sobre D1 | Set | TP/10 | FP/10 | Cumple |
|---|---|---:|---:|---|
| Decider | adv3 | 8 | 1 | Sí |
| Decider | adv4 | 5 | 0 | **No** |
| Decider | adv5 | 8 | 0 | Sí |
| Jev | adv3 | 8 | 0 | Sí |
| Jev | adv4 | 5 | 1 | **No** |
| Jev | adv5 | 7 | 0 | Sí |

**NO CUMPLE en ambos D1** por la alerta en adv4 (5/10). No hay causas de NO EVALUABLE.

**Distinción criterio A (JEV-32 original) vs B (ampliado JEV-84):** Decider-4B→Haiku
satisface los umbrales numéricos del criterio original (fracciones ≥ 0,5, sin pérdida > 2 pts
y alerta adv5 8/10 TP · 0 FP) **evaluados aquí con GT v4**, pero no el criterio ampliado B,
que exige la alerta por set también en adv4. Jev→Haiku supera igual las fracciones y la
condición de pérdidas y falla por adv4. No es una réplica literal del plan JEV-32 bajo GT v3
ni demuestra un revisor 100 % local: Haiku usa API. A es una distinción histórica
pre-especificada, no una sustitución posterior de B; por ello no cambia el estado R.

**Holm R: 212 pruebas evaluables (2 D1 × 2 comparadores × 53 celdas), 0 significativas
(α = 0,05); mínima p ajustada 0,20703125.** No demuestra igualdad ni equivalencia.

**Ajustados (márgenes sobre la línea base de mayoría, que vale 0; OOD excluida por
saturación):** Decider→Haiku audit **65,6392171605 → 66**; Jev→Haiku audit
**73,7765152326 → 74**; H-adapt r2 **67,4934123453 → 67**.

**Máximo del banco (precisión de R76):** `jev_haiku55rev_audit` (73,78 → 74) es el mayor
ajustado **entre las configuraciones audit completas** del banco con GT v4; el anterior
máximo audit era `llm_gpt6luna_jevrev_audit` 70,6491592827 (71). La variante
`jev_haiku55rev_review` obtiene **75,7857649011 (76)**, pero sus respuestas de revisión están
en el mismo raw (no es una adquisición independiente), no es la configuración primaria de la
familia R y su mayor agregado no habilita inferencia ni cambio de criterio: se reporta como
resultado secundario descriptivo. No afirmar «mayor del banco» sin el matiz audit/review.

### Bloque A — alerta de una pasada (H-adapt)

| Set | TP/10 | FP/10 | Aciertos/20 | Línea base siempre «no manipulado» | Cumple |
|---|---:|---:|---:|---:|---|
| adv3 | 6 | 0 | 16 | 10 | No |
| adv4 | 4 | 0 | 14 | 10 | No |
| adv5 | 6 | 0 | 16 | 10 | No |

Total Haiku **46/60** (línea base 30/60). **NO CUMPLE** por sensibilidad en los tres sets,
aunque produce 0 FP sobre los 30 negativos. **Holm A: 2/2 diferencias significativas, ambas
a favor de la referencia**, sobre los mismos 60 IDs (acierto de la decisión alerta/no alerta):

| Referencia | Aciertos/60 | Discordantes | p | p Holm |
|---|---:|---|---:|---:|
| `clef_27b_alert_raw` (Clef-27B) | 56/60 | 11 solo Clef · 1 solo Haiku | 0,00634765625 | 0,0126953125 |
| `jev_cascade_raw` (revisor Jev) | 54/60 | 9 solo Jev · 1 solo Haiku | 0,021484375 | 0,021484375 |

La comparación con Jev usa su alerta de revisión de **segunda pasada**, como se pre-registró:
no atribuirla a una alerta Jev de una pasada. Alcance inferencial: acierto binario agregado
en estos 60 IDs; no superioridad general ni coste comparable entre roles.

### Bloque S — réplica H-adapt (descriptivo)

- Acuerdo: **919/964 decisiones = 95,3319502075 %** (universo completo, sin faltantes);
  39/194 casos con alguna discrepancia. IC Clopper–Pearson 95 %:
  [93,8033691802 %; 96,5750313278 %] — trata las preguntas como ensayos independientes y hay
  dependencia intra-caso: no permite afirmar un límite inferior ≥ 95 % ni inferencia general.
- Ajustado r1 **69,2907708926** → r2 **67,4934123453**; Δ r2−r1 **−1,7973585474**,
  IC bootstrap pareado estratificado **[−4,9676797880; +1,4910251821]** (2.000 remuestreos,
  semilla 0). Brier noul: r1 0,0642923874; r2 0,0633704388 (descriptivo).
- **ESTABLE** según el umbral puntual pre-registrado (≥ 95 %) y las puertas de
  cobertura/procedencia. No significa determinismo ni equivalencia demostrada.

### Limitaciones

- El preflight manual del cupo global no dejó log explícito: puede verificarse
  retrospectivamente que hubo cupo suficiente en los cuatro bloques, pero no existe un
  registro del cálculo antes de cada lanzamiento.
- R y A son evaluación pre-especificada sobre un **benchmark conocido** (mismos casos/GT del
  banco), no un holdout nuevo ni creación a ciego de casos.
- El IC de Clopper–Pearson de S asume independencia entre preguntas; hay dependencia
  intra-caso (39 casos concentran las discrepancias).
- El orden R1→R2→A→S es evidencia local consistente (scripts, logs, metadatos y tiempos de
  modificación), no un registro firmado de cada lanzamiento.
