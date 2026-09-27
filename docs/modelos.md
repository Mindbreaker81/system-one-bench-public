# Modelos evaluados

Todos implementan (o imitan) el contrato "System One": estado + preguntas tipadas
(`choice` / `score` / `noul`) → distribuciones de probabilidad, sin generar texto.

---

## Jev

- **Proveedor:** TypeSafe AI. Modelo cerrado, solo por API.
- **Acceso:** OpenRouter, alias `~typesafe/jev-latest`, endpoint
  `/api/alpha/decisions`. Clave: `OPENROUTER_API_KEY` en `.env`.
- **Versión probada:** el alias resolvía a `jev-1.13-20260917` (20–23 sep 2026).
  Verificar siempre la versión real antes de comparar con resultados anteriores.
- **Relacionado:** `typesafe/jev-router` (router de modelos que usa Jev por dentro;
  no es lo que evaluamos).
- **Coste/latencia:** ~$0.0003/caso, ~2 s.
- **Particularidades observadas:**
  - Jitter pequeño entre llamadas (|Δ| medio 0.013, máx 0.07 en relevancia).
    Importa solo en la frontera: 10/84 binarios cayeron en 0.45–0.55.
  - Cuando un caso adversarial está cerca de la frontera, el flip puede ser confiado
    (A09: 0.86).
  - Circuito recomendado: **decisor Jev → revisor Jev (framing auditor) → reglas
    duras** (ver [legacy/jev_vs_laya.md](../legacy/jev_vs_laya.md) §3–5).

## Laya

- **Proveedor:** ConvAI Innovations. HF: `convaiinnovations/laya`. Apache-2.0.
- **Arquitectura:** encoder no autoregresivo. Backbone ModernBERT-large (421M, inglés)
  o mmBERT-base (322M, multilingüe) + cabeza de decisión de 2 capas; cada opción se
  puntúa en su propio `[MASK]`. Entrenado con RLCD (proper scoring rules).
- **Checkpoints:** `laya` (raíz, inglés, 512 tok), `laya-multilingual` (100+ idiomas,
  1024 tok ampliable a 8192), `laya-typed-decisions` (fine-tune, 0.766 en su set).
- **Instalación:**
  ```bash
  pip install laya            # extras: [serve] [mcp] [onnx] [fast]
  ```
  ```python
  from laya import Router
  router = Router()                        # detecta idioma y enruta al checkpoint
  r = router.predict(state, questions)     # questions en formato dict tipo Jev
  ```
- **Hardware:** ~800 MB; corre en CPU (35–464 ms) o GPU (~33 ms).
- **Particularidades observadas en nuestra batería:**
  - **Determinista**: rerun bit a bit idéntico.
  - Zero-shot no compite en este dominio (decisor, revisor ni cross-check).
  - Los propios autores avisan: base checkpoints ~0.36 zero-shot en typed-decisions,
    sobreconfiado de fábrica, `noul` sensible a la redacción de la etiqueta.
  - Única vía útil: fine-tuning en dominio si hace falta on-premise.
- **Re-test en GPU con el harness (27-sep, `laya` 0.3.20, GB10, ~30 ms/caso):** `laya_router`
  reproduce el rerun v2 de Lyra (triaje ES 62.1 / EN 73.6, papers 48.8, ρ 0.22, adv 5/20;
  casos nuevos: triaje ext 55.0/71.5, adv3 7/20). La variante `typed-decisions` (su fine-tune
  de 0.766 en su set) no ayuda aquí: 67.1/75.0, papers 45.6, adv 3/20, adv3 8/20. Las dos
  quedan en o por debajo de la línea base de mayoría en triaje ES y en adversarial.

## Decider

- **Proveedor:** Mapika (independiente, no afiliado a TypeSafe; declaran no haber
  destilado de Jev). Repo: <https://github.com/Mapika/decider>. Apache-2.0.
- **Arquitectura:** LLM decoder (familia Qwen3.5 Base) con un slot de respuesta por
  pregunta; el hidden state del slot se proyecta sobre tokens-etiqueta (A–Z…) y se
  aplica softmax sobre las opciones válidas a temperatura ajustada. Una pasada.
  Dos layouts: *state-first* (default) y *schema-first* (permite cachear prefijo).
- **Checkpoints (según su README):**

  | Modelo | Base | Params | Acc. (su set) | VRAM |
  |---|---|---|---|---|
  | decider-0.8b | Qwen3.5-0.8B-Base | 0.8B | 0.71 | — |
  | decider-2b v11 | Qwen3.5-2B-Base | 1.9B | 0.752 | ~4 GB |
  | decider-4b v2.1 | Qwen3.5-4B-Base | 4.2B | 0.784 | ~8.4 GB |
  | decider-35b-a3b v1 | Qwen3.5-35B-A3B-Base (MoE) | 34.7B / 3B act. | 0.810 | ~65 GB bf16 |
  | decider-35b-a3b-nvfp4 | idem NVFP4 | 34.7B | −1–1.5 pt | ~19.6 GB |

  Los 35B caben en un DGX Spark (128 GB unificados); NVFP4 aprovecha Blackwell (GB10).
- **Instalación / uso:**
  ```bash
  pip install decider-ai
  ```
  ```python
  from decider.infer import Decider
  d = Decider("Mapika/decider-2b")
  d.system_one(state_dict, questions_dict)   # formato cable de TypeSafe
  d.decide("texto", [{"question": "...", "options": ["a", "b"]}])  # formato simple
  ```
  Servidor HTTP: `scripts/serve.sh Mapika/decider-2b 8000` →
  `POST /v1/systemone` (compatible con SDKs de TypeSafe) y `POST /decide`.
  Para modelos grandes hay backend vLLM (`decider.serve_vllm:app`).
- **Interés para nosotros:** al exponer `/v1/systemone` compatible con TypeSafe, el
  mismo cliente de Jev debería poder apuntar a Decider cambiando solo la URL.
- **35B-A3B en GB10 (27-sep):**
  - bf16 con `decider.infer`: hay que pasar `--opt use_graphs=false`, porque los CUDA graphs rompen el MoE. ~680 ms/caso.
  - NVFP4 **solo con vLLM 0.29 + ModelOpt** (`scripts/serve_decider_nvfp4.sh`, adaptador
    `systemone_http`). Carga con kernels CUTLASS FP4 en sm_121. **Rinde igual que bf16**
    (sin diferencias pareadas significativas; triaje 85.0/81.4, papers 70.3, ρ 0.87, adv3 12/20)
    y va 3.5× más rápido (190 ms/caso), con ~20 GB.
- **Intento anterior (26-sep, Lyra):** `decider-2b` en CPU ARM bf16 sin soporte bf16
  nativo: fallback de mkldnn a BLAS, sin `causal_conv1d` ni `flash-linear-attention`
  (Qwen3.5 usa gated delta-net), **~240 s por estado**. Se abortó en triaje ES T12 y no
  hay resultados. Hay que repetirlo en GPU (DGX) con esos kernels instalados.

## AnyJev

- **Proveedor:** Nokia Applied Research (+ Tencent Hunyuan).
  Repo: <https://github.com/nokia-applied-research/AnyJev>. Apache-2.0, pip `anyjev`.
- **No es un modelo, es un framework** que convierte cualquier LLM abierto en decisor
  tipo Jev (un prefill, lectura de logits).
- **Niveles:** raw → **L0** (marginalización de permutaciones + prior de lote, sin
  labels) → L1 (temperature scaling, 100–500 labels) → L2 (cabeza lineal sobre hidden
  state, 100–300 labels por pregunta y por modelo).
- **Quirk de instalación:** `anyjev[hf]` no declara `accelerate`, pero hace falta para
  `device_map` → `pip install "anyjev[hf]" accelerate`.
- **Probado:** Qwen3-1.7B, F32, L0, CPU ARM 4 cores (~60 s/estado).
  Scripts y resultados en [../anyjev_investigacion/](../anyjev_investigacion/).
- **Siguiente paso posible:** Qwen3-8B / 32B L0 en DGX Spark (Opción B del informe).

## Julia

- **Proveedor:** SupersonicLabs (<https://huggingface.co/SupersonicLabs/Julia-1>), Apache-2.0.
  La organización publica solo `Julia-1` y `Julia-1-ONNX` (para navegador/WebGPU).
- **Arquitectura:** mmBERT-small (JHU CLSP, multilingüe) + cabeza de decisión. 144.3M
  parámetros, 550 MB en FP32, contexto de 8192 tokens, 2–20 opciones por pregunta.
- **Formato:** el mismo que Jev (`choice`/`score`/`noul` con `instructions`/`criteria`).
  `score` es el índice esperado y `noul` la probabilidad de true.
- **Instalación** (local, CPU): `snapshot_download('SupersonicLabs/Julia-1',
  local_dir='models/Julia-1')` + `pip install -e models/Julia-1`, en `.venv-julia` con torch
  CPU. Adaptador: `julia`.
- **Resultados (26-sep, CPU x86, 835 ms/caso):** triaje 36.4/37.1, papers 48.8 (ρ 0.22),
  adversarial 3/20. Queda **por debajo de la línea base de mayoría** en todo, y su Brier en
  sí/no (0.485) indica respuestas muy confiadas y equivocadas.
- **Diagnóstico:** es extremadamente sensible a la redacción. Sobre la factura duplicada:
  - con los departamentos descritos en corto ("billing and refunds") → `admin` 0.98; con
    las descripciones largas de la batería → `urgencias` 0.92, y 0.995 si cambia el orden;
  - "Is the sender hostile?" → 0.11; "…hostile, insulting, or threatening?" → 0.98.

  Adaptar las preguntas a Julia rompería la regla de "mismas preguntas para todos", así que
  el resultado oficial es el de la batería estándar. Si interesa, se puede medir aparte
  una variante "julia-friendly".

## GLiNER

- **Proveedor:** Fastino (<https://huggingface.co/fastino>), autores de GLiNER2
  (arXiv 2507.18546). Apache-2.0, `pip install gliner2`.
- **Arquitectura:** encoder DeBERTa-v3 con cabezas de clasificación por span/etiqueta.
  No es System One de verdad: la API `classify_text` devuelve la etiqueta (argmax), y las
  confianzas solo si se piden de forma explícita.
- **Variantes de decisión:**

  | Repo | Params | Nota |
  |---|---|---|
  | `fastino/GLiNER2.5-Decide` | ~0.5B (carga 486M F32) | **probado 24-sep** |
  | `fastino/GLiNER2.5-Decide-1B` | 1B | sin probar |
  | `fastino/GLiNER2.5-multi-Decide` | 0.3B | multilingüe, sin probar (útil para ES) |
  | `fastino/gliner2.5-{small,base,multi}-v1` | 74M–0.3B | extracción, no decisión |
  | `fastino/gliner2-privacy-filter-PII-multi` | 0.3B | PII/guardrail: posible capa de reglas |

  Dataset propio: `fastino/fast-decisions` (con él publican 60.2% vs "JevK5" 57.6%).
- **Resultados (Decide 0.5B, zero-shot):** triaje 79.3/71.4, papers 45.6% (relevance=1 en
  los 32: varianza cero), adversarial 3/20. Falla toda la familia keyword-stuffing.
- **Problemas del test anterior que hay que corregir:**
  - Urgencia y relevancia se pasaron como etiquetas `"0"/"1"/"2"`, sin la descripción de
    los niveles. Así el modelo no puede saber que hay un orden y se refugia en el centro.
  - Solo se guardó el argmax. Hay que pedir las confianzas para poder calcular Spearman y
    calibración.
  - `legacy/.../gliner_ft/train_triage_v1.jsonl` (28 ejemplos) son **los mismos 14 casos
    de triaje** ES+EN, y hay un adapter LoRA entrenado con ellos (`output/final`).
    Cualquier resultado de ese fine-tune medido sobre la batería estaría contaminado.
