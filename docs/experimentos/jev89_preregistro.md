# JEV-89 paso 3 — pre-registro: decisor propio sobre Qwen3.5-9B

**Estado:** fijado el 17-oct-2026, **antes** de entrenar ni de ejecutar ningún modelo sobre la batería.
Aprobado por el autor (base Qwen3.5-9B, prueba de la cadena con 2B, criterio de evaluación). Cualquier
cambio posterior va como enmienda fechada debajo, sin editar este texto.

## Pregunta

¿Un LoRA de Qwen3.5-9B entrenado con el conjunto propio de JEV-89 (sin ningún caso de evaluación)
decide mejor que la misma base sin entrenar, y dónde queda frente a Jev y frente a un decisor dedicado
del mismo tamaño (Nimble-9B)?

## Datos

- Conjunto `run-20261017-192634` (`ai-models/datasets/derived/jev89/`; `docs/plan_modelo_propio.md`
  §8.2): `train.jsonl` + `train_nc.jsonl` para entrenar; `val.jsonl` + `val_nc.jsonl` solo para elegir
  el checkpoint. Índice de exclusión `23a21a1f…642d`: 0 solapamientos con la batería.
- Incluir PMR-Bench (CC BY-NC 4.0) hace que el modelo resultante sea **solo para investigación no
  comercial**; sus pesos no se publican.
- Una muestra de entrenamiento por pregunta etiquetada (`gt` parcial: solo las presentes).

## Formato (contrato de Tev1, el que lee el adaptador `tev1` ya existente)

- `system`: el texto fijo de `jevbench/adapters/tev1.py::SYSTEM`.
- `user`: JSON `{"state", "question", "options": [{"label": "A", "key", "description"}, …]}` construido
  con `jevbench/adapters/tev1.py::_options` a partir de `jevbench.battery.TRIAGE_QS` / `PAPERS_QS`
  (importados, sin editar).
- Respuesta: **una letra**. Pérdida solo sobre el token de la letra.
- Aumento: en preguntas `choice`, el orden de las opciones se baraja por ejemplo (semilla fija), para
  que el modelo aprenda el contenido y no la posición; `score` y `noul` mantienen su orden.
- Evaluación con el adaptador `tev1` sin cambios: softmax sobre las letras permitidas del primer token.

## Entrenamiento (fijo)

| Parámetro | Valor |
|---|---|
| Base | `Qwen/Qwen3.5-9B` @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a` (copia de ai-models), bf16 |
| Adaptador | LoRA r=16, α=32, dropout 0,05, proyecciones lineales del modelo de lenguaje (q, k, v, o, gate, up, down; sin la torre de visión) |
| Optimización | AdamW, lr 2e-4, coseno, warmup 3 %, batch efectivo 16, longitud máx. 2.048 tokens, semilla 89 |
| Épocas | 3; checkpoint al final de cada una |
| Selección | el checkpoint con menor log-loss media de la letra correcta en `val + val_nc`; empate → el anterior |
| Biblioteca | Unsloth si funciona en el DGX (aarch64, CUDA 13); si no, transformers + peft con la misma configuración (se registra cuál) |
| Hardware | DGX Spark .81 (GB10); .80 de reserva |

**Prueba de la cadena** (no se interpreta): Qwen3.5-2B-Base, misma tubería, 200 pasos, más
`jevbench.run tev1 … --limit 2`. Solo verifica que las letras son tokens únicos, que la pérdida baja y
que el adaptador lee el modelo. **Parada:** si en validación el 9B no supera la mayoría por pregunta
en `department` y `domain`, se detiene y se informa sin pasar a la batería.

## Evaluación (una sola vez)

1. **Control — base sin entrenar:** run `qwen35_9b_base_tev1fmt` (adaptador `tev1`,
   `model=<ruta local de la base>`), `--phases all+new` y `--phases adv4,adv5`.
2. **Modelo:** run `jev89_qwen35_9b_lora` con el checkpoint elegido fusionado, mismas fases.
   Nunca se re-entrena ni se re-selecciona después de ver la batería.

## Análisis

- `python3 -m jevbench.score --summary --adj-ci` (ajustado con IC, mayoría, Brier/ECE, frontera 0,45–0,55,
  errores seguros de `scripts/errores_seguros.py`).
- McNemar exacto por celda en las 53 celdas, Holm por comparación (`jevbench.dgemma_report.mcnemar_holm(run, ref=…)`, la misma función usada en JEV-106):
  - **H1 (primaria):** `jev89_qwen35_9b_lora` frente a `qwen35_9b_base_tev1fmt`.
  - **Secundarias:** frente a `jev_v3` y frente a `nimble_9b`.
- Redacción: solapamiento de IC o Holm 1 **no** prueban equivalencia («sin diferencias significativas»).

## Criterio de éxito (fijado ahora)

- **H1 confirmada** si al menos una celda sobrevive a Holm a favor del modelo entrenado y ninguna en
  contra; **refutada** si alguna sobrevive en contra o el ajustado del entrenado es menor que el del
  control; **inconclusa** en otro caso.
- **Éxito práctico** si además el ajustado es ≥ 44 (la franja de los decisores dedicados de ~9B del
  banco: Nimble 46,9, Drex 43,7, Clef-Flash 44,6) y ninguna celda sobrevive a Holm a favor de `jev_v3`.
- Se publica el resultado sea cual sea, incluido si no hay mejora.

## Registro

Manifiesto en `docs/infra_runs/jev89_*.md` (hardware, versiones de torch/transformers/peft/unsloth,
hashes del conjunto y del adaptador LoRA, checkpoint elegido y su log-loss de validación).

## Enmienda E1 (17-oct-2026, antes de entrenar)

La arquitectura de Qwen3.5-9B es híbrida (inspección de módulos en .81): 24 capas de atención lineal
(`linear_attn`: `in_proj_qkv`, `in_proj_z`, `in_proj_a`, `in_proj_b`, `out_proj`) y 8 de atención completa
(`self_attn`: q/k/v/o), con MLP (gate/up/down) en las 32. La lista «q, k, v, o, gate, up, down» dejaría
sin adaptar la mezcla de tokens de 24 de las 32 capas. Se fija ahora:
LoRA en `self_attn.{q,k,v,o}_proj`, `linear_attn.{in_proj_qkv,in_proj_z,out_proj}` y
`mlp.{gate,up,down}_proj` del modelo de lenguaje; sin `in_proj_a`/`in_proj_b` (proyecciones de puerta
de una dimensión por cabeza), sin `lm_head` ni la torre de visión. El resto, sin cambios.
