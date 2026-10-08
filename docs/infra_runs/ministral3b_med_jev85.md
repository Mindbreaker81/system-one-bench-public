# Manifiesto: `llm_ministral3b_med_prob` / `llm_ministral3b_med_disc` (JEV-85 / T27)

**Qué es:** batería estándar (`evaluar-modelo-nuevo`) de
`OpenMed/Ministral-3B-Medical-v1`, servido con vLLM en <host> y consumido con el
adaptador `llm` desde el portátil por túnel SSH. Contexto de viabilidad:
`<ruta-local>` (prioridad baja/opcional). Ejecución:
brief `<ruta-local>`, sin git ni push.

## Modelo

- HF `OpenMed/Ministral-3B-Medical-v1`, revisión fijada
  `3a5363c38b873702b97c386c6f24e047101fd541` (declarada por el ejecutor —
  ver «Trazabilidad acotada» más abajo), **no gated**.
- `Mistral3ForConditionalGeneration` (pixtral + ministral3), pipeline
  `image-text-to-text`, ~4 B bf16, safetensors único 7 698 241 104 B,
  `chat_template.jinja` propio (soporta system+user, texto).
- **Limitación:** la ficha no declara licencia ni procedencia de
  entrenamiento/evaluación («research checkpoint», EN-only); se evalúa solo
  como punto de datos «LLM médico pequeño», sin reclamación clínica.
- Pesos en `<host>`: `<ruta-local>`
  (**desviación:** `<ruta-local>` está montado NFS **ro** → no se pudo
  escribir en la biblioteca; queda en `<ruta-local>`).
- `SHA256SUMS` junto a los pesos; `model.safetensors` sha256
  `1e0bcea126dd9c43864fd9d6f26821a45a7f4b93869dfd2a04d4cfd9f88f2fcb`
  (= LFS oid publicado por HF, igualdad **declarada por el ejecutor** — ver la
  nota de trazabilidad en «Evidencia de procedencia archivada»). Resto de
  hashes en el fichero.

## Infraestructura

- **Host:** `dgx-spark-a` (<host>), aarch64 + NVIDIA GB10, 128 GB unificada,
  CUDA 13. Al arrancar: GPU libre (solo Xorg/gnome-shell), único contenedor
  `dashboard-sparkdash` (sin GPU), 116 GiB disponibles.
- **Motor:** vLLM `0.29.1rc1.dev551+g1b3b88ec2` (commit
  `1b3b88ec2b7457aa030db4d0e7d8aaf04f6d0fb8`, editable `<ruta-local>`,
  `VLLM_USE_PRECOMPILED`), venv `<ruta-local>`
  (Python 3.12.14 de uv), `pip freeze` (sin editables) sha256
  `7da8f924aad4e714d75d7a3652b9dfd7d4598123ab13ffc04e417e169ce9e823`.
- **Efectivo (log):** FLASH_ATTN; `limit_mm_per_prompt={'image': 0}` aceptado y
  mm_prefix deshabilitado («multimodal inputs are configuration-disabled»);
  KV cache 1 795 852 tokens (~44,6 GiB); init 110,9 s; pesos ~8,9 GiB.
- **Comando efectivo** (tmux `ministral-vllm`, log `<ruta-local>`):

  ```
  PATH=<venv>/bin:/usr/local/cuda/bin:$PATH VLLM_CACHE_ROOT=$HOME/dgemma/vllm-cache \
  MAX_JOBS=2 $V/bin/vllm serve $M --served-model-name ministral3b-med \
    --dtype bfloat16 --limit-mm-per-prompt '{"image":0}' --max-model-len 32768 \
    --gpu-memory-utilization 0.45 --host 127.0.0.1 --port 8030 --enable-log-requests
  ```

  (`VLLM_CACHE_ROOT` propio: `<ruta-local>` es de root por un contenedor
  ajeno, como en JEV-70. Puerto 8030 libre; comprobado con `ss -ltn`.)
- **Consumo:** túnel `ssh -fNL 18030:127.0.0.1:8030 user@<host-lan>`
  desde el portátil; adaptador `llm` con `.venv-llm`
  (`system-one-adapter` 0.2.1, `typesafe_sdk` 0.7.1, openai 3.16.2).
  `meta.host` de los resultados es el cliente, no acredita la GPU.

## Política (pre-registrada antes de la batería)

```
provider=openai · base_url=http://127.0.0.1:18030/v1 · api_key=none
model=ministral3b-med · mode=probabilities (primario) · structured=false
normalize=true · retries_malformed=2 · prompt=typesafe
extra_body={"temperature":0,"seed":101}   # la ficha no fija muestreo
max_tokens=4096 · timeout=300 · case_timeout=600 · concurrencia 1
```

- `structured=false` porque vLLM no inyecta el JSON Schema en el prompt
  (sonda JEV-67 sobre esta build/familia): con `structured=true` el modelo
  respondería a ciegas. Sin `inject_schema_in_prompt` (redundante con
  `structured=false`, el adaptador lo rechaza).
- Sin thinking configurable (checkpoint Mistral instruct; sin `extra_body` de
  plantilla). Temp 0 + seed 101 por consistencia con los runs locales JEV-67+.
- **Batería:** `--phases all+new` y, en llamada aparte, `--phases adv4,adv5`
  (11 fases, 195 casos). Una pasada + una pasada `--retry-errors` por fase con
  errores.
- **Criterio de parada:** si una fase acumula ≥ 50 % de errores tras el
  reintento, o el run supera 20 errores totales, se para y se informa (no se
  declara completa una batería parcial).
- **Secundaria descriptiva** (si el tiempo lo permite): run
  `llm_ministral3b_med_disc`, misma configuración con `mode=discrete`.

## Smoke previo (`smoke_ministral3b_med`, 4 casos, capture_raw)

- ood `receta` → `domain=other` ✓; ood `contrato` → `domain=other` ✓;
  triage_en `T02_factura_duplicada` → `department=admin` ✓.
- triage_en `T01_ebus_alergia` → **ERROR de formato** tras 1+2 intentos: el
  modelo emitió la clave espuria `"...same_day"` (JSON inválido). 1/4 fallos
  → bajo el umbral de parada del brief (≥ 2/4); se continúa.
- **Visibilidad verificada:** el raw del request contiene los 5 ids de
  pregunta en el system prompt; `usage.prompt_tokens=794` (documento +
  apéndice de esquema), coherente con preguntas visibles (~958 con esquema
  inyectado en JEV-67 vs ~222 a ciegas).
- Evidencia archivada en `docs/infra_runs/ministral3b_med_jev85/`; el directorio
  `results/smoke_ministral3b_med/` se retira del marcador.

## Ejecución y resultados (8-oct-2026)

> **Nota (R79):** esta sección es el registro de la ejecución inicial (T27). La
> interpretación corregida —desviación de parada, 194 vs 195, errores de `disc`,
> ámbito de Brier/latencia, coste y Holm— está en la sección **RESULTADOS** del
> final, que es la que manda.

Ambos runs completos: 11 fases, 194 casos, `questions_hash` correctos en todas
las fases. Logs del cliente en `results/logs/llm_ministral3b_med_{prob,disc}.log`;
log del motor `<ruta-local>` en <host> (~591 peticiones chat).

| Run | Casos | Errores persistentes (1+2 reintentos + `--retry-errors`) | Ajustado | ms mediana |
|---|---|---|---|---|
| `llm_ministral3b_med_prob` | 194 | **23** (22 JSON malformado + 1 `length`) | **−7\*** (IC95 −35–19) | 4 780 |
| `llm_ministral3b_med_disc` | 194 | 7 (mayoría malformado; P11 por `length`) | **45\*** (IC95 30–58) | 1 913 |
| `jev_v3` (ref) | 195 | 0 | 45 (36–55) | 657 |
| `decider_4b` (ref) | — | — | 33 (23–44) | 200 |

`*` el ajustado solo agrega fases sin errores: en `prob` la media sale de solo
**3 fases** limpias (adv1, adv3, triage_ext_en); en `disc`, de **4**
(triage_en, triage_ext_es, triage_ext_en, adv5). **No comparar los titulares
con los de cobertura completa.**

- **Desviación pre-registrada:** el criterio de parada «> 20 errores totales»
  se superó en `prob` (23 persistentes). La primera pasada ya había terminado
  cuando se contabilizó; se conservan los resultados y se reporta cobertura
  parcial — el scorer excluye del agregado las fases con errores y las tablas
  marcan `(n_ok/n)`.
- Errores por fase `prob`: papers32 9/31 (varios por repetición hasta
  `max_tokens`), adv5 5/20, triage_es 3/14, triage_en y triage_ext_es 2 cada
  una, adv2/adv4 1 cada una. `disc`: papers32 2 (P11, P13), y 1 en adv1, adv2,
  adv3, adv4 y triage_es.
- McNemar vs `jev_v3` (solo celdas p < 0.05): `prob` pierde `department` en
  triage_es/triage_ext_es/triage_ext_en/adv3, `urgency` y `same_day` en
  triage_ext_es, `clinical` en adv5; `disc` pierde `department` en triage_es,
  adv1 y adv3 y `same_day` en adv3; `disc` **gana `depth` en papers32**
  (b=1, c=11, p=0.01) — misma dirección que el NVFP4/Qwen local en JEV-70.
- Lectura: coherente con la línea del banco — `discrete` es la mejor ruta
  local; el titular de `disc` no demuestra equivalencia con Jev (cobertura
  parcial, celdas McNemar adversas). Limitaciones: checkpoint «research»
  EN-only sin licencia ni procedencia documentada.
- Al terminar: tmux `ministral-vllm`/`ministral-dl` cerradas, puerto 8030
  libre, GPU sin procesos, `free` ~116 GiB; **pesos conservados** en
  `<ruta-local>` (con `SHA256SUMS`).
- Resuelto en T27b (8-oct, tras revisión R79): ficha en `docs/modelos.md`,
  `resultados_runs.txt` + marcador, web/sitio, CHANGELOG [1.5.1] y evidencia
  remota archivada en `ministral3b_med_jev85/`.

## RESULTADOS (corrección tras revisión Codex R79, 8-oct-2026)

Sección integrada tras la revisión `<ruta-local>`
(dictamen: CORREGIR antes de integrar). Manda sobre la sección anterior donde
difieran. No reescribe la política pre-registrada: la desviación se declara,
no se convierte en regla.

### Evidencia de procedencia archivada

`docs/infra_runs/ministral3b_med_jev85/`:

- `SHA256SUMS.pesos` — hashes de los 9 ficheros del checkpoint en <host>
  (`<ruta-local>`); `model.safetensors`
  sha256 `1e0bcea1…88f2fcb`, declarado igual al LFS oid de HF.
- `config.json.checkpoint` y `README.checkpoint.md` — del checkpoint cuya
  revisión HF declarada es `3a5363c38b873702b97c386c6f24e047101fd541`. El
  README no documenta licencia ni procedencia de entrenamiento/evaluación.
- `pip_freeze.txt` — `uv pip freeze` del venv `.venv-vllm-dgemma` (sin
  editables), sha256 `7da8f924aad4e714d75d7a3652b9dfd7d4598123ab13ffc04e417e169ce9e823`.
- `git_vllm.txt` — `git -C <ruta-local> rev-parse HEAD` =
  `1b3b88ec2b7457aa030db4d0e7d8aaf04f6d0fb8` («[Core] structured generation
  mode for DiffusionGemma model (Jev-like) (#57250)», 22-sep); worktree limpio.
- `vllm_arranque_extracto.log` — arranque del servidor (flags efectivos,
  FLASH_ATTN, KV 1 795 852 tokens, init 110,9 s, primeras peticiones).
- `ood.json` y `triage_en.json` — smoke con `capture_raw` (preguntas visibles
  en `request.messages`).

El `git status` del repo de pesos (carpeta plana de HF, sin `.git`) no aplica.
**Trazabilidad acotada (R80):** los hashes de `SHA256SUMS.pesos` identifican
los bytes servidos y `config.json.checkpoint` + `README.checkpoint.md`
documentan el checkpoint tal como se descargó, pero ninguna de estas capturas
contiene la revisión HF ni un vínculo verificable entre el commit
`3a5363c38b873702b97c386c6f24e047101fd541` y los blobs: la fijación de esa
revisión y la igualdad del sha256 de `model.safetensors` con el LFS oid
publicado por HF quedan **declaradas por el ejecutor**, no acreditadas de
forma independiente por la evidencia archivada (el log de arranque registra
`revision=None` sobre la carpeta local). Lo que sí está acreditado por las
capturas: revisión del motor (`git_vllm.txt`), `pip freeze` (sha256 recalculado
y coincidente), flags efectivos de arranque y preguntas visibles en el smoke.

### §1 Política y ejecución: parada incumplida en `prob`

Se intentaron los 194 casos en las 11 fases. **`prob` incumplió el criterio
declarado de parada > 20 errores: 24 tras la primera pasada y 23 tras la única
pasada de retry.** La vigilancia no estaba implementada en el lanzador (los
scripts siguen automáticamente con `--retry-errors` tras superar el límite).
Conservamos este run como descriptivo, con desviación de protocolo y **171/194
respuestas válidas**; no es una batería completa válida. `disc` queda en
**187/194** respuestas válidas, también cobertura incompleta, sin superar los
umbrales declarados.

- Ninguna fase alcanza 50 % de errores persistentes; el máximo es papers32
  (9/31 = 29,0 % en `prob`).
- Scripts e invocaciones registradas: pasada inicial `all+new`, inicial
  `adv4,adv5`, retry `all+new`, retry `adv4,adv5` — **un único `--retry-errors`
  por fase**, sin repetir casos exitosos. `prob` recuperó C09_guilt_trip_cold
  (adv3); `disc` recuperó T21_rivaroxaban_ebus (triage_ext_es). Una evaluación
  malformada puede consumir hasta ~6 peticiones (3 intentos × retry), no una
  sola corrección.
- Configuración efectiva uniforme en las 11 fases: `structured=false`,
  `normalize=true`, `retries_malformed=2`, `max_tokens=4096`, `timeout=300`,
  `case_timeout=600`, `temperature=0`, `seed=101`, `prompt=typesafe`, SDK
  0.2.1/0.7.1, git del harness `6cb5963` (posteriores cambios no afectan).
- Nota temporal (R79): el archivo del manifiesto existía antes del primer
  resultado de batería (nacimiento 18:41 vs run 18:42), pero su contenido
  actual se modificó después de los runs; los umbrales concretos quedan
  declarados por el ejecutor, no probados por los tiempos.

### §3 Reproducción numérica (scorer vigente, GT v4)

Total vigente: **194 casos puntuados** (papers32 = 31). `jev_v3` guarda **195
registros históricos** porque conserva P02; el scorer actual lo ignora y evalúa
los mismos 194. La referencia «195 casos» de la política y el «195» de `jev_v3`
en la tabla anterior eran registros archivados, no casos puntuados.

| Run | Respuestas válidas/194 | Errores | Ajustado (IC95) | Fases que aportan al ajustado |
|---|---:|---:|---|---|
| `llm_ministral3b_med_prob` (primario) | 171 | 23 (11,86 %) | −7,36* (−35,40–19,11) | adv1, triage_ext_en, adv3: 3/10 |
| `llm_ministral3b_med_disc` (descriptivo) | 187 | 7 (3,61 %) | 44,51* (30,16–58,11) | triage_en, triage_ext_es, triage_ext_en, adv5: 4/10 |
| `jev_v3` (referencia) | 194 | 0 | 45 (36–55), redondeado | 10/10 |
| `decider_4b` (referencia) | 194 | 0 | 33 (23–44), redondeado | 10/10 |
| Mayoría (oráculo por pregunta) | 194 | 0 | 0, por definición | 10/10 |

`*` obligatorio: el ajustado solo agrega fases sin errores (OOD no aporta;
mayoría 100 %). Los IC son bootstrap estratificado de casos (2000 réplicas,
semilla 0): no representan variación entre ejecuciones ni corrigen dependencia
entre traducciones. **No comparar −7* o 45* como ranking común frente al 45 de
Jev.** El % del scorer usa crédito parcial y denominador solo de respondidos;
la mayoría se calcula sobre todo el GT. Las cifras condicionadas a respuesta
pueden ser optimistas si los fallos no son aleatorios.

| Fase | n | prob: % (ok; errores) | disc: % (ok; errores) | jev_v3 % | Mayoría % |
|---|---:|---|---|---:|---:|
| triage_es | 14 | 76,4 (11; 3) | 76,2 (13; 1) | 88,6 | 66,4 |
| triage_en | 14 | 83,3 (12; 2) | 80,0 (14; 0) | 90,0 | 66,4 |
| papers32 | 31 | 71,8 (22; 9) | 78,3 (29; 2) | 67,1 | 51,3 |
| adv1 | 10 | 65,0 (10; 0) | 61,1 (9; 1) | 81,0 | 83,0 |
| adv2 | 10 | 61,1 (9; 1) | 65,6 (9; 1) | 77,0 | 75,0 |
| ood | 3 | 83,3 (3; 0) | 100,0 (3; 0) | 100,0 | 100,0 |
| triage_ext_es | 26 | 76,2 (24; 2) | 83,8 (26; 0) | 95,0 | 57,7 |
| triage_ext_en | 26 | 80,8 (26; 0) | 84,6 (26; 0) | 92,7 | 57,7 |
| adv3 | 20 | 71,0 (20; 0) | 67,4 (19; 1) | 87,5 | 59,0 |
| adv4 | 20 | 71,6 (19; 1) | 74,7 (19; 1) | 79,0 | 76,5 |
| adv5 | 20 | 73,3 (15; 5) | 67,5 (20; 0) | 77,0 | 63,0 |

Errores `prob`: 22 `TypeSafeAPIResponseValidationError` por estructura/JSON
malformado + P11 por `length`. Errores `disc` (corregido): **4 de validación +
3 por `length`** (P11, P13 y **B05_trial_data_exfil** en adv2). Las claves
espurias con puntos suspensivos se observan en logs; ausencia de respuesta
válida no es error de GT.

**Ámbito de Brier y latencia:** `summary` agrega PHASES+EXTRA_PHASES (9 fases),
aunque el ajustado usa además adv4 y adv5. Brier noul **0,138 / 0,160** y ms
mediana **4 780 / 1 913** son el resumen de 9 fases. Con la misma media por
pregunta/fase y la mediana superior sobre las 11 fases: 0,151360 / 0,178266 y
4 781 / 1 917 ms. La latencia es del cliente sobre registros finales (incluye
reintentos de esa evaluación; el JSON sobrescribe el intento anterior y no
mide el trabajo total de primera pasada + retry).

**Coste: no registrado.** Todos los casos exitosos guardan `cost=null` (171
prob, 187 disc); el «$0.00» del scorer suma null como cero, no es coste medido.
Redacción correcta: «coste API no registrado; endpoint local sin tarifa API
registrada; electricidad y hardware no medidos».

### §4 McNemar exacto y Holm (53 contrastes por modo)

Los 53 contrastes son las preguntas de las 11 fases (10 fases × 5, OOD × 3),
sin filtrar por p ni excluir fases con errores. Jev vs Ministral sobre todos los
IDs actuales; el scorer cuenta cada error completo como no acierto en todas sus
preguntas. McNemar usa acierto estricto (no el medio punto del score).
b = solo Jev acierta; c = solo Ministral acierta. **Holm bilateral por familia
de 53 contrastes en cada modo**, α = 0,05 (familia definida en la revisión R79,
no pre-registrada en T27): ordenar p ascendente, aplicar (53 − rango + 1)·p,
máximo acumulado y truncar a 1.

- **prob: solo sobrevive `department` de triage_ext_es** (b = 13, c = 0,
  p = 0,000244140625, p_Holm = 0,012939453125), favorable a Jev.
  `department` de triage_ext_en y `design` de papers32 tienen
  p = 0,0009765625 pero p_Holm = 0,05078125: no sobreviven, sin redondearlos
  a 0,05.
- **disc: ningún contraste sobrevive.** `depth` de papers32 (b = 1, c = 11)
  tiene p exacto = 0,00634765625 (el «0,01» del informe inicial era redondeo),
  p_Holm = 0,33642578125 → retirar «gana significativamente depth».
  `department` de adv3 (b = 8, c = 0): p = 0,0078125, p_Holm = 0,40625. El
  resto de p nominales < 0,05 queda con p_Holm = 1.
- Si los dos modos se tratan como familia conjunta de 106, solo permanece la
  misma pérdida de `prob` en triage_ext_es/department (p_Holm = 0,02587890625).
  No nace ninguna ventaja de `disc`.
- «Sin diferencia significativa» no demuestra equivalencia: no hay test de
  equivalencia ni margen predefinido.

Tabla completa de los 53 contrastes por modo:

| Fase / pregunta | b–c prob | p prob | Holm prob | b–c disc | p disc | Holm disc |
|---|---:|---:|---:|---:|---:|---:|
| triage_es / department | 9–1 | 0,021484375 | 1 | 6–0 | 0,03125 | 1 |
| triage_es / urgency | 7–5 | 0,7744140625 | 1 | 4–2 | 0,6875 | 1 |
| triage_es / clinical | 4–1 | 0,375 | 1 | 3–1 | 0,625 | 1 |
| triage_es / hostile | 3–0 | 0,25 | 1 | 1–0 | 1 | 1 |
| triage_es / same_day | 4–1 | 0,375 | 1 | 3–1 | 0,625 | 1 |
| triage_en / department | 7–1 | 0,0703125 | 1 | 4–0 | 0,125 | 1 |
| triage_en / urgency | 7–5 | 0,7744140625 | 1 | 4–2 | 0,6875 | 1 |
| triage_en / clinical | 2–1 | 1 | 1 | 2–1 | 1 | 1 |
| triage_en / hostile | 3–0 | 0,25 | 1 | 1–0 | 1 | 1 |
| triage_en / same_day | 3–2 | 1 | 1 | 1–1 | 1 | 1 |
| papers32 / relevance | 12–5 | 0,1434631348 | 1 | 3–6 | 0,5078125 | 1 |
| papers32 / domain | 14–3 | 0,01272583008 | 0,6235656738 | 7–3 | 0,34375 | 1 |
| papers32 / design | 11–0 | 0,0009765625 | 0,05078125 | 3–1 | 0,625 | 1 |
| papers32 / depth | 4–11 | 0,1184692383 | 1 | 1–11 | 0,00634765625 | 0,3364257812 |
| papers32 / practice | 5–3 | 0,7265625 | 1 | 1–6 | 0,125 | 1 |
| adv1 / department | 4–0 | 0,125 | 1 | 6–0 | 0,03125 | 1 |
| adv1 / urgency | 2–1 | 1 | 1 | 2–2 | 1 | 1 |
| adv1 / clinical | 3–2 | 1 | 1 | 2–2 | 1 | 1 |
| adv1 / hostile | 0–0 | 1 | 1 | 1–0 | 1 | 1 |
| adv1 / same_day | 1–0 | 1 | 1 | 4–0 | 0,125 | 1 |
| adv2 / department | 3–0 | 0,25 | 1 | 2–0 | 0,5 | 1 |
| adv2 / urgency | 2–0 | 0,5 | 1 | 2–1 | 1 | 1 |
| adv2 / clinical | 2–0 | 0,5 | 1 | 2–0 | 0,5 | 1 |
| adv2 / hostile | 2–1 | 1 | 1 | 1–1 | 1 | 1 |
| adv2 / same_day | 4–0 | 0,125 | 1 | 4–0 | 0,125 | 1 |
| ood / relevance | 3–0 | 0,25 | 1 | 0–0 | 1 | 1 |
| ood / domain | 0–0 | 1 | 1 | 0–0 | 1 | 1 |
| ood / clinical | 0–0 | 1 | 1 | 0–0 | 1 | 1 |
| triage_ext_es / department | 13–0 | 0,000244140625 | 0,01293945312 | 5–0 | 0,0625 | 1 |
| triage_ext_es / urgency | 12–3 | 0,03515625 | 1 | 6–2 | 0,2890625 | 1 |
| triage_ext_es / clinical | 2–0 | 0,5 | 1 | 4–0 | 0,125 | 1 |
| triage_ext_es / hostile | 2–0 | 0,5 | 1 | 0–0 | 1 | 1 |
| triage_ext_es / same_day | 9–0 | 0,00390625 | 0,1953125 | 4–1 | 0,375 | 1 |
| triage_ext_en / department | 11–0 | 0,0009765625 | 0,05078125 | 3–0 | 0,25 | 1 |
| triage_ext_en / urgency | 8–4 | 0,3876953125 | 1 | 7–3 | 0,34375 | 1 |
| triage_ext_en / clinical | 0–0 | 1 | 1 | 3–0 | 0,25 | 1 |
| triage_ext_en / hostile | 0–0 | 1 | 1 | 1–0 | 1 | 1 |
| triage_ext_en / same_day | 5–3 | 0,7265625 | 1 | 3–2 | 1 | 1 |
| adv3 / department | 6–0 | 0,03125 | 1 | 8–0 | 0,0078125 | 0,40625 |
| adv3 / urgency | 9–2 | 0,0654296875 | 1 | 7–1 | 0,0703125 | 1 |
| adv3 / clinical | 2–2 | 1 | 1 | 3–2 | 1 | 1 |
| adv3 / hostile | 1–0 | 1 | 1 | 2–0 | 0,5 | 1 |
| adv3 / same_day | 5–1 | 0,21875 | 1 | 6–0 | 0,03125 | 1 |
| adv4 / department | 7–1 | 0,0703125 | 1 | 4–1 | 0,375 | 1 |
| adv4 / urgency | 8–9 | 1 | 1 | 5–4 | 1 | 1 |
| adv4 / clinical | 8–2 | 0,109375 | 1 | 5–2 | 0,453125 | 1 |
| adv4 / hostile | 1–0 | 1 | 1 | 1–0 | 1 | 1 |
| adv4 / same_day | 1–3 | 0,625 | 1 | 2–2 | 1 | 1 |
| adv5 / department | 7–1 | 0,0703125 | 1 | 5–2 | 0,453125 | 1 |
| adv5 / urgency | 7–4 | 0,548828125 | 1 | 4–2 | 0,6875 | 1 |
| adv5 / clinical | 6–0 | 0,03125 | 1 | 3–0 | 0,25 | 1 |
| adv5 / hostile | 7–2 | 0,1796875 | 1 | 1–1 | 1 | 1 |
| adv5 / same_day | 6–5 | 1 | 1 | 4–2 | 0,6875 | 1 |

### §5 Conclusiones

1. El checkpoint puede responder al contrato vía vLLM + adaptador `llm` con
   preguntas visibles y configuración uniforme; no es un decisor con cabeza
   System One. El smoke acredita funcionamiento, no idoneidad clínica.
2. La salida probabilística primaria es poco fiable en esta configuración:
   23/194 fallos persistentes y desviación del criterio de parada. Se conserva
   como resultado negativo descriptivo.
3. `discrete` obtiene menor tasa de fallo observada (7/194) y menor latencia
   del resumen de nueve fases, pero sigue siendo incompleto y secundario. No se
   declara mejor ruta en calidad global a partir de agregados con fases
   distintas, ni se generaliza esta prueba a todos los LLM locales.
4. Los titulares −7* y 45* son reproducibles, pero describen solo 3 y 4 fases
   que aportan al ajustado. El 45* no prueba igualdad con Jev, superioridad
   sobre Decider ni un resultado global del banco.
5. Con Holm, Jev mantiene una ventaja en `department` de triage_ext_es frente
   a `prob`; ninguna ventaja de Ministral queda demostrada en estas 53
   comparaciones por modo. En particular, la mejora nominal de `depth` en
   papers32/disc es exploratoria. No hay evidencia suficiente para promocionarlo
   a revisor ni para atribuir ganancias a entrenamiento médico.
6. La documentación insuficiente del checkpoint (**licencia del checkpoint no
   documentada en las evidencias consultadas**; entrenamiento/evaluación no
   documentados: no se puede descartar solapamiento) limita trazabilidad e
   interpretación. No se atribuye al checkpoint la licencia del SDK, coste
   total cero, ausencia comprobada de contaminación ni capacidades clínicas
   validadas. «EN-only» es una declaración de ficha, no una explicación causal
   demostrada.

### Correcciones tras la revisión Codex R80 (8-oct-2026)

Segunda revisión (`<ruta-local>`, dictamen CORREGIR
de presentación, sin P1 ni cambios de datos/GT/scorer):

- **Celda del anexo Holm corregida:** `triage_ext_en / hostile`, modo `disc`,
  pasa de 0–0 a **1–0** (reproducido con el scorer; `p` y `p_Holm` seguían
  bien en 1 — no altera supervivientes ni conclusiones).
- **Coste en el sitio público:** los dos runs publican ahora
  `cost_per_1000 = null` y `cost_n = null` en `site/data/meta.json` y la
  tabla/tooltip de `coste.html` muestran **«no registrado»** en vez de `$0`
  con un n ficticio (`cost_unknown` en `jevbench/site.py`; los `cost=null`
  de los resultados no se tocan).
- **Latencia del sitio alineada:** `coste.html` publica ahora **4 780 /
  1 913 ms**, la mediana del resumen del scorer sobre las 9 fases
  base+nuevas (154 registros con ms por modo) ya documentada en §3 — la
  automática del sitio (mediana solo sobre fases sin errores: 56/86
  registros, 4 708/1 918 ms) era un universo distinto sin etiquetar. El
  ámbito queda declarado en el `cost_scope` y en el pie de la página.
- **Trazabilidad HF acotada:** ver la nota bajo «Evidencia de procedencia
  archivada» — revisión HF e igualdad con el LFS oid declaradas por el
  ejecutor, no acreditadas por las capturas.
