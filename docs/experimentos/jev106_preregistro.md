# JEV-106 — Pre-registro: Drex v2.0, Classify-1 y Perplexity Decider V1.1 27B

Congelado el 16-oct-2026 **antes** de ejecutar la batería. Solo se midió un smoke de 2 casos
× (triage_es, papers32, adv3) por modelo para comprobar el contrato; esas salidas no se
usan en el análisis (`/var/tmp/smoke_*`, fuera del repo).

## Configuraciones

Las tres van por la Decisions API de OpenRouter (`/api/alpha/decisions`) con el adaptador
`jev` (`--opt provider=openrouter --opt retries=3`), igual que `jev_ms_decision1` (JEV-90).
Sin cambios en `battery.py`, `score.py` ni el adaptador.

| run | `--opt model=` | snapshot resuelto en el smoke |
|---|---|---|
| `drex_v20_or` | `nace-ai/drex-v2.0` | `nace-ai/drex-v2.0-20261009` |
| `classify1_or` | `scaledown/classify-1` | `scaledown/classify-1-20260928` |
| `pplx_decider_v11_27b_or` | `perplexity/pplx-decider-v1.1-27b` | `perplexity/pplx-decider-v1.1-27b-20261006` |

- Fases: `all+new` y, en llamada aparte, `adv4,adv5` (194 casos, GT v5).
- Guardas de coste: `--max-case-cost 0.01 --max-cost 0.10` por llamada.
- Errores transitorios: `--retry-errors` sobre el mismo run, sin cambiar la configuración.
  Si el snapshot resuelto cambia a mitad de batería, el run se descarta y se repite entero.
  Un rechazo o error persistente se informa como tal (no se rellena ni se puntúa como fallo
  silencioso).

## Análisis (fijado de antemano)

1. `python3 -m jevbench.score --summary --adj-ci` con la línea base de mayoría, `jev_v3`,
   `jev_ms_decision1`, `drex_v15_9b` y los tres runs nuevos. El ajustado es descriptivo.
2. **Frente a `jev_v3`**: McNemar en las 53 celdas (11 fases) para cada run nuevo; Holm
   dentro de cada familia de 53. Mejor/peor solo si una celda sobrevive a Holm; si no,
   «sin diferencias significativas».
3. **Drex v2.0 frente a Drex v1.5** (`drex_v15_9b`): mismas 53 celdas y Holm. La lectura es
   de configuración, no de versión: v1.5 se sirvió en local (`serve.py`, DGX) y v2.0 por
   OpenRouter, así que una diferencia no se atribuye solo al modelo.
4. Coste y latencia: los medidos en los JSON (cliente, por OpenRouter), no el tarifario.
5. Fuera de alcance de este pre-registro: alerta de una pasada, revisor de Decider-4B,
   rotación d1 y réplica r2. Si se hacen, irán en una enmienda congelada antes de medirlos.

## Enmienda E1 (16-oct-2026, congelada antes de medir)

Escrita y confirmada en git **antes** de lanzar ninguna batería de los runs de abajo (solo se
habrán hecho smokes de 2 casos × `triage_es`, `papers32`, `adv3` por modelo en
`/var/tmp/jev106/smoke_*`, fuera del repo y fuera del análisis). Amplía el pre-registro a
10 decisores más servidos por la Decisions API de OpenRouter.

### Runs

| run | `--opt model=` | homólogo local |
|---|---|---|
| `clef_omni_or` | `cloudflare/clef-omni` | — |
| `solar_decide_or` | `upstage/solar-decide` | — |
| `solar_decide_flash_or` | `upstage/solar-decide-flash` | — |
| `kev_4b_or` | `jaredpalmer/kev-4b` | — |
| `liquid_d1_or` | `liquid/d1` | — |
| `mercury_decide_or` | `inception/mercury-decide` (de pago, no `:free`) | — |
| `drex_v15_or` | `nace-ai/drex-v1.5` | `drex_v15_9b` |
| `tev1_4b_or` | `togethercomputer/tev1-4b-experimental` | `tev1_4b` |
| `clef_27b_or` | `cloudflare/clef` | `clef_27b` |
| `clef_flash_or` | `cloudflare/clef-flash` | `clef_flash_9b_xpu` |

El snapshot resuelto (`meta.resolved`) se anota tras la batería; debe ser único por run.

Configuración de los homólogos locales (de `docs/modelos.md` y `meta` de los JSON):

| run local | repo HF @ revisión | dtype | hardware / servicio |
|---|---|---|---|
| `drex_v15_9b` | `nace-ai/drex-v1.5` @ `328ee227` | bf16 + `head.pt` | DGX .80 (GB10), `serve.py` del repo vía `systemone_http` (13-oct) |
| `tev1_4b` | `togethercomputer/Tev1-4B-experimental` @ `0b7becf0` | bf16 | DGX .81 (GB10), adaptador `tev1` (logits del 1.er token, temperature 0) (30-sep) |
| `clef_27b` | `Cloudflare/clef` @ `2f3de3dd` | bf16 | DGX .81 (GB10), adaptador `clef`, `max_length` 16384 (3-oct) |
| `clef_flash_9b_xpu` | `Cloudflare/clef-flash` @ `17f0b0ad` | bf16 | .70 Intel Arc Pro B70 (XPU), adaptador `clef`, `max_length` 16384 (3-oct) |

### Configuración, guardas y errores

Idénticas al pre-registro: adaptador `jev` con `--opt provider=openrouter --opt retries=3`;
fases `all+new` y, aparte, `adv4,adv5` (194 casos, GT v5); `--max-case-cost 0.01
--max-cost 0.10` por llamada; `--retry-errors` sobre el mismo run sin cambiar la
configuración; si el snapshot cambia a mitad de batería, el run se descarta y se repite
entero; un rechazo o error persistente se informa como tal. Un modelo que falle el smoke o
dé respuestas absurdas no se mide y se anota.

### Análisis (fijado de antemano)

1. `python3 -m jevbench.score --summary --adj-ci` con la mayoría, `jev_v3`, los 13 runs de
   OpenRouter de JEV-106 y los 4 homólogos locales. Ajustado descriptivo; coste y latencia
   medidos en los JSON.
2. **Cada run frente a `jev_v3`**: McNemar en las 53 celdas (11 fases); Holm dentro de cada
   familia de 53. Mejor/peor solo si una celda sobrevive a Holm; si no, «sin diferencias
   significativas».
3. **Pares mismo modelo local ↔ OpenRouter** (`drex_v15_9b`↔`drex_v15_or`,
   `tev1_4b`↔`tev1_4b_or`, `clef_27b`↔`clef_27b_or`, `clef_flash_9b_xpu`↔`clef_flash_or`):
   - acuerdo de decisiones pareadas con `python3 -m jevbench.jev81 repeat <local> <or>`
     (descriptivo; referencia: 97 % de las réplicas de JEV-81; **no** es una prueba de
     equivalencia);
   - McNemar en las 53 celdas + Holm dentro de cada familia de 53.
   Una diferencia se lee como **de configuración/servicio** (pesos, cuantización, plantilla
   o servidor pueden diferir entre el local y el proveedor), no se atribuye a una causa
   concreta.
