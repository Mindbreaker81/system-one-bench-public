# llm_cerebras_qwen38_27b_nostruct_disc — Qwen3.8-27B Cerebras discrete sin esquema (JEV-61)

Run de `qwen-3.8-27b` contra `https://api.cerebras.ai/v1` con el adaptador `llm`
(system-one-adapter 0.2.1, `provider=openai`), en modo `discrete` con
`structured=false` + `normalize=true`. Cuarta celda de la cuadrícula 2×2
(mode × structured) de Cerebras, pre-registrada en JEV-61 (comentario
4-oct-2026). Ejecutado el 4-oct-2026 desde el portátil; inferencia 100 % API.

## Configuración

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.run llm --run llm_cerebras_qwen38_27b_nostruct_disc \
  --opt model=qwen-3.8-27b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=discrete --opt structured=false --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt usd_in=0.99 --opt usd_out=1.49 \
  --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5
```

`questions_hash` 9a81e9763d94.

## Smoke previo (`results/smoke_cerebras_qwen38_nostruct_disc/`)

- 8 casos: 0 errores, 0 reintentos por malformado — el JSON inducido por prompt
  (sin esquema forzado) sale bien formado en Cerebras también en discrete.

## Resultado de la batería (4-oct-2026)

- **195/195 casos, 11 fases, 0 errores**, 1 reintento por malformado (papers32/P23), 98 s.
- Coste total medido **$0.27044** (~$0.0014/caso, el más barato de la
  cuadrícula); mediana **462 ms**.
- **Ajustado 58**, igual por redondeo al run discrete con esquema:
  no implica las mismas decisiones ni equivalencia. Cero errores finales,
  pero el JSON de un caso requirió corrección.
- Cuadrícula 2×2 completa de Cerebras qwen-3.8-27b (ajustado):

  | | structured=true | structured=false |
  |---|---|---|
  | **probabilities** | 59 (`low_prob`) | **65** (`nostruct_prob`) |
  | **discrete** | 58 (`disc`) | 58 (`nostruct_disc`) |

  Las cuatro celdas completan la batería. Cada variante sin esquema tuvo
  un reintento por malformado. Choice casi uniformes: 0/259 en 11 fases,
  0/219 en las 9 del resumen. No prueba independencia del esquema ni
  permite excluirlo como factor en la brecha nube/local.

## Notas

- Marcador, `docs/modelos.md`, webs y CHANGELOG diferidos al cierre de JEV-58
  (ver manifiesto `llm_cerebras_qwen38_27b_nostruct_prob.md`).
