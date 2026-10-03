# Changelog

Historial de lo realizado en el banco de pruebas, de lo más reciente a lo más antiguo.
Entre paréntesis, los commits de referencia (`git show <hash>`); el detalle numérico está en
`docs/resultados.md` y `docs/experimentos/`. Seguimiento de tareas: YouTrack, proyecto JEV.

El repo tiene **una única versión semántica** (`jevbench.__version__`), alineada con este
documento y el README. Qué sube cada nivel:

- **major**: cambian casos, ground truth o preguntas → los resultados dejan de ser comparables;
- **minor**: runs, modelos, experimentos o funciones nuevas;
- **patch**: documentación y arreglos.

Las versiones 0.1.0–0.4.0 son retroactivas (se asignaron a 27-sep sobre los commits ya existentes).

## [0.19.0] - 2026-10-03 — Variante trunc de Strands y token HF persistente

- Nuevo run `strands_2b_hobson_v19_xpu_trunc`: batería completa (195/195, 0 errores)
  sin `--strict-window`, es decir, con el truncado silencioso por defecto del
  servidor. Ajustado **21** (sin `*`); los 194 casos dentro de ventana responden
  idéntico al run estricto y P11 truncado acierta 2/5 preguntas (papers 59.1).
  El run primario del marcador sigue siendo el estricto (`_xpu`, 21*).
- Token HF del repo persistido en `~/.cache/huggingface/token` de .70, .80 y .81
  (a petición del usuario; verificado como `Mindbreaker81`).
- Web/sitio: fila de Strands en la tabla de modelos, latencias de CLM y Strands
  en la nota, hardware con la Arc Pro B70, y `coste.html` corrige que los
  abiertos ya no corren solo en GB10.

## [0.18.0] - 2026-10-03 — Strands Decider 2B Hobson v19 en Intel XPU (JEV-51)

- Nuevo run `strands_2b_hobson_v19_xpu`: `StrandsAgents/strands-decider-2B-hobson-v19`
  (checkpoint `bb282d78`, MANIFEST verificado; base `Qwen/Qwen3.5-2B-Base` `b1485b2f`,
  coincidente con la revisión inferida de `provenance.json`), servido con
  `strands-decider` git `eb89e5c` en Intel Arc Pro B70 (estación .70, backend XPU
  experimental confirmado por `/health`), ventana 4096 estricta y
  `--max-batch 5`; adaptador `systemone_http` por túnel SSH.
- 195 casos / 11 fases, 1 error pre-registrado: P11 excede la ventana (HTTP 422),
  papers32 queda 31/32 y el ajustado lleva `*`. Ajustado **21\***: por debajo de
  Decider-4B (33) y de Jev (45), por encima de la mayoría en casi todas las fases;
  falla en dept de adv1+2 (9/20 frente a 17/20 trivial). Derrotas significativas en
  `same_day` de triaje_ext_es frente a Jev y `relevance` de papers frente a
  Decider-4B (p<0.01); ninguna victoria significativa. Mediana ~0,13 s/caso cliente.
- Primer manifiesto remoto: `docs/infra_runs/strands_2b_hobson_v19_xpu.md`
  (hardware, revisiones, `/health`, comando efectivo, plan de ventana
  pre-registrado). `docs/dgx-spark.md` documenta la estación .70.
- Ficha en `docs/modelos.md` (incluye el inventario de entrenamiento — ContractNLI,
  MuSiQue, BoardgameQA, HelpSteer2, generados — sin solapamiento conocido, y la
  cuarentena de su «JevBench public» de 231 tareas) y marcador, web y sitio con la
  familia nueva "Strands" (color propio).

## [0.17.1] - 2026-10-03 — Procedimientos y controles de publicación (JEV-52)

- Skills y procedimientos de evaluación/web: evidencia de viabilidad por dispositivo,
  manifiesto remoto, entrega delegada y concurrencia, validación independiente del scorer,
  criterio de cascada con valores sin redondear y McNemar pareado para alertas.
- Cierre por alcance: distinguir batería, integración local y despliegue remoto;
  preservar cambios preexistentes y no exigir despliegues no solicitados.
- Sitio: entorno verificado por run en `extra.env`; un endpoint HTTP genérico no implica
  GPU NVIDIA ni cuantización, y un LLM con endpoint propio no se etiqueta como API OpenAI.
- Regresiones: presencia y familia de runs en ambas webs (con excepciones históricas
  explícitas), etiquetas remotas correctas y ausencia de inferencias desde el host cliente.
- Exportador del espejo: elimina endpoints de metadatos y opciones anidadas, que
  conservaban la IP privada de CLM; regresión que verifica que las predicciones no cambian.
- actualizar-web: «Historia del marcador» documentada — `RUN_DATES` obligatorio para
  fusiones de cascada sin `meta.updated` y `HIST_EVENTS` solo para hitos del relato.

## [0.17.0] - 2026-10-03 — Historial del marcador en la web (JEV-50)

### Añadido
- **Sección «Historia del marcador»** en la web y la portada del sitio
  (`docs/web/template.html`, sección `#historia` + nav): línea temporal con
  cada run como punto (color por familia, tooltip con fecha/tipo/cobertura) y
  tres récords escalonados — decisor dedicado de una pasada (Jev → Clef-27B),
  una pasada incluyendo LLM (Jev → gpt-6-luna → gpt-6.1-sol) y cualquier
  configuración (Jev → Jev→Jev → luna→Jev). Hitos curados como marcadores
  verticales (`HIST_EVENTS` en el template).
- **`RUN_DATES` y `run_date()` en `jevbench/web.py`**: cada run lleva `when` —
  el menor `meta.updated` de sus fases; para las fusiones de cascada (sin sello)
  la fecha va fijada a mano en el mapa.

## [0.16.0] - 2026-10-03 — CLM y revisión de conclusiones de Clef (JEV-49, JEV-48)

### Evaluación de Contrastive-LM CLM-v0.1-8B en Intel Arc Pro B70 (JEV-49)
- **Run `clm_v0.1_8b`** (`results/clm_v0.1_8b/`): batería completa de 195 casos
  (`all+new` + `adv4`/`adv5`), 11 fases y 0 errores, servida mediante vLLM XPU en
  la Arc Pro B70 de 32 GB. Mediana de 80 ms por caso.
- Resultado negativo: ajustado **−35** frente a 0 de la mayoría, triaje ES/EN
  67.9/58.6, papers 50.6, adversarial 1+2 52.5, adv3 59.0, adv4 54.5,
  adv5 59.5 y Brier noul 0.238. No obtiene victorias significativas frente a
  Jev o Decider-4B; no es candidato a recomendación.
- Integrado CLM en marcador, artifact y sitio público, con familia propia y ficha.
- Revisión de JEV-48: el criterio de cascada local de Clef se mantiene. Se retira
  adv2 como evidencia comparativa y se matiza la alerta 27/30 frente a 25/30:
  McNemar p=0.50, sin diferencia significativa. Corregida la nota de la web que
  todavía decía que ningún revisor local superaba el listón.
- Corregida la tabla de cascada Clef: adv4 = **88.0**, no 83.5; ganancia media
  de triaje = 3.93 puntos. Ambos salen de los JSON mediante el scorer.

## [0.15.0] - 2026-10-03 — Clef-27B (Cloudflare) y primera cascada 100 % local (JEV-48)

### Añadido
- **Adaptador `clef`** (`jevbench/adapters/clef.py`): carga `joint_schema_model.py`
  del propio snapshot de HF y llama a `systemone` (API SystemOne nativa).
  `scripts/alert_onepass.py`: alerta de una pasada (solo `manipulation`, umbral 0.5)
  sobre adv3–adv5.
- **Run `clef_27b`** (`results/clef_27b/`): 195 casos, 0 errores, bf16 en DGX .81
  (revisión `2f3de3dd`). Ajustado **52** — el mejor single open-weight, por encima
  de `jev_v3` (45) en agregado: victoria significativa en `depth` de papers
  (p = 0.02), sin derrotas significativas. adv1/adv2 no se usan como evidencia
  comparativa. Mediana ~0.87 s/estado.
- **Cascada `decider_4b_clefrev_*`** (runs `raw/review/audit/avg`): Clef-27B es el
  **primer revisor que cumple el criterio JEV-32 sin ser Jev** — ~89 % de su
  ganancia en adv3+adv5, ~61 % en triaje, sin fase peor >2 puntos y alerta 9/10 ·
  1 FP en adv5. `decider_4b_clefrev_audit` = ajustado **58**, la primera cascada
  100 % local que da la talla.
- **Alerta de una pasada `clef_27b_alert_raw`**: 27/30 TP · 1/30 FP en adv3+4+5,
  cumple el criterio en los tres sets; frente al revisor Jev (25/30), la diferencia
  no es significativa (McNemar exacto p = 0.50).
- Documentación: ficha en `docs/modelos.md`, secciones nuevas en
  `docs/experimentos/cascada_jev.md` y `alerta_manipulacion.md`, recomendación
  vigente actualizada en `docs/resultados.md`; web y sitio con la familia Clef
  (color `--f-clef`, dumbbell y unidades de alerta).

## [0.14.0] - 2026-10-01 — gpt-6.1-sol con razonamiento `low` (JEV-47)

### Añadido
- **Opción `reasoning_effort` del adaptador `llm`** (`jevbench/adapters/llm.py`):
  `minimal`/`low`/`medium`/`high`, traducida a `reasoning={"effort": …}` en la API
  Responses y a `reasoning_effort=…` en Chat Completions. Solo para `provider=openai`
  (con Anthropic/Gemini falla al construirse, como los demás límites); cualquier otro
  valor da `ValueError`. Sin la opción no se envía ninguna clave de razonamiento, así
  que los runs anteriores no cambian. `meta()` guarda el valor aunque sea `None`.
- **Precio de `gpt-6.1-sol`** en `PRICES` ($2.00/$10.00 por Mtok; la página de precios
  de OpenAI no fue legible y el dato coincide en OpenRouter y fichas de terceros).
- **Run `llm_gpt61sol_low_prob`** (`results/llm_gpt61sol_low_prob/`): gpt-6.1-sol con
  `reasoning_effort=low`, modo `probabilities`, 195 casos (`all+new` + adv4/adv5),
  0 errores. Pre-registro y presupuesto ($3) en `docs/plan_gpt61sol.md` (ejecutado).
- Pruebas offline de la opción en `tests/test_llm_adapter.py`: las dos APIs reciben la
  clave correcta, sin la opción no aparece, valor inválido y proveedor no OpenAI → error,
  y `meta()["reasoning_effort"]`.

### Resultado (195 casos, coste medido $0.56, ~$0.0029/caso, mediana 3.4 s)
- **Ajustado 65: la mejor una pasada medida**, por encima de gpt-6-luna (61) y a la par
  de la cascada `jev_cascade_audit` (64); por debajo de la mejor config absoluta,
  `llm_gpt6luna_jevrev_audit` (71). Brier noul 0.054 (≈ luna, 0.053).
- Comparaciones pre-registradas: frente a luna solo es significativo `urgency` de adv4
  (6–0, p = 0.03); frente a `jev_v3`, `depth` de papers (13–1, p < 0.01); frente a
  `jev_cascade_audit`, nada significativo.
- Documentación: marcador (`docs/resultados_runs.txt` + `jevbench.report`), ficha en
  `docs/modelos.md`, bullet en «Por modelo», `RUNS` de `web.py` y `site.py` (familia
  LLM) y textos de portada (mejor una pasada, tabla de modelos, latencias). El
  circuito recomendado no cambia: sigue siendo Jev → revisor Jev.

### Revisión de la web y la documentación de sol
- **Alcance limitado por coste**, anotado en la portada (tarjeta de Jev, matiz del circuito,
  «Qué no se ha probado»), en `docs/modelos.md` y en `docs/resultados.md`: de gpt-6.1-sol solo
  hay una pasada en modo `probabilities`; faltan `discrete`, su papel como revisor, la cascada
  sol → revisor Jev y la alerta de manipulación.
- Portada: la tarjeta de Jev pasa a «mejor decisor **dedicado**» (dos LLM generalistas le
  superan en agregado); el matiz del circuito compara sol con Jev → revisor Jev (65 frente a
  64, ~34× el coste por mensaje); gpt-6.1-sol tiene su propio paso, fechado el 1-oct, en «Las
  pruebas, en orden», en vez de una frase añadida al paso de luna del 29-sep.
- `docs/modelos.md`: el bullet de sol estaba entre el «Probado» y el «Resultado» de luna, así
  que el «~5.5× más caro» de luna parecía de sol; reordenado y etiquetado.
- `docs/resultados.md`: el sentido de los McNemar (6–0 y 13–1, **a favor de sol**).

## [0.13.3] - 2026-10-01 — Revisión de la web de resultados

### Web y sitio
- La cabecera de la portada ya no fija «26–27 sep 2026»: muestra la versión del banco y su fecha,
  que `jevbench.web.version_date()` lee del CHANGELOG (marcador `__VERSION_DATE__`).
- Versión de Jev comprobada de nuevo (`check_versions --log`): sigue en jev-1.13 a 1-oct.
- Conclusiones al día con los runs de 29-sep a 1-oct: tarjeta de Nimble-9B (mejor abierto de una
  pasada, ajustado 44) y Tev1-4B; descartes ampliados con Tev1-0.8B y los Qwen3.8 locales;
  gpt-6-luna como revisor en la tarjeta y la nota de revisores.
- La alerta de manipulación pinta también las cascadas con LLM (`llm_gpt6luna_jevrev`, 25/30 y
  1 FP; `decider_4b_llmrev`, 20/30 y 2 FP), que ya se calculaban pero no se mostraban.
- «Las pruebas, en orden» incluye los seis bloques de 29-sep a 1-oct (línea base LLM, cascadas
  LLM, Span-01 y score ajustado, LLM locales, Nimble/Tev1, robustez del adaptador).
- Coste del circuito con las medias medidas (~$0.000035 + ~$0.00005 por caso), no la estimación
  antigua; tamaño de los sets «10 a 32 casos»; colores de Nimble/Tev1 en el tema oscuro forzado.
- `tests/test_site.py` comprueba que la cabecera lleva versión + fecha y ningún «sep 2026» fijo.

### Publicación del espejo (arreglo)
- **Fallo:** el tag público `v0.13.2` (commit `2d525b0` del espejo) añadió los ficheros nuevos,
  pero dejó README, CHANGELOG y `jevbench/__init__.py` en 0.5.0. Causa: `jevbench.publish`
  exportaba el snapshot al clon y **después** `publish()` hacía `git reset --hard origin/main`,
  que devolvía a su versión anterior todo fichero ya existente (y recuperaba los que tenían que
  borrarse); solo sobrevivían los nuevos. La simulación sin `--push` tenía el mismo defecto y
  daba un falso «todo bien».
- **Arreglo:** `prepare_clone()` (antes `clone_or_fetch`) deja el clon en `origin/main`, o en una
  rama huérfana si el espejo está vacío, y vacía el árbol **antes** del export; `publish()` ya no
  hace reset ni checkout. `export()` devuelve el id de blob de git de cada fichero y
  `verify_commit()` exige que el commit contenga exactamente ese snapshot (mismos ficheros y
  mismos bytes) antes de crear el tag o subir nada, también en la simulación.
- **Regresión:** `tests/test_publish.py::PublishGit` usa un remoto local que parte de un README
  en 0.5.0 y de un fichero fuera del manifiesto: el commit debe llevar la versión nueva, el
  fichero añadido y la eliminación; si se restaura contenido viejo tras el export, falla sin
  etiquetar. Cubre también el espejo vacío.
- El tag público `v0.13.2` no se reescribe (las versiones publicadas son inmutables): la
  corrección se publica como `v0.13.3`.

## [0.13.2] - 2026-10-01 — Cierre y alineación de la documentación

### Documentación
- Alineados README, guía de agentes, infraestructura y fichas con los adaptadores y modelos
  presentes en el código: Nimble-9B y Tev1 ya aparecen en los inventarios y en la tabla pública.
- Marcados como ejecutados los planes del revisor local y de robustez LLM; eliminadas referencias
  pendientes ya resueltas en los planes e informes históricos, y aclarado el carácter histórico
  del run Flash anterior a los límites.
- Corregida la descripción de Nimble: usa un forward por campo, no una sola pasada por estado.
- Actualizadas y regeneradas la web interactiva y el sitio público.

## [0.13.1] - 2026-10-01 — Nota pública sobre la robustez del adaptador `llm`

### Documentación
- Añadida en la ficha, el informe, el artifact y el sitio público una explicación del
  problema encontrado y de su corrección: el timeout no cubría todo el caso, faltaba un
  tope de salida y la telemetría se descartaba. Desde 0.13.0 hay presupuesto total,
  `max_tokens`, diagnóstico persistido y redacción de secretos. La nota aclara que no
  cambiaron el prompt, las preguntas, el GT, el scorer ni los resultados históricos.

## [0.13.0] - 2026-10-01 — Robustez del adaptador `llm` (JEV-44)

### Añadido
- **Límites del adaptador `llm`** (`jevbench/adapters/llm.py`): `case_timeout`
  (presupuesto de pared por caso que incluye las correcciones por JSON mal formado;
  cada petición usa `min(timeout, restante)` y falla antes de abrir otra petición si la
  bolsa está agotada), `max_tokens` (traducido a `max_output_tokens` en Responses,
  `max_completion_tokens` en Chat Completions oficial y `max_tokens` en endpoints
  compatibles) y `timeout` ahora efectivo también con OpenAI directo — antes se ignoraba
  si no había `base_url`/`extra_body`. `extra_body` fuera de Chat Completions y los
  límites con provider=anthropic/gemini fallan con error explícito en vez de ignorarse.
  Los miembros privados de `system-one-adapter==0.2.1` se concentran en
  `_openai_internals()` con test de compatibilidad.
- **Telemetría persistida:** `jevbench.run` guarda `usage` compacto (tokens, reintentos,
  `attempts`, latencia) en los casos exitosos y `ms` + `diag` seguro (intentos, tipo de
  error, categorías de reintento) en los errores. Nunca prompts, estados ni cuerpos HTTP.
- **Redacción de secretos:** las opciones `--opt` cuyo nombre contiene `api_key`,
  `token`, `secret` o `password` se guardan como `<redacted>` en `meta.opts`; el
  adaptador sigue recibiendo el valor real. La redacción también recorre JSON anidado
  en `extra_body` (incluidos `Authorization`, credenciales y cookies) antes de guardar
  o imprimir el `meta`.
- **Validación de límites:** `timeout`, `case_timeout` y `max_tokens` rechazan cero y
  valores negativos; el parche de API privada comprueba además la versión exacta 0.2.1.
- **Pruebas offline** (`tests/test_llm_adapter.py`, `tests/test_run.py`): transporte
  OpenAI contra servidor HTTP local de vida corta (esquema, `extra_body`,
  `structured=false`, `max_tokens` en las tres APIs, 429/500, conexión cerrada,
  respuesta truncada, timeout), reintentos por JSON mal formado, presupuesto por caso
  con reloj inyectado, telemetría del runner y secretos centinela, también dentro de
  `extra_body`. 18 tests en el venv y 5 del runner con el Python del sistema.
- **Entorno `.venv-llm` reconstruido** con uv + Python 3.12 gestionado (el anterior
  quedó roto tras actualizar el sistema a 3.14): `system-one-adapter[openai]==0.2.1`,
  `typesafe-sdk==0.7.1`, `openai==3.16.2`, `httpx2==2.13.0`, `httpcore2==2.13.0`. El
  roto se conserva apartado como `.venv-llm.broken-20261001` (no versionado).
- **`scripts/smoke_llm.py`**: smoke diagnóstico de 6 casos fijados × N repeticiones
  contra un endpoint compatible (control OOD, adv2/adv3/triage_ext/triage_es), con
  registro de ms, tokens, intentos y memoria. Salida en `results/logs/`, no es un run.

### Smoke DGX .81
- 18 ejecuciones (6 casos × 3 reps) contra `qwen3.8-flash-next` (mismo endpoint del
  run `llm_qwen38flash_prob`, contenedor `vllm-fn-tp1`) con `timeout=1800`,
  `case_timeout=600`, `max_tokens=16384`: todas ok, 1 petición cada una, 16–170 s,
  sin errores de transporte (`results/logs/smoke_llm_jev44.json`).
- Comprobación dirigida: `case_timeout=45` aborta el caso a los 45.0 s exactos sin
  dejar petición viva y el caso normal posterior responde en 30.9 s; un intento con
  generación desbocada terminó en `finish_reason=length` al llegar al tope de
  salida, error acotado que demuestra que `max_tokens` llega al servidor.

## [0.12.0] - 2026-09-30 — Nimble-9B y Tev1 (4B y 0.8B), JEV-41/42/43

### Añadido
- **Adaptador `nimble`** (`jevbench/adapters/nimble.py`) sobre el `ParallelScorer`
  oficial que embarca el repo HF de Bespoke-Nimble-9B (verifica los SHA256 del
  prompt de entrenamiento y del codebook antes de correr). Mapea `noul`→boolean,
  `choice`→enum con `choice_descriptions` y `score`→enum de enteros
  (`score` = `expected_score`). Una pasada forward por pregunta: cada prompt lleva
  el estado + el esquema completo; no hay pasada única multi-pregunta.
- **Run `nimble_9b`** (195 casos, 0 errores, DGX .81): `bespokelabs/Bespoke-Nimble-9B`
  rev `bd792f44` (LoRA PEFT sobre `Qwen/Qwen3.5-9B@c2022362`), T=1.0 del checkpoint
  actual, torch 2.14.1+cu130, transformers 5.17, peft 0.21. Ajustado **44**, entre
  Jev (45) y Decider-4B (33): triaje 92.9/88.6, papers 70.3 (ρ 0.48), adv3 85.5,
  adv4 79.0, adv5 81.5, ood 100 %, Brier noul 0.084, mediana 1.6 s/estado. Sin
  diferencias significativas frente a jev_v3 / decider_4b / gpt-6-luna salvo
  `urgency` de adv4, donde supera a gpt-6-luna (9–0, p<0.01). Es el open-weight
  puro más fuerte de los evaluados sin revisor; hace una pasada forward por pregunta.
- **Adaptador `tev1`** (`jevbench/adapters/tev1.py`) para los Tev1 de Together:
  system prompt y JSON `{state, question, options}` oficiales, y en lugar de
  generar la letra hace softmax sobre los logits de las letras candidatas en el
  primer token (equivale al argmax restringido del contrato: temperature=0 +
  regex, `enable_thinking=false`). Una inferencia por pregunta; cada caso guarda
  `raw.generations`.
- **Run `tev1_4b`** (195 casos, 0 errores, DGX .81):
  `togethercomputer/Tev1-4B-experimental` rev `0b7becf0` (Qwen3.5-4B, bf16).
  Ajustado **27**, por debajo de Nimble-9B (44), Jev (45) y Decider-4B (33):
  triaje 87.1/87.1, papers 64.4 (ρ 0.83), adv3 75.0, adv4 77.5, adv5 72.5,
  ood 100 %, Brier noul 0.115, mediana 0.45 s/estado. Sin diferencias
  significativas frente a los incumbentes salvo `depth` de papers32, donde
  gpt-6-luna le gana (16–2, p<0.01). Licencia de los pesos pendiente de
  publicación según la propia ficha.
- **Run `tev1_0.8b`** (195 casos, 0 errores, DGX .81):
  `togethercomputer/Tev1-0.8B-experimental` rev `6bb2dff1` (Qwen3.5-0.8B,
  bf16), mismo adaptador sin cambios. **Resultado negativo:** ajustado −7,
  bajo la mayoría trivial (triaje 67.9/72.1, adv total 58.5 vs 79.0 del
  baseline, adv3 64.0, Brier 0.171, 12 binarios en 0.45–0.55 en adv3). El 4B
  le gana en `same_day` de adv4 (10–1, p=0.01) y los incumbentes en varias
  preguntas (department adv3/ext_es, clinical triaje ES). Mediana
  0.14 s/estado. Licencia de los pesos también pendiente.

## [0.11.0] - 2026-09-30 — LLM local Qwen3.8-Flash-Next (negativo), JEV-39

### Añadido
- **Run `llm_qwen38flash_prob`**: Qwen3.8-Flash-Next NVFP4 servido con vLLM en el DGX .81,
  mediante `system-one-adapter` con thinking activado (sin él fallaba el smoke). Resultado
  negativo y peor que el 27B: ajustado −40, triaje 65.7/55.0, papers 38.1 (ρ −0.01), adv3
  65.3 y Brier 0.317. Jev y gpt-6-luna son significativamente mejores en múltiples preguntas;
  el Flash no obtiene ninguna ventaja significativa. Tras reintentar entrega 191/195 respuestas
  (4 timeouts), con mediana 49.7 s/caso y ~14.7 h de pared entre ambas pasadas.
- Documentado un límite operativo del adaptador: `timeout` se aplica por petición y los
  reintentos internos pueden alargar un caso; este run no fijó un máximo total ni de tokens.

## [0.10.0] - 2026-09-29 — score ajustado y alerta de manipulación con Span-01, JEV-40

### Añadido
- **Score ajustado** (`jevbench.score.adjusted`, columna en `--summary` y en la
  tabla de la web): media por fase de (acierto − línea base de mayoría) /
  (100 − línea base). 0 = responder siempre lo más frecuente, <0 = peor que el
  trivial; `ood` queda excluida (mayoría = 100 %) y `*` marca cobertura
  incompleta de las 11 fases. Jev→Jev 64, gpt-6-luna→Jev 71, Jev solo 45,
  gpt-6-luna solo 61, Decider-4B 33, Span-01 pro 18.
- **Alerta de manipulación con Span-01 (negativo):** como detector de una sola
  pasada (misma pregunta `manipulation` y umbral 0.5 del revisor), pro detecta
  8/30 y lite 5/30 en adv3–5 con 0 falsos positivos — muy por debajo del
  criterio (≥7/10 por set) y del revisor Jev (25/30). Runs
  `span01_pro_alert_raw` / `span01_lite_alert_raw`; documentado en
  `docs/experimentos/alerta_manipulacion.md`.

### Corregido
- Coste de Span-01 pro: era "~10× más barato que Jev"; medido: $0.0032 los 195
  casos ($0.000016/caso), ~2× menos que Jev ($0.000035) y ~12× menos que
  gpt-6-luna ($0.000194).
- Web: matiz sobre el LLM generalista — gpt-6-luna supera a Jev en agregado
  (61 vs 45) y gpt-6-luna→revisor Jev es la mejor configuración medida (71), a
  ~5× coste/latencia por mensaje.

## [0.9.0] - 2026-09-29 — Span-01 y Span-01 Lite (Respan), JEV-40

### Añadido
- **Adaptador `respan`** (`jevbench/adapters/respan.py`) para Span-01 de Respan,
  clasificador de comportamientos hiper-paralelo (anunciado 24-sep-2026). Dos
  caminos: API nativa `api.respan.ai/api/v1/scores` (`provider=respan`, clave
  `RESPAN_API_KEY`; `span-01-pro` requiere créditos Respan, `span-01-free` es
  Lite gratis) y OpenRouter `/api/alpha/decisions` (`provider=openrouter`, donde
  Respan solo admite `noul`, así que `choice`/`score` se expanden a una noul por
  opción). Mapeo: `noul` → una definición; `choice`/`score` → una por opción;
  en nativo p = present/(present+absent) (`not_observable` = evidencia neutra).
- **Runs `span01_pro`** (OpenRouter, resuelto `span-01-20260925`, $0.003 los 185
  casos), **`span01_lite`** (API nativa `span-01-free`, gratis) y
  **`span01_lite_or`** (Lite vía OpenRouter, `span-01-lite-20260925`), todos con
  all+new + adv4 + adv5 y 0 errores. Competitivo pero por debajo de Jev en
  conjunto: triaje 85.0/84.3, adv3 72.0 (pro) vs 88.6/90.0 y 87.5 de Jev; Jev le
  gana con significación en `same_day` de triaje ext (p<0.05) y en urgency de
  adv3. Span-01 sí supera a Jev en `depth` de papers32 (17/32 vs 6/32, p=0.01).
  Coste medido: $0.000016/caso (~2× menos que Jev, ~12× menos que
  gpt-6-luna). Lite y pro dan prácticamente lo mismo por OpenRouter.

## [0.8.0] - 2026-09-29 — LLM local en DGX: Qwen3.8-27B (negativo), JEV-39

### Añadido
- **Adaptador `llm`: opciones `extra_body`, `api_key` y `timeout`** para endpoints
  OpenAI-compatibles (SGLang/vLLM en los Sparks): `chat_template_kwargs` (thinking on/off),
  muestreo recomendado por la ficha y timeout largo para modelos con thinking.
- **Run `llm_qwen38_27b_prob`** (`RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead` en SGLang, .80):
  195 casos, 2 errores por timeout. **Resultado negativo**: apenas por encima de la línea
  base trivial (triaje 73.6, papers 52.2, ρ −0.17, adv total 58.5 < 79.0 del baseline,
  Brier 0.231, ~6.8 s/caso). Thinking `low` no mejora y encarece la latencia. Un LLM
  grande no basta si no sigue el contrato System One.
- En marcha en .81: `llm_qwen38flash_prob` (Qwen3.8-Flash-Next NVFP4 en vLLM, thinking on).

## [0.7.0] - 2026-09-29 — cascadas LLM: revisor LLM y LLM → revisor Jev

### Añadido
- **Cascada `llm_gpt6luna_jevrev_*`** (LLM → revisor Jev, JEV-38): mejor configuración medida —
  adv total 92.0, adv5 88.5, Brier noul 0.045, alerta 9/10 con 1 FP. Estadísticamente
  equivalente a `jev_cascade_audit` a ~4× el coste y la latencia.
- **Cascada `decider_4b_llmrev_*`** (revisor LLM sobre Decider-4B): recupera el 77 % de la
  ganancia de Jev en adv3+adv5 (primer revisor no-Jev que pasa del 50 % ahí), pero no cumple
  JEV-32 por triaje (28 %) ni por la alerta de manipulación (6/10). Detalle:
  `docs/experimentos/cascada_jev.md`.

## [0.6.0] - 2026-09-29 — línea base LLM (system-one-adapter + gpt-6-luna)

### Añadido
- **Adaptador `llm`** (`jevbench/adapters/llm.py`) sobre `system-one-adapter` 0.2.1 de TypeSafe
  (sustituto de `system_one` con un LLM: OpenAI, Anthropic, Gemini o endpoint compatible con
  OpenAI). Opciones `mode=probabilities|discrete`, `structured`, `base_url`, `usd_in`/`usd_out`.
  Venv local `.venv-llm` con versiones fijadas (≥ 7 días). Test offline con proveedor falso:
  `tests/test_llm_adapter.py` (se salta si la librería no está instalada). JEV-38.
- **Runs `llm_gpt6luna_prob` y `llm_gpt6luna_disc`**: gpt-6-luna por API directa de OpenAI,
  fases `all+new`, `adv4` y `adv5` (195 casos, 0 errores). En una pasada queda al nivel de la
  cascada de Jev: triaje 93.6/95.7, papers 78.8, adv 18/20, adv3 17/20, adv5 83.5, Brier noul
  0.053. Frente a `jev_v3`, solo `depth` de papers es significativo (p < 0.01, a favor del LLM);
  frente a `jev_cascade_audit`, solo `urgency` de adv4 (p = 0.01, a favor de la cascada). Coste
  $0.00019/caso (5.5× Jev) y mediana 3.1 s (5× Jev). `discrete` calibra peor (Brier 0.077).
- Familia `LLM` en el marcador, la web y el sitio (color `--f-llm`); `OPENAI_API_KEY` en
  `.env.example`.

## [0.5.0] - 2026-09-27 — versionado, licencias y espejo público

### Añadido
- **Versión semántica única** (`jevbench.__version__`), comprobada por `tests/test_version.py`
  contra este CHANGELOG y el README. Tags anotados `v0.1.0`–`v0.4.0` sobre los commits
  retroactivos y `v0.5.0` sobre el commit de esta entrada.
- **Licencias**: MIT para el código (`LICENSE`) y CC BY 4.0 para casos, GT y resultados
  (`LICENSE-DATA`).
- **`jevbench.publish`**: exporta a mano, por versión, un snapshot saneado al espejo público
  (`Mindbreaker81/system-one-bench-public`): lista blanca de ficheros, `meta.host` genérico,
  abstracts de PubMed sustituidos por su hash, nombres propios neutralizados y un escáner
  bloqueante de cadenas sensibles. `tests/test_publish.py` lo cubre.
- **`jevbench.fetch_abstracts`**: reconstruye los abstracts de `data/papers32.json` desde
  PubMed (necesarios para ejecutar `papers32`, no para puntuar) y avisa si el hash difiere.
- **Procedimiento `publicar-version`** (`docs/procedimientos/`, `.claude/skills/`): cuándo
  sube cada nivel de versión y cómo se publica el espejo.
- Enlaces a GitHub y etiqueta de versión en la web (`docs/site_src/_nav.html`,
  `docs/web/template.html`).

### Cambiado
- `paper_state` (`jevbench/battery.py`) tolera papers sin abstract (marcador
  `[abstract no descargado]`); `jevbench.run` aborta en `papers32` si falta alguno.
- `jevbench.site` ya no borra la línea de YouTrack del resumen: el pie del template habla del
  repo público, no del seguimiento interno.
- `data/adversarial2_cases.json` (y `.anot2`): el email inventado del caso B02 pasa de
  `@gmail.com` a `@example.com` — dominio reservado, no un buzón real. El GT no cambia y las
  puntuaciones guardadas siguen siendo las medidas (registrado en `data/GT_CHANGELOG.md`);
  la copia de `legacy/` se mantiene de solo lectura y se enmascara al exportar.

## [0.4.0] - 2026-09-27 — procedimientos, sitio público y documentación

Tag: `v0.4.0` → `0093c8c`. (Sección "27-sep-2026 (tarde)" del changelog anterior.)

### Añadido
- **Procedimientos y skills** para las tareas que se repiten: evaluar un modelo nuevo, evaluar una
  versión nueva de Jev y crear un set de casos (`docs/procedimientos/`, `.claude/skills/`) (`98eebd4`).
  Un test (`tests/test_procedimientos.py`) comprueba que cada comando, flag y ruta citados existe.
- **Sitio público para Netlify** (`jevbench.site`, `docs/site_src/`, `netlify.toml`):
  - resumen;
  - explorador caso a caso;
  - acierto por pregunta, matrices de confusión y calibración;
  - comparador A/B con McNemar;
  - qué cambia el revisor;
  - coste y latencia;
  - metodología.

  El saneado está cubierto por tests (sin abstracts, emails, hostnames ni YouTrack; emails y enlaces
  de los casos inventados, ocultos) (`3986bfb`).
- **README** con guía de reproducción en tres niveles y aviso sobre el ground truth, también en la
  web (`b485a52`).
- **Web resumen** interactiva (`jevbench.web`): conclusiones, marcador, revisor, seguridad, cómo leer
  los números, las pruebas en orden y la tabla de modelos con enlaces (`5e44f6a`, `0361ac2`).

### Cambiado
- `docs/bateria.md` reescrito al estado actual; `docs/plan.md` marcado como histórico.
- `.gitignore`: se ignoran `node_modules/`, `package*.json` de netlify-cli, `.netlify/` y la config
  local de agentes, salvo `.claude/skills/` (`3267111`, `7d531be`).

### Corregido
- `node_modules` se coló en un commit con `git add -A`; se retiró del historial reescribiéndolo. Desde
  entonces, los ficheros se añaden uno a uno.

## [0.3.0] - 2026-09-27 — revisores abiertos, alerta y versiones

Tag: `v0.3.0` → `4b1aece`. (Sección "27-sep-2026 (mañana)" del changelog anterior.)

- **Revisor 100 % local (JEV-32), resultado negativo.** Ningún revisor abierto (Decider-35B NVFP4,
  AnyJev-32B, AnyJev-8B) alcanza el 50 % de la ganancia que da Jev como revisor. Ejecutado por otro
  agente a partir de `docs/plan_revisor_local.md` (`4b1aece`, `25cbf62`).
- **Alerta de manipulación validada** en adversarial-5, un set nuevo con pre-registro: 9/10
  detectados y 1 FP. Acumulado adv3–5: 25/30 y 1/30 (`33f2df5`, `25cbf62`).
- **`check_versions`:** OpenRouter y TypeSafe siguen sirviendo jev-1.13; `jev-preview` también. Registro
  en `docs/versiones_jev.md` (`33f2df5`).

## [0.2.0] - 2026-09-27 — GT v3, modelos grandes, reglas y cascadas

Tag: `v0.2.0` → `173fdb3`. (Sección "27-sep-2026 (madrugada)" del changelog anterior.)

- **Reglas duras regex descartadas.** Con el set nuevo adversarial-4 y las reglas congeladas por hash:
  0/10 ataques detectados y 3/10 falsos positivos, uno de ellos una fiebre tras la EBUS (`2783475`,
  `173fdb3`). Primera versión en `9805256`.
- **Decider-35B NVFP4** servido con vLLM en la GB10: igual que bf16 y 3.5× más rápido. Script de
  arranque y notas sobre memoria unificada, OOM y `ninja` (`c553757`).
- **Laya en GPU** con el harness: reproduce el rerun de Lyra; la variante typed-decisions no mejora
  (`c68dd2e`).
- **`jevbench.report`** regenera el marcador de `docs/resultados.md`, con `--check` para CI (`f8e4191`).
- **Cascada con cualquier revisor.** Decider→Decider apenas mejora; Decider-4B→Jev iguala a Jev→Jev
  (`8bd3259`).
- **GT v3:** adjudicación de la segunda anotación con el usuario (9 cambios), con versiones v1 y v2
  conservadas. Decider-35B bf16 (sin CUDA graphs) y AnyJev-8B/32B completos (`d6cf667`).
- **Segunda anotación (JEV-27):** concordancia separada por procedencia (78 respuestas humanas),
  variante de GT `anot2` y análisis de sensibilidad: el orden entre modelos no cambia (`e1ba32a`,
  `0a2256f`).

## [0.1.0] - 2026-09-26 — harness, modelos abiertos y casos nuevos

Tag: `v0.1.0` → `d8ad35a`. (Sección "26-sep-2026" del changelog anterior.)

- **Segunda anotación:** paquete a ciegas y scorer de concordancia (`8c9eadd`); corregido el kappa en
  preguntas nominales (`d8ad35a`).
- **YouTrack** documentado en `AGENTS.md` (`47e6ca2`).
- **Casos nuevos validados por el usuario:** triaje ampliado (26 × ES/EN) y adversarial-3 (20,
  equilibrado), ejecutados en todos los modelos. La cascada se confirma en casos nuevos (`c3950b9`,
  `735df3b`, `781ba5a`).
- **Julia-1** (SupersonicLabs): por debajo de la mayoría por su sensibilidad a la redacción (`e188211`).
- **Jev por la API directa de TypeSafe:** equivalente a OpenRouter (406/409). **GT P04 corregido**,
  con versionado. **Experimento de cascada Jev→Jev** pre-registrado: mejora los cuatro bloques
  (`d0ca552`).
- **Modelos abiertos en los DGX Spark:** Decider 0.8B/2B/4B, GLiNER2.5 (Decide, 1B y multi; con y sin
  descripciones), AnyJev 1.7B en GPU. Scripts de venv y colas (`c8ba4dd`).
- **Harness `jevbench`:**
  - batería única en formato TypeSafe y adaptadores por modelo;
  - scorer con línea base de la mayoría, IC bootstrap, Brier/ECE y McNemar;
  - tests que reproducen los informes de Lyra;
  - Jev v3 (`aaa733f`).

  Resumen por modelo y correcciones de McNemar en `1cf03ce`, `a67e9fa` y `ff8b364`.
- **Inicio:** `AGENTS.md`, documentación e importación de la batería de Lyra en `legacy/` (`9311bf8`).

## Antecedentes (20–25 sep 2026, antes de este repo)

Pruebas hechas por el agente Lyra (Hermes) con scripts sueltos, importadas en `legacy/`:
- Jev frente a Laya: triaje, papers y adversarial-1.
- Rerun, revisor-auditor de Jev, vote-of-3 y gate Jev↔Laya; adversarial-2.
- GLiNER2.5-Decide.
- AnyJev con Qwen3-1.7B en CPU.
