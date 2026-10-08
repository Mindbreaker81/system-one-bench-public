# Manifiesto: `llm_qwen38_27b_fp8_nostruct_prob` (JEV-57, fase 3)

**Qué es:** batería completa de Qwen3.8-27B servido local en <host> con los **pesos
oficiales FP8** (`Qwen/Qwen3.8-27B-FP8`), como configuración alternativa a la ficha NVFP4 de la
comunidad tras el hallazgo de abstención del run `llm_qwen38_27b_prob` (−16).

**Resultado verificado:** FP8 con esquema tiene 5/10 elecciones casi uniformes
en adv1; sin esquema, 0/10 y 9/10 dept. La batería FP8 sin esquema tiene
0/259 elecciones casi uniformes. NVFP4 sin esquema acierta 9/10, solo en smoke.
Ollama reproduce el contraste: 8/10 uniformes con esquema, 0/10 sin él,
10/10 dept. Debilita una causa exclusiva de SGLang; no distingue modelo,
prompt/esquema compartido del adaptador y servidor, ni efectos de precisión.
Dos casos NVFP4 sin normalizar contienen vectores nulos; uniformidad
normalizada no prueba ceros crudos.

## Matriz del discriminador (adv1, endpoints y configuraciones distintos)

| Pesos | Backend | Config | Uniformes dept | dept correcto |
|---|---|---|---|---|
| NVFP4 comunidad | SGLang | struct, temp 0 | 6/10 | 2/10 |
| NVFP4 comunidad | SGLang | struct, thinking, temp 0 | 8/10 | 0/10 |
| FP8 oficial | SGLang | struct, temp 0 | 5/10 | 3/10 |
| FP8 oficial | SGLang | struct, thinking, temp 0 | 7/10 | 1/10 |
| FP8 oficial | SGLang | **nostruct**, temp 0 | **0/10** | **9/10** |
| NVFP4 comunidad | SGLang | **nostruct**, temp 0.7/top_p 0.8/presence 1.5 | **0/10** | **9/10** |
| GGUF `qwen3.8:27b` | Ollama/llama.cpp | struct, temp 0 | 8/10 | 2/10 |
| GGUF `qwen3.8:27b` | Ollama/llama.cpp | **nostruct** | **0/10** | **10/10** |
| fp16/FP8 decl. | Cerebras | struct | 0 | 9/10 |

Runs de smoke versionados: `smoke_qwen38_t0`, `smoke_qwen38_t0_think`,
`smoke_qwen38_t0_nonorm` (NVFP4); `smoke_qwen38_fp8_t0`,
`smoke_qwen38_fp8_t0_think`, `smoke_qwen38_fp8_t0_nostruct`,
`smoke_qwen38_nvfp4_nostruct`; `smoke_qwen38_ollama_struct`,
`smoke_qwen38_ollama_nostruct` (Ollama 0.32.14, GGUF en <host>, túnel 11435).

## Infraestructura

- **Host:** `dgx-spark-a` (<host>), GB10 aarch64, 128 GB unificada, CUDA 13.
- **Servidor:** contenedor `lmsysorg/sglang:qwen38-27b` lanzado con
  `<ruta-local>` (`QUANT=fp8`, `PORT=8000`),
  misma receta SGLang que el run NVFP4: `--attention-backend flashinfer`,
  `--kv-cache-dtype fp8_e4m3`, `--mamba-ssm-dtype bfloat16`, `--reasoning-parser
  qwen3`, MTP EAGLE spec decode, `--sampling-defaults model`.
- **Pesos:** `Qwen/Qwen3.8-27B-FP8` (oficiales; snapshot ModelScope — HF CDN iba
  a ~30 B/s el 4-oct) en
  `<ruta-local>`,
  servido con `--model-path` apuntando ahí (override vía `EXTRA_ARGS`).
- **Consumo:** adaptador `llm` desde el portátil por túnel SSH a `127.0.0.1:8000`.

## Configuración del run (FP8 + `structured=false`)

```
adapter=llm · provider=openai · model=qwen3.8-27b-sglang (alias API)
base_url=http://127.0.0.1:8000/v1 (túnel SSH)
mode=probabilities · structured=false · normalize=true · retries_malformed=2
extra_body={"chat_template_kwargs":{"enable_thinking":false},
            "temperature":0.7,"top_p":0.8,"presence_penalty":1.5}  # ficha
max_tokens=8192 · timeout=300 · case_timeout=600 · sin min_interval (local)
```

**Desviación respecto al protocolo JEV-54:** `structured=false` cambia el canal
de salida (JSON guiado por prompt frente a decodificación restringida por
esquema). Frente al histórico también cambian NVFP4→FP8 y límites:
no una sola variable. Scorer/casos/preguntas/GT son idénticos. Falta fijar
revisión/hash de pesos y versiones/digest inmutables del servidor/backend.

## Telemetría de la batería

- 195/195 casos, 11 fases, 0 errores, 0 reintentos por malformado.
- Tokens: 203 091 in / 29 270 out.
- Latencia: mediana 6.4 s/caso, máx 18.0 s (~22 min totales).
- Emisión de ceros: **0/259** decisiones `choice` (26 % en el run NVFP4+struct).

## Resultado

Ajustado **49** — por encima de Jev (45), bajo Clef-27B (52) y el Qwen por
Cerebras (59). Contrastes por pregunta frente a Jev: `depth` (p<0.01) y
`practice` (p≈0.016, redondeado 0.02), p crudas sin corrección de
multiplicidad — Holm sobre las 53 celdas fase×pregunta: 0.12 y 0.81;
no superioridad global. FP8 sin esquema obtiene 49, no un score universal
ni medido en NVFP4. Brier peor que Jev (0.080 vs 0.071), ~10× su latencia.
Papers 80.3 supera ligeramente sol 80.0 de forma descriptiva; rho 0.82
no es la mejor correlación. Diferencia con Cerebras: múltiples factores.
Seguimiento: JEV-58 (NVFP4 completo y controles), JEV-A-2.
