# llm_cerebras_qwen38_27b_nostruct_prob — Qwen3.8-27B Cerebras sin salida estructurada (JEV-61)

Run de `qwen-3.8-27b` contra `https://api.cerebras.ai/v1` con el adaptador `llm`
(system-one-adapter 0.2.1, `provider=openai`), en modo `probabilities` con
`structured=false` + `normalize=true`. Celda que faltaba de la cuadrícula
Cerebras × structured on/off (pre-registro: descripción de JEV-61 + comentario
del 4-oct-2026 con el alcance ampliado). Ejecutado el 4-oct-2026 desde el
portátil; inferencia 100 % API Cerebras, sin hardware local.

## Configuración

```bash
set -a; . ./.env; set +a; export OPENAI_API_KEY="$CEREBRAS_API_KEY"
.venv-llm/bin/python -m jevbench.run llm --run llm_cerebras_qwen38_27b_nostruct_prob \
  --opt model=qwen-3.8-27b --opt base_url=https://api.cerebras.ai/v1 \
  --opt mode=probabilities --opt structured=false --opt normalize=true \
  --opt retries_malformed=2 --opt reasoning_effort=low \
  --opt 'extra_body={"temperature":0,"reasoning_format":"parsed"}' \
  --opt max_tokens=8192 --opt timeout=120 --opt case_timeout=300 \
  --opt usd_in=0.99 --opt usd_out=1.49 \
  --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5
```

Idéntica a `llm_cerebras_qwen38_27b_low_prob` salvo `structured=false`.
`questions_hash` depende de la fase (triaje/adv: 9a81e9763d94);
los hashes de cada fase coinciden con su batería correspondiente.

## Smoke previo (`results/smoke_cerebras_qwen38_nostruct_prob/`)

- 8 casos (`ood,triage_es,papers32,adv3`, límite 2): 0 errores, 0 reintentos por
  malformado, distribuciones sanas (nada de ceros).
- Cabeceras `x-ratelimit` revalidadas 4-oct-2026: 450 req/min, 27 000 req/h,
  150 k tok/min — sin cambios respecto al 3-oct; sin pacing.

## Resultado de la batería (4-oct-2026)

- **195/195 casos, 11 fases, 0 errores**, 1 reintento por malformado (triage_ext_en/T21_rivaroxaban_ebus), 131 s.
- Coste total medido **$0.39553** (~$0.0020/caso); mediana **636 ms**.
- Elecciones casi uniformes: 0/259 en 11 fases; el resumen usa 0/219
  en 9 fases sin adv4/adv5. No inferir ceros crudos de salidas normalizadas.
- **Ajustado 65** vs 59 con esquema: mínimo McNemar por pregunta **0.0625**
  (triage_ext_es/urgency, discordancias 5–0 en favor del run con esquema).
  Sin significación al 5 % ni corrección de multiplicidad; no equivalencia
  o independencia del esquema demostrada.
- Ambas rutas funcionan en esta muestra. La comparación nube/local mezcla
  precisión, razonamiento, muestreo y backend; no aísla la causa de la brecha.
- Mediana de casos de las 11 fases ~636 ms; resumen de 9 fases 627 ms.

## Notas

- Marcador (`docs/resultados.md`), `docs/modelos.md`, webs y CHANGELOG se
  actualizan al cierre de JEV-58 (working tree compartido, cambios suyos sin
  commit). Run a añadir a `docs/resultados_runs.txt` en ese momento.
- Runs hermanos de la misma sesión: `llm_cerebras_qwen38_27b_disc`,
  `llm_cerebras_qwen38_27b_nostruct_disc`, `jev_cerebrasqwenrev_*`,
  `jev_cerebrasqwennsrev_*` (ver sus manifiestos).
