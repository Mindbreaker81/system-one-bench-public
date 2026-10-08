# llm_cerebras_gptoss120b_low_prob — GPT-OSS-120B en la API de Cerebras (JEV-54)

Run de `gpt-oss-120b` contra `https://api.cerebras.ai/v1` con el adaptador `llm`
(system-one-adapter 0.2.1, `provider=openai` = protocolo compatible, no OpenAI).
Plan pre-registrado: `docs/plan_cerebras.md`. Ejecutado el 3-oct-2026 desde el
portátil (`<host>`, x86_64); la inferencia es 100 % API Cerebras, sin hardware local.

## Credenciales y transporte

- `CEREBRAS_API_KEY` de `.env`, asignada a `OPENAI_API_KEY` solo en el subshell de
  ejecución (el cargador usa `setdefault` y conserva el override). No se pasó por
  `--opt`, no se escribió en disco remoto ni aparece en `meta`.
- El endpoint exige `User-Agent` explícito: el primer probe de catálogo con el UA por
  defecto de urllib devolvió 403; con `system-one-bench/<versión>` responde 200. El SDK
  de OpenAI envía su propio UA y no tuvo problema.
- API: Chat Completions (el endpoint compatible resuelve a `chat_completions`, no a la
  API Responses). `max_tokens` va como `max_tokens` (no `max_completion_tokens`).

## Catálogo y límites de cuenta (revalidado 3-oct-2026)

- `GET /v1/models` autenticado: HTTP 200, lista `gpt-oss-120b` y `qwen-3.8-27b`.
- Catálogo público formato OpenRouter: `gpt-oss-120b` `fp16`, contexto 131 072,
  salida máx. 40 960, $0.35/$0.75 por Mtok (in/out). El catálogo nativo declara
  `FP16/8 (weights only)`: discrepancia conservada, no se afirma FP16 completo.
- **Límites de la cuenta (cabeceras `x-ratelimit-*` del servicio):**
  5 peticiones/minuto, **150 peticiones/hora**, 2 400/día;
  30 k tokens/minuto, 1M tokens/hora y 1M tokens/día.
- Sin pacing, el smoke (12 casos secuenciales a ~0.4-2 s cada uno) recibió 3 veces
  `TypeSafeRateLimitError: 429 Requests per minute limit exceeded`. El adaptador no
  reintenta 429 (tenacity solo corrige JSON mal formado) y `run.py` es secuencial.

## Cambio de harness: `min_interval`

Para respetar los límites sin pasar por un proxy se añadió la opción `min_interval=<s>`
al adaptador `llm` (`_pace()` en `BoundedProvider`: espacia el *inicio* de peticiones
HTTP consecutivas, correcciones por JSON mal formado incluidas). Queda registrada en
`meta`. Test: `tests/test_llm_adapter.py::test_min_interval_spaces_requests`.

- Con `min_interval=27`: ~2.2 peticiones/min (~133/hora), bajo ambos topes con margen
  para las correcciones. 195 casos ≈ 90 min.
- **Efecto conocido en telemetría:** `usage.latency` y `ms` incluyen la espera del
  pacing (los casos espaciados registran ~24-27 s aunque la API responde en ~0.4-2 s).
  Para latencia real usar los casos no espaciados del smoke o restar la espera.

## Smoke (borrado tras validar)

- 12 casos (`ood,triage_es,papers32,adv3`, límite 2 por fase + reintentos de los 429):
  0 errores con pacing, `questions_hash` correcto, `resolved=gpt-oss-120b`,
  `attempts=1` y `n_retries_malformed=0` en todos.
- Respuestas sanas: OOD `domain=other`, factura duplicada `admin`.
- Uso medido: entrada mediana 985 / máx 2 138 tokens; salida mediana 226 / máx 415;
  coste total $0.00735 → proyección ~$0.12 por batería.
- Caso más largo (`papers32/P11`, estado 23 335 caracteres): petición aparte
  7 092 in / 347 out, JSON válido, 0.74 s, $0.0027. Sin consultar su GT.
- Latencia API real (casos no espaciados): 0.37-2.16 s, mediana ~0.45 s.

## Batería

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.run llm --run llm_cerebras_gptoss120b_low_prob \
  --opt model=gpt-oss-120b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=probabilities --opt structured=true --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt min_interval=27 --opt usd_in=0.35 --opt usd_out=0.75 \
  --phases all+new     # y luego --phases adv4,adv5 en llamada aparte
```

- `extra_body`: `temperature=0` (muestreo determinista a nivel de parámetro; el
  servicio no garantiza determinismo) y `reasoning_format=parsed` (razonamiento
  separado del contenido JSON; no llega al scorer).
- `reasoning_effort=low` va como `reasoning_effort` de Chat Completions. Los tokens
  de razonamiento cuentan como salida en `usage` y en la factura.

## Resultado de la batería (3-oct-2026)

- **195/195 casos, 11 fases, 0 errores**, `questions_hash` correcto en todas.
  `all+new` en 4 159 s + `adv4,adv5` en 1 054 s (~87 min en total).
- **0 peticiones 429 durante la batería** con `min_interval=27` (los únicos 429
  fueron los 3 del smoke sin pacing). `n_retries_malformed=0` en los 195 casos.
- Coste total medido **$0.12152** (~$0.00062/caso), muy por debajo del techo
  autorizado de $2: tokens 239 124 entrada + 50 430 salida = 289 554.
- `ms` mediana 27 000 ms/caso ≈ todo pacing; latencia API real estimada ~0.4-0.9 s
  (`usage.latency` incluye la espera; solo los 2 primeros casos de cada lanzamiento
  quedaron sin espaciar: 0.53-0.57 s; smoke sin pacing: 0.37-2.16 s).
- El segundo lanzamiento (`adv4,adv5`) arrancó dentro de la misma hora y no topó
  límites: la primera petición va sin espera por diseño.
