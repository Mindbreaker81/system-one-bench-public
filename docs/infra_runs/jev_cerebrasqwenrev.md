# jev_cerebrasqwenrev / jev_cerebrasqwennsrev — Jev con revisor Cerebras qwen-3.8-27b (JEV-61)

Cascada **Jev → revisor Cerebras**: `jev_v3` como pasada-1 (D1) y
`qwen-3.8-27b` (API Cerebras, adaptador `llm`, mode=probabilities) como
pasada-2 auditora, en las dos variantes de salida estructurada del revisor.
Pre-registrado como ampliación de JEV-61 (comentario 4-oct-2026: "todo por
API, sin tocar los DGX"). Ejecutado el 4-oct-2026 desde el portátil.

- `jev_cerebrasqwenrev_*` — revisor con `structured=true`
- `jev_cerebrasqwennsrev_*` — revisor con `structured=false`
- Cada prefijo genera `_raw` (respuestas de pasada-2), `_review`, `_audit`
  (override si el revisor marca la respuesta incorrecta o hay manipulación) y
  `_avg` (media), como el resto de cascadas. `--control ""`: `jev_avg2_control`
  ya existe de la cascada Jev→Jev y no se regenera.

## Configuración

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.cascade --d1 jev_v3 --adapter llm \
  --prefix jev_cerebrasqwenrev --control "" \
  --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5 \
  --opt model=qwen-3.8-27b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt usd_in=0.99 --opt usd_out=1.49
# y la misma llamada con --prefix jev_cerebrasqwennsrev --opt structured=false
```

`questions_hash` de la pasada-2: befaae4c4fe6 (preguntas de auditoría, propias
de la cascada — no comparables con las de pasada-1).

## Resultado (4-oct-2026)

- **195/195 casos revisados en cada variante**, 0 errores.
- Coste pasada-2: **$0.7841** (struct) / **$0.7313** (nostruct); mediana por
  caso 1233 / 1078 ms (prompts de revisión más grandes: texto + respuestas de
  pasada-1 + preguntas `__ok` + manipulación).
- **Ajustado**:

  | run | ajustado |
  |---|---|
  | `jev_cerebrasqwennsrev_audit` | **69** |
  | `jev_cerebrasqwenrev_audit` | **68** |
  | `jev_cerebrasqwenrev_avg` | 68 |
  | `jev_cerebrasqwennsrev_avg` | 67 |
  | `jev_cascade_audit` (revisor Jev, referencia) | 64 |
  | `jev_v3` (una pasada) | 45 |

- McNemar por pregunta frente a `jev_cascade_audit`: **todo p ≥ 0.12** —
  mejora de ranking, no significativa. Notable: `skip LOO` 9/10 en ambos
  `_audit` (vs 5/10 de la cascada Jev→Jev).
- Las dos variantes del revisor dan prácticamente lo mismo (68 vs 69):
  coherente con que en Cerebras el modo de salida no importa.

## Notas

- Marcador, `docs/modelos.md`, webs y CHANGELOG diferidos al cierre de JEV-58
  (ver manifiesto `llm_cerebras_qwen38_27b_nostruct_prob.md`). Runs a añadir a
  `docs/resultados_runs.txt` al regenerar: `jev_cerebrasqwenrev_audit`,
  `jev_cerebrasqwenrev_avg`, `jev_cerebrasqwennsrev_audit`,
  `jev_cerebrasqwennsrev_avg` (los `_raw`/`_review` también están en results/
  por reproducibilidad).
