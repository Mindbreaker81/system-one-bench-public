# JEV-90 — `Microsoft-Decision-1` (OpenRouter decisions): batería, réplica y rotación d1

**Pre-registro CONGELADO el 10-oct-2026** (borrador T31–T31e; revisión Codex R94–R100, APTO; aprobado por el usuario antes de ejecutar la batería completa ni ninguna réplica/rotación de pago). Ningún resultado de las celdas D0/R/D1 de
este documento se ha calculado aún. Datos de partida (comprobados el
10-oct, fuera de las celdas): el alias `microsoft/microsoft-decision-1`
responde por el endpoint de decisiones de OpenRouter
(`/api/alpha/decisions`) con el adaptador `jev` existente
(`provider=openrouter`); versión resuelta
`microsoft/microsoft-decision-1-20261009`; `choice`/`score`/`noul` con
probabilidades; coste observado ≈ `$0,042` por M tokens de entrada
(salida gratis). Humo autorizado (§0): run `smoke_ms_decision1`.
Vigilancia de versión: familia `ms_decision_1` en
`jevbench.check_versions` (`KNOWN_MS_DECISION`).

**Analizadores:** reutilización opt-in de `jevbench/jev81.py`
(repetibilidad) y `jevbench/jev82.py` (rotación), pasando los nombres de
run; **más** el módulo opt-in `jevbench/jev90.py` (puerta de snapshot,
Holm confirmatorio sin IDs expuestos, primacía confirmatoria sin
expuestos en toda la familia, discordancias `department` con puerta de
réplica, preflight con exit coherente, costes; cupo global por
construcción). **No** cambia el comportamiento por defecto de
jev81/jev82/score.

**Afirmaciones del fabricante (anuncio / Command Line, 9-oct-2026) — NO
son resultados de este banco:** mayor acierto en 36 benchmarks ajenos;
~35× más rápido (P50) que GPT-6 Sol; 0 cambios al barajar/invertir
opciones (y 1,3 % ante otras perturbaciones); seguridad en 5.250
peticiones. Solo se contrastan aquí, con operacionalizaciones acotadas,
las que este banco puede medir (§3 y §6).

**Azure Foundry:** el endpoint System One del recurso del proyecto quedó
sin cuota de despliegue (comentario JEV-90). Esta celda mide **solo** la
ruta OpenRouter. Una celda Foundry exigiría adaptador/pre-registro
aparte.

## 0. Humo e inventario de exposición (antes del pre-registro)

### 0.1 Humo autorizado

```sh
python3 -m jevbench.run jev --run smoke_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.001 --max-cost 0.01 \
    --phases ood,triage_es --limit 2
```

Ejecutado el 10-oct-2026 (exit 0, ~5 s de pared, acumulado registrado
`$0,000042168`):

| Fase / id | department / domain | input_tokens | cost | ms | model |
|---|---|---|---|---|---|
| ood / receta | domain=`other` | 230 | $9,66e-6 | 1640 | `…-20261009` |
| ood / contrato | domain=`other` | 240 | $1,008e-5 | 1119 | `…-20261009` |
| triage_es / T01_ebus_alergia | department=`bronchoscopia` | 279 | $1,172e-5 | 698 | `…-20261009` |
| triage_es / T02_factura_duplicada | department=`admin` | 255 | $1,071e-5 | 1125 | `…-20261009` |

- Respuestas con sentido (receta → `other`; factura duplicada → `admin`).
- `usage.cost / input_tokens` = **$0,042 / M** en los 4 casos; salida 3–5
  tokens (gratis en tarifa).
- `meta.resolved` = `microsoft/microsoft-decision-1-20261009`;
  `meta.cost_guard` y `meta.cost_ledger` presentes.
- Tras documentar, borrar `results/smoke_ms_decision1/` (no es celda
  oficial). **Borrar el run no elimina la exposición.**

### 0.2 IDs expuestos congelados (P1)

Casos del banco vistos antes de fijar las hipótesis confirmatorias
(congelados; no se amplían tras medir):

| fase / id |
|---|
| `ood/receta` |
| `ood/contrato` |
| `triage_es/T01_ebus_alergia` |
| `triage_es/T02_factura_duplicada` |

Sondas previas del endpoint (10-oct), **ajenas al banco** (estados
sintéticos; no son ids de la batería; inventariadas igual):

| id procedimental | estado (prefijo) |
|---|---|
| `probe_roast_chicken_20261010` | «Roast the chicken…» |

Constante reproducible: `jevbench.jev90.EXPOSED_CASE_IDS` /
`EXPOSED_SYNTHETIC_PROBES` / `exposed_tags()`.

**Política confirmatoria:** la batería oficial completa y sus scorers se
conservan para lo **descriptivo** (ajustado, tablas por fase, mayoría;
también `jev82 analyze` / `qwen_session.primacy_analysis`). Los
contrastes **confirmatorios** (familia Holm53 frente a `jev_v3`;
primacía vía `jev90 primacy`; operacionalización «0 cambios» en
`department`) **excluyen** los IDs expuestos del banco en *todos* los
integrantes de sus familias (en primacía: tanto «todos» como
«primacía»). Las sondas sintéticas nunca entran en scorers. Si una
celda Holm queda sin observaciones tras la exclusión → `n=0`, `p=1.0`
(entra en Holm; no se omite). El subconjunto de primacía
(`4e7e2877f27d`) no solapa con los IDs expuestos; eso no basta por sí
solo: la corrección de multiplicidad de «todos» tampoco puede
alimentarse de expuestos.

## 1. Celda principal D0 — `jev_ms_decision1`

**Hipótesis / criterios fijados antes de medir:**

1. **Confirmatorio vs Jev:** familia de **53** pruebas McNemar–Holm
   (acierto estricto por pregunta×fase), **excluyendo** los IDs
   expuestos (§0.2), vía `python3 -m jevbench.jev90 holm53` (no el
   fragmento que solo imprime significativas). Se reportan las **53**
   filas (p nominal, p Holm, n). **No** se afirma superioridad ni
   inferioridad a Jev sin al menos una prueba significativa tras Holm;
   la ausencia de significación **no** demuestra equivalencia.
2. **Descriptivo (sin familia Holm propia):** ajustado + IC95 bootstrap
   del scorer (`--adj-ci`) frente a `nimble_9b`, `jev_luna_decisions` y
   `oai_luna_decisions`, **incluyendo** IDs expuestos. Coberturas
   distintas se declaran. El IC del scorer es descriptivo y **supone
   independencia entre registros** (no agrupa ES/EN ni mide variación
   entre ejecuciones) — limitación del flag `--adj-ci`.
3. **Línea base trivial:** mayoría (oráculo) en **todas** las tablas.
4. **Afirmación del fabricante «mayor acierto en 36 benches»:**
   **no evaluable** aquí.
5. **Puerta de snapshot (D0):** todas las versiones por caso de éxito =
   `microsoft/microsoft-decision-1-20261009` y ≥1 éxito válido
   (`python3 -m jevbench.jev90 snapshot jev_ms_decision1`). Si falla →
   contrastes confirmatorios de D0 = **NO EVALUABLE** como propiedad de
   ese snapshot (los números entre versiones solo descriptivos).

**Adquisición (política fija; misma que JEV-80/81/82):**

1 pasada completa + **1** `--retry-errors` por bloque. La API de
decisiones no admite temperature ni seed. Si aparecen rechazos nuevos no
se decide reintentar más después de verlos.

**Intentos HTTP:** `--opt retries=3` explícito (1 decide = 1–3 intentos;
`--retry-errors` = pasada nueva sobre registros con error). Igual que
JEV-82 §2.

**Guarda de coste por run** (mismas desigualdades que JEV-82; ledger
durable `meta.cost_ledger`):

- caso con coste registrado > $0,01 → parada (`--max-case-cost 0.01`);
- acumulado registrado del run > $0,05 → parada (`--max-cost 0.05`).

**Cupo GLOBAL del experimento** (D0+R+D1): **≤ $0,15** POR
CONSTRUCCIÓN. Exactamente tres celdas (D0, R, D1), cada una con las
guardas fijas `--max-case-cost 0.01 --max-cost 0.05` y **un único**
`--retry-errors` dentro de la misma guarda. El gasto registrado no puede
superar 3 × $0,05 = $0,15 más el sobrepaso del último caso de cada run
(guarda post-caso: umbral de parada, no cota estricta; declarado).
Cualquier run que alcance su tope queda **parado sin reanudación**
salvo enmienda aprobada. No hay cupo dinámico ni tope efectivo por
celda: los comandos de adquisición son ejecutables tal cual y
`meta.cost_guard` coincide con lo que validan jev82/jev90
(`{"max_case_cost": 0.01, "max_cost": 0.05}`). Costes desconocidos no
suman al spent medido ni disparan guardas (§5). Ampliar topes, añadir
celdas o reanudar tras tope exige nueva aprobación.

```sh
python3 -m jevbench.run jev --run jev_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run jev --run jev_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run jev --run jev_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
python3 -m jevbench.run jev --run jev_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5 --retry-errors
```

**Análisis D0 (offline, tras adquirir) — comandos exactos:**

```sh
# Preflight (universo, hashes, expuestos, snapshot); exit ≠ 0 si falla:
python3 -m jevbench.jev90 preflight jev_ms_decision1 --ref jev_v3

# Descriptivo: ajustado + IC95 (limitación de independencia arriba):
python3 -m jevbench.score jev_ms_decision1 --summary --adj-ci
python3 -m jevbench.score jev_ms_decision1 nimble_9b jev_luna_decisions \
    oai_luna_decisions jev_v3 --summary --adj-ci

# McNemar crudo por fase (descriptivo; NO es la familia Holm) — 11 fases:
python3 -m jevbench.score jev_ms_decision1 --vs jev_v3 \
    --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5

# Familia confirmatoria Holm 53 (excluye IDs expuestos; imprime las 53).
# Aplica universo/hash + puerta de snapshot a D0 antes de etiquetar
# confirmatorio; fallos de entrada abortan; drift → NO EVALUABLE (exit ≠ 0).
# Solo con --descriptive se imprime Holm sin puertas (no confirmatorio):
python3 -m jevbench.jev90 holm53 jev_ms_decision1 jev_v3

# Puerta de snapshot D0:
python3 -m jevbench.jev90 snapshot jev_ms_decision1

# Coste: suma final / ledger / desconocidos vigentes + reemplazados:
python3 -m jevbench.jev90 costs jev_ms_decision1
```

`score --vs` **no** aplica Holm. `holm_cells` de `qwen_session` (sin
exclusión) es solo diagnóstico descriptivo; la familia confirmatoria es
`jev90 holm53` (con puertas). Preflight con referencia ausente o
snapshot no evaluable → exit ≠ 0.

## 2. Réplica R — `jev_ms_decision1_r2` (repetibilidad)

Misma política de adquisición que D0 (1 pasada + 1 `--retry-errors` por
bloque; `retries=3`; guardas fijas 0,01 / 0,05). **No** se lanza hasta
tener D0 completo y aprobación de gasto (~segundo ×$0,003). Cupo global
por construcción (3 × $0,05).

```sh
python3 -m jevbench.run jev --run jev_ms_decision1_r2 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run jev --run jev_ms_decision1_r2 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run jev --run jev_ms_decision1_r2 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
python3 -m jevbench.run jev --run jev_ms_decision1_r2 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5 --retry-errors
```

**Análisis:**

```sh
python3 -m jevbench.jev90 preflight jev_ms_decision1_r2 --ref jev_v3
python3 -m jevbench.jev90 snapshot jev_ms_decision1 jev_ms_decision1_r2
python3 -m jevbench.jev81 repeat jev_ms_decision1 jev_ms_decision1_r2
python3 -m jevbench.jev90 costs jev_ms_decision1_r2
```

**Métricas y umbral (descriptivos, congelados como JEV-81 «934/934»):**

- Acuerdo de decisiones pareadas (`paired_decisions`) con IC95
  Clopper-Pearson; referencia **descriptiva ≥ 97 %** sobre la estimación
  puntual — no es umbral de veredicto confirmatorio.
- Δp: media y máximo |Δp| sobre componentes escalares comunes.
- Δ ajustado solo si las fases completas coinciden; si no, `null`.
- Rechazos both / solo r1 / solo r2 por `error_kind` (criterio JEV-81).
- **Puerta de snapshot (R):** `jev90 snapshot` sobre el par exige todas
  las versiones = `…-20261009` y ≥1 par válido. Si falla →
  **NO EVALUABLE** como repetibilidad de ese snapshot. El indicador
  `repeatable_model` de jev81 solo compara igualdad *dentro* de cada par
  (no garantiza snapshot único ni compara con `…-20261009`); no sustituye
  la puerta. Números entre versiones = solo descriptivos.
- Si hay negativas parciales por pregunta (§4) → jev81 aborta → R
  **NO EVALUABLE** vía ese analizador.

## 3. Rotación D1 — `jev_ms_decision1_d1` (orden de `department`)

Contraste de sensibilidad al orden / primacía, **y** operacionalización
acotada de la afirmación del fabricante «0 cambios al barajar/invertir
opciones». Datos de partida: D0 canónico; subconjunto de primacía
congelado sha `4e7e2877f27d` (regla JEV-72/82 intacta).

**Qué cambia:** solo el orden de las claves de `criteria` de
`department` (`choice_order=department:d1` → consulta_externa, urgencias,
admin, bronchoscopia). Etiquetas, textos, casos y GT intactos.

**Adquisición** (igual que JEV-82: retries=3, guardas fijas 0,01/0,05,
1+1 retry; cupo global por construcción 3 × $0,05):

```sh
python3 -m jevbench.run jev --run jev_ms_decision1_d1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run jev --run jev_ms_decision1_d1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run jev --run jev_ms_decision1_d1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
python3 -m jevbench.run jev --run jev_ms_decision1_d1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5 --retry-errors
```

**Análisis:**

```sh
python3 -m jevbench.jev90 preflight jev_ms_decision1_d1 --ref jev_v3
python3 -m jevbench.jev90 snapshot jev_ms_decision1 jev_ms_decision1_d1
# Descriptivo (jev82; familia de primacía puede incluir expuestos en «todos»):
python3 -m jevbench.jev82 analyze jev_ms_decision1 jev_ms_decision1_d1
python3 -m jevbench.jev82 analyze jev_ms_decision1 jev_ms_decision1_d1 \
    --json <ruta-local>
# Primacía CONFIRMATORIA (excluye expuestos en {todos, primacía}):
python3 -m jevbench.jev90 primacy jev_ms_decision1 jev_ms_decision1_d1
# Contador + lista de discordancias department (confirmatorio, sin expuestos)
# y veredicto «0 cambios» solo con --r2 válido + D1 acreditada como rotación:
python3 -m jevbench.jev90 department-discords \
    jev_ms_decision1 jev_ms_decision1_d1 \
    --r2 jev_ms_decision1_r2
python3 -m jevbench.jev90 costs jev_ms_decision1_d1
```

Validación **dentro** del comando confirmatorio (idéntica a JEV-82 §1 +
puerta jev90): universo, hashes, procedencia canónica de D0, rotación
d1 de D1 (`opts.choice_order` / `meta.choice_order` / `perm_sha256` por
fase), `meta.cost_guard` en d1, vectores pareados completos
(`_check_paired_vectors`), sha del subconjunto `4e7e2877f27d`, puerta
de snapshot. Sin `--r2` → **NO EVALUABLE** (conteo d0↔d1 descriptivo;
**no** se imprime REFUTADA/COMPATIBLE causal). D1 canónica (sin
declarar rotación) → **NO EVALUABLE** aunque haya cambios.

**Contrastes:**

1. Cobertura/rechazos; casos con error en cualquiera de los dos runs fuera
   de contrastes pareados.
2. Δ ajustado (d1−d0) descriptivo; sin umbral de equivalencia.
3. Acuerdo pareado; referencia descriptiva ≥ 97 % puntual.
4. **Primacía confirmatoria (umbral JEV-72/82, vía `jev90 primacy`):** Δ
   errores `department` (d0−d1) en el subconjunto congelado. Familia Holm
   {todos, primacía} **sin IDs expuestos en ningún integrante**.
   CONFIRMADA si Δ ≥ 5 pp ∧ L95 > 0 ∧ significativa tras Holm; REFUTADA
   si U95 < 5; si no, INCONCLUSA. Si la puerta de snapshot falla, hay
   negativas parciales, falta procedencia/rotación/guarda, o los
   vectores pareados no son conformes (pregunta ausente o
   probabilities incompletas) → **NO EVALUABLE**. `jev82 analyze` puede
   imprimir un veredicto descriptivo (su «todos» aún ve expuestos);
   este pre-registro toma como confirmatorio solo `jev90 primacy`.
   Pregunta instrumental distinta de la del fabricante.
5. Δp por etiqueta; `same_model` de jev82 es igualdad *dentro* del par —
   no sustituye la puerta de snapshot único.
6. Coste: suma final / ledger / desconocidos vigentes + reemplazados.
7. **Afirmación del fabricante «0 cambios» — operacionalización acotada:**
   - **Qué se mide:** nº de cambios de decisión del scorer en
     `department` entre d0 y d1 sobre éxitos pareados **excluyendo IDs
     expuestos**, más la lista de ids discordantes
     (`jev90 department-discords`).
   - **Qué no se mide:** barajar/invertir *todas* las opciones de *todas*
     las preguntas, ni el espacio completo de permutaciones, ni las
     «otras perturbaciones» del 1,3 %.
   - **Lectura (tabla de veredictos) con `--r2`:**
     - snapshot drift / <1 par / negativas parciales en d0 o d1 →
       **NO EVALUABLE**;
     - D1 sin rotación acreditada (choice_order/perm_sha256), sin
       guarda, o vectores d0↔d1 no conformes → **NO EVALUABLE**
       (conteo descriptivo; **nunca** REFUTADA);
     - réplica ausente, con drift de snapshot, con negativas parciales,
       con vectores no conformes, sin pares department tras exclusión,
       sin cobertura de control sobre los casos contrastados, o con
       procedencia de orden no canónica → **NO EVALUABLE** (conteo
       d0↔d1 descriptivo; **nunca** REFUTADA por omisión del control);
     - si la réplica R (mismo orden) ya cambia `department` →
       **NO EVALUABLE** como prueba de que el *orden* causó el cambio
       (conteo d0↔d1 descriptivo);
     - si `n_cambios_department ≥ 1` (sin expuestos) y R evaluable sin
       cambios → **REFUTADA** bajo esta operacionalización (una sola
       rotación d1);
     - si `n_cambios_department = 0` → **COMPATIBLE / INCONCLUSA**.
   - Separar «se observó un cambio bajo d1» de «el orden lo causó».
   - Sin `--r2`: **NO EVALUABLE** (conteo descriptivo; no se imprime
     veredicto causal REFUTADA/COMPATIBLE).

## 4. Política de adquisición, rechazos y drift de versión

| Aspecto | Regla fijada |
|---|---|
| Pasadas | 1 completa + 1 `--retry-errors` por bloque (`all+new`, luego `adv4,adv5`) |
| HTTP por decide | `--opt retries=3` |
| Temperature / seed | no disponibles en el endpoint |
| Guardas por run | `--max-case-cost 0.01 --max-cost 0.05` + ledger durable (coinciden con `meta.cost_guard` que validan jev82/jev90) |
| Cupo global experimento | ≤ **$0,15** POR CONSTRUCCIÓN: exactamente 3 runs × guarda fija $0,05 (+ sobrepaso ≤1 caso/run declarado); sin cupo dinámico ni consulta previa de presupuesto en el procedimiento |
| Reanudación | progreso por caso dentro de la guarda del run; al alcanzar el tope del run → **parada sin reanudación** salvo enmienda; documentar paradas por exceso individual (como JEV-82); sobrepaso de ≤1 caso post-guarda declarado |
| Rechazo de caso (OpenRouter) | `error_kind=rejection` si HTTP **502** parseado **y** «refused to answer» (`jev81.error_kind`). Registro de **caso entero**; esa fase deja de ser completa para el ajustado sin imputación (igual JEV-82) |
| **Refusal por pregunta** | Si el wire trae `answers[qid]={"type":"refusal"}` (HTTP 200): esa pregunta = **0** (`metrics.point` / `normalize` → refused); el resto del caso se conserva. El adaptador `jev` devuelve `answers` intacto aunque no rellene el auxiliar `refusals`. **Fijado ahora** (no se elige tras ver casos) |
| Qué análisis admite cada formato | `python3 -m jevbench.jev90 formats` — score y Holm confirmatorio admiten refusal=0; **jev81/jev82 abortan** ante negativas parciales (vectores ordinarios) → R/D1 vía esos analizadores = **NO EVALUABLE**; primacía/«0 cambios» vía jev90 con la misma puerta |
| Versión / snapshot | puerta `jev90 snapshot`: todas las versiones de éxito = `microsoft/microsoft-decision-1-20261009` y ≥1 par/éxito. Drift o ausencia → **NO EVALUABLE** como propiedad del snapshot. `check_versions` vigila el alias |

## 5. Coste y tiempo (resumen)

**Estimación D0 (antes de medir):** tokens del humo (1.004) / mismos ids
en `jev_luna_decisions` (2.704) = razón **0,37130**. Escalando 193.778
tokens de los 188 éxitos luna × 0,37130 × $0,042/M ≈ **$0,003022** ≈
**~$0,003** por pasada completa (194 casos si no hay rechazos). Los
cuatro casos cortos **no** validan solos el perfil de papers largos.
Latencia media del humo ≈ 1,15 s/caso → orden de **~4 min** de pared por
pasada. Estimación, no factura.

| Celda | Estimación (antes de medir) | Cupo guarda / run |
|---|---|---|
| Humo (hecho) | **$0,000042** / ~5 s / 4 casos | 0,001 / 0,01 |
| D0 `jev_ms_decision1` | ~$0,003 / ~4–10 min | 0,01 / 0,05 |
| R `jev_ms_decision1_r2` | ≈ D0 | 0,01 / 0,05 |
| D1 `jev_ms_decision1_d1` | ≈ D0 | 0,01 / 0,05 |

**Cupo GLOBAL** D0+R+D1: **≤ $0,15** por construcción (3 × $0,05;
ver §1 / §4). Tras medir, informar separadamente vía `jev90 costs`:
(1) suma final de `cost` vigentes, (2) máximo del ledger durable
(`meta.cost_ledger`, incluye retries reemplazados), (3)
`unknown_current` = registros **vigentes** sin coste, (4)
`unknown_captured` = capturados antes del retry (**reemplazo no
acreditado**: éxitos sin coste o errores cuyo retry no sustituyó),
(5) `unknown_replaced` = **reemplazos comprobados** (había error sin
coste y el vigente ya tiene coste o dejó de ser error).

Comando exacto (opt-in; no modifica `run.py`):

```sh
# ANTES de cada bloque --retry-errors de una celda:
python3 -m jevbench.jev90 capture-unknowns jev_ms_decision1
python3 -m jevbench.run jev --run jev_ms_decision1 \
    --opt provider=openrouter --opt model=microsoft/microsoft-decision-1 \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
# (igual para adv4,adv5 y para R/D1)
```

`capture-unknowns` persiste los vigentes sin coste en
`meta.cost_unknown_history` con `replaced=False` /
`status=captured_pre_retry` (vía `note_unknown_replacement`). No afirma
reemplazo consumado: un éxito sin coste o un error cuyo retry queda
bloqueado figuran en `unknown_captured`, no en `unknown_replaced`.
Lista vacía de `unknown_replaced` **no acredita ausencia** si no se
ejecutó ese comando antes del reemplazo. La escritura automática en
`jevbench.run` queda **aplazada** al próximo `attest freeze` (cambiar
`run.py` invalidaría los hashes congelados de jev78/82). Los intentos
HTTP internos del adaptador no tienen trazabilidad individual. No se
computa una estimación como gasto medido. Este borrador **no** autoriza
D0/R/D1 hasta aprobación.

## 6. Qué se concluirá y qué no

| Afirmación / contraste | Criterio pre-registrado | Veredictos posibles |
|---|---|---|
| Diferencia vs `jev_v3` (Holm 53, sin expuestos) | ≥1 prueba significativa tras Holm; snapshot OK | significativas reportadas; sin ellas no hay sup./inf.; equivalencia no evaluable; drift → **NO EVALUABLE** |
| «Mayor acierto en 36 benches» (fabricante) | — | **no evaluable** |
| Descriptivo vs `nimble_9b` / luna OR / luna nativa | ajustados + IC + cobertura (con expuestos) | solo descriptivo |
| Por encima de la mayoría | ajustado del scorer | factual del run |
| Repetibilidad (R) | acuerdo puntual ≥ 97 % (descriptivo); puerta snapshot | observada bajo esas condiciones; drift/refusals → **NO EVALUABLE** |
| Primacía (trampa bronchoscopia, JEV-72) | `jev90 primacy` (familia sin expuestos) + puerta snapshot; jev82 = descriptivo | CONFIRMADA / REFUTADA / INCONCLUSA / **NO EVALUABLE** |
| «0 cambios al barajar/invertir» (fabricante) | `jev90 department-discords --r2` (§3.7); D1 rotación + vectores + R válida; sin `--r2` o R/D1 inválidos → NO EVALUABLE | REFUTADA / COMPATIBLE-INCONCLUSA / **NO EVALUABLE** |
| ~35× más rápido que GPT-6 Sol | — | **no evaluable** aquí |
| Cascada / revisor / alerta por rechazo | — | **exploratorio**; fuera de alcance |

## 7. Integración posterior (después de medir y revisar — no ahora)

Solo tras resultados conformes y aprobación:

- Ficha en `docs/modelos.md`; fila en `docs/resultados.md` +
  `docs/resultados_runs.txt`.
- Web ES **y** EN a la par (`jevbench/web.py` **y** `jevbench/site.py`).
- `python3 -m jevbench.attest freeze` **si** se adopta `jev90` como
  analizador confirmatorio congelado (hoy es opt-in del pre-registro;
  jev81/jev82 ya auditados).
- CHANGELOG + versión semántica según
  `docs/procedimientos/publicar-version.md`.
- YouTrack JEV-90 → Done con cifras y rutas.

**No** se tocan en este encargo: `docs/articulo/`,
`scripts/article_figures.py`, `tests/test_article_*`.

## 8. Lo que no se hace en este borrador

| Descartado | Motivo |
|---|---|
| Lanzar D0/R/D1 | Exige aprobación tras re-revisión del pre-registro |
| Celda Azure Foundry | Sin cuota de despliegue; ruta distinta |
| Fallback a Jev / alerta por rechazo | No pre-registrados (fueron JEV-81 para luna) |
| d2/d3 u otras preguntas | Una sola rotación acota la sensibilidad |
| Cambiar defaults de jev81/jev82/score | Correcciones vía `jev90` opt-in |
| Adoptar cifras del fabricante | Regla 1 del banco |

## Registro de cambios

| Fecha | Cambio |
|---|---|
| 10-oct-2026 | Borrador inicial T31 (Cursor): humo `smoke_ms_decision1`, celdas D0/R/D1, criterios Holm53 / réplica / primacía / «0 cambios» acotado, guardas y drift |
| 10-oct-2026 | T31b (Cursor, R94): IDs expuestos + sondas sintéticas; Holm confirmatorio sin ellos (`jev90`); refusal por pregunta=0 y formatos; puerta snapshot único + NO EVALUABLE; comandos exactos (preflight, `--adj-ci`, 11 fases, Holm 53 completo, discordancias department); coste razón 0,37130 / ~$0,003; suma/ledger/desconocidos; cupo global ≤ $0,15 |
| 10-oct-2026 | T31c (Cursor, R96): primacía confirmatoria sin expuestos en {todos, primacía} (`jev90 primacy`); réplica ausente/drift/negativas → NO EVALUABLE (nunca REFUTADA); Holm53 con preflight+snapshot y exit coherente; cupo global operativo (`jev90 budget --before`); inventario unknown vigentes + reemplazados |
| 10-oct-2026 | T31d (Cursor, R98): contador «0 cambios» exige rotación D1 (perm/choice_order) + vectores conformes; sin `--r2` → NO EVALUABLE (no causal); `effective_max_cost` al reanudar; `capture-unknowns` antes de cada retry |
| 10-oct-2026 | T31e (Cursor, R99): cupo global POR CONSTRUCCIÓN (3×$0,05 fijos; sin `effective_max_cost` / `budget --before` en el procedimiento); `meta.cost_guard` = guarda validada; inventario `unknown_captured` vs `unknown_replaced` comprobado |

## RESULTADOS

**Cierre (10-oct-2026).** Adquisición D0→R→D1 conforme a R101 (revisión Codex APTO tras correcciones de documentación). Evidencia archivada en `docs/infra_runs/ms_decision1_jev90/` (`cells.log`, `analysis.log`, `analysis_extra.log`, `d1_analysis.json`, `run_cells.sh`). Commit de los JSON de fase: `79fb434`. Snapshot servido: `microsoft/microsoft-decision-1-20261009`. Integración pública: versión **1.6.0** (fila D0 en el marcador; R y D1 solo como análisis).

### Ejecución

Orden acreditado por `run_cells.sh`, `cells.log` y tiempos: **D0 → R → D1**. Cada celda: proveedor OpenRouter, alias Microsoft, `retries=3`, guardas **0,01 USD/caso y 0,05 USD/run**, bloques `all+new` y `adv4,adv5`, un `--retry-errors` por bloque. Solo D1 añade `choice_order=department:d1`. Los tres runs: **194/194 casos, 11 fases**, 0 errores de caso, 0 refusals por pregunta. Log final `EXIT=0`. Sin `STOP`/`PARADA` ni reanudación tras tope.

| Celda | Coste registrado (suma = ledger máx.) | Máx. por caso |
|---|---:|---:|
| D0 `jev_ms_decision1` | **$0,004120914** | $0,000277830 |
| R `jev_ms_decision1_r2` | **$0,004120914** | idem |
| D1 `jev_ms_decision1_d1` | **$0,004120914** | idem |
| **Total D0+R+D1** | **$0,012362742** | — |

Media ≈ $0,00002124/caso. Humo previo (documental, run borrado): $0,000042168; suma humo+experimento $0,012404910 (no es factura exhaustiva). Inventarios `unknown_current` / `unknown_captured` / `unknown_replaced`: vacíos en los tres. Los bloques `--retry-errors` registran **0 to run** en todas las fases (sin llamadas nuevas).

### Desviaciones (R101 §7.1–7.2)

1. **`capture-unknowns` una vez por celda, no dos.** El contrato §5 pide capturar antes de *cada* bloque de retry. El script capturó una vez por celda (antes del retry `all+new`), no otra vez entre ese bloque y el retry `adv4,adv5`: tres capturas, no seis. Las tres quedaron vacías; ambos retries no ejecutaron casos; los 582 registros vigentes tienen coste. **Impacto nulo acreditado** (sin reemplazos ni desconocidos perdidos atribuibles). No se altera el pre-registro congelado.
2. **Envoltura sin comprobación de exit de la captura.** La tubería con `tail` y el `continue` pueden ocultar un fallo de `capture-unknowns`. Aquí la salida visible y los costes completos no revelan daño; es debilidad de la envoltura para futuras ejecuciones, no fallo estadístico de estas celdas.
3. **Análisis: 16 comandos en `analysis.log` + 2 en `analysis_extra.log`.** El log principal no contiene todos los bloques del contrato: faltaban el resumen individual D0 y la exportación `jev82 analyze … --json`. Ambos se completaron offline después (`analysis_extra.log`; JSON en `d1_analysis.json`). No afirmar que `analysis.log` solo cubre el contrato entero.

### Cifras (R101 §2; límites §7.3)

| Run | Ajustado (sin redondear) | Publicable | IC95 | Cobertura |
|---|---:|---:|---|---|
| Microsoft D0 | 43,625457 | **44** | 34–53 | 194/194; 11 fases |
| Jev v3 | 45,375326 | 45 | 36–55 | 194/194 |
| Nimble-9B | 44,284432 | 44 | 34–54 | 194/194 |
| luna decisions OpenRouter | 47,702745 | 48* | 36–59 | 188/194; 6 fases al ajustado |
| luna decisions nativa | 38,247967 | 38 | 27–48 | 194/194; negativas parciales = 0 |
| Mayoría (oráculo) | 0 | 0 | — | Misma batería |

**44 no es % de acierto** (es mejora sobre la mayoría). El 48* no es comparable como agregado completo. Brier noul del resumen D0 = **0,090** (9 fases base+nuevas). Latencia del resumen = **693 ms** (cliente vía OpenRouter; no avala el 35× del fabricante).

D0 por fase (descriptivo): triaje 91,4/86,4; department triaje 28/28; ampliado 92,3/88,1; papers 73,9 (ρ 0,855); depth 7/31 frente a mayoría 17/31; adv1+2 dept 16/20 (mayoría 17/20); adv3 dept 16/20, total 84,0 (mayoría 59,0).

| Contraste | Resultado | Lectura |
|---|---|---|
| Holm53 vs Jev (sin expuestos) | 53 filas, todas `p_holm=1`; 0 significativas; p nominal mín. 0,0625 | Sin superioridad/inferioridad; equivalencia no evaluada |
| Réplica R | 959/964 = 99,4813 % → **99,5 %**; IC95 Clopper–Pearson 98,8–99,8; Δ ajustado −1,032882 (−1,0 pub.); Δp medio 0,0078 máx 0,1665 | Repetibilidad observada; no determinismo (5 decisiones cambian; `department` canónico 0/158 no expuestos) |
| Rotación D1 | 956/964 = 99,1701 % → **99,2 %**; IC95 98,4–99,6; ajustado D1 42,743257; Δ −0,882200 [−3,97; +2,13] | Descriptivo; sin margen de equivalencia |
| Primacía (sha `4e7e2877f27d`) | 37 pareados; errores 10→10; Δ 0,00 [0,00; 0,00]; p_Holm=1 | **REFUTADA** (U95=0<5); no prueba ausencia universal de sesgo |
| «0 cambios» fabricante | 0/158 discordancias `department` D0↔D1; control R 0/158 | **COMPATIBLE/INCONCLUSA** (una rotación cíclica; no todas las permutaciones) |

### Clasificación (R101 §4)

- vs Jev: **0 significativas tras Holm53**; sin superioridad/inferioridad demostrada; equivalencia no evaluada.
- vs Nimble / luna OR / luna nativa: **descriptivas** (coberturas distintas).
- vs mayoría: por encima en ajustado global; no en toda fase/pregunta.
- Mayor acierto en 36 benches, 35× vs GPT-6 Sol, seguridad 5.250, 1,3 % otras perturbaciones: **NO EVALUABLE** aquí.
- Cascada / revisor / alerta: **fuera de alcance**; **no cambia la recomendación vigente** del banco.
