# Repetibilidad y determinismo — réplicas r2 de la batería completa

Síntesis descriptiva de las réplicas ya medidas: para cada configuración, una segunda
ejecución (`<base>_r2`) de la misma batería, con las mismas preguntas y el mismo GT,
comparada con su run base. **No se midió nada nuevo** para este documento; las cifras se
recalcularon sobre los JSON versionados con:

```bash
python3 -m jevbench.jev81 repeat <base> <base>_r2
# nimble/tev1: python3 scripts/jev103_typed_analyze.py r2 <base>   (enmienda E1 de JEV-103)
```

## Universo y unidades

- El **acuerdo r2** cuenta **decisiones pareadas** (pregunta × caso, sobre los éxitos
  comunes de ambas réplicas) en las **once fases**, incluida ood: 191 casos × 5 preguntas +
  3 casos ood × 3 = **964** (955 sin ood). Los rechazos comunes lo reducen (luna: 934, con los
  mismos 6 rechazos en las dos réplicas; Strands: 959, con el rechazo de `papers32/P11`
  repetido). El ajustado, en cambio, usa diez fases (excluye ood). El acuerdo no es un
  recuento de aciertos contra el GT.
- No se mezcla con McNemar/Holm53, que mide otra cosa: las discordancias **b/c** cuentan
  **casos** que solo acierta uno de los dos runs (contra el GT) dentro de cada pregunta ×
  fase, y las **53** son las pruebas de la familia Holm.
- El IC95 es Clopper-Pearson sobre la proporción pareada.
- **Δp** es la media y el máximo de |Δ probabilidad| sobre los componentes escalares
  comunes (cada opción, una observación).
- **Δ ajustado** solo se calcula cuando las dos réplicas tienen las mismas fases
  completas; aquí se cumple en todos los pares. El valor absoluto cubre las fases
  completas de ese par (en luna, las incompletas por rechazo quedan fuera): sirve para
  comparar base con r2 dentro de cada fila, no entre filas ni con el marcador.
- **Criterio de referencia:** en repetibilidad no hay línea base de mayoría que poner en
  la tabla. La referencia es el acuerdo **≥ 97 %** fijado como descriptivo en JEV-81
  (sobre la estimación puntual, no sobre el IC). JEV-84 pre-registró para Haiku un listón
  propio de ≥ 95 %. Ninguno de los dos es una prueba de equivalencia.

## Tabla por modelo

| modelo (run base → r2) | tipo · cómo se sirve | acuerdo r2 (IC95) | Δp medio · máx | Δ ajustado | fechas base → r2 |
|---|---|---|---|---|---|
| **Jev 1.14** (`jev_v114_typesafe_preview`) | decisor dedicado · API TypeSafe (`jev-preview` → `jev-1.14.0`) | 955/964 = **99,1 %** (98,2–99,6) | 0,007 · 0,12 | −0,5 (50,3→49,8) | 15-oct → 15-oct (JEV-104) |
| **Jev 1.13** (`jev_v113_typesafe`) | decisor dedicado · API TypeSafe (`jev-latest` → `jev-1.13.0`) | 957/964 = **99,3 %** (98,5–99,7) | 0,007 · 0,10 | −1,3 (50,3→49,0) | 15-oct → 15-oct (JEV-104, E2) |
| **Microsoft-Decision-1** (`jev_ms_decision1`) | decisor tipado · OpenRouter (snapshot `…-20261009`) | 959/964 = **99,5 %** (98,8–99,8) | 0,008 · 0,17 | −1,0 (47,3→46,3) | 10-oct → 10-oct (JEV-90) |
| **gpt-6-luna-decisions** (`jev_luna_decisions`) | LLM generalista · endpoint de decisiones de OpenRouter (`…-20261006`) | 934/934 = **100 %** (99,6–100,0) | 0,000 · 0,00 | 0,0 (49,7→49,7) | 7-oct → 7-oct, mismo día (JEV-81) |
| **Claude Haiku 5.5** (`llm_haiku55_adapt_prob`) | LLM generalista · API Anthropic con adaptador `llm` (probabilities, thinking adaptativo) | 919/964 = **95,3 %** (93,8–96,6) | 0,037 · 0,70 | −1,4 (73,0→71,5) | 8-oct → 8-oct, mismo día (JEV-84) |
| **CLM-v0.1-8B** (`clm_v0.1_8b`) | cabeza de decisión local · estación Intel (vLLM XPU) | 958/964 = **99,4 %** (98,7–99,8) | 0,004 · 0,05 | −1,3 (−41,0→−42,3) | 3-oct → 14-oct, **entre sesiones del servidor** (JEV-103) |
| **Strands Decider 2B v19** (`strands_2b_hobson_v19_xpu`) | LoRA + cabeza pointer local · estación Intel (XPU) | 958/959 = **99,9 %** (99,4–100,0) | 0,001 · 0,01 | +0,2 (17,9→18,1) | 3-oct → 14-oct, **entre sesiones** (JEV-103) |
| **Drex v1.5** (`drex_v15_9b`) | cabeza pointer local · `serve.py` en el DGX | 964/964 = **100 %** (99,6–100,0) | 0,000 · 0,00 | 0,0 (43,7→43,7) | 13-oct → 14-oct (JEV-103) |
| **Nimble-9B** (`nimble_9b`) | LoRA local sobre Qwen3.5-9B · DGX | 964/964 = **100 %** (99,6–100,0) | 0,000 · 0,00 | 0,0 (46,9→46,9) | 30-sep → 14-oct (JEV-103) |
| **Tev1-4B** (`tev1_4b`) | fine-tune local · DGX | 964/964 = **100 %** (99,6–100,0) | 0,000 · 0,00 | 0,0 (27,0→27,0) | 30-sep → 14-oct (JEV-103) |
| **Tev1-0.8B** (`tev1_0.8b`) | fine-tune local · DGX | 964/964 = **100 %** (99,6–100,0) | 0,000 · 0,00 | 0,0 (−8,8→−8,8) | 30-sep → 14-oct (JEV-103) |

## Lecturas

a) **La repetibilidad observada varía entre las configuraciones medidas y no se separa por
   la etiqueta LLM/decisor.** Hay pares idénticos tanto locales (Drex, Nimble, Tev1 ×2 en el
   DGX, Δp = 0) como por API (luna, 934/934 con los mismos 6 rechazos). Jev por API cambia
   7–9 decisiones de 964 (~99 %). Haiku por API cambia 45 (95,3 %), por encima de su listón
   propio del 95 % y por debajo de la referencia descriptiva del 97 %. CLM y Strands, también
   cabezas locales, difieren **entre sesiones del servidor** en la estación Intel (6/964 y
   1/959). En CLM, la rotación d1 de la misma sesión que la r2 da salidas idénticas a r2 en
   los 194 casos. La causa no está identificada; la caché de prefijos de la pila servida es
   solo una hipótesis sin verificar. Estos pares mezclan modelos, servicios, hardware y
   fechas distintos, así que **no permiten atribuir las diferencias al modelo, al servicio o
   a la sesión**. Un par idéntico tampoco demuestra determinismo general.

b) **Cada configuración del marcador se mide con una sola ejecución** (algunas son cascadas
   de dos pasadas). Este consolidado describe la variación observada entre dos ejecuciones
   por configuración (hasta 45 decisiones de 964 en la que más cambia) y sirve de contexto
   para leer discordancias entre versiones o modelos. Conserva los veredictos
   pre-registrados publicados, pero **no reevalúa su robustez** frente a la variabilidad
   entre ejecuciones: Holm corrige la multiplicidad de pruebas, no esa variabilidad, y dos
   réplicas no fijan un límite garantizado de ruido.

c) **La rotación d1 se lee junto a r2** (regla de atribución de JEV-104). Si d1 y r2 tienen
   acuerdos parecidos según la regla pre-registrada, los cambios **no se atribuyen** al
   orden. Ese contraste no identifica su causa ni demuestra que no haya efecto de orden.
   Ejemplos con sus dictámenes: Jev 1.14, d1 98,7 % frente a r2 99,1 %, estable; Nimble-9B,
   d1 94,5 % con r2 100 %, sensible al orden según el criterio pre-registrado.

d) **Cobertura (pendiente, no hallazgo).** La tabla cubre **configuraciones concretas**.
   No tienen réplica r2 de la batería completa en el harness moderno:
   - las familias Decider, AnyJev, GLiNER, Julia, gpt-6.1-sol, GPT-OSS-120B,
     Qwen3.8-Flash-Next, Ministral-3B-med, Gemma 3 / MedGemma, Span-01, Clef-27B y Clef-Flash;
   - gpt-6-luna por el adaptador `llm` (`llm_gpt6luna_*`) ni por su ruta nativa
     (`oai_luna_decisions`): la fila de luna es solo el endpoint de decisiones de OpenRouter;
   - las variantes de Haiku sin thinking.
   Casos intermedios: **Qwen3.8-27B** solo tiene réplicas de recortes diagnósticos (JEV-67/72),
   y las `diag_qwen38_*_r2` de JEV-63/65/66/71 son subruns sobre 2 casos fijos por fase con
   prompts y formatos distintos: sirven como cobertura de formato y **no son comparables** con
   esta tabla. **DiffusionGemma** solo replicó papers32+adv3, y **Laya** solo tiene el rerun
   histórico bit a bit (legacy). El run principal de Jev (`jev_v3`, por OpenRouter) **no
   tiene réplica moderna**: las disponibles son de las configuraciones TypeSafe 1.13/1.14, que
   no acreditan la repetibilidad de ese run.

## Discrepancia anotada (Haiku, Δ ajustado)

El acuerdo publicado de Haiku (919/964 = 95,33 %) coincide con el recálculo. El Δ
ajustado publicado en JEV-84 era **−1,80** (69,29→67,49), calculado con GT v4; con el GT
v5 vigente el mismo par da **−1,4** (73,0→71,5), coherente con el marcador actual
(73/72). Solo cambia la versión del GT, no las respuestas.
