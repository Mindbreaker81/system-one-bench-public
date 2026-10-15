# Preflight JEV-103: `decider_4b_drexrev`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: revisor de Decider-4B (§3); cubre `_raw`, `_review`, `_audit` y `_avg`. Preflight archivado **antes** de adquirir.

## Pesos y servidor

- `nace-ai/drex-v1.5` @ `328ee227c0425669d9f37fa82d400aa52c22139c` (los 40 hex; los
  `.metadata` de descarga de todos los ficheros en `<ruta-local>` registran esa
  revisión). `head.pt` sha256 `9c9fe6c3b81f997e1813d4adc0f94b720afd317ecc8ce2f690edf56614755881`.
- Servidor: `serve.py` del repo, mismos flags que el run base:
  `serve.py --model <ruta-local> --host 127.0.0.1 --port 8010 --name drex-v1.5`
  (venv `.venv-drex`: torch 2.14.1+cu130, transformers 5.19.0, igual que JEV-101).
  `/health` → `{"status": "ok", "model": "drex-v1.5"}`.
- Host <host> (dgx-spark-a), GB10; GPU libre antes de arrancar (solo `dashboard-sparkdash`,
  que no se toca). Cliente: <host>, túnel `ssh -fNL 8010:127.0.0.1:8010`, adaptador
  `systemone_http`, alias `drex-v1.5`.
- Licencia: el usuario confirmó por escrito el 14-oct-2026 que el §2(c) no le aplica.
