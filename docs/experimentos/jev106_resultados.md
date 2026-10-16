# JEV-106 — resultados: 13 decisores por OpenRouter (pre-registro + E1)

Pre-registro: [`jev106_preregistro.md`](jev106_preregistro.md), congelado el 16-oct-2026
antes de medir (enmienda E1 en `e43a2a4` antes de lanzar ninguna batería). Resultados en
`8a9e5c9` (`results/<run>/`). Receta idéntica a los runs previos de Decisions API:
adaptador `jev`, `--opt provider=openrouter --opt retries=3`, fases `all+new` y, aparte,
`adv4,adv5` (194 casos, GT v5), `--max-case-cost 0.01 --max-cost 0.10` por llamada,
`--retry-errors` (no hizo falta: 0 errores en la primera pasada).

Smokes (2 casos × `triage_es`, `papers32`, `adv3`): los 10 pasaron con respuestas en
contrato; ninguno se descartó. Verificación de los 13 runs OR: **11 fases, 194 casos,
0 errores, un único `meta.resolved` por run.**

Coste total medido (suma de `cases[*].cost` de los 13 runs × 194 casos): **≈ $0,166**.

## 1. Tabla (194 casos, GT v5)

Ajustado = descriptivo, IC95 bootstrap. adv3/adv4/adv5 = total %. Brier = noul (9 fases
base+nuevas). ms = mediana superior de cliente (`score --summary`: nueve fases base+nuevas, excluye adv4/adv5). Coste = suma de `cost` de los 194 casos (USD,
medido por OpenRouter).

| run | snapshot (`meta.resolved`) | ajustado [IC95] | adv3 | adv4 | adv5 | Brier | ms | coste 194 |
|---|---|---|---|---|---|---|---|---|
| `jev_v3` (ref.) | jev-1.13 | 49 [39–59] | 90.0 | 79.0 | 77.0 | 0.062 | 657 | $0.0068 |
| `drex_v20_or` | nace-ai/drex-v2.0-20261009 | 42 [33–51] | 85.0 | 80.5 | 81.0 | 0.081 | 891 | $0.0055 |
| `classify1_or` | scaledown/classify-1-20260928 | 43 [31–54] | 85.5 | 81.0 | 74.0 | 0.104 | 692 | $0.0202 |
| `pplx_decider_v11_27b_or` | perplexity/pplx-decider-v1.1-27b-20261006 | 53 [43–63] | 88.0 | 83.0 | 81.0 | 0.067 | 997 | $0.0074 |
| `clef_omni_or` | cloudflare/clef-omni-20261009 | 45 [36–54] | 85.5 | 85.5 | 80.5 | 0.067 | 533 | $0.0253 |
| `solar_decide_or` | upstage/solar-decide-20260928 | 40 [26–52] | 80.5 | 77.0 | 81.5 | 0.091 | **9332** | $0.0312 |
| `solar_decide_flash_or` | upstage/solar-decide-flash-20261008 | 37 [24–49] | 77.5 | 82.0 | 82.5 | 0.092 | 1032 | $0.0312 |
| `kev_4b_or` | jaredpalmer/kev-4b-20260924 | 31 [19–42] | 81.5 | 73.0 | 81.0 | 0.114 | 941 | $0.0039 |
| `liquid_d1_or` | liquid/d1-20260930 | 33 [24–41] | 85.5 | 70.0 | 79.5 | 0.111 | 613 | $0.0061 |
| `mercury_decide_or` | inception/mercury-decide-20260930 | 50 [39–60] | 89.5 | 82.0 | 83.0 | 0.070 | 831 | $0.0028 |
| `drex_v15_or` | nace-ai/drex-v1.5-20261009 | 41 [27–53] | 87.0 | 80.0 | 82.0 | 0.082 | 921 | $0.0037 |
| `tev1_4b_or` | togethercomputer/tev1-4b-experimental-20260923 | 32 [19–44] | 79.5 | 79.0 | 78.0 | 0.105 | 787 | $0.0160 |
| `clef_27b_or` | `cloudflare/clef` (**sin fecha**) | 54 [44–64] | 91.0 | 83.5 | 81.5 | 0.052 | 767 | $0.0088 |
| `clef_flash_or` | `cloudflare/clef-flash` (**sin fecha**) | 45 [36–54] | 84.0 | 82.0 | 80.0 | 0.075 | 738 | $0.0038 |
| *mayoría (oráculo)* | — | 0 | 55.5 | 76.5 | 63.0 | — | — | — |

Homólogos locales (referencia de los pares): `drex_v15_9b` 44 [30–56], `tev1_4b` 27 [15–39],
`clef_27b` 56 [46–65], `clef_flash_9b_xpu` 45 [36–54].

Los IC de todos los runs OR se solapan con el de `jev_v3`; eso **no** prueba equivalencia.
IC solapados o Holm=1 → «sin diferencias significativas», no «equivalentes».

## 2. Cada run frente a `jev_v3` (McNemar 53 celdas, Holm dentro de la familia)

b = solo acierta `jev_v3`; c = solo acierta el run.

| run | b | c | celdas p<0.05 sin corregir | Holm<0.05 | mín. p Holm |
|---|---|---|---|---|---|
| `drex_v20_or` | 87 | 67 | 0 | 0 | 1.000 |
| `classify1_or` | 76 | 68 | 1 (adv4.urgency, c=6/b=0) | 0 | 1.000 |
| `pplx_decider_v11_27b_or` | 55 | 70 | 0 | 0 | 1.000 |
| `clef_omni_or` | 67 | 76 | 1 (adv4.urgency, c=7/b=0) | 0 | 0.828 |
| `solar_decide_or` | 77 | 56 | 0 | 0 | 1.000 |
| `solar_decide_flash_or` | 85 | 58 | 2 (adv3.department b=7/c=0; adv4.urgency c=6/b=0) | 0 | 0.828 |
| `kev_4b_or` | 91 | 50 | 1 (triage_ext_en.same_day b=6/c=0) | 0 | 1.000 |
| `liquid_d1_or` | 89 | 53 | 2 (triage_en.same_day, triage_ext_es.same_day; b=7/c=0) | 0 | 0.828 |
| `mercury_decide_or` | 55 | 66 | 0 | 0 | 1.000 |
| `drex_v15_or` | 62 | 42 | 0 | 0 | 1.000 |
| `tev1_4b_or` | 79 | 39 | 1 (papers32.practice b=6/c=0) | 0 | 1.000 |
| `clef_27b_or` | 54 | 89 | 1 (adv2.urgency c=6/b=0) | 0 | 1.000 |
| `clef_flash_or` | 76 | 79 | 1 (papers32.depth c=8/b=1) | 0 | 1.000 |

**Ninguna celda sobrevive a Holm en ninguno de los 13 runs: sin diferencias significativas
frente a `jev_v3`.** Las celdas p<0,05 sin corregir son exploratorias; no se usan para
declarar mejor/peor.

## 3. Pares mismo modelo local ↔ OpenRouter

Acuerdo = decisiones pareadas (964) con `python3 -m jevbench.jev81 repeat <local> <or>`
(descriptivo; referencia del 97 % de JEV-81 — **no** es prueba de equivalencia). El propio
`repeat` avisa de que la versión servida difiere en los 194 casos. Δp = diferencia
media/máxima de probabilidades sobre 2151 componentes pareados. b = solo acierta el local;
c = solo acierta OpenRouter. Lectura pre-registrada: una diferencia es de
configuración/servicio (pesos, cuantización, plantilla o servidor), sin atribuir causa.

| par (local ↔ OR) | acuerdo [IC95] | ≥97 % | Δp media / máx | ajustado local → OR | b / c | Holm<0.05 |
|---|---|---|---|---|---|---|
| `drex_v15_9b` ↔ `drex_v15_or` | 947/964 = 98.2 % [97.2–99.0] | sí | 0.011 / 0.220 | 43.7 → 40.8 (Δ −3.0) | 12 / 5 | 0 (mín. 1.000) |
| `tev1_4b` ↔ `tev1_4b_or` | 927/964 = 96.2 % [94.7–97.3] | **no** | 0.029 / 0.422 | 27.0 → 31.8 (Δ +4.8) | 9 / 25 | 0 (mín. 1.000) |
| `clef_27b` ↔ `clef_27b_or` | 958/964 = 99.4 % [98.7–99.8] | sí | 0.003 / 0.179 | 55.8 → 54.1 (Δ −1.7) | 3 / 2 | 0 (mín. 1.000) |
| `clef_flash_9b_xpu` ↔ `clef_flash_or` | 963/964 = 99.9 % [99.4–100.0] | sí | 0.004 / 0.237 | 44.6 → 44.7 (Δ +0.1) | 0 / 1 | 0 (mín. 1.000) |

- Ningún par tiene celdas p<0,05 ni sin corregir: sin diferencias significativas local↔API.
- Tev1-4B es el único por debajo de la referencia del 97 % (96,2 %, IC hasta 97,3) y el de
  mayor Δp; su Δ ajustado (+4,8) y el desequilibrio b/c (9/25) no llegan a significación.
  Lectura: diferencia de configuración/servicio (en local se leen los logits del 1.er token
  en bf16 con el adaptador `tev1`; OpenRouter sirve su propia implementación), no
  atribuible a una causa.
- Drex v1.5: 98,2 % de acuerdo, b/c 12/5, sin celdas significativas.
- Clef y Clef-Flash: prácticamente las mismas decisiones que en local (99,4 % y 99,9 %).

### Desviación de método (solo `tev1_4b`)

El run local de 30-sep guarda las respuestas sin el campo `type`, y el validador de
contrato de `jev81 repeat` lo rechaza (964 componentes «fuera del contrato»).
`jev81 repeat` está atestado (`jevbench/attest.py`): **no** se modificó ni se editó
`results/tev1_4b`.

Se calculó con el mismo `repeatability_report` añadiendo en memoria `type` desde
`battery.py`:

```bash
python3 scripts/jev106_repeat_typed.py tev1_4b tev1_4b_or
```

Comprobado: reproduce **96,2 %** (927/964, IC95 94,7–97,3) para Tev1, y con
`clef_27b` ↔ `clef_27b_or` da el mismo resultado que el comando normal
(`python3 -m jevbench.jev81 repeat clef_27b clef_27b_or`: 99,4 %).

### Drex v2.0 (OpenRouter) frente a Drex v1.5 (local) — punto 3 del pre-registro

McNemar 53 celdas + Holm, `mcnemar_holm('drex_v20_or', ref='drex_v15_9b')`: b = 66 (solo acierta
v1.5 local), c = 59 (solo acierta v2.0 por OpenRouter), 0 celdas p<0,05 sin corregir, 0 tras Holm
(mín. p Holm 1,000): **sin diferencias significativas**. Ajustado 43,7 → 41,9. Lectura de
configuración/servicio (versión, ruta y servidor cambian a la vez), no solo de versión.

## 4. Rarezas (descriptivas, exploratorias)

- **Solar-Decide (`solar_decide_or`): latencia ~14× la del resto** (mediana 9,3 s,
  máx. 24 s, frente a 0,5–1 s); la batería tardó ~28 min (suma de `ms`, 1690 s). Además ρ de relevancia en
  papers baja (0,65 frente a 0,82–0,90 del resto) y Brier/ECE de adv4 altos
  (0,183 / 0,225).
- **Solar-Decide y Solar-Decide-Flash: coste idéntico caso a caso** ($0,0312 total;
  mismos `usage` de entrada/salida y mismo `cost` por caso): el proveedor factura igual
  ambas variantes. Las decisiones sí difieren (ajustado 40 vs 37; latencia 9,3 s vs 1,0 s).
- **Snapshot sin fecha**: `clef_27b_or` resuelve a `cloudflare/clef` y `clef_flash_or` a
  `cloudflare/clef-flash` (todos los demás llevan sufijo `-YYYYMMDD`). Único dentro del
  run, pero no fija versión: una re-medición futura no puede asegurar que sea el mismo
  snapshot.
- **Confianza extrema — Mercury-Decide y Perplexity Decider**: sobre los 514 `noul` de las 11
  fases, el 50,6 % de Mercury y el 48,8 % de Perplexity están en <0,01 o >0,99 (resto 0–34,6 %:
  Drex v2.0 y Classify-1 0 %, Kev 0,6 %; jev_v3 0,2 %). Mercury tiene solo 3 binarios en 0,45–0,55; choice con p máx. mediana
  0,996. Brier descriptivo 0,070 (Jev 0,062); no se contrastó una diferencia de calibración.
- **Distribuciones planas — Kev-4B**: 55 binarios en la frontera 0,45–0,55 (el máximo del
  grupo; jev_v3 30) y p máx. mediana de choice 0,77 (resto 0,89–1,0). En adv5, 9 binarios
  en frontera.
- **Liquid D1 y Kev-4B: `same_day` débil** (celdas p<0,05 sin corregir, b=6–7/c=0, frente
  a jev_v3), y adv4 de Liquid 70,0 % (por debajo de la mayoría, 76,5 %). Kev-4B adv4
  73,0 % también bajo la mayoría.
- **Clef-Omni: adv1+2 department 8/20** (la mayoría `admin` saca 17/20), igual que
  Clef/Clef-Flash (10/20): la familia Clef manda menos casos adversariales a `admin`.
  Coste el más alto tras Solar ($0,025).
- Tev1-4B OR coste $0,016 (≈4× Drex/Clef-Flash OR) con ajustado 32.
- Sin rechazos, sin distribuciones uniformes (`unif choice` 0/216 en los 13), sin colapsos
  a una opción en `department` (todas reparten las 4 opciones; el sesgo más marcado es
  `bronchoscopia` 65/160 en Clef-Omni frente a 48 de jev_v3).
- En el smoke, `liquid_d1_or` mostró `hostile=1.3007`: es `1.3e-05` truncado en el log,
  no un valor fuera de rango.
- `tev1_4b` (local) muestra `unif choice 0/0` en el resumen por la misma falta de `type`.

## Lo que esto cambia

- Los 13 runs de OpenRouter entran en la documentación del banco (fichas en
  `docs/modelos.md`; marcador/web/sitio los integra otro agente).
- **Ningún run OR se distingue de `jev_v3` tras Holm** en las 53 celdas: sin diferencias
  significativas. Los IC solapados no prueban equivalencia.
- Los cuatro pares local↔API tampoco muestran celdas significativas; tres superan la
  referencia descriptiva del 97 % de acuerdo; Tev1 queda en 96,2 % (configuración/servicio).
- La recomendación vigente del banco (cascada/revisor/alerta) no cambia con este
  experimento: fuera de alcance del pre-registro.
