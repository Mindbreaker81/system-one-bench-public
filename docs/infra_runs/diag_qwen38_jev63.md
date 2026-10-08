# Manifiesto: matriz `diag_qwen38_*` (JEV-63) — prompt × esquema en 4 configuraciones

**Qué es:** el diagnóstico reducido pre-registrado en JEV-63 /
`docs/plan_diagnostico_estabilidad_llm.md` (continuación de JEV-58/61): separar el
efecto del **prompt** y del **esquema** en la emisión de vectores degenerados por
Qwen3.8-27B servido en local, y comprobar si se repite en NVFP4, FP8, Cerebras y
(extensión opcional) GGUF en Intel Arc.

**Resultado, en una línea:** los vectores nulos (`0.0` en todas las opciones) solo
aparecen en la celda **prompt TypeSafe + esquema forzado** de los backends locales
— no con el mismo esquema y un prompt simple, no con el mismo prompt sin esquema —
mientras Cerebras no lo reproduce en ninguna celda. **Mecanismo identificado
(4-oct, revisión externa):** con `structured=true` la librería
`system-one-adapter` envía solo el system prompt fijo y el documento; las
preguntas y criterios van únicamente en las `description` del JSON Schema
(`_client.py`, `_prepare_evaluation`). SGLang y llama.cpp usan
`response_format` solo para construir la gramática y **no inyectan el esquema
en el prompt**: en esa celda el modelo nunca ve las preguntas y responde a
ciegas. Cerebras y OpenAI sí lo inyectan — tokens de entrada del mismo caso:
222 en local struct frente a 958 en Cerebras (806 en nostruct, donde la
librería añade el esquema como texto). La «interacción prompt×esquema» es por
tanto «structured=true en un servidor que no inyecta el esquema», no una
propiedad del prompt TypeSafe ni de la precisión: los runs struct locales
quedan medidos **sin preguntas visibles** y no valen para valorar el modelo.
Alcance: la no-inyección está verificada en las builds de SGLang y
llama.cpp usadas; OpenAI/Cerebras inyectan según los tokens de entrada
(riesgo bajo para gpt-6-luna, sin `usage` guardado); vLLM y Ollama no están
verificados — el smoke de Ollama dio 8/10 uniformes con tokens intermedios
(430–1088), pendiente de `capture_raw`. Lo que hizo el **cliente** está
verificado siempre por la ruta de la librería 0.2.1.

**Addendum (cerrado por JEV-67, 6-oct):** vLLM 0.29.0 y Ollama
0.32.14 quedaron verificados con sonda T+C y rutas D: tampoco inyectan
el esquema (16 nulos a ciegas / 0 inyectado en vLLM; 10/0 en Ollama).

## Matriz ejecutada

12 casos fijados × 4 celdas × 3 repeticiones = **144 evaluaciones por bloque**,
576 en total con la extensión Intel. Celdas: `typesafe_struct`,
`simple_struct`, `typesafe_nostruct`, `simple_nostruct` (orden alternado por rep:
`CELL_ORDER` en `jevbench/diag63.py`; seeds 101/202/303 vía `extra_body`).

| Bloque | Pesos / serving | typesafe_struct | simple_struct | typesafe_nostruct | simple_nostruct |
|---|---|---|---|---|---|
| `nvfp4` (<host>) | RadixArk NVFP4, SGLang | **9 nulos/rep + 1 error** | 0 | 0 | 0 |
| `fp8` (<host>) | `Qwen/Qwen3.8-27B-FP8`, SGLang | **14 nulos/rep** | 0 | 0 | 0 |
| `arcgguf` (<host>) | Q4_K_M GGUF, llama.cpp SYCL | **9 nulos/rep** | 0 | 0 | 0 |
| `cerebras` | API Cerebras | 0 | 0 | 0 | 0 |

(nulos = vectores `choice`/`score` con `0.0` literal en todas las opciones, leídos
del raw antes de normalizar; "0" = ninguno en las 3 reps. Casos: 12/rep.)

Misma firma en los tres backends locales (dos motores de gramática distintos:
xgrammar en SGLang y la gramática propia de llama.cpp; tres precisiones), y nula
en la ruta de salida de Cerebras. El acuerdo de decisiones entre repeticiones es
102–112/112 según celda según el informe existente (incluye valores score/noul
redondeados, no solo decisiones de clase). Los IDs de vectores nulos coinciden
en las tres reps de cada bloque; no demuestra determinismo general.

## Configuración congelada dentro de cada bloque (diferencias entre proveedores)

```
adapter=llm · provider=openai · mode=probabilities
normalize=true · retries_malformed=2 · temperature=0 (extra_body)
max_tokens=8192 · timeout=300 · case_timeout=600 · capture_raw=true
prompt=typesafe|simple · structured=true|false (según celda) · seed=101/202/303
thinking off: extra_body chat_template_kwargs.enable_thinking=false (SGLang/llama.cpp)
              reasoning_effort=none (Cerebras; verificado reasoning_tokens=0)
```

Casos (manifiesto `cases_sha256` en cada meta): `T01_ebus_alergia`,
`T02_factura_duplicada` (triage_es); `T15_neumotorax_espontaneo`,
`T16_epoc_saturacion` (triage_ext_en); `P01`, `P02` (papers32);
`A01_keyword_recipe`, `A02_vet_dog` (adv1); `C01_downplay_hemoptysis`,
`C02_injected_billing_label` (adv3); `receta`, `contrato` (ood). `questions_hash`:
9a81e9763d94 (triaje/adv), 74026502c3ac (papers), 93ea3deb7eab (ood).

## Bloques

### nvfp4 — <host> (`dgx-spark-a`, GB10)

- Contenedor `qwen3.8-27b-sglang` del usuario (`lmsysorg/sglang:qwen38-27b`,
  digest `sha256:febfb971c7352570fc445c466ebd6ffc9d896024958e544a60f2137fd85856b1`,
  image ID `0076dffa60b7`), sin tocar su servicio; consumido por túnel SSH 18000→8000.
- `get_server_info`: SGLang `0.0.0.dev0+qwen38.27b.g561c8f3`,
  `grammar_backend=xgrammar`, `model_path=RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`,
  flashinfer, KV fp8_e4m3, spec EAGLE.
- Revisiones (snapshot HF del caché del servicio, = main de HF en 4-oct):
  pesos `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`
  `009632fef96dd349150baa780c984e62e70e91fe`; draft EAGLE
  `RadixArk/Qwen3.8-27B-DSpark` `b9a5dbdf03bc999c6c73c426b19c2d9041cea393`.
- `typesafe_struct`: 9 vectores nulos por rep (T15/urgency, P01×4 preguntas,
  A01/dept+urgency, receta/relevance, contrato/relevance) **más** un error
  `finish_reason=length` en `T16_epoc_saturacion` las 3 reps: el raw capturado
  termina en un bucle de repetición (`"55555…"`) hasta `max_tokens` — la misma
  familia degenerada, otra forma.
- Resto de celdas: 0 nulos, 0 errores; decisiones coherentes con Cerebras.

### fp8 — <host> (`dgx-spark-b`, GB10)

- Montaje nuevo para este experimento: pesos `Qwen/Qwen3.8-27B-FP8` (29 GB)
  copiados desde el caché del proyecto en <host> a
  `<ruta-local>` (tar por
  SSH, misma revisión), repo SGLang rsync (sin `.cache` ni `.env`), imagen
  `lmsysorg/sglang:qwen38-27b` transferida por `docker save|load` (mismo digest).
- Arranque: `QUANT=fp8 PORT=8000 EXTRA_ARGS="--model-path
  <ruta-local>" ./start.sh`; túnel 18001→8000.
- `get_server_info`: misma build SGLang y `xgrammar` que <host>.
- Revisión de pesos verificada por contenido: `Qwen/Qwen3.8-27B-FP8`
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` — sha256 de
  `layers-0.safetensors` (`07f700e2…`) y `tokenizer.json` (`0997f410…`) en
  la copia de <host> iguales a los OID LFS del repo en esa revisión, y los 75
  ficheros coinciden en tamaño con la copia local de <host> de la que salieron.
  La sesión tmux del servicio ya no existe: la línea de arranque efectiva es
  la reconstruida del script, no una captura.
- `typesafe_struct`: 14 vectores nulos por rep (P01×4, P02×4, A01×2, A02×2,
  receta, contrato). No es superconjunto de NVFP4: T15/urgency aparece
  en NVFP4 y no en FP8. Firma repetida en las tres reps de este bloque.
- Resto: 0 nulos.

### cerebras — API

- `qwen-3.8-27b` en `https://api.cerebras.ai/v1`; `reasoning_effort=none`
  (thinking off verificado: `reasoning_tokens=0` en usage), `seed` aceptada por la
  API, `reasoning_format=parsed`, temp 0. `system_fingerprint` registrado en raw.
- 144 evals, 0 errores, 0 reintentos, 0 nulos, acuerdo 112/112 entre reps.
- Coste registrado por tokens y tarifas **$0.17217723** (presupuesto $1); mediana
  ~0.3 s/eval. `chat_template_kwargs` no existe en esta API (diferencia
  inevitable registrada: thinking se apagó con `reasoning_effort=none`).

### arcgguf — <host> (`<host>`, Intel Arc Pro B70 32 GB) — extensión opcional

- `llama-server` 0.5.0-dev build `889edf4`, build SYCL (IntelLLVM 2026.1.1),
  `-ngl 99 -c 32768 --jinja` sobre `<ruta-local>`
  (la GPU Intel quedó confirmada por el smoke: offload completo, ~7–15 s/eval).
- Acepta `response_format` json_schema (gramática propia de llama.cpp),
  `chat_template_kwargs` y `seed` — mismas opciones que SGLang.
- `typesafe_struct`: 9 vectores nulos por rep, misma firma que NVFP4 (T15,
  P01×4, A01×2, receta, contrato). Resto: 0 nulos.
- El servidor se paró al terminar la matriz.

## Conclusión por bloque (pregunta del pre-registro)

**¿El problema aparece con el esquema, con el prompt o con su interacción?**

La **interacción**, ya con mecanismo. En los tres bloques locales el síntoma
exige a la vez el prompt completo TypeSafe **y** la ruta estructurada porque,
como muestran los tokens de entrada (222 vs 806/958/1158), `typesafe_struct` es
la única celda en la que el modelo no ve las preguntas: la librería solo envía
el system prompt y el documento, y los servidores locales no inyectan el
esquema. En Cerebras no aparece en ninguna celda porque sí lo inyecta — no
hace falta suponer una «ruta de salida» oculta. No atribuir el síntoma al
aviso anti-inyección (verificado por ablación en JEV-65) ni afirmar que
precisión/gramática no influyen en otros aspectos.

Lo que sigue abierto: ~~confirmación experimental~~ **confirmada en JEV-66**
(`docs/infra_runs/diag_qwen38_jev66.md`: `typesafe_struct` con el esquema
además inyectado en el system prompt → 0 nulos en los tres backends; el
control sin inyección reproduce la firma), el techo local real de Qwen3.8-27B
con preguntas
visibles a temperatura 0, y la rotación de opciones en `probabilities`
(el control se hizo en `discrete`, donde no hay nulos; con normalización un
nulo se normaliza a uniforme y el argmax del scorer resuelve el empate con la
primera clave, luego el orden sí puede actuar ahí). Muestra de 12 casos
fijados, determinista por temperatura 0: las 3 reps son una observación
repetida, no evidencia acumulada de tamaño 36.

**Addendum (cerrado por JEV-67, 6-oct):** el techo local con
preguntas visibles a temp 0 se midió (struct+inject: FP8 51 / NVFP4 50
/ GGUF 48; discrete+inject: 63 en NVFP4 y GGUF) y la rotación en
`probabilities` también (celda A3: 24/259 cambios, +6.2 pp de acierto
a favor de rot1). Manifiesto `docs/infra_runs/qwen38_jev67.md`.

## Reproducir

```bash
# prompt simple pre-registrado: docs/experimentos/diag_qwen38_prompt_simple.txt
.venv-llm/bin/python -m jevbench.diag63 <bloque> \
  --opt model=<id> --opt base_url=<endpoint>/v1 \
  --opt mode=probabilities --opt normalize=true --opt retries_malformed=2 \
  --opt 'extra_body={"chat_template_kwargs":{"enable_thinking":false},"temperature":0}' \
  --opt max_tokens=8192 --opt timeout=300 --opt case_timeout=600 --opt api_key=none
.venv-llm/bin/python -m jevbench.diag63_report <bloque>
```

Runs: `results/diag_qwen38_{nvfp4,fp8,cerebras,arcgguf}_{typesafe,simple}_{struct,nostruct}_r{1,2,3}/`
(48 runs × 6 fases × 2 casos; `raw` por caso = petición real + respuesta sin
normalizar; en errores, `raw` dentro de `diag`).
