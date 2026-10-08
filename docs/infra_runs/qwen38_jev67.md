# JEV-67 — Qwen3.8-27B local con preguntas visibles (thinking off, temp 0)

Manifiesto del experimento: **pre-registro congelado** (abajo, verbatim de la
issue v2) + resultados al final. La issue:
<<tracker>

## Estado del congelado

- Base del repo: `dba4852` (incluye JEV-66). Cambios del harness para JEV-67 en
  working tree (opción `rotate_choice` del adaptador, `jevbench/rotation.py`,
  `--prefix` en diag66, `jevbench/jev67.py`, `jevbench/probe_injection.py`,
  `tests/test_jev67.py`).
- **Desviación autorizada**: el pre-registro pedía commitear el manifiesto
  antes de inferir; el usuario ordenó NO commitear (lo hará tras la revisión
  de codex). El texto del pre-registro quedó congelado en este fichero antes
  de cualquier inferencia y no se toca después.
- Suite: 141 tests en verde (`.venv-llm`), incluidos los nuevos de rotación,
  P+fix, prefix, puerta y sonda.

## Valores congelados calculados (cierre de §7.3)

`perm_sha256` por familia de esquema (rot1 = `rotation.rotate_choice(qs, 1)`):

| Familia | `questions_hash` | `perm_sha256` rot1 |
|---|---|---|
| triaje/adv (9 fases) | `9a81e9763d94` | `15f6174736a0` |
| papers32 | `74026502c3ac` | `030bd9f1149c` |
| ood | `93ea3deb7eab` | `15a3e725392c` |

`sha256[:12]` del `response_format` enviado (JSON del kwargs completo, orden
de claves ordenado — reproducido exacto contra un raw de JEV-66):

| Familia | prob rot0 | prob rot1 | disc rot0 |
|---|---|---|---|
| triaje/adv | `4f5fbfe27d29` | `b790add48443` | `7e1f566a046d` |
| papers32 | `ab40cf338a5e` | `bbd960b4e379` | `77048d766207` |
| ood | `ae0862d3c2be` | `f1c6151ba513` | `1a15bf4dfe1f` |

Otros hashes congelados:

- Relleno de la variante (T)-d (`probe_injection.PADDING`,
  `"Padding note for schema-size discrimination. " x 48` ≈ 300 tokens):
  `47aae553e6a3`.
- Documentos del canario (`probe_injection.CANARY_DOCS`, 5 textos neutros
  inventados, verbatim en `jevbench/probe_injection.py`):
  `cacf09380be0`, `f9b6cba66dad`, `b58dc5ea1b8b`, `4ab8cc75236c`,
  `2de5346cdfac`.

---

# PRE-REGISTRO CONGELADO (v2, verbatim de la issue)

## 1. Resumen

JEV-66 confirmó que todos los runs `structured=true` locales de Qwen3.8-27B (SGLang y
llama.cpp) se midieron **a ciegas**: la librería solo envía el system prompt y el documento,
las preguntas viajan en el `response_format` y esos servidores no lo inyectan en el prompt.
La opción `inject_schema_in_prompt=true` lo arregla (0 nulos en 12 casos × 3 reps × 3
backends; decisiones 56/56 iguales a `typesafe_nostruct`).

Esta issue mide, sobre la batería completa (195 casos × 11 fases), **una configuración
concreta**: Qwen3.8-27B servido en local, **thinking desactivado, temperatura 0**, con las
preguntas verificablemente visibles. No es el «techo» del modelo: el thinking, otras
temperaturas o prompts quedan fuera (§4.3). En concreto:

1. el marcador de esa configuración por la ruta del contrato (struct + inyección), en tres
   precisiones/backends;
2. si, **en FP8**, la gramática forzada cambia decisiones frente a nostruct con las mismas
   preguntas visibles (¿generaliza el 56/56?);
3. el efecto del orden de las opciones `choice` en `probabilities` con preguntas visibles;
4. `discrete` con inyección (¿desaparecen los fallos de papers vistos a ciegas?);
5. si vLLM y Ollama hacen visibles las preguntas del `response_format` (en la versión y el
   modelo que se prueben);
6. el impacto de `normalize` en la condición visible (auditoría offline, sin run nuevo).

Coste: solo GPU local (<host>, <host>, <host>). **Cero API**. Sin tocar GT, scorer, `battery.py` ni
runs históricos.

## 2. Evidencia de partida (verificada contra el repo, `dba4852`)

| Hecho | Fuente |
|---|---|
| Struct local a ciegas: tokens de entrada 205–222 por caso frente a 789–806 con el esquema visible; **conteos idénticos** en NVFP4, FP8 y GGUF (mismo tokenizador/plantilla) | `results/diag_qwen38_jev66_*` |
| `inject` = `nostruct` byte a byte en el system prompt (test) y en tokens (A01 806, A02 789, C01 792, C02 796 en ambos) | `tests/test_llm_adapter.py::test_inject_schema_in_prompt`; `diag_qwen38_fp8_typesafe_nostruct_r1` |
| El apéndice inyectado es literalmente `"Return one JSON object that matches this schema exactly:\n\n{schema}\n\nDo not include text or Markdown fencing before or after the JSON object."` con `schema` = `to_json(schema)` del mismo esquema que va en `response_format.json_schema.schema`. Las preguntas viajan en sus `description` (`"…\nQuestion: <instructions>"`) y cada opción `choice` como propiedad con su criterio en `description`. **La palabra «criteria» no aparece** | `system_one_adapter/_client.py:83`, `providers/openai.py:35`, `raw` de JEV-66 |
| Cada intento capturado en `raw` trae su propio `llm_response.usage.prompt_tokens` (y `cached_tokens` aparte); `usage.input_tokens` del caso es `input_tokens_total` = **suma de todos los intentos**, reintentos con mensajes de corrección incluidos | `jevbench/adapters/llm.py` (`decide`), `raw` de JEV-66 |
| Referencia por caso válida: `llm_qwen38_27b_fp8_nostruct_prob` tiene 195/195 casos con **un único intento** y `input_tokens` presente → su total = primer intento | comprobado sobre `results/` |
| Batería nostruct local existente: NVFP4 **52**, FP8 **49**, GGUF(<host> CUDA) **48** — a temp 0.7, top_p 0.8, presence 1.5, sin seed. El FP8 49 corrió en **<host>** (no en <host>) | manifiestos `llm_qwen38_27b_*_nostruct_prob.md` |
| Cerebras Qwen3.8-27B (inyecta; **temp 0 + `reasoning_effort=low`**): prob struct 59, prob nostruct 65, disc 58/58 | `docs/resultados.md` |
| JEV-65 discrete struct a ciegas: papers P01/P02 con timeouts de 300 s (+1 `length` en NVFP4) en 2/2/2 (nvfp4) y 2/1/1 (fp8) por rep | `docs/infra_runs/diag_qwen38_prompt_ablacion.md` |
| Preguntas `choice` de la batería: triaje/adv (9 fases, 160 casos) 1 × 4 opciones; papers32 2 × 5 + 1 × 3; ood 1 × 4 → **259 decisiones `choice`: 163 de k=4, 64 de k=5, 32 de k=3. No hay `choice` binarias** | `jevbench/battery.py` |
| Con un vector nulo la librería elige la primera clave (`max(answers, key=…)`, empate); el scorer lee `ans["choice"]` | `_client.py`, `jevbench/metrics.py:17` |
| Ollama struct (adv1, temp 0): 8/10 uniformes; tokens 912, 815, 483, 1088, 729, 575, 513, 561, 586, 430 — sin relación con el nostruct del mismo caso (804…785) ni con el ciego (~220). Ollama nostruct: 779–815 (= SGLang −2) | `results/smoke_qwen38_ollama_{struct,nostruct}` |
| vLLM en el repo: solo `.venv-vllm` en <host> (`vllm==0.29.0`), usado vía `decider.serve_vllm`; **no hay receta documentada de servidor OpenAI-compatible** ni constancia de que 0.29 cargue Qwen3.8-27B. Regla GB10: `gpu_memory_utilization ≤ 0.45`, `MAX_JOBS=2`, memoria con `free -g`; primer arranque JIT ~25 min | `docs/dgx-spark.md`, `scripts/serve_decider_nvfp4.sh` |
| `normalize`: tolerancia 1e-6; reescalado positivo (cero → uniforme). `choice` = argmax en orden de criterios; `score` = valor esperado sobre `rescale_probabilities` **siempre** (normalice o no) y el scorer lo redondea con `round()` (redondeo bancario); `noul` no se normaliza | `probability_normalization.py`, `_client.py:123-160`, `metrics.py:29` |

**Sobre `capture_raw`:** guarda el cuerpo que **envía el cliente**, idéntico sea cual sea el
servidor; no muestra el prompt que el servidor renderiza. Lo que hace el servidor se mide
del lado servidor (conteo de `prompt_tokens` del primer intento y una prueba conductual con
canario, §6). `capture_raw` sigue siendo obligatorio como prueba de lo que salió del
cliente y como fuente del primer intento.

## 3. Preguntas de investigación

| ID | Pregunta | Alcance |
|---|---|---|
| **RQ1** | ¿Qué ajustado obtiene Qwen3.8-27B local, thinking off, temp 0, con preguntas visibles por la ruta struct + inyección? | por precisión/backend (FP8, NVFP4, GGUF) |
| **RQ2** | Con preguntas visibles, ¿la gramática forzada cambia decisiones frente a nostruct? | **solo FP8/SGLang**; no se generaliza a otras precisiones |
| **RQ3** | ¿Cómo se compara nostruct temp 0 con el 49 histórico (temp 0.7)? | **descriptiva**: cambian host (<host>→<host>), temperatura, top_p, presence y seed; no aísla la temperatura |
| **RQ4** | Con preguntas visibles en `probabilities`, ¿el orden de las opciones `choice` cambia decisiones o acierto? | FP8/SGLang |
| **RQ5** | En `discrete` con inyección, ¿desaparecen los fallos de papers (timeouts/`length`) y cuánto saca frente a `probabilities`? | NVFP4 y GGUF |
| **RQ6** | ¿vLLM y Ollama hacen visibles las preguntas del `response_format`? | la versión de servidor y el modelo probados |
| **RQ7** | ¿Cuánto pesa la normalización en la condición visible? | auditoría offline de A1, A2, A3, B1, C1 |
| **RQ8** | Dispersión entre FP8/SGLang, NVFP4/SGLang y GGUF/llama.cpp SYCL con la misma ruta | descriptiva |

## 4. Matriz

### 4.1 Celdas de batería (195 casos × 11 fases salvo A4; temp 0; una pasada)

| Celda | Run (nombre congelado) | Host | Ruta | RQ |
|---|---|---|---|---|
| **A1** | `llm_qwen38_27b_fp8_inject_prob` | <host> FP8 | struct + inject, prob | RQ1, RQ2, RQ7, RQ8 |
| **A2** | `llm_qwen38_27b_fp8_nostruct_t0_prob` | <host> FP8 | nostruct, prob | RQ2, RQ3, RQ7 |
| **A3** | `llm_qwen38_27b_fp8_inject_rot1_prob` | <host> FP8 | struct + inject, prob, `rotate_choice=1` | RQ4, RQ7 |
| **A4** | `llm_qwen38_27b_fp8_inject_prob_s202` | <host> FP8 | = A1 con seed 202, **solo papers32 + adv3** (52 casos, 260 decisiones) | suelo de ruido para RQ2/RQ4 |
| **B1** | `llm_qwen38_27b_nvfp4_inject_prob` | <host> NVFP4 | struct + inject, prob | RQ1, RQ7, RQ8 |
| **B2** | `llm_qwen38_27b_nvfp4_inject_disc` | <host> NVFP4 | struct + inject, discrete | RQ5 |
| **C1** | `llm_qwen38_27b_arcgguf_inject_prob` | <host> GGUF | struct + inject, prob | RQ1, RQ7, RQ8 |
| **C2** | `llm_qwen38_27b_arcgguf_inject_disc` | <host> GGUF | struct + inject, discrete | RQ5 (réplica) |

**Por qué A1 y A2 (las dos) y solo en FP8.** A1 es la ruta del contrato TypeSafe (gramática
= formato garantizado) con las preguntas visibles; es la que se recomendará para runs
locales y va en los tres hosts (RQ1, RQ8). A2 es el control que da sentido a A1: sin ella no
sabemos si la gramática cambia decisiones a escala (RQ2; JEV-66 solo lo vio en 12 casos).
Se corre solo en FP8 (pesos oficiales); la conclusión de RQ2 queda **limitada a FP8/SGLang**.
A2 frente al 49 histórico es solo descriptiva (RQ3): no es el mismo host ni el mismo
muestreo.

**Rotación (A3), dentro de esta issue.** Con preguntas visibles cuesta ~25 min y las 259
decisiones `choice` dan más potencia que los 6 casos de JEV-65. Se empareja con A1 (mismo
servidor, misma sesión). Su validación de pipeline es P+ (§4.2).

**Discrete (B2, C2).** NVFP4 es donde JEV-65 vio el `length` además de los timeouts; GGUF lo
replica en otro motor de gramática.

**`normalize=false`: no se ejecuta** (§8.5). El reescalado no cambia decisiones en ninguna
de las tres rutas; se sustituye por una reproducción offline desde el `raw`. Contar los
nulos como error exigiría cambiar el scorer: se reporta solo como sensibilidad descriptiva.

### 4.2 Celdas de diagnóstico

| Celda | Qué | Host | RQ |
|---|---|---|---|
| **G** (puerta) | Verificación de visibilidad previa a cada batería (§5.1): 4–5 evaluaciones por host × modo | cada host × modo | requisito |
| **P+fix** | Test determinista (servidor falso): un vector nulo pasa por adaptador + rotación + scorer y la etiqueta elegida es la primera clave del orden enviado, rotado y sin rotar | portátil | RQ4 (valida el pipeline) |
| **P+live** | `typesafe_struct` **a ciegas**, 12 casos JEV-63, **rot0 y rot1 en la misma sesión**, 1 rep (`--reps 1 --cells typesafe_struct`) | <host> FP8 | RQ4 (pipeline sobre datos reales) |
| **S-\*** | Sonda de visibilidad (§6): tokens del primer intento + canario conductual | <host> SGLang, <host> SGLang (solo peticiones normales), <host> llama.cpp, vLLM y Ollama propios en <host> | RQ6 |
| **D-vllm / D-ollama** | Conductual con el modelo del benchmark: celdas JEV-66 × 12 casos × 1 rep, **solo si el servidor sirve Qwen3.8-27B** | <host> (servicios propios) | RQ6 |

### 4.3 Lo que no se ejecuta, y por qué

| Descartado | Motivo |
|---|---|
| `normalize=false` en batería | No cambia decisiones por construcción (§8.5); auditoría offline |
| nostruct t0 en NVFP4/GGUF | RQ2 queda declarada solo para FP8; ampliarla es otra issue |
| Celda que aísle la temperatura (nostruct temp 0.7 en <host>) | Fuera de alcance; RQ3 queda descriptiva |
| Repeticiones completas de cada batería | Temp 0: JEV-66 dio acuerdo 111–112/112 entre reps; A4 da el suelo de ruido |
| Rotación en `discrete` o de niveles `score` | discrete ya medido en JEV-65; rotar niveles ordinales cambia su semántica |
| Thinking activado | Principal diferencia que queda con Cerebras (`reasoning_effort=low`), sin equivalente directo en SGLang y ×5–10 de latencia. **Siguiente issue** (§8.4) |
| Ollama de <host> | Es servicio del usuario: `keep_alive:0`, cargar otro modelo o reiniciarlo violan «solo consumir». Todo Ollama va en contenedor propio en <host> |
| Instalar otra versión de vLLM | Infraestructura nueva; si `vllm==0.29.0` no carga el modelo, la rama queda «no ejecutable» (§6.3) |
| Issue upstream en `system-one-adapter` | Se redacta aparte con los resultados de RQ6 |

## 5. Controles: visibilidad (bloqueante) frente a degeneración (se registra)

**Lección de JEV-65/66:** se puede correr una batería entera sin que el modelo vea las
preguntas y sin ningún error visible. Se separan dos cosas:

- **Visibilidad verificable** — **bloqueante**: si falla, no hay batería (o se aborta la
  que esté corriendo).
- **Salida degenerada** (nulos, uniformes, timeouts, `length`, malformados) — **no bloquea**:
  es lo que se quiere medir (puede refutar una predicción). Se registra y tiene reglas de
  parada propias por presupuesto (§5.3).

### 5.1 Puerta G (antes de cada batería, misma sesión de servidor)

Si el servidor se reinicia, la puerta se repite. Casos: uno por familia de esquema —
`adv1/A01_keyword_recipe` (triaje/adv), el primer caso de `papers32`, el primer caso de `ood`
— más un control negativo.

| Variante | Run | Casos | Papel |
|---|---|---|---|
| `inject` (la celda que se va a correr; en A2, nostruct) | `gate67_<host>_<modo>_<celda>` | 3 | debe verse |
| `blind` (struct, sin inject, mismo modo) | `gate67_<host>_<modo>_blind` | 1 (A01) | **control negativo**: debe salir ciego |
| `inject_rot1` (solo antes de A3) | `gate67_81_prob_rot1` | 3 | rotación aplicada y visible |

Total: 4 evaluaciones por host × modo (7 antes de A3) → ~30 en toda la issue.

**Criterios bloqueantes (todos)**, evaluados sobre el **primer intento** de cada caso
(`raw[0]`; en casos con error, `diag.raw[0]`):

1. **Cliente — esquema serializado real.** En `raw[0].request`:
   (a) `sha256[:12]` del mensaje de sistema = valor congelado (§7.3) para fase × celda;
   (b) el mensaje de sistema termina en el apéndice de la librería y el JSON incrustado,
   parseado, es **igual** a `response_format.json_schema.schema` de la misma petición
   (en A2: igual al esquema que la librería construye para ese `questions`);
   (c) para cada pregunta de la fase: su id es propiedad de `answers`, su `instructions`
   aparece en la `description` correspondiente, y en `choice`/`score` cada opción/nivel
   está con su criterio en `description` — comparando **cadenas decodificadas del JSON**, no
   subcadenas del texto bruto;
   (d) en `inject_rot1`, el orden de propiedades de cada `choice` es el de `rotate_choice`
   y coincide con `perm_sha256` congelado.
2. **Servidor — tokens del primer intento** (`raw[0].llm_response.usage.prompt_tokens`):
   `inject` prob y nostruct = `input_tokens` del mismo caso en
   `llm_qwen38_27b_fp8_nostruct_prob` ± 2; `inject_rot1` ± 10 de ese valor; `inject` disc:
   se registra el desplazamiento por familia `offset = tokens − ref` (debe ser negativo y
   estable: el apéndice discrete es más corto) y además `tokens(inject) − tokens(blind) ≥ 200`
   en A01.
3. **Control negativo discrimina:** `tokens(blind, A01) ≤ ref(A01) − 200` (prob; ~806 → ~222).
   Si el ciego no sale ciego, el servidor inyecta por su cuenta → **la puerta falla** y se
   para; el hecho se documenta como hallazgo de RQ6, no como run válido.
4. **`usage` presente** en los 4–7 primeros intentos de la puerta. Sin `usage` el servidor no
   se puede vigilar por tokens: no hay batería en ese servidor (solo la sonda conductual
   de §6).

**No bloqueante (se registra en el manifiesto):** nulos crudos, uniformes, errores,
`finish_reason`, reintentos malformados de la puerta.

`python3 -m jevbench.jev67 gate <host> <modo> <celda>` evalúa 1–4 y **sale con código ≠ 0**
si alguno falla. Su salida se pega en el manifiesto.

### 5.2 Vigilancia de visibilidad durante la batería (supervisor)

`jevbench.run` no pausa por fase, no para por errores y sobrescribe `meta.opts` al
reanudar. Por eso las baterías de esta issue se lanzan con un **supervisor nuevo**,
`python3 -m jevbench.jev67 run <celda>` (§10), que escribe exactamente el formato de
`jevbench.run` (`results/<run>/<fase>.json`, mismo `meta` + `raw`), así que el scorer y
`report` lo leen sin cambios. El supervisor:

- **antes de escribir nada**, si `results/<run>/` existe: compara la configuración efectiva
  guardada (opts redactadas, `meta` del adaptador, `questions_hash`, sha esperado del prompt
  por fase) con la pedida, con la semántica de `diag65._check_resume`; si difiere, **rechaza
  la reanudación** sin tocar el fichero. Los casos con error se conservan salvo
  `--retry-errors` explícito;
- tras **cada caso**, aplica la regla de tokens del primer intento (§8.1). Un caso que la
  incumple **aborta la batería entera** (visibilidad perdida): el run queda marcado
  `invalid` en el manifiesto, no se borra;
- si un caso no trae `usage` en el primer intento: se marca «visibilidad no verificable por
  tokens» y se aplica solo la comprobación de cliente (criterio 1 de §5.1). Si más del 2 %
  de los casos del run (≥ 4/195) acaban así → el run es **no evaluable** para el marcador.

### 5.3 Reglas de parada por degeneración y presupuesto (no son de visibilidad)

- **Por fase:** 3 errores (timeout, `length`, malformado agotado o transporte) en una fase →
  se dejan de ejecutar los casos restantes de **esa fase** (quedan como «no ejecutados por
  regla de parada») y se sigue con la siguiente.
- **Por run:** 10 errores en total, o superar el presupuesto de tiempo del run (§9.2) → se
  detiene el run.
- Los casos no ejecutados **no se rellenan**: cuentan en el denominador de «no evaluable»
  (§8.2). Si los errores ya observados bastan para refutar una predicción (p. ej. 2 fallos
  en papers en B2), esa componente se clasifica **refutada** aunque la fase no termine.

### 5.4 Auditoría posterior (obligatoria, en el informe)

Para cada run: regla de tokens §8.1 en 195/195 (52/52 en A4) primeros intentos; casos sin
`usage`; nulos crudos (de `raw`, antes de normalizar); casi-uniformes; errores por tipo y
fase; reintentos malformados; `meta.opts` constante en las 11 fases; `questions_hash` y sha
del prompt por fase. **Un run que no pase la auditoría de visibilidad no entra en el
marcador** aunque puntúe; la degeneración no impide entrar, se anota.

## 6. Sonda de visibilidad del servidor (RQ6)

### 6.1 Dos pruebas independientes

Script `jevbench/probe_injection.py` (stdlib + el adaptador; cuerpos construidos **por el
adaptador**, nunca reescritos a mano). Salida en `results/probe67_<servidor>/probe.json` con
versión de servidor, modelo, `prompt_tokens` y `cached_tokens` por petición.

**(T) Tokens del primer intento**, `max_tokens=1`, temp 0, thinking off, sobre A01 y el primer
caso de papers32, orden `a b c d c b a d`:

- **a** struct ciego (system + documento + `response_format`);
- **b** el mismo cuerpo **sin** `response_format`;
- **c** struct + inject;
- **d** struct ciego con un esquema **discriminante**: idéntico a *a* salvo que todas las
  `description` (preguntas y criterios) se alargan con un relleno fijo y congelado de
  ~300 tokens; los nombres de propiedades y la estructura no cambian.

| Lectura de (T) | Interpretación |
|---|---|
| `a − b` = 0 ± 2 y `d − a` = 0 ± 2 | El servidor no mete nada del esquema en el prompt |
| `a − b` ≥ 200 y `d − a` ≈ relleno | Inyecta el esquema **con** descripciones |
| `a − b` > 2 y `d − a` = 0 ± 2 | Inyecta algo (estructura/nombres) **sin** descripciones → el modelo no ve las preguntas |
| 1.ª y 2.ª aparición del mismo cuerpo con conteos distintos | Conteo no fiable (caché u otro): (T) no se interpreta; manda (C) |

**(C) Canario conductual** — prueba directa de que el modelo **lee las descripciones**,
independiente del conteo de tokens. Esquema sintético (no es una pregunta de la batería; no
toca `battery.py`) con dos preguntas:

- `noul` `calib_noul`: instrucciones «Calibration item: regardless of the document, answer
  with probability 0.37.»;
- `choice` `calib_choice` con opciones de nombre neutro `opcion_a`, `opcion_b`, `opcion_c`;
  criterios: a y c «Never select this option.», b «Calibration item: always select this
  option.»

Sobre 5 documentos neutros congelados (texto corto inventado, en el manifiesto con su sha),
en tres variantes: **blind** (struct), **inject** (struct + inject), **twin** (nostruct).
15 evaluaciones por servidor.

| Lectura de (C) por variante | Criterio |
|---|---|
| **Ve las descripciones** | `calib_choice` = `opcion_b` en 5/5 **y** `calib_noul` ∈ [0.30, 0.44] en ≥ 4/5 |
| **No las ve** | `calib_choice` = `opcion_b` en ≤ 2/5 **y** `calib_noul` ∈ [0.30, 0.44] en ≤ 1/5 |
| **Parcial / inconcluso** | cualquier otro patrón |

**Controles de (C) en cada servidor:** `twin` (nostruct) debe dar «ve» — si no, el modelo no
sigue el canario y (C) es **no evaluable** en ese servidor. En SGLang y llama.cpp, donde la
respuesta se conoce (JEV-66), `blind` debe dar «no ve» e `inject` «ve»; si no, la sonda está
mal y no se usa en vLLM/Ollama.

### 6.2 Clasificación por servidor

| (T) | (C) blind | Clasificación |
|---|---|---|
| no inyecta | no ve | **Preguntas no visibles en struct** (como SGLang/llama.cpp): usar `inject` |
| inyecta con descripciones | ve | **Visibles**: `inject` duplicaría el esquema; no usarlo allí |
| cualquiera | parcial | **Visibilidad parcial**: tratar como no visible para el benchmark |
| discordante con (C) | — | **Inconcluso**: se documenta; manda (C) para la recomendación práctica |
| — | (C) no evaluable | **No evaluable** en ese servidor/modelo |

**Alcance de la conclusión:** solo la versión exacta del servidor y el modelo probados
(registrados en `probe.json`). No se generaliza a otras versiones.

### 6.3 Dónde y con qué

- **SGLang <host> (FP8, propio)** y **llama.cpp <host> (propio):** calibración, antes que nada.
- **SGLang <host> (servicio del usuario):** (T) y (C) son peticiones normales de inferencia
  (`max_tokens=1` en T): se permite, **sin** parámetros de servidor, cargas de modelo ni
  reinicios.
- **vLLM — solo en <host>, receta fijada.** Con SGLang FP8 ya parado y `free -g` mostrando
  ≥ 60 GiB libres:
  ```bash
  MAX_JOBS=2 PATH="$PWD/.venv-vllm/bin:/usr/local/cuda/bin:$PATH" \
  .venv-vllm/bin/python -m vllm.entrypoints.openai.api_server \
    --model <ruta-local> \
    --served-model-name qwen3.8-27b-vllm --gpu-memory-utilization 0.45 \
    --max-model-len 32768 --host 127.0.0.1 --port 8002
  ```
  Se registra `vllm --version` y el backend de structured outputs que reporte el log.
  Si `vllm==0.29.0` no reconoce la arquitectura o no arranca en la caja de tiempo (§9.2):
  **D-vllm = «no ejecutable»**, y (T)+(C) se corren con el modelo instruct más pequeño
  (≥ 1.5B) que **ya esté en la caché HF de <host>** y cargue con ese venv; la conclusión se
  limita a vLLM 0.29 + ese modelo. Si no hay ninguno: la rama vLLM entera queda «no
  ejecutable» (no se descargan modelos nuevos para esto). No se instala otra versión de
  vLLM.
- **Ollama — solo en contenedor propio en <host>** (`ollama/ollama:0.32.14`, la versión del
  smoke), tras vLLM, con el mismo control de memoria. Modelo: `qwen3.8:27b` (mismo tag que el
  smoke) dentro del presupuesto de descarga (§9.2); si no cabe, se importa el GGUF ya
  presente en la bóveda de <host> (`<ruta-local>`) con un `Modelfile`
  y se anota que **no** es el mismo artefacto que el smoke. En el contenedor propio sí se
  permiten `keep_alive:0` (caché fría para T) y `OLLAMA_DEBUG=1` (se captura el prompt
  renderizado de un caso si el log lo muestra). Hipótesis abiertas sobre 430–1088, sin
  predicción única: H-O1 inyección parcial/variable; H-O2 conteo no fiable con `format`;
  H-O3 otra.
- **D-vllm / D-ollama:** runner `diag66` con `--prefix diag_qwen38_jev67`, 12 casos, celdas
  `typesafe_struct` y `typesafe_struct_schema_in_prompt`, `--reps 1`.

## 7. Configuración congelada

### 7.1 Común a todas las baterías

```
adapter=llm · provider=openai · prompt=typesafe · api_key=none
normalize=true · retries_malformed=2 · capture_raw=true
max_tokens=8192 · timeout=300 · case_timeout=600
extra_body={"chat_template_kwargs":{"enable_thinking":false},"temperature":0,"seed":101}
  (A4: seed 202. Sin top_p/presence_penalty: mismo extra_body que JEV-66)
fases: triage_es, triage_en, papers32, adv1, adv2, ood, triage_ext_es, triage_ext_en, adv3, adv4, adv5
  (A4: papers32, adv3)
```

| Celda | `mode` | `structured` | `inject_schema_in_prompt` | `rotate_choice` |
|---|---|---|---|---|
| A1, A4, B1, C1 | probabilities | true | true | 0 |
| A2 | probabilities | false | false (`true` es inválido con nostruct) | 0 |
| A3 | probabilities | true | true | 1 |
| B2, C2 | discrete | true | true | 0 |

El servidor puede aplicar muestreo por defecto (`--sampling-defaults model` en SGLang;
defaults de llama.cpp): se registran los efectivos (`get_server_info`, `/props`) sin
cambiarlos respecto a JEV-66.

### 7.2 Servidores (identidad congelada de JEV-66; cualquier diferencia → parar)

| Host | Servidor | Pesos | Política |
|---|---|---|---|
| <host> `dgx-spark-a` | contenedor del usuario `qwen3.8-27b-sglang`, imagen `0076dffa60b7` (digest `sha256:febfb971…56b1`), SGLang `0.0.0.dev0+qwen38.27b.g561c8f3`, xgrammar | `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead` @ `009632fe…`, draft `RadixArk/Qwen3.8-27B-DSpark` @ `b9a5dbdf…` | **solo consumir** por túnel 18000→8000 con peticiones de inferencia; no reiniciar, reconfigurar ni cargar nada. Si no está arriba o `get_server_info` difiere → parar y avisar |
| <host> `dgx-spark-b` | contenedor **propio**, misma imagen: `QUANT=fp8 PORT=8000 EXTRA_ARGS="--model-path <ruta-local>" ./start.sh` | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7a…` | `nvidia-smi; docker ps; free -g` antes (GPU libre); túnel 18001→8000; parar y eliminar al terminar. Luego vLLM/Ollama propios (§6.3), uno a la vez |
| <host> `<host>` | `llama-server` build `889edf4` SYCL, `-ngl 99 -c 32768 --jinja --port 8080` (entorno oneAPI) | `<ruta-local>` (**registrar sha256**; JEV-66 no lo guardó) | proceso propio; túnel 18002→8080; parar al terminar |

### 7.3 Hashes congelados (calculados el 4-oct sobre `dba4852` con `.venv-llm`)

`sha256[:12]` del system prompt por fase × celda (`expected_system_prompt_sha256`; el blind es
el prompt base de cada modo, igual en todas las fases):

| Fases | casos | `questions_hash` | prob inject (= nostruct) | disc inject | prob inject rot1 | **blind prob** | **blind disc** |
|---|---|---|---|---|---|---|---|
| triage_es/en, triage_ext_es/en, adv1–adv5 | 14/14/26/26/10/10/20/20/20 | `9a81e9763d94` | `da8dc56b75f7` | `9edd553f6f42` | `64191fd2a4fb` | `388de09c70e7` | `01bc74cc0141` |
| papers32 | 32 | `74026502c3ac` | `2915492ffaee` | `487c9f69683b` | `e8761e9f8246` | `388de09c70e7` | `01bc74cc0141` |
| ood | 3 | `93ea3deb7eab` | `5dbace8178de` | `427ddd505638` | `a9c6380e1962` | `388de09c70e7` | `01bc74cc0141` |

- nostruct: `expected_system_prompt_sha256` devuelve `None` (el apéndice lo construye la
  librería), pero es el de prob inject por construcción (test byte a byte); la puerta lo
  comprueba sobre `raw[0]`.
- rot1: calculados con `diag65.rotate_choice(qs, 1)`; la opción nueva del adaptador **debe
  reproducirlos** (test). Si no, la implementación diverge de JEV-65 y no se corre A3.
- Al cerrar T0 se añaden al manifiesto: commit del harness, `perm_sha256` por fase (como
  `diag65.rotation_manifest`), sha256 del `response_format` por fase × modo × rotación,
  sha256 del relleno de (T)-d y de los 5 documentos del canario.

## 8. Predicciones, clasificación y lecturas

### 8.1 Regla de tokens (visibilidad por caso, primer intento)

`t = raw[0].llm_response.usage.prompt_tokens`; `ref` = `input_tokens` del mismo caso en
`llm_qwen38_27b_fp8_nostruct_prob` (195/195 con un solo intento).

- prob inject y nostruct: `|t − ref| ≤ 2`.
- rot1: `|t − ref| ≤ 10`.
- disc inject: `|(t − ref) − offset_familia| ≤ 2`, con `offset_familia` medido en la puerta.
- Sin `usage` en el primer intento: «no verificable por tokens» (§5.2).

Los reintentos (mensajes de corrección añadidos) **no** se comparan con `ref`: se reportan
aparte (`input_tokens_total`, nº de intentos).

### 8.2 Clasificación de cada componente

Cada predicción se divide en componentes y cada una recibe **una** de cuatro etiquetas:

- **CONFIRMADA** — el valor cae en la zona de confirmación;
- **REFUTADA** — cae en la zona de refutación (o los errores observados ya la refutan, §5.3);
- **INCONCLUSA** — cae entre ambas zonas;
- **NO EVALUABLE** — el run no pasó la auditoría de visibilidad, o el denominador está por
  debajo del mínimo de la componente.

Denominadores: «decisiones» = respuestas del scorer (choice exacta, nivel `score` tras
`round()`, `noul ≥ 0.5`) en los casos respondidos por **los dos** runs comparados; cada caso
de triaje/adv aporta 5, papers 5, ood 3 (969 en total; 259 `choice`). Los acuerdos se dan
con IC de Clopper-Pearson al 95 % (`L`, `U`). Los casos con error no cuentan como fallo en
el marcador (así lo hace el scorer: `n_ok`), pero se reportan siempre junto al ajustado.
El ajustado de un run solo se clasifica con `n_ok ≥ 190/195`; si no, sus componentes de
marcador son **no evaluables**.

| Componente | Confirmada | Inconclusa | Refutada | Mínimo / no evaluable |
|---|---|---|---|---|
| **A1.a** ajustado | [47, 60] | [44, 47) ∪ (60, 63] | < 44 o > 63 | `n_ok ≥ 190` |
| **A1.b** nulos crudos | 0 | — | ≥ 1 (con IDs) | `raw` en ≥ 98 % de casos |
| **A1.c** errores | ≤ 2 | 3–4 | ≥ 5 | — |
| **A2.a** acuerdo A1↔A2 (969 dec.) | `p ≥ 97 %` y `L ≥ 95 %` | resto | `p < 95 %` | ≥ 900 decisiones pareadas |
| **A2.b** Δ ajustado A2−A1 | \|Δ\| ≤ 3 | 3 < \|Δ\| ≤ 6 | \|Δ\| > 6 | ambos `n_ok ≥ 190` |
| **A2.c** reintentos malformados | A2 ≥ A1 | — | A2 < A1 | — |
| **A2.d** vs 49 histórico | **sin clasificación** (descriptivo, RQ3) | | | |
| **A4** acuerdo A1↔A4 (260 dec.) | `p ≥ 98 %` | 95 % ≤ p < 98 % | `p < 95 %` | ≥ 240 decisiones |
| **A3.a** estabilidad: cambios de etiqueta `choice` A1→A3 | `U ≤ 10 %` | resto | `L > 10 %` | ≥ 240 decisiones `choice` pareadas |
| **A3.b** dirección: ¿los cambios siguen a la posición? (abajo) | exceso no significativo (unilateral `p ≥ 0.05`) | — | exceso significativo (`p < 0.05`) | ≥ 10 cambios; si menos → no evaluable (y A3.a manda) |
| **A3.c** acierto `choice` A3−A1 (diferencia pareada, IC Newcombe 95 %) | IC ⊂ [−5, +5] pp | IC cruza ±5 pp sin excluir 0 | IC excluye 0 | ≥ 240 |
| **P+fix** | test en verde | — | test en rojo → **A3 no se corre** | — |
| **P+live** | 100 % de los vectores nulos comunes a rot0/rot1 eligen la primera clave enviada | — | < 100 % → A3 no se interpreta | ≥ 5 vectores nulos comunes; si menos, no evaluable (manda P+fix) |
| **B1.a** ajustado vs A1 | \|Δ\| ≤ 5 | 5 < \|Δ\| ≤ 10 | \|Δ\| > 10 | ambos `n_ok ≥ 190` |
| **B1.b / C1.b** nulos crudos | 0 | — | ≥ 1 | ídem A1.b |
| **C1.a** ajustado vs A1 | \|Δ\| ≤ 6 | 6 < \|Δ\| ≤ 10 | \|Δ\| > 10 | ídem |
| **B2.a / C2.a** fallos en papers32 (timeout/`length`) | 0 | 1 | ≥ 2 | papers32 ejecutado; con parada por regla, los fallos observados cuentan |
| **B2.b / C2.b** ajustado disc vs prob (B1/C1) | \|Δ\| ≤ 4 | 4 < \|Δ\| ≤ 8 | \|Δ\| > 8 | ambos `n_ok ≥ 190` |
| **B2.c / C2.c** errores totales | ≤ 1 | 2–4 | ≥ 5 | — |
| Sondas | §6.1–6.2 | | | |

**A3.b, cómo se calcula.** Para cada decisión `choice` que cambia de etiqueta al rotar, se
mira si la nueva etiqueta ocupa en el orden rotado **el mismo índice** que la antigua en el
orden base («conserva posición»). Bajo la hipótesis nula de que el cambio no sigue a la
posición, la probabilidad de conservarla es `1/(k−1)` (k = nº de opciones: 1/3 con k=4,
1/4 con k=5, 1/2 con k=3). Se compara el nº observado con su esperado mediante una prueba
exacta de suma de Bernoullis heterogéneas (Poisson-binomial), unilateral; se reporta también
por k. Las `choice` binarias (k=2), donde todo cambio conserva posición por construcción, se
**excluyen**; en esta batería no hay ninguna.

**McNemar** (`jevbench.score --vs`) se reporta por pregunta con corrección de Holm, solo
como descripción: un `p ≥ 0.05` **no** se lee como equivalencia; la equivalencia la dan los
márgenes de A2.a/A3.a/A3.c.

**Suelo de ruido.** Si A4 sale inconclusa o refutada, las componentes de acuerdo (A2.a, A3.a)
se reportan además como discrepancia **neta** (discrepancia − discrepancia de A4 en las
mismas fases) y no pueden pasar de «inconclusa».

### 8.3 Lecturas según resultado (y lo que **no** se puede concluir)

| Resultado | Se concluye | No se concluye / queda descartado |
|---|---|---|
| A2.a y A2.b confirmadas | En FP8/SGLang, thinking off, temp 0, la gramática no cambia decisiones **más allá del margen** pre-registrado | Equivalencia exacta; nada sobre NVFP4/GGUF u otros servidores |
| A2.a refutada, A2.b dentro de margen | La gramática cambia decisiones concretas sin mover el agregado | «inject ≡ nostruct» decisión a decisión |
| A2.b refutada (A1 < A2) | En FP8 la gramática cuesta puntos con preguntas visibles; el 56/56 de JEV-66 no generaliza | «La ruta del contrato es la mejor en local» |
| A2.b refutada (A1 > A2) | En FP8 la gramática ayuda; mirar A2.c (formato) antes de atribuirlo al contenido | «nostruct es la referencia superior» |
| A2.d (vs 49) | Solo descriptivo | Cualquier atribución a la temperatura (cambian host, top_p, presence, seed) |
| A1.a confirmada con A1 < 59 | Esta configuración queda por debajo de Cerebras (59–65) | Que la ceguera explique **todo** el hueco; candidatos sin medir: thinking `low` en Cerebras, precisión, servidor |
| A1 ≥ 59 | Esta configuración alcanza a Cerebras | Que precisión/servidor tengan efecto material **en esta configuración** |
| B1/C1 confirmadas, A1 fuera de rango | Las tres precisiones son coherentes entre sí y la predicción de nivel era errónea | Un fallo propio de FP8 |
| A1 en rango, B1 o C1 refutada | Dispersión por precisión/backend mayor de lo esperado (descriptivo, RQ8) | Atribuirlo a la precisión **o** al backend por separado (C1 cambia ambos) |
| A3.a confirmada, P+ ok | El orden de opciones apenas cambia decisiones con preguntas visibles (≤ 10 %, cota superior) | Ausencia total de efecto; nada sobre discrete o niveles `score` |
| A3.a refutada y A3.b refutada | Sesgo de posición con preguntas visibles: el marcador depende del orden de `criteria`; se anota en todas las superficies | «La rotación es inocua» |
| A3.a refutada, A3.b no significativa | Inestabilidad ante el orden **sin** dirección de posición (sensibilidad al contexto, empates) | Sesgo de posición como causa |
| A3.c excluye 0 | El orden afecta al acierto | — |
| P+ falla | La métrica de rotación o el pipeline no son válidos | Cualquier lectura de A3 |
| B2.a y C2.a confirmadas | Los timeouts de discrete en JEV-65 eran compatibles con el modelo a ciegas forzado a emitir literales | Que discrete local sea inviable para papers **en esta configuración** |
| B2.a o C2.a refutadas | Con preguntas visibles persisten fallos en papers en discrete | Que todo el síntoma de JEV-65 fuera ceguera. **No** demuestra un problema «independiente»: puede ser agotamiento de salida, longitud de papers, servidor o interacción; se abre diagnóstico |
| B2.a confirmada, C2.a refutada (o al revés) | El fallo depende del backend/precisión | Una propiedad del modelo o del modo discrete en general |
| Sonda: (T) y (C) concuerdan | Clasificación de §6.2 para esa versión y modelo | Generalizarla a otras versiones |
| Sonda: (T) y (C) discrepan | Inconcluso; la recomendación práctica sigue a (C) | Cualquier afirmación sobre el mecanismo interno |
| D-* contradice la sonda | Se documenta; manda D-* para el modelo del benchmark | — |

### 8.4 Qué abre trabajo nuevo

Subtareas bajo JEV-3 (`depends on` JEV-67) si: A1 < 59 y A1.a confirmada (thinking local);
A3.a/A3.b refutadas (orden de opciones en el contrato); B2.a o C2.a refutadas (diagnóstico
discrete); §8.5 encuentra decisiones que cambian sin normalizar (run `normalize=false`);
vLLM u Ollama no hacen visibles las preguntas (issue upstream).

### 8.5 `normalize` (RQ7) — reproducción offline, sin run nuevo

Sobre el último intento válido de `raw` de A1, A2, A3, B1 y C1 (contenido JSON parseado,
antes de normalizar), por cada pregunta se reproducen las **tres rutas** de la librería con
y sin normalización y se comparan las decisiones del scorer:

- **choice:** `normalize=true` → si `|suma−1| > 1e-6`, `rescale_probabilities` (total 0 →
  uniforme); `normalize=false` → crudo. Decisión = primer máximo en el orden de criterios
  **enviado** (el rotado en A3).
- **score:** valor esperado sobre `rescale_probabilities(probabilidades)` en **ambos** casos
  (la librería reescala siempre); nivel = `metrics.level` (`round()`, redondeo bancario).
  Se comprueba que el `score` recomputado coincide con el guardado (± 1e-9).
- **noul:** sin normalización en ninguna ruta; se comprueba identidad.

Se reporta: (i) nulos crudos; (ii) distribución de `|suma−1|` por tipo (mediana, p95, máx,
nº > 0.05); (iii) **nº de decisiones que cambian sin normalizar** (predicción: 0 por
construcción; si ≠ 0 la premisa es falsa → §8.4); (iv) Brier, NLL y **ECE** (10 bins, como
`metrics.calibration`) con las probabilidades crudas, **descriptivos**, fuera del marcador.
Tratamiento fijado para vectores que no suman 1: Brier sobre los valores crudos sin
renormalizar; NLL con `max(1e-6, p_objetivo)` como `metrics.py`; confianza ECE = máximo
crudo (un vector nulo aporta confianza 0); (v) sensibilidad «nulo = error»: ajustado
recontado contando como fallo cada pregunta cuyo vector crudo es nulo, descriptivo. Si (i)=0,
(v) coincide con el marcador y se dice así.

## 9. Ejecución

### 9.1 Orden

**T0 — sin GPU (portátil):** implementar §10, tests en verde (incluido P+fix), completar §7.3,
commit del pre-registro (manifiesto `docs/infra_runs/qwen38_jev67.md`). **Ninguna inferencia
antes de este commit.** Issue a `In Progress`.

**T1 — los tres hosts en paralelo**, una batería a la vez por servidor (no se lanzan dos
baterías concurrentes contra el mismo servidor, para no mezclar efectos de batching):

| Paso | <host> (FP8 propio → vLLM → Ollama) | <host> (NVFP4 del usuario) | <host> (GGUF Arc propio) |
|---|---|---|---|
| 0 | `nvidia-smi; docker ps; free -g`; arrancar SGLang FP8; túnel; `get_server_info` | `nvidia-smi; docker ps; free -g`; verificar identidad (§7.2) **sin tocar nada**; túnel | arrancar `llama-server`; sha256 del GGUF; túnel |
| 1 | S-sglang (T + C): calibración | S-sglang80 (T + C, peticiones normales) | S-llamacpp (T + C): calibración |
| 2 | G prob A1 → **A1** | G prob B1 → **B1** | G prob C1 → **C1** |
| 3 | G prob A2 → **A2** | G disc B2 → **B2** | G disc C2 → **C2** |
| 4 | **A4** (misma sesión que A1) | — | parar `llama-server` |
| 5 | **P+live** (rot0 y rot1) | — | — |
| 6 | G rot1 → **A3** (solo si P+fix verde y P+live no refutada) | — | — |
| 7 | parar y eliminar SGLang; `free -g` | — | — |
| 8 | vLLM (§6.3): S-vllm (+ D-vllm si sirve 27B); parar | — | — |
| 9 | Ollama propio (§6.3): S-ollama (+ D-ollama); parar y eliminar | — | — |

**T2 — análisis (portátil):** `jev67 report`, scorer con `--vs` (A2 vs A1, A3 vs A1, A4 vs
A1, B1/C1 vs A1, B2 vs B1, C2 vs C1, A1 vs `jev_v3`), auditoría §5.4, §8.5, clasificación
§8.2 componente a componente.

### 9.2 Presupuesto de tiempo

Latencias de referencia (JEV-66, inject, mediana/máx): 5.1/8.9 s (<host>), 6.3/10.8 s (<host>),
7.6/18.3 s (<host>) por caso; papers es lo más largo (hasta 7 219 tokens de entrada). Peor caso
por run con las reglas de §5.3: 10 errores × 600 s = 100 min de más.

| Partida | <host> | <host> | <host> |
|---|---|---|---|
| Montaje (arranque, túneles, verificación) | SGLang 20 min | 10 min | 20 min |
| Sondas S-* | 15 min | 10 min | 15 min |
| Puertas G (4–7 eval. c/u) | 3 × 5 min | 2 × 5 min | 2 × 5 min |
| Baterías (esperado / tope por run) | A1, A2, A3: 25 / 90 min c/u; A4: 8 / 30; P+live: 5 / 20 | B1: 20 / 90; B2: 25 / 120 | C1: 30 / 90; C2: 35 / 120 |
| vLLM: montaje + JIT primer arranque (~25 min) | **caja 45 min** + sonda/D 20 min | — | — |
| Ollama: imagen + modelo (~17 GB) | **caja 45 min** de descarga + sonda/D 20 min | — | — |
| **Límite global del host** | **7 h** | **4 h** | **5 h** |

Al agotar una caja de tiempo, la rama se marca «no ejecutable» en el manifiesto y se sigue.
Al agotar el límite global de un host, lo pendiente en ese host se documenta como no
ejecutado; no se reparte a otro host sin anotarlo como desviación.

## 10. Implementación (mínima, sin API nueva, todo opt-in)

1. **`rotate_choice=<int>` en el adaptador `llm`** (defecto 0). Mover `rotate_choice` y
   `rotation_manifest` a `jevbench/rotation.py` y reexportarlos desde `diag65` sin cambiar su
   comportamiento. El adaptador rota las preguntas antes de construir prompt y esquema y
   registra `rotate_choice` y `perm_sha256` en `meta`. Añadir `rotate_choice` a `CONFIG_KEYS`
   de diag65/diag66. Tests: payload rotado = `diag65.rotate_choice`; `questions_hash`
   invariante; los sha rot1 de §7.3 se reproducen; etiquetas/GT intactos; **P+fix** (servidor
   falso que devuelve un vector nulo: la decisión es la primera clave enviada, base y rotada,
   leída por el scorer).
2. **`--prefix` en `jevbench.diag66`** (defecto `diag_qwen38_jev66`) para P+live y D-* sin
   chocar con los runs JEV-66. P+live: `python3 -m jevbench.diag66 fp8_rot0 --prefix
   diag_qwen38_jev67 --reps 1 --cells typesafe_struct …` y lo mismo con `fp8_rot1 --opt
   rotate_choice=1`, consecutivos en la misma sesión. Test de nombres y de rechazo de
   reanudación con opciones distintas.
3. **`jevbench/jev67.py`** con subcomandos:
   - `gate` (§5.1; código de salida ≠ 0 si falla);
   - `run <celda>` — supervisor de batería (§5.2–5.3): comprobación de configuración antes
     de reutilizar un directorio, regla de tokens por caso sobre el primer intento, reglas
     de parada por fase/run/tiempo, mismo formato de fichero que `jevbench.run`;
   - `report` — auditoría §5.4, acuerdos con IC, métricas A3 (cambios, «conserva posición»
     con prueba Poisson-binomial por k, Newcombe), errores discrete por fase y tipo, §8.5, y
     tabla de clasificación §8.2.
   Tests con fixtures mínimos (incluidos: reanudación rechazada sin escribir, aborto por
   caso ciego, parada tras 3 errores en una fase, caso sin `usage`).
4. **`jevbench/probe_injection.py`** (§6): (T) con el esquema discriminante y (C) con el
   canario sintético, cuerpos generados por el adaptador. Test con servidor falso.
5. **Sin tocar** `battery.py`, GT, `metrics.py`/`score.py`, `jevbench.run`, runs históricos ni
   la ruta por defecto del adaptador. `python3 -m unittest discover tests` en verde antes del
   commit de pre-registro.

## 11. Entregables

- Código de §10 + tests.
- Manifiesto `docs/infra_runs/qwen38_jev67.md`: pre-registro congelado (commit **antes** de
  ejecutar) + resultados: salidas de puertas y sondas, tablas por celda, auditoría, tabla de
  clasificación §8.2 (CONFIRMADA / REFUTADA / INCONCLUSA / NO EVALUABLE por componente, con
  denominadores) y la fila de §8.3 que aplica, desviaciones y ramas no ejecutables.
- Runs en `results/` con los nombres de §4 (`raw` incluido; `publish.py` lo elimina del
  espejo).
- Marcador: **A1, A2, B1, B2, C1, C2** entran en `docs/resultados_runs.txt` como filas
  «preguntas visibles, thinking off, temp 0» si pasan la auditoría de visibilidad; A3, A4,
  P+live, puertas, sondas y D-* no (diagnóstico). `llm_qwen38_27b_prob` (−16) y
  `llm_qwen38flash_prob` mantienen su asterisco de medición a ciegas.
  `python3 -m jevbench.report` y `--check`.
- `docs/resultados.md`, `docs/modelos.md` (LLM generalista: resultado de esta configuración,
  ruta recomendada, estado vLLM/Ollama con su versión), `CHANGELOG.md` + versión **minor**
  (0.32.0).
- Web/sitio: solo tras la revisión externa, con `docs/procedimientos/actualizar-web.md`.
- YouTrack: `In Progress` al empezar T0; `Done` con las cifras clave (ajustados A1/A2/B1/C1/
  B2/C2 con `n_ok`, acuerdo A1↔A2 con IC, cambios de rotación, clasificación de cada
  servidor en la sonda) y la ruta del manifiesto. Subtareas de §8.4 si procede.

## 12. Encargo al ejecutor

1. Lee este pre-registro entero, `docs/infra_runs/diag_qwen38_jev66.md`,
   `docs/dgx-spark.md` y `docs/procedimientos/evaluar-modelo-nuevo.md`. Respeta AGENTS.md:
   `git add <ruta>` concretas (nunca `-A`), sin push salvo que se pida, claves solo por
   variable de entorno, nada de servicios ajenos.
2. T0: implementa §10 con tests; completa §7.3; commitea el pre-registro. **Ninguna
   inferencia antes de ese commit.**
3. T1: sigue §9.1 por host. **Ninguna batería sin su puerta aprobada en la misma sesión de
   servidor**, y todas lanzadas con `jevbench.jev67 run`, no con `jevbench.run`. En <host> solo
   peticiones de inferencia al servicio del usuario; si algo no cuadra con §7.2, para y
   avisa. En <host>/<host> comprueba `nvidia-smi; docker ps; free -g` antes de arrancar y para/
   elimina lo tuyo al terminar. vLLM con `gpu_memory_utilization ≤ 0.45` y `MAX_JOBS=2`.
4. No ajustes umbrales, márgenes, rangos ni celdas tras ver resultados. Si algo obliga a
   desviarse (servidor caído, rama no ejecutable, caja de tiempo agotada), documenta la
   desviación en el manifiesto **antes** de mirar los resultados afectados.
5. Resultados negativos, refutaciones, inconclusos y no evaluables se documentan igual que
   los positivos.
6. T2: informe completo, marcador, CHANGELOG/versión, YouTrack. Entrega para revisión
   externa antes de tocar la web o el sitio público.


---

# RESULTADOS (post-ejecución, 4-oct-2026)

## T1 — Verificación de entorno y sondas

- **<host>** (servicio del usuario, solo consumo): identidad §7.2 verificada —
  SGLang `0.0.0.dev0+qwen38.27b.g561c8f3`, `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`,
  xgrammar, contenedor `qwen3.8-27b-sglang` (no se tocó).
- **<host>** (propio): SGLang FP8 del pre-registro (`Qwen/Qwen3.8-27B-FP8` local),
  parado y eliminado al terminar las baterías. vLLM 0.29.0 y Ollama 0.32.14 en
  servicios propios, también eliminados.
- **<host>** (propio): `llama-server` build `889edf4` SYCL (`-ngl 99 -c 32768
  --jinja`); GGUF sha256 = `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`
  (registrado; JEV-66 no lo guardó). Parado al terminar.
- **Desviación documentada**: el venv de vLLM está en `<ruta-local>`
  (no dentro del directorio del modelo); la receta §6.3 se ejecutó con esa ruta,
  mismo `--model`, `gpu_memory_utilization 0.45` y `MAX_JOBS=2`. El `docker pull`
  de `ollama/ollama:0.32.14` se lanzó mientras vLLM capturaba CUDA graphs
  (solo disco/red, sin GPU); la descarga del modelo empezó tras parar vLLM.

### Sondas S-* (§6): todas las pruebas concuerdan

| Servidor | (T) tokens a/b/c/d (A01) | (C) blind | (C) inject | (C) twin | Clase §6.2 |
|---|---|---|---|---|---|
| SGLang <host> NVFP4 | 222/222/806/222 | no ve | ve | ve | **no_visibles** |
| SGLang <host> FP8 | 222/222/806/222 | no ve | ve | ve | **no_visibles** |
| llama.cpp <host> GGUF | 222/222/806/222 | no ve | ve | ve | **no_visibles** |
| vLLM 0.29.0 <host> FP8 | 222/222/806/222 | no ve | ve | ve | **no_visibles** |
| Ollama 0.32.14 <host> (`qwen3.8:27b`, contenedor propio) | 220/220/804/220 | no ve | ve | ve | **no_visibles** |

- En (C), el canario discrimina en los cinco servidores conocidos: blind →
  `opcion_a` + noul 0.0 en todas las repeticiones salvo una de Ollama blind
  (`opcion_c` + 0.5 — igualmente «no ve», que es lo que manda); inject/twin
  → `opcion_b` + noul **0.37 exacto** (5/5). (T): `a=b=d` y `d−a=0` →
  ningún servidor inyecta nada del esquema en el prompt (solo la gramática);
  `c−a` = +584 en A01 (+815 en P01).
- **D-vllm** (12 casos × 2 celdas × 1 rep): ciego 16 nulos (tok-in med 206),
  inyectado 0 nulos (790; acierto 50/56 vs 34/56) — confirma la sonda.

## T1 — Puertas G (§5.1): todas PASS en primera ejecución

| Puerta | Salida |
|---|---|
| `gate 81 prob inject` | PASS — inject 806/1946/669 (= ref), blind A01 222 ≤ 606 |
| `gate 81 prob nostruct` | PASS — nostruct 806/1946/669, blind 222 |
| `gate 81 prob rot1` | PASS — rot1 806/1946/669 (±10), perm_sha256 = congelados (`15f6174736a0`, `030bd9f1149c`, `15a3e725392c`) |
| `gate 80 prob inject` | PASS — inject 806/1946/669, blind 222 |
| `gate 80 disc inject` | PASS — offsets triageadv −291 / papers −340 / ood −216; inject−blind A01 = 356 ≥ 200 |
| `gate 70 prob inject` | PASS — inject 806/1946/669, blind 222 |
| `gate 70 disc inject` | PASS — mismos offsets que <host>; inject−blind 356 ≥ 200 |

## T1 — Baterías: las 8 celdas, 195/195 (52/52 A4), 0 errores totales

| Celda | Run | ajustado | n_ok | errores | nulos crudos | sin usage | violación token |
|---|---|---|---|---|---|---|---|
| A1 | `llm_qwen38_27b_fp8_inject_prob` | **51.4** | 195/195 | 0 | 2 (B07 dept+urgency) | 0 | 0 |
| A2 | `llm_qwen38_27b_fp8_nostruct_t0_prob` | **51.2** | 195/195 | 0 | 2 (mismo B07) | 0 | 0 |
| A3 | `llm_qwen38_27b_fp8_inject_rot1_prob` | **58.6** | 195/195 | 0 | 2 (mismo B07) | 0 | 0 |
| A4 | `llm_qwen38_27b_fp8_inject_prob_s202` | — | 52/52 | 0 | 0 | 0 | 0 |
| B1 | `llm_qwen38_27b_nvfp4_inject_prob` | **50.1** | 195/195 | 0 | 0 | 0 | 0 |
| B2 | `llm_qwen38_27b_nvfp4_inject_disc` | **62.6** | 195/195 | 0 | 0 | 0 | 0 |
| C1 | `llm_qwen38_27b_arcgguf_inject_prob` | **48.1** | 195/195 | 0 | 2 (mismo B07) | 0 | 0 |
| C2 | `llm_qwen38_27b_arcgguf_inject_disc` | **62.6** | 195/195 | 0 | 0 | 0 | 0 |

Auditoría §5.4: regla de tokens §8.1 cumplida en 195/195 (52/52) primeros
intentos de cada run (diff máx 0); `meta.opts` constante en las 11 fases;
`questions_hash` y sha del system prompt por fase = congelados §7.3; reintentos
malformados 0 en todos los runs.

### Acuerdos y rotación

- **A1↔A2 (gramática):** 967/969 decisiones iguales (99.79 %, IC95
  [0.9926, 0.9997]). Únicas discordantes: `papers32/P04/depth`
  (abstract/full) y `papers32/P12/depth` (abstract/skip).
- **A1↔A4 (suelo de ruido, seed 202, papers32+adv3):** 258/260 (99.23 %,
  [0.9725, 0.9991]).
- **A1↔A3 (rotación):** 24/259 etiquetas `choice` cambiadas (9.3 %;
  por k: 15 de k=4, 8 de k=3, 1 de k=5). **3/24 «conservan
  posición»** (B07/department —el del nulo→uniforme→primera clave—,
  P12/depth y P27/depth; esperados ~9.25 bajo H0; p Poisson-binomial
  unilateral = 0.9991).
  Acierto choice pareado: A3−A1 = **+6.2 pp** (IC95 Newcombe
  [+2.6, +9.9]; 19 aciertos solo-A3 vs 3 solo-A1) — el orden afecta al acierto y
  rotar lo **mejora** aquí.
- **McNemar por pregunta con Holm (descriptivo):** la familia aquí es la
  de las **10 preguntas agregadas entre fases** — conteos b/c apilados por
  pregunta sobre las 11 fases, Holm sobre 10 contrastes; **no** son las 53
  celdas fase×pregunta del banco (en esa familia ninguna celda de estos
  contrastes es significativa). Incluyen adv1/adv2 y las traducciones ES/EN
  relacionadas: alcance diagnóstico adicional, no una victoria por fase.
  A2↔A1, B1↔A1 y C1↔A1:
  ninguna significativa. A3↔A1: `department` p_Holm=0.001 (14–0 a favor
  de A3). B2↔B1 y C2↔C1: `same_day` p=0.010/0.007 a favor de discrete.
  A1↔`jev_v3`: `urgency` p=0.005 a favor de Jev.

### P+live (a ciegas, 12 casos, rot0+rot1 en la misma sesión)

13 vectores nulos comunes: **7/7 decisiones `choice` eligen la primera clave
enviada** (rot0→`bronchoscopia`/`full`/`rct`/`ip`, rot1→`consulta_externa`/
`abstract`/`meta`/`oncology`). Los nulos `score` (no rotan) dan el nivel
medio por construcción. Pipeline de rotación válido sobre datos reales.

## T2 — Clasificación §8.2 (verbatim de `jev67 report`)

```
- A1.a ajustado: CONFIRMADA (51, n_ok=195)
- A1.b nulos crudos: REFUTADA (2: adv2/B07_maintenance_spoof department+urgency)
- A1.c errores: CONFIRMADA (0)
- A2.a acuerdo A1↔A2: CONFIRMADA (967/969 p=0.998 L=0.993)
- A2.b Δ ajustado A2−A1: CONFIRMADA (-0)
- A2.c reintentos malformados: CONFIRMADA (A2=0, A1=0)
- A2.d vs 49 histórico: descriptivo (A2=51)
- A4 acuerdo A1↔A4 (ruido): CONFIRMADA (258/260 p=0.992)
- A3.a cambios de etiqueta: INCONCLUSA (24/259 U=0.135)
- A3.b dirección posición: CONFIRMADA (exceso no significativo; 3/24 conservan, p=0.9991)
- A3.c Δ acierto choice A3−A1: REFUTADA (IC excluye 0; +6.2 pp [+2.6, +9.9] a favor de rot1)
- P+fix: CONFIRMADA (test en verde)
- P+live: CONFIRMADA (7 nulos comunes × 2 records: 14/14 eligen 1ª clave enviada — rot0 la base, rot1 la rotada)
- B1.a ajustado vs A1: CONFIRMADA (-1)
- B1.b nulos crudos: CONFIRMADA (0)
- C1.a ajustado vs A1: CONFIRMADA (-3)
- C1.b nulos crudos: REFUTADA (2, mismo B07)
- B2.a fallos papers32: CONFIRMADA (0)
- B2.b ajustado disc vs prob: REFUTADA (+13)
- B2.c errores totales: CONFIRMADA (0)
- C2.a fallos papers32: CONFIRMADA (0)
- C2.b ajustado disc vs prob: REFUTADA (+15)
- C2.c errores totales: CONFIRMADA (0)
```

## §8.3 — Lecturas que aplican

- **A2.a y A2.b confirmadas:** en FP8/SGLang, thinking off, temp 0, la
  gramática forzada no cambia decisiones más allá del margen pre-registrado
  — 967/969 etiquetas idénticas. Pero **no es neutra en los valores**: en
  papers, skip LOO (métrica sobre probabilidades) da 9/10 con gramática
  frente a 4/10 sin ella, y papers 77.2 vs 75.9 — no cambia las etiquetas
  pero sí mueve las probabilidades. (No es equivalencia exacta; no dice
  nada de NVFP4/GGUF.)
- **A1.a confirmada con A1=51 < 59:** esta configuración queda **por debajo
  de Cerebras**. Lectura defendible del hueco: la comparación más limpia
  es A2 (51) vs Cerebras nostruct (65) — mismo prompt, temp 0; lo que
  cambia es `reasoning_effort=low`, precisión y servidor. La ceguera no
  explica el hueco; el candidato principal sin medir es thinking (coherente
  con la inversión discrete/prob entre local y Cerebras); la dispersión entre
  precisiones es de 3.3 puntos de ajustado (51.4/50.1/48.1) — descriptiva,
  no excluye la precisión como causa. Además el
  orden de opciones mueve ~7 puntos por sí solo — rot1 (59) empata con
  Cerebras struct—, así que un hueco de 8–14 no se puede atribuir con
  seguridad a una sola causa con un único orden.
- **B1.a/C1.a confirmadas con A1 en rango:** las tres precisiones son
  coherentes (51/50/48), dispersión pequeña (RQ8 descriptivo). C1.b, en
  cambio, refutada por el mismo vector nulo de B07.
- **A3.a inconclusa, A3.b confirmada, A3.c refutada:** la estabilidad ante
  el orden queda sin cota suficiente (U=13.5 %); 3/24 conservan posición —
  **sin exceso significativo** de conservación, que es lo que acredita el
  criterio— y con un efecto neto en acierto choice (+6.2 pp a favor de
  rot1 — el orden sí afecta al acierto; firma coherente con sensibilidad al
  contexto — A3.b descarta conservar el mismo índice, no una ventaja de
  primacía; de hecho 14 de los 15 cambios en `department` parten de `bronchoscopia`
  en A1 (primera opción en base, última en rot1): 13 correcciones desde
  `bronchoscopia` y B07 va a `consulta_externa`, que sigue fallando — el
  15.º cambio es `consulta_externa`→la correcta; el 14–0 de aciertos
  pareados se mantiene:
  compatible con ventaja para la etiqueta que encaja con la palabra clave
  cuando va primera. A acotar con más rotaciones (JEV-72).
- **B2.a/C2.a confirmadas:** los timeouts/`length` de papers en JEV-65 eran
  compatibles con el modelo a ciegas forzado a emitir literales — con
  preguntas visibles desaparecen en ambos backends.
- **B2.b/C2.b refutadas (+13/+15):** con preguntas visibles, `discrete`
  supera a `probabilities` muy por encima del margen pre-registrado. La
  ganancia se concentra en `same_day`/`urgency`/`department` y el modo
  cambia prompt (`388de09…` vs `01bc74…`) y formato a la vez — no se puede
  atribuir al literal; además el signo se invierte en Cerebras con
  thinking low (58 vs 59/65). Es la mejor ruta local medida (63, a la par
  de Cerebras nostruct 65 y la cascada Jev 64–65 — Jev de una pasada es
  45). No demuestra que discrete sea siempre superior: abre una línea (§8.4).
- **Sonda:** (T) y (C) concuerdan en los 4 servidores probados — «preguntas
  no visibles en struct» para esas versiones exactas; usar `inject`.
- **§8.5 (RQ7):** premisa verificada — 0 decisiones cambian sin normalizar
  en A1/A2/A3/B1/C1; |suma−1| > 0.05 solo en el vector nulo de B07 (suma
  0.0 → uniforme). Brier/NLL/ECE crudos en el informe JSON. Sensibilidad
  «nulo=error»: solo afecta a B07 (−2 decisiones); el ajustado no cambia.

## Desviaciones y no ejecutado

- Commit del pre-registro pospuesto por instrucción del usuario (él lo hará
  tras la revisión de codex); el texto quedó congelado en este fichero antes
  de inferir.
- Ruta venv de vLLM distinta de la citada (ver T1). `docker pull` de Ollama
  durante la captura de CUDA graphs de vLLM (sin impacto GPU).
- Ollama 0.32.14 (`qwen3.8:27b`, mismo tag que el smoke): sonda y D-ollama
  ejecutados — `results/probe67_ollama81/` y `results/diag_qwen38_jev67_ollama_*`.
  Ciego 10 nulos / inyectado 0 (49/56 vs 37/56). Ollama tampoco inyecta el
  esquema. La explicación de los ~430–1088 tokens intermedios del smoke
  histórico queda como **hipótesis** (conteo de plantilla propio): estas
  sondas no la demuestran.
- **Limitación de evidencia de puertas:** las ejecuciones posteriores
  sobrescribieron parte de las puertas guardadas (`gate67_81_prob_inject`
  contiene casos posteriores a A1/A4). No prueba que faltara ninguna puerta
  —la auditoría posterior reconstruye los 4 criterios sobre lo guardado y la
  regla de tokens pasa en los 195 primeros intentos de cada batería—, pero
  ya no se puede acreditar cada puerta previa. Corregido: las puertas llevan
  `gate_id` + historial y `run_cell` exige puerta aprobada y la referencia.
- **Vigilancia discrete:** el supervisor cargaba mal los offsets de la
  puerta (precedencia de `or`) y regresaba `ok` sin referencia — B2/C2
  corrieron sin la regla de tokens activa. La comprobación **posterior** con
  los offsets correctos pasa 195/195 en ambos; los datos se conservan con
  esta salvedad. Corregido: los offsets van en el diag de la batería y la
  referencia ausente es violación.
- `meta.git` de estos runs es el commit base (`dba4852`), no el código
  ejecutado (sin commitear aún); `meta.git_dirty` lo señala desde ahora.
- Trabajo que abre (§8.4): discrete vs probabilities como línea nueva;
  thinking local (A1 < 59); `normalize=false` innecesario (premisa OK);
  issue upstream `system-one-adapter` con los resultados de RQ6 (4 motores
  no inyectan).
