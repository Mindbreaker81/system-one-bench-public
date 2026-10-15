# Preflight JEV-103: `nimble_9b_d1`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: rotación `department:d1` (§2). Run base: `nimble_9b`. Adaptador `nimble`, venv `.venv-nimble`.
Preflight archivado **antes** de adquirir.

## Pesos

- `bespokelabs/Bespoke-Nimble-9B` @ `bd792f44ec8e265be861bfcdf4e05967ffe0e858`
  (caché HF y MANIFEST-hf.tsv: igual; LoRA).
- Base `Qwen/Qwen3.5-9B` @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a` (caché y MANIFEST: igual).
- bf16, cuda, T=1.0 del adaptador; torch 2.14.1+cu130, transformers 5.17.0 (igual que el run base).

## Host

- Host: <host> (dgx-spark-b), aarch64, GPU NVIDIA GB10 (128 GB unificada), CUDA 13.
- GPU libre antes de lanzar (`nvidia-smi`: 0 % de uso y sin procesos de cómputo; solo
  el contenedor `dashboard-sparkdash`, que no se toca). Comprobado el 14-oct-2026.
- Código: `<ruta-local>`, sincronizado por rsync desde el repo (árbol de este
  commit; sin `results/` salvo los runs base, comprobados idénticos por md5).
- Pesos desde la caché HF local, `HF_HUB_OFFLINE=1`; la revisión de la caché coincide con
  `<ruta-local>`.
