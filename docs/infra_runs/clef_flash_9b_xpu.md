# clef_flash_9b_xpu — Cloudflare/clef-flash en Intel Arc Pro B70 (JEV-53)

Run de `Cloudflare/clef-flash` (9B multimodal, backbone Qwen3.5-9B + cabeza de esquema
conjunta) en `<host>` (<host>), ejecutado **en proceso** con el adaptador `clef`
(igual que `clef_27b` en el DGX, pero en la estación con XPU).

## Hardware y entorno

- Host: `<host>` (user@<host-lan>), <host> x86_64.
- GPU: Intel Arc Pro B70, 32 GB; torch la detecta como un dispositivo XPU.
- RAM 43 GiB (~41 libres en preflight). Disco: 739 GB libres.
- Venv propio `<ruta-local>` (Python 3.12.14):
  `torch==2.14.1+xpu`, `torchvision==0.29.1+xpu`, `transformers==5.18.0`,
  `accelerate==1.15.0`, `huggingface-hub==1.33.0`, `safetensors`, `pillow`.
  No se tocó `.venv-clm-xpu` ni `.venv-strands`.
- HF token ya persistido en `<ruta-local>` del host.

## Modelo y revisiones

- `Cloudflare/clef-flash`, revisión fijada `17f0b0ad64efb65d273590632833508766b2aae6`.
- Snapshot: `<ruta-local>`
  (4 shards safetensors ~17.6 GiB + `joint_head.safetensors` 243 MB + `joint_schema_model.py`).
- El adaptador importa `joint_schema_model.py` **de este snapshot** (sys.path del snapshot,
  proceso independiente del de clef_27b — no hay riesgo de mezclar módulos cacheados).
- `device=xpu`, `dtype=bfloat16`, `max_length=16384` (ventana oficial).
- `load_release_model` usa `device_map={"": "xpu"}` + `head.to(xpu)` — XPU no es backend
  validado por los autores, pero la inferencia funcionó (ver abajo).

## Ventana y truncado

`encode_record` recorta `state_ids` en silencio a `max_length − fija`. Se tokenizaron los
195 estados con el `encode_record` oficial del snapshot y `max_length` sin cota: el más
largo es `papers32/P11` con 6988 tokens de entrada total — **ningún caso se trunca**
con la ventana de 16384. No hizo falta variante `_trunc`.

## Ejecución

```bash
# smoke (2 casos, borrado tras validar)
.venv-clef-flash-xpu/bin/python -m jevbench.run clef --run smoke_clef_flash_9b_xpu \
  --opt model=Cloudflare/clef-flash --opt revision=17f0b0a… --opt device=xpu \
  --opt dtype=bfloat16 --phases ood,triage_es --limit 2
# batería
.venv-clef-flash-xpu/bin/python -m jevbench.run clef --run clef_flash_9b_xpu \
  --opt model=Cloudflare/clef-flash --opt revision=17f0b0a… --opt device=xpu \
  --opt dtype=bfloat16 --phases all+new   # y luego --phases adv4,adv5
```

- 11 fases, **195/195 casos, 0 errores**, `questions_hash` correcto en todas.
- Mediana ~142 ms/caso (in-process; latencia del modelo, no de cliente por túnel).
- Avisos transformers: `causal_conv1d` y `flash-linear-attention` no instalados → los
  kernels de Gated DeltaNet caen a la implementación PyTorch de referencia (correcta,
  más lenta). Se documenta; no se instalaron extras CUDA en un host Intel.

## Runs opcionales (mismo entorno)

- `clef_flash_9b_xpu_alert_raw` — alerta de una pasada `manipulation` en adv3–5
  (`scripts/alert_onepass.py clef …`): 60/60 casos.
- `decider_4b_clefflashrev_{raw,review,audit,avg}` — revisor Clef-Flash sobre D1
  decider_4b (`jevbench.cascade --d1 decider_4b --adapter clef --prefix
  decider_4b_clefflashrev --control ""`): 195/195 revisados, 0 errores.
- Resultados traídos al repo con `rsync` (el run es in-process en <host>).

## Limpieza

Sin procesos residentes: el run es in-process y termina solo. El venv y el snapshot
permanecen en <host> para reproducibilidad.
