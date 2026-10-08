# llm_cerebras_qwen38_27b_low_prob — Qwen3.8-27B en la API de Cerebras (JEV-54)

Run de `qwen-3.8-27b` contra `https://api.cerebras.ai/v1` con el adaptador `llm`
(system-one-adapter 0.2.1, `provider=openai` = protocolo compatible, no OpenAI).
Plan pre-registrado: `docs/plan_cerebras.md`. Ejecutado el 3-oct-2026 desde el
portátil; la inferencia es 100 % API Cerebras, sin hardware local. Mismo
protocolo que `llm_cerebras_gptoss120b_low_prob` salvo el modelo, las tarifas y
el pacing — **este modelo tiene límites muy superiores y corrió sin
`min_interval`**, así que `ms`/`usage.latency` sí miden latencia real.

## Límites de cuenta (cabeceras `x-ratelimit-*`, revalidados 3-oct-2026)

- `qwen-3.8-27b`: **450 req/min, 27 000 req/h**, 648 000/día; 150 k tok/min,
  9M tok/hora, 216M tok/día. La ejecución secuencial (~2 req/s pico) queda muy
  por debajo; sin pacing y sin 429.
- `gpt-oss-120b` (mismo día, misma clave): 5 req/min, 150 req/h — los límites
  son **por modelo**, no solo por cuenta. Lección: revalidar `x-ratelimit-*`
  por modelo antes de cada batería.

## Catálogo y precisión

- `GET /v1/models` autenticado: HTTP 200. Catálogo público formato OpenRouter:
  contexto 65 536, salida máx. 32 768, $0.99/$1.49 por Mtok (in/out).
- Precisión declarada: `fp16` (formato OpenRouter) frente a `FP16/FP8` (catálogo
  nativo): discrepancia conservada, no se afirma FP16 completo ni se infiere el
  detalle por capa.

## Configuración

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.run llm --run llm_cerebras_qwen38_27b_low_prob \
  --opt model=qwen-3.8-27b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt usd_in=0.99 --opt usd_out=1.49 \
  --phases all+new     # y luego --phases adv4,adv5 en llamada aparte
```

- `reasoning_effort=low` de Chat Completions; `temperature=0`;
  `reasoning_format=parsed` separa el razonamiento del JSON (no llega al scorer).
- El `low` de Qwen genera **más tokens de razonamiento** que el de GPT-OSS:
  salida mediana ~700 tokens/caso frente a ~230; `low` no es el mismo cómputo
  en ambos modelos (ya pre-registrado en el plan).

## Smoke (borrado tras validar)

- 8 casos (`ood,triage_es,papers32,adv3`, límite 2): 0 errores, `questions_hash`
  correcto, `resolved=qwen-3.8-27b`, `attempts=1`, `n_retries_malformed=0`.
- OOD `domain=other`, factura duplicada `admin` (respuestas sanas).
- Caso más largo (`papers32/P11`, 23 335 caracteres): 7 458 in / 1 247 out,
  JSON válido, 1.39 s, $0.0092. Sin consultar su GT.
- Latencia smoke: 0.39-1.44 s/caso.

## Resultado de la batería (3-oct-2026)

- **195/195 casos, 11 fases, 0 errores**, `questions_hash` correcto en todas.
  `all+new` en 126 s + `adv4,adv5` en 36 s (~3 min en total, ~75× más rápido que
  el run de GPT-OSS-120B por la diferencia de límites).
- 0× 429, `n_retries_malformed=0` en los 195 casos.
- Coste total medido **$0.43760** (~$0.0022/caso): tokens 239 394 entrada +
  134 630 salida = 374 024. Más caro que GPT-OSS-120B ($0.12) a pesar de precios
  similares por la salida de razonamiento ~2.7× mayor.
- `ms` mediana **772 ms** (máx 2 443 ms): latencia real, sin pacing.
