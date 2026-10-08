# Manifiesto: matriz `diag_qwen38_jev66_*` (JEV-66) — confirmación causal del mecanismo

**Qué es:** prueba de confirmación pre-registrada en la issue JEV-66 sobre la
causa raíz identificada en la revisión externa del 4-oct (ver
`docs/infra_runs/diag_qwen38_jev63.md` y `diag_qwen38_prompt_ablacion.md`): con
`structured=true`, `system-one-adapter` envía solo el system prompt fijo y el
documento — las preguntas y criterios viajan únicamente en las `description`
del JSON Schema del `response_format`, que SGLang y llama.cpp usan solo para
construir la gramática **sin inyectarlas en el prompt** → el modelo local
responde a ciegas.

**Resultado, en una línea:** **mecanismo confirmado.** La celda experimental
`typesafe_struct_schema_in_prompt` — mismo prompt TypeSafe, mismo
`response_format`/gramática, con el esquema serializado además en el system
prompt (el mismo apéndice que la librería añade en `structured=false`) —
produce **0 vectores nulos** en los 12 casos × 3 reps en los tres backends
locales, mientras el control `typesafe_struct` sin inyección en la misma
sesión reproduce la misma familia del síntoma (firma por ID exacta solo en
GGUF; en NVFP4/FP8 varía algo por rep). Dato adicional verificado por la
revisión externa: las decisiones de la celda inyectada coinciden 56/56 con
`typesafe_nostruct` de JEV-63 en los tres bloques — con las preguntas
visibles, la gramática forzada no cambia las decisiones— y el `length` de
T16 desaparece con la inyección.

## Matriz ejecutada

12 casos JEV-63 × 2 celdas × 3 reps × 3 bloques = **216 evaluaciones**
(principal pre-registrado: NVFP4 + FP8; extensión GGUF activada al confirmar
los dos primeros, como preveía la issue). Orden de celdas alternado por rep
(`CELL_ORDER` en `jevbench/diag66.py`; seeds 101/202/303 vía `extra_body`).

| Bloque | Motor | `typesafe_struct` (control) | `..._schema_in_prompt` (experimental) |
|---|---|---|---|
| `nvfp4` (<host>) | SGLang + xgrammar | **8/12/10 nulos** + error `length` T16 ×3 | **0/0/0** |
| `fp8` (<host>) | SGLang + xgrammar | **14/14/12 nulos** | **0/0/0** |
| `arcgguf` (<host>) | llama.cpp (gramática propia) | **9/9/9 nulos** | **0/0/0** |

(nulos = vectores `choice`/`score` con `0.0` literal en todas las opciones,
leídos del raw antes de normalizar; "0" = ninguno en las 3 reps.)

El control reproduce la misma familia del síntoma en los tres bloques
(NVFP4: ~10 nulos/rep + el `length` de T16; FP8: ~13/rep; GGUF: 9/rep con la
firma exacta de JEV-63) — la reproducción descarta una deriva de escala que
invalidaría la comparación, aunque las firmas por ID varían algo por rep.
Los tokens de entrada saltan de ~206–222 (ciegas) a
~790–1946 (esquema visible, el nivel de nostruct/Cerebras) al inyectar.
Acuerdo de decisiones entre reps: control 91/102 (nvfp4, con T16 en error) y
109–112/112; experimental 111–112/112. Acierto diagnóstico: experimental
49–50/56 (nvfp4) y 50/56 (fp8, arcgguf) frente a 28–36 del control (en nvfp4,
28–33/51 porque T16 queda fuera por error) — el modelo con preguntas visibles
rinde en la línea de `typesafe_nostruct`/Cerebras. Ambos sobre una línea base
de mayoría de 46/56 en estas 12 preguntas: el control queda muy por debajo de
la trivial y la experimental la supera solo por +3–4 puntos.

## Implementación (opción A del pre-registro)

Nueva opción del adaptador `llm`: `inject_schema_in_prompt=true`
(`jevbench/adapters/llm.py`). En `BoundedProvider.request` añade al system
prompt `"\n\n" + _OUTPUT_SCHEMA_INSTRUCTION_TEMPLATE.format(schema=...)`
construido con el esquema que recibe la petición — **idéntico** al apéndice de
la ruta `structured=false` de la librería (verificado en test: el system prompt
enviado es byte a byte el de `structured=false`, con `response_format`
activo). Solo válido con `structured=true` y provider openai; queda registrado
en `meta` (`inject_schema_in_prompt`, `system_prompt_sha256` calculable sin
petición vía `expected_system_prompt_sha256`). No se tocó `battery.py`, el
scorer ni el GT.

Runner nuevo `jevbench/diag66.py` (celdas `typesafe_struct` /
`typesafe_struct_schema_in_prompt`, orden alternado, mismas protecciones de
reanudación que diag65 + la opción nueva en `CONFIG_KEYS`) e informe
`jevbench/diag66_report.py` (nulos crudos, tokens de entrada, acuerdo y
acierto por celda/rep). Tests: `tests/test_diag66.py` + dos tests del
adaptador en `tests/test_llm_adapter.py`.

## Configuración congelada (idéntica a JEV-65)

```
adapter=llm · provider=openai · mode=probabilities · structured=true
normalize=true · retries_malformed=2 · temperature=0 (extra_body)
max_tokens=8192 · timeout=300 · case_timeout=600 · capture_raw=true
prompt=typesafe · inject_schema_in_prompt=false|true (según celda)
seed=101/202/303 · thinking off: extra_body chat_template_kwargs.enable_thinking=false
```

Casos: los 12 de JEV-63 (`cases_sha256` `e6289c9399bd`); `questions_hash`
`9a81e9763d94` (triaje/adv), `74026502c3ac` (papers), `93ea3deb7eab` (ood).
`system_prompt_sha256` por celda × fase: control `388de09c70e7` (idéntico al
V1 congelado de JEV-65); experimental `da8dc56b75f7` (triaje/adv),
`2915492ffaee` (papers), `5dbace8178de` (ood) — varía por fase porque el
esquema de cada set va incrustado.

## Bloques

### nvfp4 — <host> (`dgx-spark-a`, GB10)

- Contenedor `qwen3.8-27b-sglang` del usuario (`lmsysorg/sglang:qwen38-27b`,
  digest `sha256:febfb971c7352570fc445c466ebd6ffc9d896024958e544a60f2137fd85856b1`,
  image ID `0076dffa60b7`), **sin tocar su servicio**; consumido por túnel SSH
  18000→8000.
- `get_server_info`: SGLang `0.0.0.dev0+qwen38.27b.g561c8f3`,
  `grammar_backend=xgrammar`, `model_path=RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead`.
- Pesos `RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead` @
  `009632fef96dd349150baa780c984e62e70e91fe`, draft EAGLE
  `RadixArk/Qwen3.8-27B-DSpark` @ `b9a5dbdf03bc999c6c73c426b19c2d9041cea393`
  (mismos snapshot que JEV-63/65).
- Control: 8/12/10 nulos por rep (firma JEV-63: P01×4, A01×2, receta,
  contrato; variaciones por rep: r1 sin T15/urgency, r2 añade A02×2 y
  T01/urgency, r3 pierde receta/relevance)
  **más** el error `finish_reason=length` en `T16_epoc_saturacion` las 3 reps
  — misma familia degenerada que JEV-63 (firma no exacta salvo en GGUF;
  FP8 r3 tampoco trae A01×2).
- Nota de trazabilidad: nvfp4 r1 conserva una primera ejecución parcial
  (smoke) reanudada en la misma sesión/config — los JSON solo guardan
  `updated` por fase, así que no se puede reconstruir qué casos son de cada
  tanda; la protección de reanudación confirma que la configuración fue
  idéntica.
- Experimental: 0 nulos, 0 errores, 0 reintentos malformados.

### fp8 — <host> (`dgx-spark-b`, GB10)

- Montaje JEV-63 reutilizado otra vez: pesos `Qwen/Qwen3.8-27B-FP8` @
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` en
  `<ruta-local>`,
  misma imagen (image ID `0076dffa60b7`). GPU libre antes de arrancar
  (0 %, sin contenedores).
- Arranque propio: `QUANT=fp8 PORT=8000 EXTRA_ARGS="--model-path
  <ruta-local>" ./start.sh` (tmux `fp8`;
  la sesión terminó pero el contenedor quedó sirviendo — la línea efectiva es
  la del script). Túnel 18001→8000. `get_server_info`: misma build SGLang y
  `xgrammar` que <host>, `model_path=<ruta-local>`.
- Control: 14/14/12 nulos por rep (firma JEV-63: P01×4, P02×4, A01×2, A02×2,
  receta, contrato; en rep 3 no aparecen los 2 de A01). Experimental: 0 nulos.
- Contenedor parado y eliminado al terminar (era propio de la sesión).

### arcgguf — <host> (`<host>`, Intel Arc Pro B70 32 GB) — extensión

- `llama-server` 0.5.0-dev build `889edf4` (commit
  `889edf43ddae0cfe9a4564a882764dc879759870`), build SYCL (IntelLLVM
  2026.1.1) — mismo binario que JEV-63. Arranque propio con el entorno oneAPI
  (`source /opt/intel/oneapi/setvars.sh`): `-m
  <ruta-local> -ngl 99 -c 32768 --jinja --port 8080`,
  túnel 18002→8080. Acepta `response_format` json_schema,
  `chat_template_kwargs` y `seed`.
- Control: 9/9/9 nulos por rep — **exactamente** la firma de JEV-63 (T15,
  P01×4, A01×2, receta, contrato). Experimental: 0 nulos.
- Proceso parado al terminar (era propio de la sesión).

## Interpretación (reglas del pre-registro JEV-66)

- **0 nulos en experimental + nulos reproducidos en control → mecanismo
  confirmado.** Los runs `structured` locales (histórico NVFP4 −16, Flash −40,
  las celdas struct de los diagnósticos) quedan clasificados como **medición a
  ciegas**: el modelo nunca vio las preguntas.
- El control reprodujo el síntoma en los tres bloques → no hay deriva que
  diagnosticar.
- La extensión GGUF confirma que el mecanismo no es propio de xgrammar:
  llama.cpp con su gramática propia reproduce el mismo patrón.
- Fuera de alcance (siguientes pasos del pre-registro, otras tareas): el
  «techo local real» de Qwen3.8-27B (nostruct a temp 0 o struct con
  inyección sobre la batería completa) y la posible issue upstream en
  `system-one-adapter`.
- Muestra de 12 casos fijados a temperatura 0: las 3 reps son una observación
  repetida (acuerdo 111–112/112 en experimental), no n=36.

**Addendum (cerrado por JEV-67, 6-oct):** la batería completa con
preguntas visibles ya se midió — struct+inject FP8 51 / NVFP4 50 / GGUF 48,
discrete+inject 63 en NVFP4 y GGUF (`docs/infra_runs/qwen38_jev67.md`).
Salvedad de alcance: el «0 nulos» es de esta muestra de 12 casos ×3 reps —
en la batería, B07 conserva el vector nulo incluso con inyección.

Coste: solo GPU local; cero coste de API.

## Reproducir

```bash
# túneles: ssh -NL 18000:localhost:8000 user@<host-lan>
#          ssh -NL 18001:localhost:8000 user@<host-lan>
#          ssh -NL 18002:localhost:8080 <host>   (llama-server --port 8080)
.venv-llm/bin/python -m jevbench.diag66 <nvfp4|fp8|arcgguf> \
  --opt model=<id> --opt base_url=http://127.0.0.1:<puerto>/v1 \
  --opt normalize=true --opt retries_malformed=2 \
  --opt 'extra_body={"chat_template_kwargs":{"enable_thinking":false},"temperature":0}' \
  --opt max_tokens=8192 --opt timeout=300 --opt case_timeout=600 --opt api_key=none
.venv-llm/bin/python -m jevbench.diag66_report <bloque>
```

Runs: `results/diag_qwen38_jev66_<bloque>_<celda>_r{1,2,3}/` (18 runs × 6
fases × 2 casos; `raw` por caso = petición real + respuesta sin normalizar;
en errores, `raw` dentro de `diag`).
