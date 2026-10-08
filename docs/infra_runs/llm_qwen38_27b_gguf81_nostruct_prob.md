# Manifiesto: `llm_qwen38_27b_gguf81_nostruct_prob` + diagnóstico estructurado (JEV-58)

**Qué es:** batería completa de Qwen3.8-27B servido por **llama.cpp** en <host> con
los pesos GGUF de la bóveda local (`<ruta-local>`),
en `structured=false`. Resultado descriptivo adicional (ajustado 48),
no una ablación de precisión/backend frente a FP8 o NVFP4.

Además ejecuta el **diagnóstico acotado de JEV-58** sobre el SGLang NVFP4 de
<host>: réplica directa del wire del adaptador con casos prefijados.

## Infraestructura (<host>)

- **Host:** `dgx-spark-b` (<host>), GB10 aarch64, 128 GB unificada, CUDA 13.
- **Servidor:** `llama-server` compilado en host
  (`<ruta-local>`, target `llama-server`, ggml-cuda), puerto 8080.
  `-ngl 99 --ctx-size 32768 --jinja --alias qwen3.8-27b-gguf`.
- **Pesos:** `<ruta-local>` (Unsloth Dynamic, 16 GB),
  ya presentes en la bóveda de <host> — sin copia necesaria.
- **Consumo:** adaptador `llm` desde el portátil por túnel SSH `11435→8080` y
  `8081→8080` (los puertos se reasignaron por colisión con el ollama local).

## Configuración

```
adapter=llm · provider=openai · model=qwen3.8-27b-gguf
base_url=http://127.0.0.1:8081/v1 (túnel a <host>)
mode=probabilities · structured=false · normalize=true · retries_malformed=2
extra_body={"chat_template_kwargs":{"enable_thinking":false},
            "temperature":0.7,"top_p":0.8,"presence_penalty":1.5}
max_tokens=8192 · timeout=600 · case_timeout=900
```

## Telemetría

- 195/195 casos, 11 fases, 0 errores, 1 reintento por malformado.
- Latencia mediana 10.8 s/caso (~35 min totales).
- Emisión degenerada: **0/219** decisiones `choice` casi uniformes.

## Diagnóstico estructurado (JEV-58, <host> NVFP4 SGLang)

Réplica del wire real del adaptador (system prompt de `system-one-adapter`,
`<document>{state}</document>`, `response_format` JSON Schema estricto con
mapas de probabilidad por etiqueta, `temperature=0`, thinking off):

| Variante | Resultado crudo |
|---|---|
| Esquema 5 preguntas + caso adv1 real | **0.0 en todos los campos** (`finish_reason=stop`) |
| Esquema solo `department` + mismo caso | 0.0 |
| Mismo prompt+esquema + caso triaje normal | probabilidades reales (0.95) |
| Sin la instrucción anti-inyección + caso adversarial | 0.0 |
| Prompt propio naive + mismo caso | respuesta normal |

**Interpretación revisada:** estos controles documentados no aíslan una
causa interna. El prompt propio funciona; queda pendiente separar documento,
prompt/esquema del adaptador y servidor, conservando peticiones/respuestas
crudas saneadas versionadas (no encontradas en esta auditoría). Quitar
anti-inyección y reducir preguntas no elimina el síntoma en esos casos,
pero no descarta todas las interacciones. FP8/Ollama debilitan una causa
exclusiva de NVFP4/SGLang; vLLM corresponde a Flash-Next, otro modelo.
Uniformidad normalizada no prueba emisión cruda de ceros.

**Posdata (JEV-63, misma tarde):** la separación pendiente quedó resuelta en la
matriz prompt×esquema — los ceros exigen el prompt TypeSafe **y** el esquema a la
vez (ver `docs/infra_runs/diag_qwen38_jev63.md`).

**Posdata (cerrado por JEV-67, 6-oct):** la separación se explicó del
todo por visibilidad — los servidores locales no inyectan el esquema del
`response_format` en el prompt, así que las celdas `structured` eran
medición a ciegas. Con el esquema inyectado en el prompt la batería da
51/50/48 (FP8/NVFP4/GGUF) y 63 en discrete. Manifiesto
`docs/infra_runs/qwen38_jev67.md`.

Repetición del smoke `structured=true` (temp 0.7): 3/10 uniformes — la firma
persiste con variación de muestreo (`smoke_qwen38_nvfp4_struct_v2`).

## Resultado GGUF (<host>)

Ajustado **48**, descriptivamente cercano a FP8 49 y NVFP4 52;
no equivalencia demostrada. La tasa 0/219 anterior cubre 9 fases sin
adv4/adv5; en las 11 fases es 0/259.
