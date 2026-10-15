# JEV-103 — decisores dedicados recientes: alerta de una pasada, rotación d1, réplica r2 y revisor de Decider-4B

**Estado: CONGELADO el 14-oct-2026**, aprobado por el usuario antes de medir
(redactado el mismo día, T49; revisado por Codex en R117). En la aprobación el
usuario también: confirmó por escrito que el §2(c) de la licencia de Drex no le
aplica (§4); autorizó el coste de API de Microsoft-Decision-1 por OpenRouter, que
entra en los pasos 1 y 3 (§0); y aprobó la enmienda de atestaciones del
`choice_order` genérico. Cualquier cambio posterior es enmienda fechada al final
del documento. Ninguna celda se había ejecutado ni calculado al congelarlo.

**Resultados:** [`jev103_resultados.md`](jev103_resultados.md) (14-oct-2026), con la enmienda E1 al final
de este documento. El paso 0
(completar `adv4`/`adv5` en los runs antiguos, manifiesto
`docs/infra_runs/jev103_adv45.md`) corre aparte y **no** forma parte de este
pre-registro.

GT vigente: **v5** (11-oct, 23 etiquetas adjudicadas; `data/GT_CHANGELOG.md`).
`questions_hash` de la batería: `9a81e9763d94` (fases estándar) y
`cf30481e3428` (la pregunta `manipulation` sola de las alertas). Toda tabla
lleva la línea base de mayoría (regla 8 de AGENTS.md). Los resultados
negativos se documentan igual que los positivos (regla 5).

## 0. Modelos, runs base y revisiones

| run base | adaptador | host · venv | revisión de pesos | ajustado (GT v5) |
|---|---|---|---|---|
| `nimble_9b` | `nimble` | .81 · `.venv-nimble` | `bespokelabs/Bespoke-Nimble-9B` @ `bd792f44ec8e265be861bfcdf4e05967ffe0e858` (base `Qwen/Qwen3.5-9B@c2022362`) | 47 |
| `tev1_4b` | `tev1` | .81 · `.venv-tev1` | `togethercomputer/Tev1-4B-experimental` @ `0b7becf017daa0e5eb222f8ce7483c8c8259c52f` | 27 |
| `tev1_0.8b` | `tev1` | .81 · `.venv-tev1` | `togethercomputer/Tev1-0.8B-experimental` @ `6bb2dff14b38fea90ddb14d870166ccaf77374e9` | −9 |
| `drex_v15_9b` | `systemone_http` | .80 · `.venv-drex` + `serve.py` en 127.0.0.1:8010, consumido por túnel SSH | `nace-ai/drex-v1.5` @ `328ee227c0425669d9f37fa82d400aa52c22139c` | 44 |
| `clm_v0.1_8b` | `systemone_http` | .70 (desktopelite, Intel Arc Pro B70) · vLLM XPU en `<IP-.70>:8700` | `Contrastive-LM/CLM-v0.1-8B`, base `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`, head sha256 `b2b4a8c9…f1c4eda5` | −41 |
| `strands_2b_hobson_v19_xpu` | `systemone_http` | .70 XPU · `strands-decider` git `eb89e5c` en 127.0.0.1:8710 (túnel), `--strict-window` | `StrandsAgents/strands-decider-2B-hobson-v19` @ `bb282d786bc251fd4e3068de3ada9ddbb38127cd` (base `Qwen3.5-2B-Base@b1485b2f`) | 18* (19 en `_trunc`) |

Las revisiones vienen del `meta` de cada run y de `docs/infra_runs/` +
`docs/modelos.md`. **PENDIENTE de verificar en ejecución:** que coinciden con
`/mnt/ai-models/MANIFEST-hf.tsv` de los DGX (ese fichero no está en este repo;
lo cita `docs/infra_runs/jev103_adv45.md` — no accesible desde el portátil sin
SSH).

**Identidad de pesos — preflight archivado (fijado antes de medir):** los
indicadores `same_model` (jev82) y `repeatable_model` (jev81) comparan
únicamente el **identificador servido** escrito por caso
(`cases[id].model`): los alias HTTP `drex-v1.5`, `clm-latest`,
`strands-decider-2B-hobson-v19` o el repo HF de Nimble/Tev1. **No**
verifican `meta.revision` ni `meta.opts.revision` — dos réplicas con
revisiones distintas declaradas darían `same_model`/`repeatable_model`
verdaderos mientras el alias coincida. Por eso la identidad real de pesos
se acredita de forma externa a los analizadores congelados: **antes de
adquirir cada run** se archiva un manifiesto de preflight en
`docs/infra_runs/jev103_<run>_preflight.md` (un fichero por run nuevo:
`<base>_alert_raw`, `<base>_d1`, `<base>_r2`, `decider_4b_<x>rev_*`),
que registra la revisión completa/head sha256/configuración del servidor:

- **Nimble / Tev1** (`.81`): revisión HF completa (40 hex) resuelta por el
  adaptador + `MANIFEST-hf.tsv` correspondiente.
- **Drex** (`.80`, `serve.py`): revisión HF completa de `nace-ai/drex-v1.5`
  (`328ee227…`, los 40 hex, no el prefijo) + flags con los que arrancó
  `serve.py`.
- **CLM** (`.70`, vLLM XPU): base `Qwen/Qwen3-8B@b968826d…` + sha256
  completo de la cabeza (`b2b4a8c9…`) + versión y configuración del vLLM
  XPU que la sirve tras el alias `clm-latest`.
- **Strands** (`.70`, túnel 8710): `strands-decider-2B-hobson-v19` @
  `bb282d78…` + base `Qwen3.5-2B-Base@b1485b2f…` + commit git del servidor
  `strands-decider` (declarado `eb89e5c` en §0) + flags (`--strict-window`).

Si el preflight falta, o la revisión/configuración registrada difiere de lo
declarado en esta tabla, el run afectado es **NO EVALUABLE** para los
contrastes d1/r2/revisor que dependen de él.

**Microsoft-Decision-1** (`jev_ms_decision1`, adaptador `jev`, OpenRouter
`microsoft/microsoft-decision-1`, snapshot del run base
`microsoft/microsoft-decision-1-20261009`, ajustado **47**; coste autorizado
por el usuario el 14-oct): entra en el **paso 1** (alerta de una pasada) y en
el **paso 3** (revisor de Decider-4B). El **paso 2 no se repite**: su rotación
d1 y su réplica r2 ya existen (`jev_ms_decision1_d1`, `jev_ms_decision1_r2`,
JEV-90, `docs/infra_runs/ms_decision1_jev90.md`). Identidad de versión: como
API cerrada no hay pesos; el preflight archivado registra el `resolved` del
alias y cada caso guarda su versión. Si el snapshot resuelto en JEV-103 difiere
de `-20261009`, la celda se mide igual (es su propia pregunta) pero se declara
otro snapshot y la comparación con el run base de Microsoft es solo
descriptiva. Guardas de coste: `--max-case-cost 0.01` y `--max-cost 0.05`
(alerta) / `0.10` (cada `_raw` del revisor); `--opt retries=3`; 1 pasada + 1
`--retry-errors`, como JEV-90.

Hardware: los pasos de CLM y Strands se ejecutan **al final** en .70, con el
mismo hardware y servidor que el run base (vLLM XPU y `strands-decider`
`--strict-window`, respectivamente). Antes de lanzar nada en los DGX:
`nvidia-smi` / `docker ps` (AGENTS.md); en .80 no tocar los servicios del
usuario.

## 1. Alerta de una pasada (`<base>_alert_raw`)

Misma hipótesis, misma regla y mismo criterio que las extensiones ya
pre-registradas de `docs/experimentos/alerta_manipulacion.md` (Span-01,
Clef-27B, gpt-6.1-sol, DiffusionGemma, Haiku 5.5):

- **Regla fija:** `alerta = manipulation ≥ 0.5` con la redacción
  `MANIPULATION` de `jevbench/cascade.py`, sobre el texto crudo del caso en
  **una sola llamada**, sin prompt de revisor.
- **Script:** `scripts/alert_onepass.py <adaptador> <run_base> [k=v…]` →
  escribe `results/<run_base>_alert_raw/` (fases adv3, adv4, adv5).
- **Criterio de éxito (fijo):** sensibilidad **≥ 7/10** TP por set y
  **≤ 1/10** FP por set; se reporta el acumulado (30 manipulados / 30
  honestos) y el pareado McNemar.
- **Familia Holm (declarada exacta):** por cada modelo, **2 comparaciones
  pareadas McNemar** sobre los mismos 60 ids (acierto binario de la decisión
  alerta/no-alerta frente al GT `manipulated`): `{vs clef_27b_alert_raw
  (alerta de una pasada de referencia), vs jev_cascade_raw (alerta del
  revisor Jev, 2ª pasada con contexto)}`. Holm sobre esa familia de 2 por
  modelo. Referencias medidas: Clef-27B 27/30 TP · 1/30 FP; revisor Jev
  25/30 · 1/30 (mismo FP: adv5/E11).
- **Línea base trivial:** «nunca alertar» → 30/60 aciertos, 0 TP, 0 FP.
- **Resultado negativo (se documenta igual):** no cumplir el criterio en
  algún set (TP < 7/10 o FP > 1/10), o perder el pareado frente a la alerta
  de Clef-27B tras Holm.
- Los adaptadores locales no informan `cost` (`null`): las guardas
  `--max-case-cost/--max-cost` del script quedan inertes; se omiten, igual
  que en `clef_27b_alert_raw`.

Comandos (sin ejecutar aún). `scripts/alert_onepass.py` no es ejecutable
(permisos 664): se invoca siempre con el intérprete del venv que corre el
adaptador (`<venv>/bin/python scripts/alert_onepass.py ...` en los DGX) o
con `python3` en el portátil — nunca como `./scripts/alert_onepass.py`:

```bash
# .81 — .venv-nimble
.venv-nimble/bin/python scripts/alert_onepass.py nimble nimble_9b \
    model=bespokelabs/Bespoke-Nimble-9B \
    revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858

# .81 — .venv-tev1
.venv-tev1/bin/python scripts/alert_onepass.py tev1 tev1_4b \
    model=togethercomputer/Tev1-4B-experimental \
    revision=0b7becf017daa0e5eb222f8ce7483c8c8259c52f
.venv-tev1/bin/python scripts/alert_onepass.py tev1 tev1_0.8b \
    model=togethercomputer/Tev1-0.8B-experimental \
    revision=6bb2dff14b38fea90ddb14d870166ccaf77374e9

# portátil — Drex en .80 con su serve.py (ver docs/infra_runs/drex_v15_9b.md):
#   en .80: cd ~/modelos/drex-v1.5 && .venv-drex/bin/python serve.py \
#       --model ~/modelos/drex-v1.5 --host 127.0.0.1 --port 8010 --name drex-v1.5
#   túnel: ssh -fNL 8010:127.0.0.1:8010 <usuario>@<IP-.80>
python3 scripts/alert_onepass.py systemone_http drex_v15_9b \
    url=http://127.0.0.1:8010 model=drex-v1.5

# portátil — Microsoft-Decision-1 por OpenRouter (coste autorizado 14-oct)
python3 scripts/alert_onepass.py jev jev_ms_decision1 \
    provider=openrouter model=microsoft/microsoft-decision-1 retries=3 \
    --max-case-cost 0.01 --max-cost 0.05
# + 1 --retry-errors con el mismo comando

# AL FINAL, en .70 — CLM (vLLM XPU, misma configuración del run base)
python3 scripts/alert_onepass.py systemone_http clm_v0.1_8b \
    url=http://<IP-.70>:8700 model=clm-latest

# AL FINAL, en .70 — Strands (strands-decider --strict-window, túnel 8710)
#   túnel: ssh -fNL 8710:127.0.0.1:8710 <usuario>@<IP-.70>
python3 scripts/alert_onepass.py systemone_http strands_2b_hobson_v19_xpu \
    url=http://127.0.0.1:8710 model=strands-decider-2B-hobson-v19
```

Análisis (offline; mismo cálculo que las extensiones anteriores): TP/FP por
set con umbral 0.5 sobre `answers.manipulation.noul`, acumulado 30/30, y las
dos comparaciones pareadas McNemar–Holm de la familia declarada (los mismos
60 ids: adv3/adv4/adv5).

## 2. Rotación d1 del orden de `department` (`<base>_d1`) + réplica r2 (`<base>_r2`)

Igual que JEV-82 (`docs/infra_runs/luna_decisions_jev82.md`) y JEV-81
(`docs/infra_runs/luna_decisions_jev81.md`, §3), ahora sobre los decisores
dedicados. Requiere el `choice_order` genérico de la clase base `Adapter`
(JEV-103): con `--opt choice_order=department:d1` el adaptador reordena las
claves de `criteria` de `department` antes de construir prompt, esquema o
payload; etiquetas, textos y GT intactos, y `meta` registra
`opts.choice_order`, `meta.choice_order` resuelto y `meta.perm_sha256`
(`15f6174736a0` en las 9 fases con `department`, `c68c21f92897` en papers32,
`e54d4e3d2038` en ood — canónicos JEV-82).

**Política de adquisición (fija):** 1 pasada completa + **1**
`--retry-errors` por bloque (`all+new`, luego `adv4,adv5`), igual que el run
base. Los runs `d1` llevan además las guardas
`--max-case-cost 0.01 --max-cost 0.05`: aunque los modelos locales no
informan coste (la guarda nunca dispara), `jevbench.jev82` exige
`meta.cost_guard` declarado en cada fase del run d1 — es parte de la
procedencia, no una métrica. Las mismas guardas se ponen en `r2` por
uniformidad (inertes igual).

**Nota sobre determinismo (fijada antes de medir):** Nimble (softmax sobre
logits con T fija del checkpoint), Tev1 (lectura de logits del primer token,
equivale a temperature=0), Drex (cabeza pointer, T=1.0), CLM (cabeza CLM,
pooling) y Strands (cabeza pointer con temperaturas por primitiva) son
**deterministas o casi** en hardware fijo (sin muestreo). Un `r2` idéntico al
100 % **no es un hallazgo**: es un control de plomería — demuestra que el
pipeline (pesos, harness, servidor) es reproducible, no que el modelo sea
«consistente» en sentido fuerte. Cualquier divergencia sí es un hallazgo
(indicaría no determinismo real, p. ej. batching del servidor).

**Métricas r2** (`python3 -m jevbench.jev81 repeat <base> <base>_r2`):
acuerdo de decisiones pareadas con IC95 Clopper-Pearson (referencia
descriptiva **≥ 97 %** puntual, convención JEV-81); Δp medio/máximo sobre
componentes comunes; Δ ajustado solo si las fases completas coinciden;
versiones por caso (`repeatable_model` exige `model` igual en todos los
éxitos emparejados — igualdad del **identificador servido** por caso, no de
la revisión de pesos; la revisión la acredita el preflight archivado de
§0); rechazos/errores por réplica (both / solo r1 / solo r2).

**Métricas d1** (`python3 -m jevbench.jev82 analyze <base> <base>_d1`):
acuerdo pareado (misma referencia ≥ 97 %); Δ ajustado (d1−d0) descriptivo
sobre la intersección de fases completas; Δp por etiqueta; rechazos;
`same_model` de versiones (igualdad del **identificador servido** por caso,
no de la revisión — acreditada por el preflight de §0); y la **primacía
confirmatoria** — regla JEV-72
intacta sobre el subconjunto congelado sha `4e7e2877f27d` (Δ errores
`department` d0−d1 ≥ 5 pp, L95 > 0, significativa tras Holm de la familia
interna de jev82 `{d0vsd1 todos, primacía}` → CONFIRMADA; U95 < 5 → REFUTADA;
si no, INCONCLUSA). La corrección Holm es la que ya aplica `jev82` dentro de
cada contraste d0↔d1; **no** hay familia cruzada entre modelos (cada run es
su propia pregunta).

**Lectura declarada (se conservan los tres dictámenes de primacía — JEV-82
no interpreta falta de evidencia como ausencia de efecto):** «**sensible al
orden**» si la primacía queda CONFIRMADA o el acuerdo pareado < 97 %
puntual; «**estable**» **solo** si acuerdo ≥ 97 % **y** primacía REFUTADA;
con primacía INCONCLUSA y acuerdo ≥ 97 % se reporta literalmente «**acuerdo
observado ≥ 97 %, primacía inconclusa**» — no «estable»: un IC que aún
admite ≥ 5 pp no acredita estabilidad. Si el run no es evaluable (fases
incompletas en ambos lados, versión distinta) se declara NO EVALUABLE. El Δ
ajustado se reporta como magnitud descriptiva, sin umbral.

Precisión de terminología (fijada): un **registro presente con error no es
un registro ausente**. `jev81._validate_universe` aborta ante fases o ids
ausentes en cualquiera de los dos lados, pero **admite** registros presentes
con error (p. ej. Strands `papers32/P11`): esos casos entran en las listas
de rechazos `both`/`only_*`, quedan fuera del pareado y no invalidan el
universo del run.

**Resultado negativo (se documenta igual):** acuerdo < 97 %, primacía
CONFIRMADA o errores nuevos atribuibles al orden. Δp (medio/máximo por
componente, por etiqueta) se reporta como magnitud **puramente
descriptiva**, sin umbral fijado — no es criterio de éxito ni de fracaso.

Casos conocidos que degradan cobertura (declarados a priori): Strands con
`--strict-window` rechaza `papers32/P11` (> 4096 tokens → HTTP 422) en base,
r2 y d1 por igual — entra en las listas de rechazos `both` y papers32 queda
fuera del ajustado pareado; Drex (`KEV_CONTEXT` 16384, `strict=True`)
rechazaría un estado que la supere — en la batería ninguno lo hace
(máx. empaquetado 6578 tokens).

Comandos por modelo (sin ejecutar aún). Todas las opciones del adaptador son
idénticas a las del run base:

```bash
# ---------- nimble_9b (.81, .venv-nimble) ----------
python3 -m jevbench.run nimble --run nimble_9b_d1 \
    --opt model=bespokelabs/Bespoke-Nimble-9B \
    --opt revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run nimble --run nimble_9b_d1 \
    --opt model=bespokelabs/Bespoke-Nimble-9B \
    --opt revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque (mismo comando + --retry-errors)
python3 -m jevbench.run nimble --run nimble_9b_r2 \
    --opt model=bespokelabs/Bespoke-Nimble-9B \
    --opt revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run nimble --run nimble_9b_r2 \
    --opt model=bespokelabs/Bespoke-Nimble-9B \
    --opt revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque

# ---------- tev1_4b / tev1_0.8b (.81, .venv-tev1) ----------
python3 -m jevbench.run tev1 --run tev1_4b_d1 \
    --opt model=togethercomputer/Tev1-4B-experimental \
    --opt revision=0b7becf017daa0e5eb222f8ce7483c8c8259c52f \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run tev1 --run tev1_4b_d1 \
    --opt model=togethercomputer/Tev1-4B-experimental \
    --opt revision=0b7becf017daa0e5eb222f8ce7483c8c8259c52f \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run tev1 --run tev1_4b_r2 \
    --opt model=togethercomputer/Tev1-4B-experimental \
    --opt revision=0b7becf017daa0e5eb222f8ce7483c8c8259c52f \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run tev1 --run tev1_4b_r2 \
    --opt model=togethercomputer/Tev1-4B-experimental \
    --opt revision=0b7becf017daa0e5eb222f8ce7483c8c8259c52f \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque en cada run; ídem tev1_0.8b con
#   model=togethercomputer/Tev1-0.8B-experimental
#   revision=6bb2dff14b38fea90ddb14d870166ccaf77374e9
#   y runs tev1_0.8b_d1 / tev1_0.8b_r2

# ---------- drex_v15_9b (portátil → túnel a .80:8010, serve.py activo) ----------
python3 -m jevbench.run systemone_http --run drex_v15_9b_d1 \
    --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run drex_v15_9b_d1 \
    --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run systemone_http --run drex_v15_9b_r2 \
    --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run drex_v15_9b_r2 \
    --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque en cada run

# ---------- AL FINAL en .70 ----------
# clm_v0.1_8b (vLLM XPU en <IP-.70>:8700, alias clm-latest)
python3 -m jevbench.run systemone_http --run clm_v0.1_8b_d1 \
    --opt url=http://<IP-.70>:8700 --opt model=clm-latest \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run clm_v0.1_8b_d1 \
    --opt url=http://<IP-.70>:8700 --opt model=clm-latest \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run systemone_http --run clm_v0.1_8b_r2 \
    --opt url=http://<IP-.70>:8700 --opt model=clm-latest \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run clm_v0.1_8b_r2 \
    --opt url=http://<IP-.70>:8700 --opt model=clm-latest \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque en cada run

# strands_2b_hobson_v19_xpu (strands-decider --strict-window, túnel 8710)
python3 -m jevbench.run systemone_http --run strands_2b_hobson_v19_xpu_d1 \
    --opt url=http://127.0.0.1:8710 --opt model=strands-decider-2B-hobson-v19 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run strands_2b_hobson_v19_xpu_d1 \
    --opt url=http://127.0.0.1:8710 --opt model=strands-decider-2B-hobson-v19 \
    --opt choice_order=department:d1 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run systemone_http --run strands_2b_hobson_v19_xpu_r2 \
    --opt url=http://127.0.0.1:8710 --opt model=strands-decider-2B-hobson-v19 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run systemone_http --run strands_2b_hobson_v19_xpu_r2 \
    --opt url=http://127.0.0.1:8710 --opt model=strands-decider-2B-hobson-v19 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
# + 1 --retry-errors por bloque en cada run
```

Análisis (offline, en el portátil, sobre `results/` ya sincronizados):

```bash
python3 -m jevbench.jev82 analyze nimble_9b nimble_9b_d1
python3 -m jevbench.jev81 repeat nimble_9b nimble_9b_r2
# … ídem para tev1_4b, tev1_0.8b, drex_v15_9b, clm_v0.1_8b,
#   strands_2b_hobson_v19_xpu
```

Nota sobre `jev82` con adaptadores que no son `jev`: `analyze` no ata al
adaptador — valida `meta.opts.choice_order` (lo escribe `jevbench.run` desde
los `--opt`), `meta.choice_order`/`meta.perm_sha256` (los escribe la opción
genérica JEV-103), `meta.cost_guard` del run d1, universo, hashes y vectores
pareados. Cubierto por `tests/test_choice_order_generic.py`
(`test_analyze_acepta_otro_adaptador`). Requisito: el run base debe cubrir
las 11 fases — satisfecho por todos los runs de la tabla tras el paso 0.

## 3. Revisor de Decider-4B (`decider_4b_<x>rev`)

Mismo prompt del revisor-auditor y mismas reglas de fusión de
`jevbench/cascade.py` (`review`, `audit`, `avg`; `--control ""`), D1 =
`decider_4b`. Criterio **JEV-32** (`docs/plan_revisor_local.md`,
`docs/experimentos/cascada_jev.md`): con la regla `audit`, recuperar **≥ 50 %
de la ganancia** de `decider_4b_jevrev_audit` sobre `decider_4b` en el total
de adv3 + adv5 **y** en triaje (media ES/EN), **sin empeorar** ninguna fase
en más de 2 puntos; y alerta `manipulation ≥ 0.5` en `<prefix>_raw/adv5.json`
con sensibilidad ≥ 7/10 y FP ≤ 1/10.

Referencia calculable con el GT vigente (v5; se recalcula al analizar, no se
congela el número): `decider_4b` → `decider_4b_jevrev_audit` es
79.5/75.0 → 94.0/85.0 en adv3/adv5 (ganancia media 12.25 puntos → el 50 %
pide **6.125**) y 85.7/85.7 → 90.7/93.6 en triaje (ganancia interna 6.428571… puntos →
el 50 % pide **3.214286…**; recalculado con `score_run`, R117 hallazgo 10). El 50 % se aplica sobre los **valores internos sin
redondear** del scorer (las fracciones de acierto por componente antes del
`%` impreso) — los redondeos a 1 decimal (+6.1/+3.2) no son umbral.
Ajustados de referencia: D1 34, revisor Jev 66, revisor Clef-27B 59
(GT v5).

**Candidatos** (regla fijada: solo modelos **del alcance de JEV-103** — los
runs de §0 — con ajustado cerca o por encima de Decider-4B, 33.8 → 34
en el marcador): **Nimble-9B** (47), **Drex v1.5** (44) y
**Microsoft-Decision-1** (47). **Excluidos,
declarado ahora:** Tev1-4B (27), Tev1-0.8B (−9), CLM-v0.1-8B (−41) y
Strands-2B (18*/19) quedan por debajo de Decider-4B como D1 — es una heurística de
coste, no evidencia de incapacidad: un revisor más débil que el D1 difícilmente
recuperará la mitad de la ganancia del revisor Jev: incluso Clef-Flash 9B, con ajustado **41** (por **encima** de
D1=34; revisor local medido, aunque no el mejor: Clef-27B tiene audit 59 frente a 48), recuperó solo el 38 % y no cumplió.
Clef-Flash no es candidato aquí porque está **fuera del alcance de JEV-103**
(no es uno de los runs de §0), no por su ajustado; si se quisiera él u
otro revisor sería una celda exploratoria nueva, pre-registrada aparte.

Comandos (sin ejecutar aún):

```bash
# .81 — .venv-nimble — revisor Nimble-9B
python3 -m jevbench.cascade --d1 decider_4b --adapter nimble \
    --opt model=bespokelabs/Bespoke-Nimble-9B \
    --opt revision=bd792f44ec8e265be861bfcdf4e05967ffe0e858 \
    --prefix decider_4b_nimblerev --control "" \
    --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5

# portátil — revisor Drex v1.5 (serve.py en .80:8010 + túnel, §1)
python3 -m jevbench.cascade --d1 decider_4b --adapter systemone_http \
    --opt url=http://127.0.0.1:8010 --opt model=drex-v1.5 \
    --prefix decider_4b_drexrev --control "" \
    --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5

# portátil — revisor Microsoft-Decision-1 (OpenRouter)
python3 -m jevbench.cascade --d1 decider_4b --adapter jev --provider openrouter \
    --opt model=microsoft/microsoft-decision-1 --opt retries=3 \
    --prefix decider_4b_msrev --control "" \
    --max-case-cost 0.01 --max-cost 0.10 \
    --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5
# + 1 --retry-errors con el mismo comando
```

Cada uno genera `decider_4b_<x>rev_{raw,review,audit,avg}`. Riesgos
declarados a priori (ventanas estrictas, no se esquivan — el caso queda como
error documentado y la fase incompleta): el estado del revisor incluye el
texto original + la valoración de D1; Nimble rechaza > 8192 tokens y Drex >
16384 — en la batería ningún estado base llega (máx. ~6,6 k tokens en
papers32), pero la fusión con la valoración de D1 puede acercar algún caso de
papers32 al límite. **Regla de cobertura (fijada):** si falta cobertura
completa de **cualquiera** de las fases que el criterio necesita — adv3 y
adv5 para la ganancia, triage_es y triage_en para el triaje, y **todas** las
fases del contraste (incluida papers32) para «sin empeorar ninguna», más
adv5 de `<prefix>_raw` para la alerta — la celda es **NO EVALUABLE** para el
criterio JEV-32; las fases disponibles se reportan solo como descriptivas y
la cobertura se declara explícita. No se otorga cumplimiento parcial ni se
descarta la fase que falta.

Análisis (offline). **Alcance inferencial declarado:** los McNemar pareados
que imprime `score --vs decider_4b` (p cruda por pregunta, sin corrección
por multiplicidad) son **exclusivamente descriptivos** — el criterio JEV-32
es operacional (umbrales de ganancia/recuperación sobre los valores internos
del scorer y de la alerta), no un contraste de hipótesis, y **no** se extrae
conclusión inferencial de esos p. No hay familia confirmatoria en esta
celda (a diferencia de las familias exactas declaradas en §1 y §2). El
`--vs` se pide sobre **las 11 fases**, porque «sin empeorar ninguna fase en
más de 2 puntos» incluye papers32, ood y los demás sets — la comprobación
se hace con las cifras internas sin redondear del scorer por fase:

```bash
python3 -m jevbench.score --summary decider_4b decider_4b_jevrev_audit \
    decider_4b_clefrev_audit decider_4b_nimblerev_audit decider_4b_drexrev_audit \
    decider_4b_msrev_audit
python3 -m jevbench.score decider_4b decider_4b_nimblerev_audit \
    decider_4b_drexrev_audit decider_4b_msrev_audit --vs decider_4b \
    --phases triage_es,triage_en,papers32,adv1,adv2,ood,triage_ext_es,triage_ext_en,adv3,adv4,adv5
# alerta adv5: manipulation ≥ 0.5 sobre results/decider_4b_<x>rev_raw/adv5.json
```

**Resultado negativo (se documenta igual):** no recuperar el 50 % en alguno
de los dos bloques, empeorar una fase > 2 puntos, o alerta adv5 por debajo
del listón — mismo destino documental que D35/AnyJev/Clef-Flash.

## 4. Licencia de Drex (usos 1–3)

`nace-ai/drex-v1.5` se distribuye con **Open RAIL-M modificada** (v1.0,
oct-2026), no OSI. Texto literal del **Attachment A §2** (LICENSE del repo HF
`nace-ai/drex-v1.5`, verificada idéntica en la revisión fijada `328ee227` y
en `main` el 14-oct-2026):

> **2. Commercial:**
> (a) for any purpose if You (your employer, or the entity you are affiliated
> with) generated more than one million US dollars ($1,000,000) in gross
> revenue in the prior twelve (12) months, **except where Your Use is limited
> to personal use or research purposes**;
> (b) for any purpose if You (your employer, or the entity you are affiliated
> with) has raised more than one million US dollars ($1,000,000) in total
> equity or debt funding from any source, **except where Your Use is limited
> to personal use or research purposes**; or
> **(c) for any purpose if You (your employer, or the entity you are
> affiliated with) provides or otherwise makes available any product or
> service that competes with any product or service offered or made available
> by Licensor or its affiliates, including decision models and document
> intelligence services.**

Lectura para los usos 1–3 de este documento (alerta, rotación/réplica,
revisor — todo investigación/benchmark **no comercial**, sin redistribuir el
modelo, publicando solo métricas y outputs propios — que §7 declara del
usuario y §6 cubre «evaluating» como uso permitido):

- §2(a–b): los umbrales de ingresos/financiación **no aplican** aunque se
  superaran — ambos párrafos exceptúan expresamente el uso de investigación.
- §2(c): **no tiene excepción de investigación**. Prohíbe cualquier uso a
  quien «provide or otherwise makes available» un producto o servicio que
  compita con los del licenciante (incluidos modelos de decisión). La
  restricción es sobre **quién usa** el modelo, no sobre la actividad del
  benchmark: ejecutar un banco de pruebas no es «ofrecer un producto o
  servicio competidor» en sí mismo, pero **si el usuario o su organización
  ofrece productos/servicios que compiten con Nace.AI (modelos de decisión o
  document intelligence), ninguno de los usos 1–3 está licenciado**.
  **Confirmado por escrito por el usuario el 14-oct-2026: el §2(c) no le
  aplica.** Las cuatro celdas de Drex se ejecutan. **Regla (fijada):** las cuatro celdas de Drex de
  este pre-registro (alerta, d1, r2 y revisor) **no se ejecutan** hasta que
  el usuario confirme **por escrito** que §2(c) no le aplica; sin esa
  confirmación quedan **canceladas**. No se asume ningún sentido de la
  respuesta: «entrar en §2(c)» significaría uso **no** licenciado.
- §3(a): las decisiones automatizadas de la batería son evaluación sobre
  casos sintéticos, sin efectos sobre personas reales; la alerta medida es,
  precisamente, una marca para revisión humana.
- §9: sin logos ni apariencia de aval — este banco no tiene aval del
  proveedor (ya declarado en `docs/modelos.md` §Drex).

La regla es asimétrica: **sin confirmación escrita del usuario de que §2(c)
no le aplica, las cuatro celdas de Drex quedan canceladas** (alerta, d1, r2
y revisor); si confirma que sí le aplica, también lo están. Solo se ejecutan
tras esa confirmación — no hace falta enmienda: la exclusión ya está escrita
aquí condicionada.

## 5. Registro de decisiones abiertas

1. `MANIFEST-hf.tsv` de `/mnt/ai-models` (DGX): comprobar en ejecución que las
   revisiones de la tabla §0 coinciden (este repo no lo contiene); va en cada
   preflight.
2. §2(c) de la licencia de Drex: **resuelto** el 14-oct-2026 — el usuario
   confirmó por escrito que no le aplica (§4).
3. `d1`/`r2` de Strands: ¿servidor con `--strict-window` (idéntico al run
   primario, P11 rechazado) o también variante truncada? **Fijado aquí:**
   `--strict-window`, igual que el run base; la variante `_trunc` no se
   replica (el experimento es orden/repetibilidad, no ventana).
4. Si surge cualquier variante no escrita aquí (otros órdenes d2/d3, otros
   umbrales, revisores excluidos, fallback), es EXPLORATORIO y se dirá así.

## Enmienda E1 (14-oct-2026, antes de calcular d1/r2 de Nimble y Tev1)

Al lanzar `jev82 analyze` y `jev81 repeat` sobre `nimble_9b`, `tev1_4b` y `tev1_0.8b`, los
dos analizadores abortan **antes de calcular nada** («respuesta fuera del contrato») en todos
los componentes, también en los runs base: los adaptadores `nimble` y `tev1` guardan cada
respuesta sin el campo `type` (`{"choice", "probabilities"}`, `{"score", "probabilities"}`,
`{"noul"}`), y `_answer_ok` de `jev81` exige `type` igual al de la pregunta. La afirmación de
§2 de que `jev82` acepta cualquier adaptador solo estaba probada con `systemone_http`.

Corrección fijada (no se ha visto ninguna cifra d1/r2 de estos tres modelos):

- No se modifican los analizadores congelados ni los JSON de `results/`.
- `scripts/jev103_typed_analyze.py` ejecuta `jev82 analyze` / `jev81 repeat` sin cambios,
  pero envuelve `store.load` para añadir a cada respuesta que no lo tenga el `type` de su
  pregunta según `jevbench/battery.py`. Ningún otro campo cambia: probabilidades, `noul`,
  `choice` y `score` quedan intactos, y el resto de la validación del contrato (opciones
  completas, valor `noul` presente) se aplica igual.
- Se usa solo para los tres runs base y sus `_d1`/`_r2`; Drex, CLM, Strands y Microsoft ya
  llevan `type` y se analizan con los comandos de §2 tal cual.
- Las filas d1/r2 de Nimble y Tev1 se marcan «con normalización de formato (E1)».

---

*Redacción de privacidad (15-oct-2026, al publicar la 2.3.0):* IPs, nombres de host y usuario sustituidos por marcadores (`<IP-.70>`, `<IP-.80>`, `<usuario>`) para el espejo público. No cambia ningún contenido del pre-registro.
