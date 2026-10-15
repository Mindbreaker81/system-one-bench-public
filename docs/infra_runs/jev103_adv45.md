# JEV-103 paso 0 — completar la batería (adv4/adv5) en los runs antiguos

16 runs: los 14 que no tenían adv4/adv5 y las dos variantes GLiNER bare restantes.

Fecha: 14-oct-2026. Código: commit `edcc8b5` sincronizado por rsync (sin `results/`).
Batería estándar, sin pre-registro nuevo: mismas preguntas (`questions_hash` 9a81e9763d94),
mismo GT vigente (v5), mismo scorer. Las fases ya existentes **no se re-ejecutaron**; solo se
añadieron ficheros de fase nuevos a cada run (`--phases`, resumible, `--retry-errors`).

## Qué se ejecutó

| run | fases añadidas | host · venv | adaptador y opciones (idénticas al run original) |
|---|---|---|---|
| decider_0.8b | adv4, adv5 | <host> · .venv-decider | `decider` model=Mapika/decider-0.8b |
| decider_2b | adv4, adv5 | <host> · .venv-decider | `decider` model=Mapika/decider-2b |
| decider_35b_a3b | adv4, adv5 | <host> · .venv-decider | `decider` model=Mapika/decider-35b-a3b use_graphs=false |
| decider_35b_a3b_nvfp4 | adv4, adv5 | <host> · .venv-vllm (`scripts/serve_decider_nvfp4.sh`) | `systemone_http` model=Mapika/decider-35b-a3b-nvfp4 |
| anyjev_qwen3_{1.7b,8b,32b}_l0 | adv4, adv5 | <host> · .venv-anyjev | `anyjev` model=Qwen/Qwen3-{1.7B,8B,32B} |
| gliner_decide_desc | adv4, adv5 | <host> · .venv-gliner | `gliner` model=fastino/GLiNER2.5-Decide labels=desc device=cuda |
| gliner_decide_bare | triage_ext_es/en, adv3, adv4, adv5 | <host> · .venv-gliner | labels=bare |
| gliner_decide_1b_desc | triage_ext_es/en, adv3, adv4, adv5 | <host> · .venv-gliner | model=fastino/GLiNER2.5-Decide-1B labels=desc |
| gliner_multi_decide_desc | triage_ext_es/en, adv3, adv4, adv5 | <host> · .venv-gliner | model=fastino/GLiNER2.5-multi-Decide labels=desc |
| laya_router / laya_typed | adv4, adv5 | <host> · .venv-laya | `laya` variant=router / typed-decisions |
| julia_1 | adv4, adv5 | <host> (CPU) · .venv-julia | `julia` |
| gliner_decide_1b_bare | triage_ext_es/en, adv3, adv4, adv5 | <host> · .venv-gliner | model=fastino/GLiNER2.5-Decide-1B labels=bare (añadido 15:27, misma sesión) |
| gliner_multi_decide_bare | triage_ext_es/en, adv3, adv4, adv5 | <host> · .venv-gliner | model=fastino/GLiNER2.5-multi-Decide labels=bare (añadido 15:27) |

Colas: `scripts/jev103_q80.sh`, `scripts/jev103_q81.sh`, `scripts/jev103_q81b.sh` (solo en los
Spark, no versionados), sobre `scripts/queue.sh`. `HF_HUB_OFFLINE=1`: nada se descargó de Internet.

## Pesos y software

Revisiones en caché HF de cada Spark, iguales a las de `<ruta-local>`
(un solo snapshot por repo):
decider-0.8b `a0a01d6f`, decider-2b `533964da`, decider-35b-a3b `91470e65`,
decider-35b-a3b-nvfp4 `798555c0`, Qwen3-1.7B `70d244cc`, Qwen3-8B `b968826d`,
Qwen3-32B `9216db57`, GLiNER2.5-Decide `7ee5da4c`, -1B `52c94d3b`, -multi `6bc1d43d`,
laya `55cf4c4e`. Julia-1: copia local `models/Julia-1` (sin revisión fijada, como el run original).

Venvs de los Spark sin cambios desde los runs originales: torch 2.14.0+cu130, transformers
5.17.0; decider-ai 1.5.0, anyjev 0.0.2, gliner2 2.0.0, laya 0.3.20, vLLM 0.29.0.
Matiz (revisión R117): no se afirma identidad literal de todo el entorno. Las fases nuevas de las
variantes GLiNER registran Python **3.12.14** frente a 3.12.3 en adv1 (la venv del Spark se recreó
con el Python de uv entre ambas fechas, con los mismos paquetes), y el adaptador `gliner` añade
ahora `meta.score="ev"`. No cambia la semántica: en adv1 de las seis variantes el `score`
histórico coincide exactamente con la esperanza de sus probabilidades (máx. |score−EV| = 0).
**Desviación declarada (Julia):** la `.venv-julia` original dejó de arrancar porque el sistema
pasó de Python 3.12 a 3.14; se recreó con Python 3.12.14 gestionado por uv y las **mismas
versiones fijadas** de los 38 paquetes (torch 2.14.0+cpu, transformers 5.0.0) + editable
`models/Julia-1`. La venv antigua se conserva como `.venv-julia.broken-py312-20261014`.

## Integridad

47 ficheros de fase nuevos (37 + 10 de las dos GLiNER bare añadidas después), 0 errores, recuentos esperados (20 por adv, 26 por ext),
`adapter/model/opts/dtype/host` idénticos a la fase adv1 de cada run.

## Efecto en el ajustado (11 fases; antes `*` = fases incompletas)

| run | antes | ahora |
|---|---:|---:|
| decider_35b_a3b | 41* | 39 |
| decider_35b_a3b_nvfp4 | 35* | 33 |
| anyjev_qwen3_32b_l0 | 30* | 21 |
| decider_2b | 21* | 20 |
| anyjev_qwen3_8b_l0 | 16* | 13 |
| decider_0.8b | 10* | 13 |
| anyjev_qwen3_1.7b_l0 | 0* | −3 |
| gliner_decide_desc | −5* | −2 |
| gliner_decide_bare | −42* | −13 |
| gliner_decide_1b_desc | −45* | −22 |
| gliner_multi_decide_desc | −87* | −45 |
| laya_router | −21* | −22 |
| laya_typed | −27* | −26 |
| julia_1 | −83* | −89 |
| gliner_decide_1b_bare | 6 fases (82/194) | −22 |
| gliner_multi_decide_bare | 6 fases (82/194) | −49 |

Mayoría = 0. Las cifras «antes» promediaban menos fases y no eran comparables con los runs de
11 fases; las nuevas sí. Ningún cambio de orden se afirma sin McNemar.
