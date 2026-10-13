# drex_v15_9b — nace-ai/drex-v1.5 (9B) en el DGX <host>, servido por su `serve.py` (JEV-101)

Run del decisor open-weight Drex v1.5 (Nace.AI): backbone `Qwen3_5ForCausalLM` ~8.95B
bf16 + cabeza pointer (`head.pt`), servido por el `serve.py` del propio repo
(`POST /v1/systemone` en 127.0.0.1, sin auth) y consumido desde el portátil con el
adaptador `systemone_http` a través de un túnel SSH. Encargo `<ruta-local>`
(no versionado); ejecución delegada (Devin).

## Hardware y entorno

- Host: `dgx-spark-a` (user@<host-lan>), aarch64 + NVIDIA GB10 (sm_121),
  memoria unificada (~116 GiB disponibles), CUDA 13. GPU libre al empezar
  (`nvidia-smi` 0 %); contenedor `dashboard-sparkdash` presente y **no tocado**.
- Pesos en el propio <host>: `<ruta-local>` descargado con
  `hf download nace-ai/drex-v1.5 --revision 328ee227c0425669d9f37fa82d400aa52c22139c
  --local-dir <ruta-local>` (HF token ya persistido en `<ruta-local>`).
- Venv propio `<ruta-local>` (Python 3.12.14 de uv,
  `scripts/setup_venv.sh drex 'transformers>=5.17,<6' 'pydantic>=2' huggingface_hub`):
  `torch==2.14.1+cu130`, `transformers==5.19.0`, `pydantic==2.14.1`,
  `huggingface-hub==2.2.0`, `safetensors==0.8.0`, `tokenizers==0.23.3`.
  `uv pip freeze` sha256: `689132d7ca93ddd041fc8c9bfd4c71d696422dc027ebdd81f52247d78eb4b175`.
- **Desviación de requirements:** el repo pide `torch>=2.6,<2.9`, pero el índice
  cu130 no tiene wheel aarch64 en ese rango (el primero real es 2.9.0; GB10 exige
  CUDA 13). Se usa 2.14.1+cu130, el mismo que funcionó en `nimble_9b`/`clef_27b`.
  `transformers==5.19.0` sí está dentro del rango `>=5.17,<6`.
- Avisos transformers documentados (mismo caso que nimble/clef): sin
  `causal_conv1d` ni `flash-linear-attention`, las capas Gated DeltaNet caen a la
  implementación PyTorch de referencia — correcta pero más lenta. No se instalaron.

## Modelo y revisiones

- `nace-ai/drex-v1.5`, revisión fijada `328ee227c0425669d9f37fa82d400aa52c22139c`
  (23 ficheros; 4 shards safetensors ~17.9 GB + `head.pt` + `code/kev` +
  `serve.py`/`inference.py` + tokenizer).
- `config.json`: `Qwen3_5ForCausalLM`, `qwen3_5_text`, 32 capas híbridas
  (3 linear_attention por cada full_attention), hidden 4096,
  `max_position_embeddings` 262144, dtype bf16. `model.safetensors.index.json`:
  8 953 803 264 parámetros.
- `head.pt` (meta): `head_dim=256`, `temperature=1.0`, `option_isolation=False`,
  `state_bidir=False`, `lora=0` (sin LoRA: son los pesos completos),
  `weights_dtype=bf16`, `base=NischayDnk/drex-v1.5`, `base_revision=None`.
  La ficha declara como base `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B`.
- Carga: `kev.checkpoint.load` → CUDA, `torch.bfloat16`, atención `sdpa`
  (defecto del código en CUDA).

## Ventana (pre-registrado antes de medir)

El servidor codifica con `strict=True` y **rechaza** (HTTP 400) cualquier estado o
rama que supere su ventana (`KEV_CONTEXT`, 16384 por defecto): no hay truncado
silencioso posible. Antes de medir se codificaron los 194 estados+preguntas del
banco con el tokenizer del checkpoint y el `encode` de `code/kev` con
`max_state=max_branch=16384` strict:

- 0 `ContextOverflow` en 194/194; máx. estado 6253 tokens, máx. fila
  (estado+rama) 6370, máx. empaquetado **6578** (`papers32/P11`).
- Run primario sin truncado, con la ventana por defecto (16384); **sin variante
  `_trunc`** (como `clef_flash_9b_xpu`: ningún caso se acerca al límite).

## Ejecución

```bash
# <host> — servidor (PID real 83398 guardado en <ruta-local>, log <ruta-local>)
cd <ruta-local> && <ruta-local> serve.py \
  --model <ruta-local> --host 127.0.0.1 --port 8010 --name drex-v1.5
# portátil — túnel y batería
ssh -fNL 8010:127.0.0.1:8010 user@<host-lan>
python3 -m jevbench.run systemone_http --run drex_v15_9b \
  --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 --phases all+new
python3 -m jevbench.run systemone_http --run drex_v15_9b \
  --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 --phases adv4,adv5
```

- Smoke previo `smoke_drex_v15_9b` (ood,triage_es --limit 2): respuestas correctas
  (receta→`other`, factura duplicada→`admin`), probabilidades que suman 1.0;
  borrado tras validar.
- 11 fases, **194/194 casos, 0 errores**, `questions_hash` correcto en todas
  (comprobado con `load_phase`, no solo con el código de salida).
- Latencia **de cliente por túnel SSH**: mediana 381 ms/caso (media 897 ms;
  máx. 15,3 s en `papers32/P11`, ~6,6 k tokens). El servidor devuelve
  `latency_ms` en el nivel raíz de la respuesta, que el adaptador no registra;
  `usage.input_tokens` mediana 230,5 (máx. 6578).
- Harness en el cliente: git `72e7e5b`, Python 3.14.4, `meta.host=<host>`
  (cliente: no acredita la GPU del servidor).
- Limpieza: servidor propio parado (solo el PID de `serve.py`), túnel cerrado;
  venv `.venv-drex` y pesos `<ruta-local>` se quedan en <host>.
