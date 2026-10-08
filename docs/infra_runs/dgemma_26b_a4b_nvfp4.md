# JEV-70 — DiffusionGemma-26B-A4B (NVFP4) vía lecturas estructuradas de vLLM

Manifiesto de ejecución y **congelado de F0** (pre-registro JEV-70 v2 + revisiones 3–5 en los
comentarios de la issue: <<tracker> Este fichero se
commitea **antes** de F1; ninguna inferencia sobre casos del banco se ha hecho salvo los smokes
de §6.6 (2 casos × 3 fases por configuración). Los smokes se archivan en
`dgemma_26b_a4b_nvfp4/smokes/smokes_f0.tar.gz` y se retiran de `results/` tras este commit
(no entran en el marcador).

Orquestación: implementación delegada (Devin), revisión independiente (Codex, rondas R1–R5),
consolidación, operación de los hosts y commits (Claude). Encargos e informes en `<ruta-local>`
(no versionados); los hallazgos aceptados se resumen al final.

## 1. Hosts y disponibilidad (6-oct-2026)

| Host | Papel | Estado al empezar F0 (08:02) |
|---|---|---|
| <host> `dgx-spark-b` | P → S1 → R (+ condicional revisor/alerta) | sin procesos GPU, solo `dashboard-sparkdash` (sin GPU), `free` disponible 116 GiB, 8010/8011 libres |
| <host> `dgx-spark-a` | X → Rot1, luego sesión nueva L″ | ídem; SGLang del usuario **no** residente; 8010/8011 libres |

aarch64 + NVIDIA GB10 (sm_121), memoria unificada, driver 580, CUDA 13.0. Reserva anotada en la issue.

## 2. Build (idéntica en ambos hosts)

| Elemento | Valor |
|---|---|
| vLLM | `0.29.1rc1.dev551+g1b3b88ec2`, commit `1b3b88ec2b7457aa030db4d0e7d8aaf04f6d0fb8`, `VLLM_USE_PRECOMPILED=1`, editable desde `<ruta-local>` |
| venv | `<ruta-local>` (Python 3.12.14 de uv) |
| torch / CUDA | 2.13.0+cu130 / 13.0 |
| transformers / tokenizers | 5.18.0 / 0.23.2 |
| flashinfer | 0.6.18.post1 |
| nvidia-modelopt | no instalado (vLLM usa su cargador modelopt propio) |
| `pip freeze` sha256 (sin líneas editables) | `7da8f924aad4e714d75d7a3652b9dfd7d4598123ab13ffc04e417e169ce9e823` (<host> = <host>) |
| `structured_server.py` sha256 | `7cd9aa0081090c064eaac28db0f54f812749eeb3ae787d7f7653d2e35d8a938f` (<host> = <host>, = el de GitHub en ese commit) |
| Pesos | `nvidia/diffusiongemma-26B-A4B-it-NVFP4` @ `ec4ff3df205028f4e81c954c2227f9312b3ec2ea`, copia de `<ruta-local>` a `<ruta-local>`, `sha256sum -c SHA256SUMS` 14/14 en ambos |
| Efectivo (log del motor) | backend de atención `TRITON_ATTN`; MoE NVFP4 `FLASHINFER_CUTLASS`; KV cache fp8_e4m3 (escala 1.0, el checkpoint no trae escala q); carga 18.16 GiB; KV disponible ~29–31 GiB (647 k–694 k tokens) |
| Compilación | primer arranque con JIT completo: `Initial profiling/warmup run took 1306 s` (<host>); siguientes desde caché (34 s <host>, 105 s <host>) |

## 3. Comandos efectivos

```bash
# en cada Spark (scripts/serve_dgemma.sh: PATH con el venv, VLLM_LOGGING_LEVEL=DEBUG, MAX_JOBS=2,
# gpu_memory_utilization 0.45, TRITON_ATTN, --enable-log-requests sin --max-log-len)
scripts/serve_dgemma.sh 64 16384                                   # <host>
VLLM_CACHE_ROOT=$HOME/dgemma/vllm-cache scripts/serve_dgemma.sh 64 16384   # <host>
# portátil
ssh -fNL 18010:127.0.0.1:8010 -L 18011:127.0.0.1:8011 user@<host-lan>
ssh -fNL 18020:127.0.0.1:8010 -L 18021:127.0.0.1:8011 user@<host-lan>
```

Desviaciones de entorno (revisión 4), todas antes de cualquier caso del banco:
1. 1.er arranque (08:14) muerto en ambos hosts: `FileNotFoundError: 'ninja'` en el JIT NVFP4 → `PATH`
   con el `bin` del venv. Log `<ruta-local>`.
2. <host>: `<ruta-local>` y `modelinfos` son de root (contenedor ajeno,
   20-sep) → `PermissionError`; se usa `VLLM_CACHE_ROOT` propio sin tocar lo ajeno.
3. `VLLM_LOGGING_LEVEL=DEBUG`: en esta build el prompt solo se registra en DEBUG
   (`request_logger.py`); imprescindible para §6.4. Aplica a todas las celdas.

Sesiones de servidor (identificador que se pasa a `jevbench.dgemma_f1 --session`):
- `s81-20261006-0848` — <host>, motor arrancado 08:45:17, listo 08:48.
- `s80-20261006-0849` — <host>, motor arrancado 08:45:25, listo 08:49.
- L″: sesión nueva de <host> con `--reasoning-parser gemma4`, id `s80rp-<fecha-hora>` (se anota al arrancar).

## 4. Preflight §6.2–6.3 (`jevbench/dgemma_preflight.py`, en <host>, tokenizer del checkpoint)

Ficheros: `docs/infra_runs/dgemma_26b_a4b_nvfp4/preflight.json` (sha256 `65a8f4a0…`) y
`preflight_rot1.json` (sha256 `f8a999ef…`).

- **CANVAS = 64** (regla: menor de {64, 128} con 1 etapa y 1 grupo en las tres familias).
- **MAXLEN = 16 384** (máximo P11: prompt 6 148 + canvas 64 = 6 212 tokens; siguientes, totales con canvas: P13 3 851, P26 3 632, P20 3 573, P12 2 979).
- `format` en `extra` no lo consume el servidor (no está en `JEV_EXTENSIONS`); lo deriva: `lines` con ≤ 10 preguntas, que es el caso de las tres familias.

| Familia (`questions_hash`) | Fases | Plantilla | Ancho | sha256 sistema (base) | sha256 etiquetas | sha256 sistema (rot1) |
|---|---|---|---|---|---|---|
| `9a81e9763d94` triaje/adv | triage_es/en, adv1–5, triage_ext_es/en | 28 | 32 | `18887777f411…` | `1497aa03e722…` | `82f9db2f1757…` |
| `74026502c3ac` papers32 | papers32 | 25 | 32 | `471d2d490df4…` | `f850e989758f…` | `7a1a835c7d68…` |
| `93ea3deb7eab` ood | ood | 17 | 32 | `c488a25cfc3b…` | `2984cc9b0947…` | `95eb31032ff9…` |

## 5. Datos congelados

Harness: base `fa129d7` + el commit que contiene este manifiesto. Canario
`docs/experimentos/dgemma_canary.json` sha256 `97ba4a32fafefd6db9431fca263a8eaf2c3a140729bb3a384904dfb95a98927e`;
tokens esperados del canario (tokenizer fijado) `docs/infra_runs/dgemma_26b_a4b_nvfp4/canary_expected_tokens.json`
sha256 `b9d0c71f…`.

| Fichero | sha256[:16] |
|---|---|
| data/bench_cases.json | e5622360d7f840a9 |
| data/papers32.json | a7abe616b8a6954b |
| data/paper_gt32.json | 36d4d10070a8b39b |
| data/adversarial_cases.json | 05ab30aed4a863e2 |
| data/adversarial2_cases.json | 76fdf2824a07d0ea |
| data/adversarial3_cases.json | d400136812d7ecb4 |
| data/adversarial4_cases.json | 0bb4a5ccf3a41155 |
| data/adversarial5_cases.json | 6895fa05dbf5ccb2 |
| data/triage_ext_cases.json | ecf5bed8589bd8b3 |

`questions_hash` por fase: triage_es/en, adv1–5, triage_ext_es/en `9a81e9763d94`; papers32 `74026502c3ac`; ood `93ea3deb7eab` (195 casos).

## 6. Resultados de F0

- **§6.1** petición sintética (documentos del canario) correcta en ambos hosts; ~0.3 s en caliente.
- **§6.5 canario** `canary_dgemma_26b_a4b_nvfp4` (<host>): C+b 5/5, C+c 5/5 → **sigue los criterios**;
  C0 → `opcion_b` 5/5. Réplica de <host> (`canary_dgemma_26b_a4b_nvfp4_x80`, evidencia de puerta):
  mismas decisiones; máx |Δp| entre hosts 0.16.
- **§6.6 smoke** (<host> P; <host> X y rot1; 2 casos de ood, triage_es y papers32): receta → `other`,
  factura → `admin`, 0 errores, 1 etapa/1 grupo, `prompt_tokens` del motor = preflight + 1.
- Observaciones descriptivas (no cambian nada): el disparador de `samples="auto"` (entropía sobre el
  top-20 devuelto) extiende a 4 lecturas en la mayoría de casos del smoke y del canario, no en todos;
  en <host> un calentamiento C0 (D3) eligió `opcion_a` y la misma petición en el canario `opcion_b`
  (no determinismo intra-sesión: suelo para R.a/X.a).
- **Celdas L y L′ no ejecutables** (revisiones 4–5): L por HTTP 400 (el motor de difusión no admite
  `temperature`/`seed`); L′ (sin `extra_body`) por salida `thought\n{…}` — prefijo del canal de
  pensamiento de Gemma que vLLM deja al quitar los tokens especiales; el JSON y las respuestas
  debajo son correctos. Se pre-registra L″ con `--reasoning-parser gemma4` en sesión aparte.

### §6.4 Puerta de montaje — APROBADA en ambos hosts

`jevbench/dgemma_gate.py` con el servidor congelado (`--server`, sha256 comprobado), log DEBUG del
motor acotado por líneas a la ejecución revisada, preflight de su orden (base o rot1) y, en los
canarios, tokens independientes calculados con el tokenizer fijado. Atribuye cada caso a sus
peticiones del log (state + sistema exactos) y exige: (a) sistema congelado en el prompt
registrado, (b) `prompt_tokens` del motor = referencia ± 2 (no el respaldo del interposer),
(c) 1 etapa, 1 grupo, sin `skipped` y ancho de cada petición = preflight, (d) request
reconstruido = familia, (e) ≥ 1 caso y cobertura de familias.

| Run | Log (sha256 del completo en `log_windows/full_logs.sha256`) | Líneas | Preflight | Resultado |
|---|---|---|---|---|
| canary_dgemma_26b_a4b_nvfp4 | <host> | 47782–48049 | base + `canary_expected_tokens.json` | **15/15**, a–e OK |
| canary_dgemma_26b_a4b_nvfp4_x80 | <host> | 48165–48460 | base + `canary_expected_tokens.json` | **15/15**, a–e OK |
| smoke_dgemma (P) | <host> | 48060–48147 | base, 3 familias | **6/6**, a–e OK |
| smoke_dgemma_x80 (X) | <host> | 48469–48528 | base, 3 familias | **6/6**, a–e OK |
| smoke_dgemma_rot1 (Rot1) | <host> | 48533–48607 | rot1, 3 familias | **6/6**, a–e OK |

Líneas **físicas** (numeración LF de `wc -l` / `sed -n`; la puerta parte solo por `\n` desde la corrección de R6). Evidencia: `gate/*.json` y los extractos `log_windows/vllm81_47782-48147.log.gz` y `vllm80_48165-48607.log.gz` (`sed -n A,Bp` del log completo, sin editar); la puerta se reproduce desde el extracto anteponiendo A−1 líneas vacías (comprobado: los cinco pasan). En el
canario el motor cuenta 1 token más que el tokenizer (dentro de ±2); ancho 16 (plantilla de 1 pregunta).
Reproducir, p. ej.: `python3 -m jevbench.dgemma_gate --preflight <preflight.json> --engine-log
<vllm.log> --results results/smoke_dgemma --server structured_server.py --log-from 48060 --log-to 48147
--require-families all`.

**En F1** la puerta se repite sobre **cada batería completa**, con el log acotado por las líneas
anotadas antes y después de la celda (`wc -l <ruta-local>`), y tras cualquier reinicio del
servidor. Una batería cuya puerta no pase es «no evaluable por montaje».

## 7. F1 congelado

Runner: `python3 -m jevbench.dgemma_f1 <celda> --session <id>` (`--dry-run` imprime los comandos
exactos). Tabla congelada en `jevbench/dgemma_f1.CELLS`; cada caso es una invocación
`python3 -m jevbench.run <adaptador> --run <run> --phases <fase> --opt … --limit 1`, con las reglas
evaluadas antes de cada caso: 3 errores en la fase o 10 en el run → parar (pendientes sin ejecutar);
tras un timeout, `/health` de motor e interposer durante 2 min (si no responden → parar); tope de la
celda acumulado entre invocaciones (`results/logs/<run>.f1_state.json`); lock exclusivo por run;
`--resume` solo con la misma sesión, opts, adaptador y `questions_hash`. Tras la primera pasada
completa: `--retry-pass` (copia única a `results/<run>_pass1/`, una invocación `--retry-errors` por
fase con errores, sin relanzar).

| Host / sesión | Orden (concurrencia 1) | Celda → run | Fases | Tope |
|---|---|---|---|---|
| <host> `s81-20261006-0848` | calentamiento → **P** | P → `dgemma_26b_a4b_nvfp4` | all+new; adv4, adv5 | 60 min |
| | calentamiento → **S1** | S1 → `dgemma_26b_a4b_nvfp4_s1` (`samples: 1`) | ídem | 45 min |
| | calentamiento → **R** | R → `dgemma_26b_a4b_nvfp4_rep` | papers32, adv3 | 20 min |
| | si ajustado(P) ≥ 33 | revisor `decider_4b_dgemmarev_*`; alerta `dgemma_26b_a4b_nvfp4_alert_raw` | 11 / adv3–5 | 60 + 20 min |
| <host> `s80-20261006-0849` | calentamiento → **X** | X → `dgemma_26b_a4b_nvfp4_x80` | papers32, adv3 | 20 min |
| | calentamiento → **Rot1** | Rot1 → `dgemma_26b_a4b_nvfp4_rot1` (`rotate_choice=1`) | 11 | 60 min |
| <host> `s80rp-<fecha-hora>` (sesión nueva) | reinicio con `--reasoning-parser gemma4` → §6.1 + smoke R3.2 → **L″-prob** → **L″-rep** → **L″-disc** | Lp3 → `llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp`; Lr3 → `…_prob_rp_rep`; Ld3 → `…_disc_rp` | 11; papers32+adv3; 11 | 90; 30; 60 min |

Calentamiento: `python3 -m jevbench.dgemma_canary warmup --tag <celda> --opt url=<interposer> --opt
model=dgemma --opt timeout=120 --opt extra=<extra de P>` (3 peticiones C0 del canario, anotadas en
`results/logs/dgemma_warmup.jsonl`). Las celdas L″ no tienen calentamiento por interposer (el adaptador
llama al motor); su §6.1 hace de calentamiento.

Opts congeladas (systemone_http): `url=http://127.0.0.1:18011` (<host>) o `:18021` (<host>),
`path=/v1/systemone model=dgemma timeout=120 capture_raw=true`,
`extra={"seed":42,"samples":"auto","auto_threshold":0.1,"auto_max":4,"steps":1,"think":0,"format":"lines"}`
(S1: `"samples":1`; Rot1: + `rotate_choice=1`). L″ (`.venv-llm`, system-one-adapter 0.2.1):
`provider=openai base_url=http://127.0.0.1:18020/v1 api_key=none model=dgemma structured=false
mode=probabilities|discrete max_tokens=2048 timeout=120 case_timeout=300 capture_raw=true`, sin `extra_body`.

Arranque de la sesión L″ (en <host>, tras terminar X y Rot1 y parar solo `dgemma-srv`/`dgemma-vllm`):
`scripts/serve_dgemma.sh` con `--reasoning-parser gemma4` añadido a `vllm serve` (variable
`EXTRA_SERVE_ARGS` del script; el resto idéntico) y `VLLM_CACHE_ROOT=$HOME/dgemma/vllm-cache`.

Condicional P ≥ 33 (revisión 3, R3.4): `python3 -m jevbench.cascade --d1 decider_4b --adapter
systemone_http --opt <opts de P> --prefix decider_4b_dgemmarev --control ""` en las 11 fases (criterio
JEV-32) y `scripts/alert_onepass.py systemone_http dgemma_26b_a4b_nvfp4 <opts de P>` (criterio de
`docs/experimentos/alerta_manipulacion.md`, que se anota allí antes de ejecutar).

Informe: `python3 -m jevbench.dgemma_report --json docs/infra_runs/dgemma_26b_a4b_nvfp4/report.json`
(clasificación §8.2 + R3/R4/R5; nada se ajusta a mano).

## 8. Revisión independiente del código (Codex, R1–R5)

| Ronda | Alcance | Veredicto | Hallazgos principales (todos aceptados y corregidos por Devin) |
|---|---|---|---|
| R1 | adaptador, preflight, canario, informe, script | CORREGIR | informe roto con raw en lista (`llm`); R.b/X.b confirmadas con 0 pares; ajustado parcial publicado; auditoría numérica abortaba; residuo de `rotate_choice` compartido entre preguntas; diag truncado por caracteres |
| R2 | puerta y runner (T1) | CORREGIR | puerta abierta con 0 casos; Rot1 certificable contra el preflight base; búsqueda global sin atribución; plegado de whitespace; paradas solo al final de fase; retry sin exigir 1.ª pasada completa; sin sesión/lock; tope reiniciable; rc≠0 ignorado |
| R3 | C1 | CORREGIR | S1.b/recomendación con ajustado ausente; test de rotación sin orden |
| R4 | C2 + puerta sobre F0 real | CORREGIR | ventana de log sin fin; retry repetible ante timeout; cota de carrera inexistente → **primera pasada caso a caso**; hijo vivo tras excepción |
| R5 | C3, C4, puertas reales, manifiesto, suite | CORREGIR → cerrado | manifiesto incompleto (este fichero); estado del retry etiquetaba programados como intentados; finitud explícita del ajustado (C5) |
| R6 | C5, manifiesto, script | CORREGIR | la puerta contaba los `\r` de las barras de progreso como líneas: ventanas no transferibles a `wc -l` ni a los extractos (C6: numeración LF; ventanas y extractos regenerados) |
| R7 | C6 + reproducción desde extractos | **APTO** | 10/10 puertas (originales y extractos) abiertas; suite 219 OK (58 omitidos) |

Suite completa en la revisión R7: 219 tests OK (58 omitidos por entorno). Cambio colateral: el
residuo de `jevbench.rotation.rotate_choice` es por pregunta; con `shift=1` (único usado, JEV-67) el
resultado es idéntico (test con orden y `perm_sha256` en las 11 fases).

## 9. Resultados de F1 (6-oct, 09:58–10:25)

Todas las celdas en el orden congelado; concurrencia 1; cada celda con su ventana de log
(`gate_f1/windows_*.tsv`; sha256 de los logs completos en `gate_f1/logs.sha256`). Clasificación
completa: `dgemma_26b_a4b_nvfp4/report.txt` y `report.json` (`python3 -m jevbench.dgemma_report`).

### 9.1 Ejecución, puerta y cobertura

| Celda | Run | Host / sesión | Casos | Errores 1.ª pasada | Puerta §6.4 (líneas) |
|---|---|---|---|---|---|
| P | `dgemma_26b_a4b_nvfp4` | <host> `s81-…-0848` | 195/195 | 0 | **195/195** (48620–52195) |
| S1 | `dgemma_26b_a4b_nvfp4_s1` | <host> | 195/195 | 0 | **195/195** (52256–53465) |
| R | `dgemma_26b_a4b_nvfp4_rep` | <host> | 52/52 | 0 | **52/52** (53526–54493) |
| X | `dgemma_26b_a4b_nvfp4_x80` | <host> `s80-…-0849` | 52/52 | 0 | **52/52** (49290–50285) |
| Rot1 | `dgemma_26b_a4b_nvfp4_rot1` | <host> | 195/195 | 0 | **195/195** con preflight rot1 (50346–53907) |
| L″-prob | `llm_dgemma_26b_a4b_nvfp4_nostruct_prob_rp` | <host> `s80rp-20261006-1006` | 122/195 intentados (115 respondidos), **parada** (3 errores en triage_ext_en) | 7 | n/a (sin interposer) |
| L″-rep | `…_prob_rp_rep` | <host> rp | 52/52 | 4 → 1 tras el reintento único (`_pass1` conservado) | n/a |
| L″-disc | `…_disc_rp` | <host> rp | 195/195 | 0 | n/a |
| Revisor | `decider_4b_dgemmarev_*` | <host> | papers32 32/32 y ood 3/3 revisados; **triaje/adv 0/160** (HTTP 422) | — | — |
| Alerta | `dgemma_26b_a4b_nvfp4_alert_raw` | <host> | 60/60 | 0 | (esquema de 1 pregunta, fuera del preflight) |

Desviación de la puerta durante F1 (C7, revisada por Codex en R8): papers32 P02 y P03 tienen
`state` idéntico (paper duplicado en el banco, con GT distinto en `practice` → **JEV-73**). La puerta
atribuye ahora de forma conjunta las peticiones de casos con estado y sistema idénticos (recuento
conjunto = suma de lecturas). Antes daba 193/195 por esa ambigüedad. Es una regla de atribución,
no depende de las respuestas.

L, L′ y revisor: el revisor de `jevbench.cascade` usa 11 preguntas en triaje/adv. Con más de 10
preguntas, el interposer cambia al formato `indexed` (id pegado a la etiqueta) y el par
`hostile`+`yes/no` no tokeniza en un único hueco → 422 «labels do not share one template slot».
Es un límite del prototipo. El criterio JEV-32 (triaje, adv3, adv5) queda **no evaluable**.

### 9.2 Clasificación pre-registrada (§8.2, R3–R5)

| Componente | Valor | Clasificación |
|---|---|---|
| P.a ajustado | **52.6** (cobertura completa) | INCONCLUSA (48, 55] |
| P.b Brier noul | 0.095 | CONFIRMADA (≥ 0.085: peor calibrado que Jev, 0.071) |
| P.c errores 1.ª pasada | 0 | CONFIRMADA |
| P.d1 unif choice | 0/219 | CONFIRMADA |
| P.d2 auditoría numérica | 0 incidencias | CONFIRMADA |
| P.e latencia mediana | 318 ms (p95 515) | CONFIRMADA |
| S1.a acuerdo P↔S1 | 943/969 = 97.3 % | CONFIRMADA |
| S1.b \|Δ ajustado\| | 0.34 (P 52.62, S1 52.96; sin redondear antes de restar) | CONFIRMADA |
| S1.c Brier P < S1 | 0.095 vs 0.101 | CONFIRMADA |
| S1.d latencia S1 | 122 ms | CONFIRMADA |
| **Recomendación** (regla fijada) | | **S1** |
| R.a acuerdo P↔R | 259/260 = 99.6 % | INCONCLUSA ([98, 100)) |
| R.b distribuciones P↔R | máx \|Δp\| 0.34 | REFUTADA |
| X.a acuerdo P↔X | 249/260 = 95.8 % | REFUTADA (< 98 %) |
| X.b distribuciones P↔X | máx \|Δp\| 0.76 | REFUTADA |
| Rot1.a cambios de etiqueta | 33/259 (IC95 8.9–17.4 %) | INCONCLUSA → «inconclusa por host» (X.a no confirmada) |
| Rot1.b conservan posición | 9/33, p = 0.97 | CONFIRMADA → «inconclusa por host» |
| Rot1.c Δ acierto choice | −7.3 pp (IC95 −11.8, −3.0) | REFUTADA (el orden importa; IC excluye 0) |
| L″.c errores 1.ª pasada | prob 7 (parada) · rep 4 · disc 0 | INCONCLUSA · INCONCLUSA · CONFIRMADA |
| L″.r acuerdo L″-prob↔L″-rep | 142/155 = 91.6 % | descriptivo (suelo de ruido de la ruta generativa) |
| Alerta (criterio ≥ 7/10, ≤ 1 FP por set) | adv3 8/0 · adv4 **4**/0 · adv5 7/0 → 19/30, 0/30 FP | **no cumple** (adv4) |

McNemar exacto con Holm (familia de 53 celdas fase × pregunta, 11 fases):
- **P vs jev_v3:** única celda con p < 0.05 cruda: `papers32.depth` (b = 1, c = 13, p = 0.002;
  Holm 0.097) → **sin diferencia demostrada** frente a Jev.
- **S1:** igual que P.
- **L″-disc vs jev_v3:** `papers32.depth` (b = 1, c = 20; Holm 0.001) → **victoria significativa**
  en esa celda.
- **L″-prob:** sus comparaciones no son interpretables. El run está incompleto y las fases no
  ejecutadas cuentan como fallos en `score --vs`; las «derrotas» en triage_ext_en son ese artefacto.
- **Alerta vs Clef-27B:** 8–1, p = 0.039 (Clef detecta más).

Lecturas §8.3 aplicables:
- **P.a inconclusa:** se reporta el valor (52.6) sin lectura de nivel.
- **Ajustado ≥ 33:** se abrió el revisor/alerta pre-registrado (revisor no evaluable; alerta no
  cumple).
- **Sin superioridad sobre Jev demostrada** (Holm).
- **P.b confirmada:** la calibración noul es peor que la de Jev.
- **Recomendación S1:** vale para esta build y canvas.
- **R.a inconclusa:** hay variación entre ejecuciones idénticas en la misma sesión (1/260
  decisiones; probabilidades hasta 0.34). S1.a (97.3 %) se lee contra ese suelo.
- **Latencias:** descriptivas (GPU local con túnel frente a la API remota de Jev, 657 ms).

### 9.3 Limpieza

Sesiones `dgemma-vllm`/`dgemma-srv` paradas en ambos hosts tras F1 (0 procesos GPU propios; ningún
proceso ajeno tocado); túneles cerrados. Los pesos locales (`<ruta-local>`,
18.9 GB por host) y el venv se conservan a la espera de la decisión del usuario (pre-registro:
borrar salvo que se pida conservar).

### Nota posterior (8-oct-2026, JEV-86): Rot1.c con GT v4

La fila Rot1.c de arriba se calculó con **GT v3** (259 decisiones `choice`). Tras retirar P02 (GT v4, 6-oct), `dgemma_report.rotation` seguía recorriendo P02 y fallaba con `KeyError` oculto (Rot1 quedaba NO EVALUABLE al re-ejecutar). Corregido: solo cuenta los casos del GT vigente y `_try` avisa por stderr. Recálculo con GT v4: **256 decisiones, tabla 192/7/26/31, Δ −7,42 pp, IC Newcombe [−11,93; −3,06]**; 33/256 cambios. La clasificación no cambia (REFUTADA: el orden importa). Coincide con el recálculo independiente de Codex R82. Lo de arriba se conserva como registro histórico.
