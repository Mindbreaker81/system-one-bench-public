# Manifiesto: `llm_qwen38_27b_nvfp4_nostruct_prob` (JEV-58, celda pre-registrada)

**Qué es:** batería completa NVFP4 sin esquema, mismo checkpoint comunitario
`RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead` (revisión declarada `a7b7d4e`)
y receta SGLang. Ajustado **52**, 195 casos, cero errores/reintentos.
Frente al histórico −16 también se fijan max_tokens/timeout/case_timeout
que antes no estaban registrados: no es una única variable aislada.
Faltan revisión/digest inmutables completos del servidor para reproducibilidad.
Elecciones casi uniformes: 0/259 en 11 fases vs 67/257 histórico;
el resumen del scorer cuenta 9 fases sin adv4/adv5 (0/219 vs 53/218).

## Infraestructura

- **Host:** `dgx-spark-a` (<host>), GB10 aarch64, 128 GB unificada, CUDA 13.
- **Servidor:** contenedor `qwen3.8-27b-sglang`
  (`lmsysorg/sglang:qwen38-27b`), la receta estándar del proyecto
  (`QUANT=nvfp4`): flashinfer, KV fp8_e4m3, MTP EAGLE, `--reasoning-parser
  qwen3`, `--sampling-defaults model`, puerto 8000.
- **Consumo:** adaptador `llm` por túnel SSH a `127.0.0.1:8000`.

## Configuración

```
mode=probabilities · structured=false · normalize=true · retries_malformed=2
extra_body={"chat_template_kwargs":{"enable_thinking":false},
            "temperature":0.7,"top_p":0.8,"presence_penalty":1.5}  # = ficha del run original
max_tokens=8192 · timeout=300 · case_timeout=600
```

## Telemetría

- 195 casos, 11 fases, 0 errores, 0 mal_retries. Mediana 5.3 s/caso (~20 min).

## Resultado y lectura

- Ajustado **52** · triaje 90.7/87.1 · papers 76.9 (ρ 0.81) · adv3 83.5 ·
  Brier 0.076 (el mejor de los Qwen locales) · McNemar vs Jev: gana `depth`
  de papers en crudo (2–14, p < 0.01; no significativa tras Holm sobre las
  53 celdas fase×pregunta — Holm 0.22).
- Matriz local completa (mismo modelo, mismo banco):

| Pesos | Backend | Esquema | Ajustado | unif choice |
|---|---|---|---|---|
| NVFP4 | SGLang | sí | −16 | 53/218 |
| **NVFP4** | **SGLang** | **no** | **52** | **0/219** |
| FP8 oficial | SGLang | no | 49 | 0/219 |
| GGUF Q4_K_M | llama.cpp | no | 48 | 0/219 |
| — | Cerebras | sí / no | 59 / 65 | 0/219 |

- El spread NVFP4 52 / FP8 49 / GGUF 48 es pequeño y descriptivo (también
  cambia el backend en el GGUF); la señal robusta es el contraste estructurado.
- El diagnóstico documentado en el manifiesto GGUF señala una interacción
  pendiente de aislar entre documento, prompt/esquema y servidor. NVFP4
  no es necesaria para observar el síntoma; no se descartan efectos residuales
  de precisión. vLLM corresponde a Flash-Next, no al mismo checkpoint 27B.
  La tabla anterior usa la cobertura de 9 fases del resumen.
