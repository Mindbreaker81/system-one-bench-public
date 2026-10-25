# Manifiesto — bscribe_verif (JEV-111/112)

GT v1 congelado en `b4429e0d`; enmiendas E1 (`371ded88`, formato wire de `noul`) y E2 (`3d3b6c39`,
variante CUDA). `questions_hash` `e342efcef902`. Código `jevbench/bscribe_verif.py` y adaptador `clef`
idénticos al repo (sha256 comprobado antes de lanzar).

| run | host | modelo | entorno | fecha |
|---|---|---|---|---|
| `bv_clef_flash_9b_xpu` | <host> (Intel Arc Pro B70) | `Cloudflare/clef-flash` @ `17f0b0ad64efb65d273590632833508766b2aae6`, bf16, `device=xpu` | `.venv-clef-flash-xpu` | 25-oct-2026 |
| `bv_clef_flash_9b_cuda` | DGX Spark <host> (GB10) | la misma revisión, bf16, `device=cuda` | `.venv-clef` (torch 2.14.1+cu130, transformers 5.17.0), copiado de <host> | 25-oct-2026 |
| `bv_clef_flash_9b_xpu_r2` | <host>, tras `apt full-upgrade` (10 paquetes, ninguno de GPU) y reinicio | igual que el principal | `.venv-clef-flash-xpu` | 25-oct-2026 |
| `bv_clef_flash_9b_xpu_q8` | <host> | igual que el principal, `--max-questions 8` | `.venv-clef-flash-xpu` | 25-oct-2026 |
| `bv_jev114_typesafe` | <host> (cliente API) | Jev `jev-latest` → `jev-1.14.0`, API TypeSafe, adaptador `jev`, `retries=3` | Python del sistema | 25-oct-2026 |
| `bv_elephant_1_local` | DGX Spark <host> (GB10) | `baselabs/elephant-1` @ `c54a55c2…`, adaptador `baselabs` | `.venv-baselabs` (ver `baselabs_local.md`) | 25-oct-2026 |
| `bv_mammoth_1_local` | DGX Spark <host> (GB10) | `baselabs/mammoth-1` @ `03007ab3…`, adaptador `baselabs` | `.venv-baselabs` | 25-oct-2026 |
| `bv_clef_27b` | DGX Spark <host> (GB10) | `Cloudflare/clef` @ `2f3de3dd85f379784083b0814d997ab627200f0c`, bf16, `device=cuda` | `.venv-clef` | 25-oct-2026 |

- Pesos de Clef-Flash en <host> copiados desde la caché de <host> por la LAN (snapshot desreferenciado,
  18 GB), sin descarga de Internet. Como esa copia no tiene los blobs de HF, el run se lanzó con un
  envoltorio que fija `local_files_only=True` en `snapshot_download` (sin otro cambio).
- Diagnóstico del NaN (B6__reference, 16 preguntas en una llamada): XPU bf16 → NaN en las 8 primeras,
  idéntico al repetir; CPU bf16 y fp32 → valores válidos y deterministas; XPU con solo esas 8
  preguntas → válidos.
- `max_length` 16384 (por defecto del adaptador); el estado más largo (B6, 1.395 caracteres) cabe.
