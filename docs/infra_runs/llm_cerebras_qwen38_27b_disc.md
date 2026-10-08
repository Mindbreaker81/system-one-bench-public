# llm_cerebras_qwen38_27b_disc — Qwen3.8-27B Cerebras en modo discrete (JEV-61)

Run de `qwen-3.8-27b` contra `https://api.cerebras.ai/v1` con el adaptador `llm`
(system-one-adapter 0.2.1, `provider=openai`), en modo `discrete` (respuesta
única, sin distribuciones) con `structured=true`. Ampliación pre-registrada de
JEV-61 (comentario del 4-oct-2026): completa el eje `mode` de la cuadrícula
Cerebras. Ejecutado el 4-oct-2026 desde el portátil; inferencia 100 % API.

## Configuración

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.run llm --run llm_cerebras_qwen38_27b_disc \
  --opt model=qwen-3.8-27b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=discrete --opt structured=true --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt usd_in=0.99 --opt usd_out=1.49 \
  --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5
```

Idéntica a `llm_cerebras_qwen38_27b_low_prob` salvo `mode=discrete`.
`questions_hash` 9a81e9763d94.

## Smoke previo (`results/smoke_cerebras_qwen38_disc/`)

- 8 casos: 0 errores, 0 reintentos por malformado. Las respuestas `discrete`
  salen como valores duros (choice único, score entero, noul 0/1).

## Resultado de la batería (4-oct-2026)

- **195/195 casos, 11 fases, 0 errores**, 0 reintentos por malformado, 119 s.
- Coste total medido **$0.29499** (~$0.0015/caso; más barato que `prob` al no
  emitir el vector de probabilidades); mediana **575 ms**.
- **Ajustado 58** (referencia `prob+struct`: 59; `jev_v3`: 45). Brier noul
  peor (0.077 vs 0.060): las respuestas 0/1 no expresan incertidumbre —
  esperable, no es degradación de decisión.
- Peor punto: adv2 departamento 5/10 (prob: 6/10): el modo discrete pierde algo
  de matiz en adversarial-2, dentro del ruido (IC solapados).

## Notas

- Marcador, `docs/modelos.md`, webs y CHANGELOG diferidos al cierre de JEV-58
  (ver manifiesto `llm_cerebras_qwen38_27b_nostruct_prob.md`).
- Run hermano: `llm_cerebras_qwen38_27b_nostruct_disc` (misma celda con
  `structured=false`).
