# Preflight JEV-103: `clm_v0.1_8b_alert_raw`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: alerta de una pasada (§1). Run base: `clm_v0.1_8b`. Preflight archivado **antes** de adquirir.

## Pesos y servidor

- Base `Qwen/Qwen3-8B` @ `b968826d9c46dd6066d109eabc6255188de91218` (única snapshot de la
  caché HF de <host>; igual en `<ruta-local>`).
- Cabeza `CLM_v0.1-8B.pt` sha256
  `b2b4a8c9c2d39263eff78a351eb909a342ce9b3bf21a3f07c1d1bf15f1c4eda5` (revisión HF
  `e939398d4556fcd9400c76fa8c5a513202f42b0a`), igual que el run base.
- Embeddings: vLLM `0.30.1rc1.dev558+g0cbac6cd1.xpu`, torch 2.14.0+xpu, mismos flags que
  el 3-oct (`<ruta-local>`): `vllm serve Qwen/Qwen3-8B --served-model-name
  qwen3-8b --runner pooling --enforce-eager --enable-prefix-caching --max-model-len 2048
  --gpu-memory-utilization 0.80 --max-num-seqs 32 --host 127.0.0.1 --port 8090`.
- Cabeza: `contrastive-lm` 0.1.0, `clm-serve --no-ui --emb-url
  http://127.0.0.1:8090/v1/embeddings --emb-model qwen3-8b --max-tokens 2048 --host 0.0.0.0
  --port 8700 --device cpu --action-cache 0` (`<ruta-local>`, sin cambios).
  `/health` → `{"ok":true,"embedder":true,"models":["clm-latest","clm-raw"],"cache":null}`.
- Host <host> (<host>), Intel Arc Pro B70, encendido el 14-oct por Wake-on-LAN; sin
  otros procesos en la GPU. Cliente: <host>, alias `clm-latest`.
