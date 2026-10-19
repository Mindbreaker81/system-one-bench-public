# Errores con mucha confianza («confianza mal puesta») — análisis descriptivo

**Estado:** plan fijado el 17-oct-2026 **antes** de calcular nada; los resultados se añaden debajo
sin cambiar el plan. Análisis **exploratorio y descriptivo** sobre resultados ya medidos: no
mide nada nuevo, no cambia casos, GT, preguntas ni scorer, y no hace contrastes de hipótesis.

## Motivación

Un decisor tipado no puede inventar texto como un LLM: devuelve probabilidades sobre opciones
cerradas. Lo más parecido a «alucinar» es **decidir con mucha seguridad algo que el GT contradice**.
Este análisis cuantifica esa confianza mal puesta con lo que ya tenemos. Las dos pruebas que
miden directamente si el modelo se apoya en el texto (preguntas sin respuesta en el estado y
ablación de la evidencia) necesitan casos nuevos y están en JEV-107 y JEV-108 (bajo JEV-88).

## Plan (fijado antes de calcular)

- **Universo de runs:** las configuraciones de una pasada (`kind == "single"`) de `web.RUNS`.
  Se excluyen las cascadas (sus probabilidades son una fusión de dos decisores). Solo se
  incluyen runs con las 11 fases del ajustado (`score.ADJ_PHASES`); los incompletos se listan aparte.
- **Universo de decisiones:** las 11 fases (194 casos; 964 decisiones caso×pregunta, de ellas 514
  binarias `noul`). Casos con error del run, fuera.
- **Decisión y acierto:** los del scorer (`metrics.normalize` + `metrics.point`, acierto estricto):
  `noul` con umbral 0,5; `choice`, la etiqueta emitida; `score`, el nivel redondeado.
- **Confianza de la decisión:**
  - `noul`: max(p, 1−p);
  - `choice`: probabilidad normalizada de la etiqueta emitida;
  - `score`: probabilidad normalizada del nivel decidido; si el run no trae distribución, la
    decisión queda sin confianza y fuera de las métricas de confianza.
- **Métrica primaria (binarias `noul`, comparables en todos los runs):**
  - **errores seguros por cada 100 binarias:** decisiones erróneas con confianza ≥ 0,9, divididas
    entre todas las binarias respondidas;
  - con el mismo umbral, la **precisión cuando está seguro** (aciertos entre las binarias con
    confianza ≥ 0,9) y la **fracción de errores que son seguros**.
- **Secundarias:** lo mismo con umbral 0,99, y lo mismo sobre todas las decisiones con confianza
  (las tres clases de pregunta).
- **Salidas discretas:** los runs `*_disc` (y cualquier run cuyas binarias sean todas 0/1)
  emiten confianza 1 por construcción. Se informan aparte y **no** se ordenan junto al resto.
- **Línea base:** la mayoría oráculo no emite confianza; se da su tasa de error en binarias
  como referencia de lo que cuesta acertar en este universo.
- **Lectura:** descriptiva. Sin McNemar ni Holm; ningún «mejor/peor calibrado» se afirma a partir
  de esta tabla. Las 11 fases incluyen adv1/adv2 (pocos casos), como el ajustado.

Script: `scripts/errores_seguros.py` (solo lectura; usa `jevbench.score`/`jevbench.metrics`
sin modificarlos). Salida completa: `docs/experimentos/errores_seguros/`.

## Resultados (17-oct-2026)

64 configuraciones de una pasada con probabilidades y 13 de salida discreta, todas con las 11
fases; ninguna incompleta. Tabla completa: [`errores_seguros/tabla.md`](errores_seguros/tabla.md);
cifras: [`errores_seguros/resultados.json`](errores_seguros/resultados.json). Mayoría oráculo:
29,0 % de error en binarias (no emite confianza).

Selección (binarias; «errores seguros» = erróneas con confianza ≥ 0,9, por cada 100 binarias):

| configuración | error % | seguras ≥ 0,9 % | errores seguros /100 | precisión si ≥ 0,9 | % de sus errores que son seguros | errores /100 con ≥ 0,99 |
|---|---|---|---|---|---|---|
| Jev 1.13 (`jev_v3`) | 10,5 | 58,2 | 0,8 | 98,7 | 7,4 | 0,0 |
| Jev 1.14 preview | 9,5 | 58,2 | 0,6 | 99,0 | 6,1 | 0,0 |
| Decider-4B | 14,0 | 39,3 | 0,4 | 99,0 | 2,8 | 0,0 |
| Drex v2.0 (OR) | 11,9 | 50,0 | 0,6 | 98,8 | 4,9 | 0,0 |
| Classify-1 (OR) | 16,7 | 28,4 | 0,0 | 100,0 | 0,0 | 0,0 |
| Clef-27B | 8,6 | 73,5 | 1,2 | 98,4 | 13,6 | 0,0 |
| Perplexity Decider (OR) | 10,7 | 76,5 | 2,9 | 96,2 | 27,3 | 0,2 |
| Mercury Decide (OR) | 10,3 | 82,1 | 3,5 | 95,7 | 34,0 | 0,4 |
| Solar Decide (OR) | 12,3 | 82,5 | 6,4 | 92,2 | 52,4 | 2,5 |
| Span-01 Pro | 17,9 | 83,1 | 10,7 | 87,1 | 59,8 | 0,0 |
| Haiku 5.5 adapt (prob) | 9,7 | 67,3 | 0,4 | 99,4 | 4,0 | 0,0 |
| gpt-6-luna (prob) | 7,6 | 92,2 | 4,5 | 95,1 | 59,0 | 2,1 |
| Qwen3.8-27B FP8, esquema en el prompt (JEV-67) | 10,7 | 88,7 | 5,8 | 93,4 | 54,5 | 1,6 |
| Qwen3.8-27B NVFP4 sin preguntas visibles (ajustado −17,3) | 21,9 | 97,8 | 21,3 | 78,3 | 97,3 | 18,7 |
| AnyJev Qwen3-8B L0 | 19,6 | 93,4 | 16,3 | 82,5 | 83,2 | 12,6 |
| Julia-1 | 64,2 | 57,4 | 38,9 | 32,2 | 60,6 | 15,0 |
| salidas discretas (13 runs) | 6,6–16,9 | 100 | 6,6–16,9 | 83,1–93,4 | 100 | 6,6–16,9 |

Lectura descriptiva (sin contrastes; no prueba que una configuración esté mejor calibrada que otra):

- **La mayoría de los decisores dedicados rara vez se equivoca muy segura.** 26 configuraciones
  (Jev 1.13 y 1.14, Decider, Drex, Clef, Tev1, Kev, Nimble, Microsoft-Decision-1, Classify-1,
  Perplexity, Liquid, Mercury y Solar Flash) quedan entre 0 y 3,7 errores seguros por cada 100
  binarias y, con confianza ≥ 0,99, en 1,0 o menos. Jev 1.13: 0,8 (el 7,4 % de sus errores son
  seguros). Por encima quedan Solar Decide (6,4), DiffusionGemma (7,0–8,8), gpt-6-luna-decisions
  (7,0–8,0), Laya (9,3) y Span-01 (10,5–10,7).
- **Tajante no es lo mismo que confiado en falso.** Mercury y Perplexity emiten probabilidades
  extremas en la mitad de las binarias, pero con confianza ≥ 0,99 solo se equivocan en 0,4 y 0,2 de
  cada 100: sus extremos suelen acertar. Con ≥ 0,9 suben a 3,5 y 2,9, por encima de Jev.
- **Los LLM generalistas mal configurados son los que más «alucinan» en este sentido.** Qwen3.8-27B NVFP4
  sin preguntas visibles (la configuración del −17,3 ajustado) decide con ≥ 0,9 el 97,8 % de las binarias y el 97,3 % de sus
  errores son seguros (21,3 por cada 100). Con la configuración corregida de JEV-67 baja a 5,8, y
  con thinking activado (JEV-68) a 2,3. AnyJev, Qwen3.8-Flash y el Ministral médico quedan entre
  13,8 y 24,7. Haiku 5.5 y Qwen3.8-27B por Cerebras, entre 0,4 y 1,4.
- **Julia-1** tiene la confianza al revés: cuando está seguro acierta solo el 32,2 % (CLM también
  queda por debajo del 50 %, pero solo en 18 binarias seguras).
- **Lo que menos se equivoca seguro a veces es porque casi nunca está seguro.** GLiNER, Strands y
  CLM deciden con ≥ 0,9 entre el 0,8 y el 3,5 % de las binarias; su 0,0–2,3 no indica buena
  calibración, sino falta de confianza (y su error total es alto: 18–35 %). Por eso la tabla da
  siempre la fracción de seguras al lado.
- **La salida discreta esconde la incertidumbre.** Al emitir 0/1, todo error es un error seguro
  (6,6–16,9 por cada 100). Es el mismo modelo que en `_prob` con menos información para el
  usuario: con las probabilidades se puede filtrar lo inseguro; con la salida discreta no.

Lo que este análisis **no** dice: si el modelo se apoya en el texto o en lo habitual. Eso es lo
que miden JEV-107 (preguntas sin respuesta en el estado) y JEV-108 (ablación de la evidencia).
