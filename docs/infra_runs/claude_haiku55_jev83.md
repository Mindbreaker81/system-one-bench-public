# JEV-83 — Claude Haiku 5.5 (`claude-haiku-5-5`, API Anthropic) con la batería de Jev

**BORRADOR pre-registrado el 8-oct-2026, antes de la batería
(actualizado T21b / R60 el mismo día).**
Aprobación: JEV-83 (viabilidad y plan). Adaptador: `llm` con
`provider=anthropic` vía `system-one-adapter` 0.2.1 + inyección mínima de
`thinking` / `output_config.effort` en `jevbench/adapters/llm.py` (sin fork
del paquete). Tests offline: `tests/test_llm_adapter.py`
(`TestAnthropicContract`). Entorno: `.venv-anth` (gitignored).

## 0. Entorno

Mismas versiones fijadas que `.venv-llm` (`<ruta-local>`)
más el extra Anthropic:

```sh
python3 -m venv .venv-anth
.venv-anth/bin/pip install -U pip setuptools wheel
.venv-anth/bin/pip install -r <ruta-local> \
  'system-one-adapter[anthropic]==0.2.1' 'anthropic>=0.121.0'
# verificado 8-oct-2026: anthropic==1.12.1, system-one-adapter==0.2.1
```

Credencial: `ANTHROPIC_API_KEY` en `.env` (cargada por `jevbench/env.py`).
No se pasa por `--opt` ni se escribe en resultados.

## 1. Modelo y tarifas (fuentes oficiales, 8-oct-2026)

- **Model ID canónico (snapshot fijo):** `claude-haiku-5-5`. Desde la
  generación 4.6 los IDs sin fecha **no** son alias móviles: son el ID
  canónico de un snapshot fijo
  ([Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions);
  [ficha Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview)).
  Se acredita el run por este ID. El campo `response.model` observado se
  guarda en `meta.resolved` / registro (smoke T21: coincidió con
  `claude-haiku-5-5`). **Fecha de lanzamiento (dato documental):**
  7-octubre-2026 — no se inventa un ID fechado tipo `…-20261007`.
- **Structured outputs:** `structured_outputs.supported=true`; el adaptador
  usa `output_config.format=json_schema` (nativo Messages).
- **Thinking:** adaptativo por defecto (effort `medium`);
  `thinking:{type:"disabled"}` soportado en effort ≤ high.
- **Tarifa** ([pricing](https://platform.claude.com/docs/en/about-claude/pricing),
  8-oct-2026): Claude Haiku 5.5 para prompts ≤100k tokens →
  **$0,10 / MTok entrada** y **$0,50 / MTok salida**; prompts >100k →
  $0,50 / $2,50 (no aplica a esta batería; el adaptador no calcula el
  tramo superior). Los tokens de thinking cuentan dentro de
  `output_tokens` (se registran aparte en `usage.thinking_tokens` sin
  sumarse dos veces al coste). Respuestas con HTTP 200 rechazadas
  (`max_tokens`, `refusal`, malformado) **también se facturan**; el
  adaptador adjunta `exc.cost` para la guarda (R60).
- **Ventana:** contexto 1M / salida máx. 128k — cubre papers32 sin truncar.

## 2. Celdas: configuración por celda

Campos **comunes a las tres** (y solo estos):

| Campo | Valor |
|---|---|
| `provider` | `anthropic` |
| `model` | `claude-haiku-5-5` |
| `structured` | `true` |
| `normalize` | `true` |
| `retries_malformed` | `2` |
| `usd_in` / `usd_out` | `0.10` / `0.50` (default `PRICES`) |
| Guardas | `--max-case-cost 0.01 --max-cost 0.50` |

Configuración **específica por celda** (inequívoca; no hay «comunes» de
timeouts/`max_tokens` entre H-off y H-adapt):

| Celda | Run | mode | thinking | effort | max_tokens | timeout | case_timeout | ¿Desde el inicio? |
|---|---|---|---|---|---:|---:|---:|---|
| **H-off** (principal) | `llm_haiku55_off_prob` | probabilities | `disabled` | — | 4096 | 120 | 180 | **Sí** — comparable a luna-prob / luna-decisions |
| **H-disc** | `llm_haiku55_off_disc` | discrete | `disabled` | — | 4096 | 120 | 180 | **Sí** — par prob/disc del banco; Brier distinto |
| **H-adapt** | `llm_haiku55_adapt_prob` | probabilities | `adaptive` | `medium` | 8192 | 180 | 300 | **Sí** — default Haiku; mide si thinking aporta |

Justificación de adquirir las tres: coste estimado ($0,05–0,30/celda) cabe
en exploración; discrete vs probabilities es eje fijado; adaptive es el
default del producto.

## 3. Alcance confirmatorio (fijado ahora)

- **Inferencial (Holm 53):** solo **H-off** frente a `jev_v3` (jev-1.13).
  Ninguna afirmación de superioridad sin significación tras Holm.
- **Descriptivas:** H-disc y H-adapt — tablas con línea base de mayoría,
  coste/latencia medidos y contraste descriptivo en fases comunes frente a
  `llm_gpt6luna_prob` y `jev_luna_decisions` / `oai_luna_decisions` (si
  completo). **No** entran en el Holm de 53 ni sustituyen a H-off para
  afirmaciones de superioridad.
- H-off también puede contrastarse descriptivamente con luna-prob /
  luna-decisions (mismas tarifas de entrada $0,10/M).

## 4. Política de adquisición y tras error/parada

**Adquisición:** 1 pasada + **un único** `--retry-errors` por celda.
Guardas en **todas** las invocaciones: `--max-case-cost 0.01 --max-cost 0.50`
(smoke: `0.01` / `0.02`).

**Qué recibe `--retry-errors`:** solo casos con `error` en el registro
(transporte, timeout, malformado agotado, max_tokens/refusal elevados como
error, etc.). No se re-ejecutan casos OK. No se cambia configuración ni se
amplía presupuesto según resultados.

**Si salta la guarda (`cost_stop`):** **parar**. No ampliar `--max-cost` /
`--max-case-cost`, no relajar timeouts ni mutar thinking/effort. El progreso
ya guardado se conserva. Reanudar exige nueva aprobación explícita del
presupuesto.

**Gasto al reintentar un registro:** hoy `run.py` sobrescribe el registro del
caso y el coste del intento fallido previo puede dejar de contar en el
acumulado de la guarda. Ese fallo es del harness compartido (no específico
de Anthropic) y lo corrige Devin en **JEV-78** con un **ledger de gasto
durable**: el acumulado de la guarda **no disminuye** al reintentar. Este
pre-registro **exige esa corrección mergeada antes de ejecutar** la batería
Haiku; JEV-83 no toca `run.py`. Hasta entonces: (1) todo fallo Anthropic con
respuesta HTTP ya lleva `cost` en el registro (`exc.cost`, R60); (2) no
lanzar `--retry-errors` ni la batería completa sin el ledger de JEV-78.

### Smoke (ejecutado 8-oct-2026, ≤ $0,01; sin nuevas llamadas en T21b)

```sh
set -a; . ./.env; set +a
.venv-anth/bin/python -m jevbench.run llm --run smoke_haiku55 \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --phases ood --limit 2 \
  --max-case-cost 0.01 --max-cost 0.02
```

Resultado T21: 2/2 OK (`receta`/`contrato` → `domain=other`),
thinking_tokens=0, coste **$0,00036**, `response.model` /
`resolved=claude-haiku-5-5`. `results/smoke_haiku55/` borrado tras validar.

### Batería — H-off (`llm_haiku55_off_prob`) — 4 comandos

```sh
set -a; . ./.env; set +a
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new --retry-errors
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5 --retry-errors
```

### Batería — H-disc (`llm_haiku55_off_disc`) — 4 comandos

```sh
set -a; . ./.env; set +a
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_disc \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=discrete --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_disc \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=discrete --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_disc \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=discrete --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new --retry-errors
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_off_disc \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=discrete --opt structured=true --opt normalize=true \
  --opt thinking=disabled --opt max_tokens=4096 \
  --opt timeout=120 --opt case_timeout=180 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5 --retry-errors
```

### Batería — H-adapt (`llm_haiku55_adapt_prob`) — 4 comandos

```sh
set -a; . ./.env; set +a
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --max-case-cost 0.01 --max-cost 0.50 --phases all+new --retry-errors
.venv-anth/bin/python -m jevbench.run llm --run llm_haiku55_adapt_prob \
  --opt provider=anthropic --opt model=claude-haiku-5-5 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt thinking=adaptive --opt effort=medium --opt max_tokens=8192 \
  --opt timeout=180 --opt case_timeout=300 \
  --max-case-cost 0.01 --max-cost 0.50 --phases adv4,adv5 --retry-errors
```

## 5. Extensión del adaptador (referencia)

Opciones nuevas (solo `provider=anthropic`):

- `thinking=disabled|adaptive` → `thinking: {type: …}` en Messages
- `effort=low|medium|high|xhigh|max` → se fusiona en `output_config` junto a
  `format` structured
- `timeout` / `case_timeout` / `min_interval` / `max_tokens` — mismo contrato
  operativo que el proveedor acotado de OpenAI
- Fallos con respuesta recibida: `exc.cost` + `diag.usage` (R60); timeout sin
  respuesta → sin `cost` (desconocido)

OpenAI/Gemini y los runs existentes: comportamiento idéntico (sin
`thinking`/`effort`; `reasoning_effort` sigue siendo solo OpenAI).

## 6. Registro de cambios del borrador

| Fecha | Cambio |
|---|---|
| 8-oct-2026 | Borrador inicial: entorno `.venv-anth`, extensión Anthropic, smoke H-off, celdas H-off/H-disc/H-adapt, guardas y contrastes |
| 8-oct-2026 | T21b/R60: coste en fallos Anthropic (`exc.cost`); tabla por celda; 4 comandos/celda; Holm 53 solo H-off; política guarda/retry; ID canónico snapshot (no alias) |
| 8-oct-2026 | Nota: gasto durable en `--retry-errors` → ledger de JEV-78 (Devin); requisito antes de ejecutar; JEV-83 no toca `run.py` |

## RESULTADOS (8-oct)

Ejecución T22 (rev. R63 de Codex: **CORREGIR** — resultados retenidos válidos, con la desviación E11 declarada
abajo). Celdas H-off → H-disc → H-adapt, 4 comandos exactos por celda (`.venv-anth`); sin `cost_stop`; guardas
$0,01/$0,50 en todas las invocaciones. Informe corregido: `<ruta-local>`.

**Desviación de adquisición (bloque 10 de H-adapt):** el corte de sesión de ~07:59 interrumpió el proceso
después de que `decide` devolviera la respuesta de **E11_paciente_recibe_estafa** y antes de persistirla; la
reanudación con el mismo comando la ejecutó de nuevo: **E11 respondido dos veces**, primera respuesta y su coste
informado **no registrados** (pérdida declarada; no se imputan a cero ni se inventan). Reconciliación de logs:
H-adapt **195 respuestas / 194 ids únicos**; H-off y H-disc 194/194. La reanudación de pendientes conserva el
contrato, pero la repetición de E11 es una **desviación de adquisición** (no un `--retry-errors` sobre error);
sin evidencia de selección por GT; no afecta a H-off (única celda inferencial). H-adapt se publica
descriptivamente con esta excepción explícita.

- **Registros retenidos:** 194/194 válidos en las tres celdas (mismos ids, hashes vigentes, 0 errores, 0
  refusals); configuración efectiva congelada verificada; `resolved=claude-haiku-5-5` en todo.
- **Resumen del scorer (IC = bootstrap estratificado 2.000/semilla 0):** H-off **61,74 [54–69]**, H-disc
  **64,13 [57–71]**, H-adapt **69,29 [62–76]**; mayoría trivial 0. Brier noul 0,061/0,085/0,059.
- **Inferencial (única familia) H-off vs `jev_v3`:** Holm **53 pruebas, 0 significativas** (p Holm mínima 1;
  nominal mínima 0,03125 en adv1/urgency y adv4/urgency) — **sin superioridad ni equivalencia demostradas**.
- **Coste registrado (cotas):** H-off **$0,0501677**, H-disc **$0,0314248**, H-adapt **$0,0704196 — cota
  inferior**: cubre los registros retenidos, **no toda la adquisición** (≥1 intento pagado de E11 sin coste
  recuperado). Tokens in/out 387.177/22.900 · 271.828/8.484 · 387.371/63.365; máx/caso retenido
  $0,0013383/$0,0011962/$0,0013389 (ninguno alcanza $0,01).
- **Thinking (registros finales):** H-adapt 126/194 casos (media 207,58, máx 689); H-off/H-disc 0 — excluye la
  respuesta perdida de E11. Latencias: resumen (base+new, 154 casos) 1.656/1.285/2.639 ms; medianas sobre 194
  registros 1.656,5/1.288,5/2.655,5 ms — universos distintos, sin mezclar.
- **Descriptivas en fases comunes:** 10 puntuables — 61,74/64,13/69,29 vs luna-prob 61,23, nativo 38,25, Jev
  45,38; 6 completas de OpenRouter — 71,70/74,50/74,62 vs luna-prob 75,60, 47,70 (ambas rutas luna-decisions),
  Jev 54,63. Descriptivas: que H-adapt puntúe más no demuestra contribución causal del thinking.

**Conclusión (R63):** las tres celdas retienen 194 casos completos sin errores; H-off 61,74 sin superioridad
acreditada frente a Jev (Holm53 = 0); H-disc 64,13 y H-adapt 69,29 descriptivos; thinking en 126 casos con más
gasto/latencia, sin causalidad aislada; la primera respuesta de E11 se perdió por el corte y su reejecución es
desviación (≥195 respuestas visibles); $0,0704196 cubre los registros retenidos, no toda la adquisición.
