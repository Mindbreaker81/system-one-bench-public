# Preflight JEV-103: `tev1_0.8b_r2`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: réplica r2 (§2). Run base: `tev1_0.8b`. Adaptador `tev1`, venv `.venv-tev1`.
Preflight archivado **antes** de adquirir.

## Pesos

- `togethercomputer/Tev1-0.8B-experimental` @ `6bb2dff14b38fea90ddb14d870166ccaf77374e9`
  (caché HF y MANIFEST-hf.tsv: igual).
- bf16, cuda, temperature=0, max_tokens=8, enable_thinking=false; torch 2.14.1+cu130,
  transformers 5.17.0 (igual que el run base).

## Host

- Host: <host> (dgx-spark-b), aarch64, GPU NVIDIA GB10 (128 GB unificada), CUDA 13.
- GPU libre antes de lanzar (`nvidia-smi`: 0 % de uso y sin procesos de cómputo; solo
  el contenedor `dashboard-sparkdash`, que no se toca). Comprobado el 14-oct-2026.
- Código: `<ruta-local>`, sincronizado por rsync desde el repo (árbol de este
  commit; sin `results/` salvo los runs base, comprobados idénticos por md5).
- Pesos desde la caché HF local, `HF_HUB_OFFLINE=1`; la revisión de la caché coincide con
  `<ruta-local>`.
