# Preflight JEV-103: `strands_2b_hobson_v19_xpu_r2`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: réplica r2 (§2). Run base: `strands_2b_hobson_v19_xpu`. Preflight archivado **antes** de adquirir.

## Pesos y servidor

- `StrandsAgents/strands-decider-2B-hobson-v19` @ `bb282d786bc251fd4e3068de3ada9ddbb38127cd`
  y base `Qwen/Qwen3.5-2B-Base` @ `b1485b2fa6dfa1287294f269f5fb618e03d52d7c` (únicas
  snapshots de la caché HF de <host>, `HF_HUB_OFFLINE=1`).
- Servidor `strands-decider` `0.0.1.dev7+geb89e5c19` (git `eb89e5c`), torch 2.14.1+xpu,
  transformers 5.18.0, peft 0.21.2 (venv `.venv-strands`, igual que el run base).
- Mismo comando que el run base: `strands-decider serve <snapshot> --device xpu --host
  127.0.0.1 --port 8710 --strict-window --max-batch 5 --model-name
  strands-decider-2B-hobson-v19`. Se arranca cuando acaba CLM (una sola GPU).
- Cliente: <host>, túnel `ssh -fNL 8710:127.0.0.1:8710` a <host>.
