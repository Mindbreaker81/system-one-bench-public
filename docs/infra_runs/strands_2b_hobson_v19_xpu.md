# Manifiesto: strands_2b_hobson_v19_xpu

Run: `strands_2b_hobson_v19_xpu` (JEV-51). Ejecutado 3-oct-2026.

## Host y hardware

- Host: estación de trabajo de la LAN (`<host>`, <host-lan>). No es un DGX Spark.
- Arquitectura: x86_64.
- GPU: Intel Arc Pro B70 (`Intel(R) Graphics [0xe223]`, 30.3 GiB reportados por torch).
  Una sola GPU XPU visible aunque el host expone dos nodos DRM (card0/card1).
- RAM: 43 GiB (41 GiB disponibles al arrancar).
- Dispositivo real de ejecución: `xpu` (PyTorch XPU; backend **no** oficialmente
  soportado por strands-decider — los validados son cuda/mps/cpu/mlx). Confirmado
  por `/health`: `"device": "xpu"`, sin fallback silencioso a CPU.

## Modelo

- Checkpoint: `StrandsAgents/strands-decider-2B-hobson-v19`, revisión HF fijada
  `bb282d786bc251fd4e3068de3ada9ddbb38127cd` (37 ficheros; `MANIFEST.sha256`
  verificado con `python -m strands_decider.hf_export verify` → ok).
- Base: `Qwen/Qwen3.5-2B-Base`, revisión realmente cargada
  `b1485b2fa6dfa1287294f269f5fb618e03d52d7c` (snapshot del caché HF; coincide con la
  revisión que `provenance.json` marca como *inferida* — el loader ignora el pin de
  provenance y resuelve `main`).
- Arquitectura: LoRA r16 α32 + cabeza pointer (24 slots) sobre el torso Qwen3.5-2B.
- dtype: bfloat16 (`hobson_config.json`), ventana `max_length` 4096, temperaturas por
  primitiva (noul 0.9107, choice 0.7342, score 1.3278). Sin retocar.

## Software

- Servidor: `strands-decider` instalado desde git
  `eb89e5c191b1ae6b4d36c9ba496b82c3bdd9ca1f` (`strands-decider==0.0.1.dev7+geb89e5c19`;
  el wheel PyPI 0.1.0 es anterior y carece de `--strict-window`/`--max-batch`).
- Python 3.12.14 (uv), venv independiente `<ruta-local>`
  (se preserva `.venv-clm-xpu`).
- torch 2.14.1+xpu (índice `download.pytorch.org/whl/xpu`), triton-xpu 3.8.0,
  transformers 5.18.0, peft 0.21.2, accelerate 1.15.0, huggingface-hub 1.33.0.

## Comando efectivo

```bash
strands-decider serve <snapshot> --device xpu --host 127.0.0.1 --port 8710 \
    --strict-window --max-batch 5 --model-name strands-decider-2B-hobson-v19
```

- PID 102138, log `<ruta-local>` (en <host>).
- `--host 127.0.0.1` (no hay flag para 0.0.0.0): el harness corre en la estación de
  trabajo local del usuario contra `http://127.0.0.1:8710` a través de un túnel SSH
  (`ssh -N -L 8710:127.0.0.1:8710 <host>`).
- `--strict-window`: un prompt que exceda la ventana 4096 devuelve HTTP 422 en vez de
  truncarse en silencio.
- prefix_cache activado (default; difiere ~2e-3 en bf16 según docs upstream).

## `/health` al arrancar

```json
{"status":"ok","model":"strands-decider-2B-hobson-v19",
 "checkpoint":".../snapshots/bb282d786bc251fd4e3068de3ada9ddbb38127cd",
 "base_model":"Qwen/Qwen3.5-2B-Base","num_slots":24,"max_length":4096,
 "temperature":0.9627721607677362,"device":"xpu","prefix_cache":true}
```

## Plan pre-registrado de ventana (antes de ejecutar)

- Run primario con `--strict-window`: los casos rechazados por ventana quedan como
  errores documentados en el JSON del run.
- Si >10 casos (≈5 % de 195) fallan por ventana, o papers32 pierde >3 casos (>9 %),
  se repiten las fases afectadas sin `--strict-window` como variante etiquetada
  `strands_2b_hobson_v19_xpu_trunc`, nunca mezclada con el run estricto.
- Estimación previa: solo papers32 tiene estados largos (máx ~23,3 k chars ≈ 5,8 k
  tokens); se esperan como mucho 1–3 rechazos.

## Smoke

`ood,triage_es --limit 2` correcto: receta/contrato → `domain=other`,
`T01_ebus_alergia` → bronchoscopia, `T02_factura_duplicada` → admin; probabilidades
finitas y suman 1. Latencia cliente ~0,1–3,2 s/caso en XPU.

## Latencia

El adaptador `systemone_http` registra `server_ms` = round-trip del cliente
(incluye túnel SSH). El `latency_ms` interno del servidor no se captura.

## Variante `strands_2b_hobson_v19_xpu_trunc` (3-oct, mismo día)

El run estricto dejó 1 error (P11 > 4096 tokens, HTTP 422), por debajo de los
umbrales pre-registrados. A petición del usuario se ejecutó además la batería
completa **sin `--strict-window`** — el comportamiento por defecto del servidor,
que trunca el estado en silencio — como run aparte `strands_2b_hobson_v19_xpu_trunc`
(mismo comando sin esa flag, mismo dispositivo xpu, mismo puerto 8710).

- 195/195 casos, 0 errores. Ajustado **21** (sin `*`; el estricto queda en 21*
  por excluir papers32 de la media).
- Los otros 194 casos comparten las mismas decisiones salvo una: en adv5 cambia
  una respuesta de `same_day` (76.0 estricto frente a 77.0 truncado; McNemar
  b=0, c=1). Las probabilidades difieren ligeramente en todas las fases: el
  truncado de P11 no deja el resto del modelo intacto.
- P11 truncado: acierta `domain` y `design`, falla `depth`/`practice`/`relevance`
  (~40 % de la pregunta); papers32 baja de 59.4 (sobre 31) a 59.1 (sobre 32).
- El run **primario** del marcador sigue siendo el estricto (`_xpu`); el truncado
  es la variante etiquetada que cubre el caso largo.
