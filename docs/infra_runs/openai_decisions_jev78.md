# JEV-78 — `openai_decisions`: Decisions API nativa de OpenAI (`POST /v1/decisions`, `gpt-6-luna`)

**BORRADOR pre-registrado el 7-oct-2026, antes de ejecutar la batería;
actualizado el 8-oct (reorientación al SDK oficial + refusal por pregunta,
antes de la batería).**
Aprobación: comentario de JEV-78 del 7-oct («probar la Decisions API nativa
de OpenAI con la batería de Jev»). Objetivo declarado: saber si el modelo y
la versión coinciden con `openai/gpt-6-luna-decisions-20261006` servido por
OpenRouter, y si los 6 rechazos del run `jev_luna_decisions` vienen de
OpenAI o de la capa de OpenRouter. Adaptador:
`jevbench/adapters/openai_decisions.py` (registrado como
`openai_decisions`), sobre el **SDK oficial** `openai==3.26.0`
(`client.decisions.create`, import perezoso); tests offline
`tests/test_openai_decisions.py`.
Comparaciones fijadas: `jev_luna_decisions` (JEV-80, misma API por
OpenRouter, 188/194, 6 rechazos 502 «refused to answer») y `jev_v3`
(jev-1.13-20260917, 194/194, referencia del banco). Fuentes auxiliares
descriptivas: `llm_gpt6luna_prob` (mismo modelo vía system-one-adapter,
ajustado 61) y `docs/infra_runs/luna_decisions_jev81.md` / `_jev82.md`.

## 0. Mapeo y criterio de rechazo (fijado antes de medir)

**Mapeo (sin tocar `battery.py` ni `questions_hash`):**

- `input` = `state` del caso, literal. La batería no tiene instrucciones
  globales: cada pregunta viaja con sus `instructions` propias (la API no
  tiene `system`).
- `noul` → `predicate`; respuesta `probability` → wire `noul`.
- `choice` → `choice` con `choices[{value, description}]`: `value` =
  etiqueta del criterio, `description` = su texto, **en el orden de
  `criteria`** (rotación `choice_order` opcional, misma semántica que el
  adaptador `jev`: d0 byte a byte). Respuesta `choice` + `probabilities[]`
  por `value` → wire `choice` + `probabilities{etiqueta: p}`; `confidence`
  se conserva.
- `score` → `score` con `levels[{label, description}]`: etiqueta = texto
  antes del primer `:` del criterio (`bajo`/`medio`/`critico`…),
  descripción = el resto. Respuesta `score` (media ponderada de índices) +
  `probabilities[]` por `value` (= índice de nivel) → wire `score` +
  `probabilities{índice: p}` + `legend` (mismo formato que el run
  OpenRouter). El decimal viaja tal cual; el vector se lee por índice.
- `answers[]` se empareja por `name`; respuesta ausente, `name`
  duplicado, tipo cambiado, vector de probabilidades incompleto o con
  etiqueta/índice ajeno, `choice` fuera de los criterios, escalar no
  finito o fuera de rango, o `answers` no lista = **error local de
  contrato** (`ContractError`, mensaje «contract(local):…») — nunca un
  vector parcial ni un éxito fuera de contrato. `pydantic` valida los
  tipos del SDK; el adaptador valida rangos y completitud (R58 §3).

**SDK y entorno:** `openai==3.26.0` en un venv aparte `.venv-oai`
(`.venv-llm` fija openai 3.16.2 para system-one-adapter y no se toca):

```sh
python3 -m venv .venv-oai && .venv-oai/bin/pip install openai==3.26.0
```

Los comandos de adquisición del §2 se ejecutan con `.venv-oai/bin/python`.
El adaptador crea `OpenAI(api_key, base_url=https://api.openai.com/v1,
timeout=120, max_retries=0)` — los reintentos propios del SDK van
**desactivados** para que cada intento (y su `usage`) quede visible para
la guarda. Errores con estado reintentable (429, 5xx) y errores de
conexión/timeout del SDK comparten el presupuesto `retries` del decide;
4xx no reintentables y errores ajenos al SDK fallan en el acto.

**Rechazo — POR PREGUNTA (semántica nativa, distinta de OpenRouter):**
un `answers[]` con `type: "refusal"` rechaza **solo su pregunta** («the
host may decline one question»). Reglas fijadas:

- **Negativa parcial:** el registro **no es error**; el caso se conserva
  con la pregunta marcada `{"type": "refusal"}` en `answers` y listada en
  `refusals` del registro. Esa pregunta **puntúa 0** (error en su
  pregunta, `metrics.point`); no tiene distribución: queda fuera de
  calibración, de los pares de acuerdo/Δp (listada en `no_pair`) y de
  los vectores pareados. El resto del caso puntúa normal.
- **Negativa total** (TODAS las preguntas con `refusal`): es la negativa
  del caso entero — el adaptador eleva `ProviderRefusal` y el registro
  queda con `error` empezando por `ProviderRefusal:` + «refused to
  answer», equivalente al 502 de la ruta OpenRouter (donde la negativa
  era del caso completo).
- **Clasificador** (implementado en `jevbench/jev78.py:error_kind`,
  usado en cobertura/rechazos y todos los contrastes de este run):
  `rejection` si `error` empieza por `ProviderRefusal:` **o** cumple el
  criterio JEV-81 (502 parseado + «refused to answer»); `local` si
  empieza por `ContractError:`; el resto (timeout, transport, other)
  delega en `jev81.error_kind` tal cual. Solo mensaje/estado — nunca ids
  ni GT.
- **Comparación con OpenRouter:** allí los 6 rechazos fueron del caso
  entero (502); aquí la negativa parcial conserva el caso — la
  equivalencia de cobertura es registro-con-error vs registro-con-error
  (listas `both`/`only_openrouter`/`only_native`), y las negativas por
  pregunta se listan aparte (`question_refusals`, `score_run.refusals`).

**Coste en rechazos (R58 §4):** el coste informado (`usage.cost`, o
`input_tokens × $0,10/1M` si no viene) se **acumula sobre todos los
intentos del decide, incluidos los que devuelven refusal**. En una
negativa total el `ProviderRefusal` lleva `e.cost` y `jevbench.run` lo
registra en el registro de error (`rec["cost"]`) y lo suma al acumulado
durable de la guarda — un rechazo no convierte en desconocido lo pagado.
La nota de cota inferior sigue aplicando solo a lo realmente no
informado.

**Verificación de humo (única llamada real autorizada por etapa):**
7-oct (cliente HTTP a mano) y 8-oct (SDK, misma orden con
`.venv-oai/bin/python`, run `smoke_oai_decisions_sdk`, caso `receta`,
3/3 respuestas, 2618 ms, $0,000052 — 520 tokens de entrada × $0,10/1M):
`.venv-oai/bin/python -m jevbench.run openai_decisions --run
smoke_oai_decisions_sdk --phases ood --limit 1 --max-case-cost 0.01
--max-cost 0.01` respondió correctamente. Nombres de campo reales
verificados:
`answers[]{type,name,...}`, predicate→`probability`, choice→`choice` +
`probabilities[{value,probability}]` + `confidence`, score→`score` +
`probabilities[{value,label,probability}]` + `confidence`;
`usage{input_tokens,output_tokens,total_tokens}` **sin** `usage.cost` → el
coste se calcula `input_tokens × $0,10/1M`; `model` en la respuesta repite
el alias `gpt-6-luna` **sin fecha de snapshot**, y la respuesta no trajo
cabeceras de modelo/versión (`api_headers` vacío). Consecuencia fijada:
la comparación de versión (§3.2) puede quedar **inconclusa por versión
desconocida** — el alias no discrimina el snapshot servido.

## 1. Validación previa (obligatoria, antes de cualquier contraste)

- `oai_luna_decisions` cubre las 11 fases con todos los ids vigentes;
  la excepción declarada de `P02` en papers32 aplica igual que en JEV-81
  (extra permitido en fuentes históricas, nunca evaluado). Ausencias o ids
  ajenos = error de entrada.
- `questions_hash` de cada fase igual al vigente y al del run OpenRouter.
- Vectores pareados conformes al contrato de la batería por pregunta
  (`jev78._check_paired`): componente `invalid`/`missing` en un éxito
  pareado = error de entrada. El estado `refused` (negativa por pregunta,
  §0) es un resultado de adquisición declarado — no es conformidad ni
  error de entrada; se lista en `question_refusals` y queda fuera de los
  pares (`no_pair`).
- Cada fase del run declara `meta.cost_guard = {"max_case_cost": 0.01,
  "max_cost": 0.05}` — la guarda es parte del protocolo de adquisición.
- Se registran `meta.model`, `meta.resolved`, `meta.api_headers` y el
  `usage` por caso (procedencia de versión y coste; regla 4).

## 2. Adquisición (política fija; misma que JEV-80/81/82)

1 pasada completa + **1** `--retry-errors` por bloque (all+new, luego
adv4,adv5). La API de decisiones no admite temperature ni seed. Si
aparecen rechazos nuevos no se decide reintentar más después de verlos.

**Intentos por caso:** `--opt retries=3` explícito, igual que la celda
OpenRouter (1 decide = 1–3 intentos HTTP). Los errores de transporte, los
HTTP **y los `refusal` estructurados** comparten ese presupuesto — en la
ruta OpenRouter la negativa era un HTTP 502 que el adaptador `jev`
reintentaba dentro del mismo `decide`; tratar la negativa nativa igual
mantiene la política de adquisición comparable entre las dos celdas.

**Guarda de coste efectiva** (mismas desigualdades que JEV-82; las aplica
`jevbench.run` tras registrar cada caso y antes del siguiente, y también
antes del primer caso de cada fase con trabajo pendiente): caso con coste
registrado > $0,01 → parada; acumulado registrado del run (todas las
invocaciones) > $0,05 → parada. La parada conserva el progreso y deja la
causa en `meta.cost_stop`; repetir el comando no elude el presupuesto —
ampliarlo exige nueva aprobación. **Costes desconocidos** (casos sin
coste informado): no disparan la guarda ni suman; se cuentan y listan
aparte — limitación declarada si el endpoint dejara de informar
`usage.input_tokens`. Estimación ~$0,02 (la pasada equivalente por
OpenRouter costó $0,0194; el humo confirmó ~$0,00005/caso en ood).

```sh
.venv-oai/bin/python -m jevbench.run openai_decisions --run oai_luna_decisions \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
.venv-oai/bin/python -m jevbench.run openai_decisions --run oai_luna_decisions \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
.venv-oai/bin/python -m jevbench.run openai_decisions --run oai_luna_decisions \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
.venv-oai/bin/python -m jevbench.run openai_decisions --run oai_luna_decisions \
    --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5 --retry-errors
```

El análisis (todo offline, lee `results/`): `python3 -m jevbench.jev78
analyze [--json F]` — valida §1 y emite cobertura/rechazos, negativas por
pregunta, versiones, acuerdo CP95, Δ ajustado, McNemar–Holm vs `jev_v3`,
Δp, coste y latencia con el clasificador `jev78.error_kind`.

## 3. Contrastes y reglas de lectura (congeladas)

Contraste principal: `oai_luna_decisions` (nativo) frente a
`jev_luna_decisions` (OpenRouter); referencia del banco: `jev_v3`.

1. **Cobertura y rechazos:** casos por run; errores por `error_kind` con
   el criterio del §0 (rejection/timeout/transport/local/other); listas
   `both` / `only_openrouter` / `only_native`. **Regla fijada:** un caso
   con error en cualquiera de los dos runs sale de todos los contrastes
   pareados y su fase deja de ser completa para el ajustado; las listas se
   publican explícitas, sin imputación.
   **Origen de la negativa (lectura factual ACOTADA — R58 §1, sin regla
   dura de atribución):** se publican las listas de casos con negativa
   por OpenRouter y éxito nativo, los rechazados por ambas rutas, las
   versiones conocidas/desconocidas y las condiciones de adquisición.
   Un éxito nativo muestra que ese caso **pudo responderse por esa
   ruta** en esa ejecución — **no prueba** qué capa produjo la negativa
   histórica (alias sin snapshot = versión subyacente desconocida, rutas
   con contratos distintos, ejecuciones separadas sin seed fijable).
   Seis negativas repetidas en ambas rutas son *consistentes* con
   comportamiento compartido, sin identificar por sí solas la causa.
2. **Versión servida:** `model`/`resolved` de cada lado sobre los éxitos
   pareados; las versiones **ausentes se conservan y se listan por id**
   (`unknown`), convención JEV-82 §3.6: `same_model` solo es true con
   ≥ 1 par conocido e igual y **cero** ausencias ni discrepancias. La
   nativa devuelve el alias sin fecha (verificado en el humo), así que la
   comparación puede quedar «versión desconocida»: se declara tal cual,
   sin suplirla.
3. **Acuerdo de decisiones pareado** (decisión por criterio del scorer,
   misma convención que S202/JEV-81/82) con IC95 Clopper-Pearson.
   Referencia **descriptiva** ≥ 97 % sobre la estimación puntual — la
   convención de repetibilidad, no un umbral de veredicto. Una pregunta
   rechazada no tiene decisión: no entra ni al numerador ni al
   denominador y se lista en `no_pair` (nunca cuenta como acuerdo ni
   desacuerdo).
4. **Δ ajustado (nativo − OpenRouter)** sobre las **fases completas en
   ambos runs** (intersección; convención `paired_delta`: peso igual por
   fase, baselines fijas, bootstrap pareado por clusters ES/EN + PMID,
   10 000 réplicas, semilla 271828, IC95). Si los conjuntos difieren, Δ
   sobre la intersección y `same_phases=false`; ajustados propios aparte.
   **Lectura descriptiva** — sin umbral de equivalencia fijado: un IC que
   incluye 0 no prueba igualdad de endpoint.
5. **McNemar–Holm frente a `jev_v3`:** familia completa de **53 pruebas**
   (acierto estricto por pregunta×fase, Holm sobre la familia), misma
   convención que JEV-81. Una pregunta rechazada puntúa 0 → su acierto
   es `False`. Descriptivo: sin equivalencia demostrable.
6. **Δp, coste y latencia:** media y máximo |Δp| sobre componentes
   escalares comunes alineados por etiqueta (una pregunta rechazada no
   tiene componente escalar: fuera del Δp); coste = suma de lo
   registrado por run **incluidos los registros de error con coste
   informado** (desconocidos aparte, nunca cero; cota inferior del coste
   de adquisición) y máximo por caso; latencia = `ms` mediano por fase.
   Todo descriptivo. La comparación con `llm_gpt6luna_prob`
   (ajustado 61) y `jev_v3` (45,4) se limita a una fila descriptiva de
   ajustados con IC95 — sin contraste confirmatorio pre-registrado.

Todo lo no fijado aquí (rotación d1/d2/d3, cascada nativo→revisor Jev,
réplica de repetibilidad, uso como revisor) es **EXPLORATORIO** y se dirá
así; requiere nueva aprobación y pre-registro propio, como en JEV-81 §4.

## 4. Lo que no se hace en esta prueba

| Descartado | Motivo |
|---|---|
| Rotación del orden | No aprobada para esta celda; la sensibilidad al orden de luna-decisions ya se midió por OpenRouter (JEV-82) |
| Cascada o uso como revisor | Fuera del alcance aprobado (mismo criterio que R51/JEV-82 §4) |
| Réplica de repetibilidad | No aprobada; la ruta OpenRouter ya midió 934/934 (JEV-81) |
| Batería sin guardas | La guarda `--max-case-cost 0.01 --max-cost 0.05` es parte del protocolo |

## Registro de cambios

| Fecha | Cambio |
|---|---|
| 7-oct-2026 | Pre-registro inicial: adaptador `openai_decisions` + tests offline (mapeo, normalización, refusal→rejection, error HTTP, coste por tokens, `choice_order` d0/d1 con `perm_sha256`) + humo real de un caso (`smoke_oai_decisions`, verifica formato y campos; `model` devuelve solo el alias, sin snapshot fechado ni cabeceras de versión) |
| 8-oct-2026 | Reorientación al SDK oficial `openai==3.26.0` (venv aparte `.venv-oai`, `client.decisions.create`, `max_retries=0`; el cliente HTTP a mano se elimina) y refusal **por pregunta**: negativa parcial = caso conservado con la pregunta marcada y puntuada 0; negativa total = `ProviderRefusal` (`rejection`). Arreglos de R58: lectura factual acotada del origen de la negativa (§3.1, sin regla dura de atribución), clasificador propio `jev78.error_kind` implementado y usado en los contrastes (`ProviderRefusal:`→rejection, `ContractError:`→local), validación de contrato completa (vectores, rangos, etiquetas, duplicados) y coste informado contabilizado también en intentos rechazados (`e.cost` → registro → guarda). Análisis `python3 -m jevbench.jev78 analyze` |
| 8-oct-2026 | Correcciones de R58c (mismo protocolo, sin cambiar reglas): (1) `e.cost` lleva el gasto informado acumulado con **cualquier** desenlace terminal del decide — timeout, HTTP 4xx, `ContractError` — conservando la clase/clasificación del error; (2) `jevbench.run` mantiene un **ledger durable** `meta.cost_ledger` por run (acumulado informado de todas las invocaciones, monótono) que la guarda consulta junto a los registros vigentes — un `--retry-errors` que reemplaza registros pagados ya no reduce el acumulado; (3) en `jev78` la **versión acreditada** exige id con fecha de snapshot — el alias `gpt-6-luna` sin fecha queda observado pero cuenta como desconocido en `same_model`/`unknown`; (4) el informe cuenta preguntas rechazadas (qids), no casos |

## RESULTADOS (8-oct)

Ejecución T22 (rev. R63 de Codex: **APTO**; `jev78 analyze` reproducido con JSON idéntico). Sin desviaciones:
4 comandos exactos del §2 en orden (`.venv-oai`), exits 0, ambos `--retry-errors` sin trabajo; sin `cost_stop`.
Informe corregido: `<ruta-local>`.

- **Cobertura:** nativo **194/194** (11 fases, excepción P02 declarada), 0 errores de caso; OpenRouter 188/194.
- **Negativas:** nativas **por pregunta: 8 en 6 casos** (department en B05, C08, D05, D07, E01, E02; urgency
  además C08 y D07) — casos conservados, esas preguntas puntúan 0 y salen de calibración/pares/Δp. Totales:
  **both=0, only_native=0, only_openrouter = esos 6 casos**. Lectura acotada: diferencia de cobertura bajo
  contratos distintos, sin identificar la capa causal del rechazo histórico.
- **Versión:** alias `gpt-6-luna` sin snapshot, cabeceras vacías → **0 pares conocidos, 188 desconocidos,
  0 discrepancias; versión inconclusa, same_model=false**.
- **Acuerdo:** **934/934** [CP95 99,6058–100 %] (referencia ≥97 % descriptiva satisfecha); Δp **media y máx 0**
  (2.091 componentes) — sin demostrar equivalencia general entre endpoints.
- **Δ ajustado nativo−OpenRouter:** **0,00 [0,00; 0,00]** sobre las 6 fases completas comunes;
  `same_phases=false`. Ajustados propios descriptivos: nativo **38,25 [27–48]** (11 fases, refusals a 0),
  OpenRouter 47,70 [36–59] (6) — conjuntos distintos, sin contraste causal; en las 6 comunes, ambos 47,70.
- **McNemar–Holm vs `jev_v3`:** 53 pruebas, **0 significativas**.
- **Coste registrado:** nativo **$0,0204992** (194 registros, máx $0,000669, 0 desconocidos; 6 registros con
  coste 3× el input del último intento por retries internos de refusal — `usage` guarda solo el último intento,
  `cost` acumula), OpenRouter $0,0193778 (188, 6 desconocidos). Ledger durable concordante. Latencias medianas:
  nativo 431–505 ms vs OpenRouter 656–708 ms por fase.

**Conclusión (R63):** la ruta nativa completó 194 casos conservando ocho negativas parciales en seis casos que
OpenRouter había rechazado enteros — diferencia de cobertura bajo contratos distintos, sin identificar la capa
causal; el alias sin snapshot deja la versión inconclusa; acuerdo 934/934 y Δp=0 sin equivalencia demostrada;
Δ ajustado 0,00 en las 6 fases comunes; coste $0,0204992 con refusals internos contabilizados y Holm53 sin
diferencias significativas frente a Jev.
