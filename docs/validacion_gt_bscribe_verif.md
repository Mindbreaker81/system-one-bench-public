# Validación del GT — bscribe_verif (borrador)

Generado con `python3 -m jevbench.bscribe_verif labels --md …`. Pre-registro: `docs/experimentos/bscribe_verif.md` (JEV-111; validación JEV-112). Las dudas concretas para validar están en su sección «Dudas para la validación».

## 1. Hechos por caso

### A1

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| A1-01 | 1 | via | El broncoscopio se introdujo por vía nasal. |  |
| A1-02 | 1 | hallazgo | Se observa una estenosis en el bronquio principal derecho. |  |
| A1-03 | 1 | muestras | Se tomaron biopsias con pinza en cuatro ocasiones. |  |
| A1-04 | 1 | tecnica | Se realizó lavado broncoalveolar en el lóbulo inferior derecho. |  |
| A1-05 | 1 | cantidad | Se instilaron 150 mililitros en el lavado broncoalveolar. |  |
| A1-06 | 1 | administrativo | Se documenta el consentimiento informado. |  |
| A1-07 | 1 | complicaciones | No hubo complicaciones inmediatas. |  |
| A1-08 | 0 | via | El broncoscopio se introdujo por vía oral. |  |
| A1-09 | 0 | muestras | Se tomaron biopsias con pinza en seis ocasiones. |  |
| A1-10 | 0 | tecnica | El lavado broncoalveolar se hizo en el lóbulo superior derecho. |  |
| A1-11 | 0 | complicaciones | Hubo un neumotórax como complicación. |  |
| A1-12 | 0 | tecnica | Se realizó criobiopsia. |  |
| A1-13 | 0 | tecnica | Se realizó EBUS. |  |

### A2

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| A2-01 | 1 | hallazgo | La exploración llegó hasta los bronquios segmentarios de ambos lados. |  |
| A2-02 | 1 | muestras | Se tomó citología con cepillo. |  |
| A2-03 | 1 | hallazgo | No se observaron lesiones endobronquiales. |  |
| A2-04 | 1 | destino | Las muestras se enviaron a anatomía patológica. |  |
| A2-05 | 0 | muestras | Se tomaron biopsias con pinza. |  |
| A2-06 | 0 | hallazgo | Se observa una masa endobronquial. |  |
| A2-07 | 0 | complicaciones | Hubo sangrado significativo. | ⚠ El guion dice «sin sangrado significativo»: negación |
| A2-08 | 0 | tecnica | Se realizó lavado broncoalveolar. |  |

### A3

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| A3-02 | 1 | tecnica | Se hizo solo broncoscopia flexible, sin EBUS. |  |
| A3-03 | 1 | muestras | Se tomaron tres biopsias transbronquiales. |  |
| A3-04 | 1 | localizacion | El nódulo está en el lóbulo superior izquierdo. |  |
| A3-05 | 1 | complicaciones | Hubo un sangrado de grado uno. |  |
| A3-06 | 1 | cantidad | La saturación mínima fue del noventa y dos por ciento. |  |
| A3-08 | 0 | autocorreccion | Se realizó EBUS. | ⚠ El guion dice «Se realiza EBUS, perdonen… sin EBUS»: GT 0 por la corrección |
| A3-09 | 0 | localizacion | Las biopsias se tomaron en el lóbulo inferior izquierdo. |  |
| A3-10 | 0 | complicaciones | Hubo un sangrado de grado dos. |  |

### A4

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| A4-01 | 1 | hallazgo | Se observa una masa endoluminal parcialmente oclusiva. |  |
| A4-02 | 1 | complicaciones | El procedimiento fue sin complicaciones. |  |
| A4-03 | 1 | indicacion | La indicación es sospecha de neoplasia. |  |
| A4-04 | 0 | omision | Se documenta el consentimiento informado. |  |
| A4-05 | 0 | omision | Se indica la vía de entrada del broncoscopio (nasal u oral). |  |
| A4-06 | 0 | omision | Se especifica el número de muestras o biopsias tomadas. |  |
| A4-07 | 0 | omision | Se especifica en qué lóbulo o bronquio está la masa. |  |
| A4-08 | 0 | tecnica | Se realizó lavado broncoalveolar. |  |

### B1

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B1-01 | 1 | estacion | Se puncionó la estación 7. |  |
| B1-02 | 1 | tamano | El ganglio de la estación 7 mide quince por diez milímetros. |  |
| B1-03 | 1 | calibre | Se usó una aguja de 22 G. |  |
| B1-04 | 1 | pases | En la estación 7 se hicieron siete pases. |  |
| B1-05 | 1 | rose | ROSE no estaba disponible. |  |
| B1-06 | 1 | destino | Se envió material a bloque celular. |  |
| B1-07 | 1 | estacion | Se puncionó la estación 4R (cuatro derecha). |  |
| B1-08 | 1 | pases | En la estación 4R se hicieron cinco pases. |  |
| B1-09 | 1 | complicaciones | No hubo complicaciones. |  |
| B1-10 | 1 | administrativo | Se documenta el consentimiento informado. |  |
| B1-11 | 0 | estacion | Se puncionó la estación 4L (cuatro izquierda). |  |
| B1-12 | 0 | estacion | Se puncionó la estación 11R (once derecha). |  |
| B1-13 | 0 | calibre | Se usó una aguja de 25 G. |  |
| B1-14 | 0 | pases | En la estación 7 se hicieron seis pases. |  |
| B1-15 | 0 | rose | ROSE fue positiva para malignidad. |  |
| B1-16 | 0 | complicaciones | Hubo hemoptisis franca. | ⚠ El guion dice «sin hemoptisis franca»: negación |
| B1-17 | 0 | tecnica | Se realizó EUS-B por vía transesofágica. |  |

### B2

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B2-01 | 1 | estacion | Se puncionó la estación 10R (diez derecha). |  |
| B2-02 | 1 | pases | En la estación 10R se hicieron seis pases. |  |
| B2-03 | 1 | rose | ROSE fue negativa para malignidad. |  |
| B2-04 | 1 | estacion | Se puncionó la estación 10L (diez izquierda). |  |
| B2-05 | 1 | pases | En la estación 10L se hicieron ocho pases. |  |
| B2-06 | 1 | estacion | Se puncionó la estación 11R (once derecha). |  |
| B2-07 | 1 | pases | En la estación 11R se hicieron nueve pases. |  |
| B2-08 | 1 | destino | Se envió muestra a microbiología. |  |
| B2-09 | 0 | estacion | Se puncionó la estación 7. |  |
| B2-10 | 0 | complicaciones | Hubo una complicación mayor. | ⚠ El guion dice «sin complicaciones mayores»: negación |
| B2-11 | 0 | pases | En la estación 10L se hicieron doce pases. |  |
| B2-12 | 0 | rose | ROSE fue positiva para malignidad. |  |
| B2-13 | 0 | estacion | Se puncionó la estación 11L (once izquierda). |  |
| B2-14 | 0 | omision | Se especifica el calibre de la aguja. |  |

### B3

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B3-01 | 1 | estacion | Se puncionó la estación 7. |  |
| B3-02 | 1 | tamano | El ganglio mide dieciséis milímetros. |  |
| B3-03 | 1 | pases | Se hicieron cuatro pases. |  |
| B3-04 | 1 | calibre | Se usó una aguja de 22 G. |  |
| B3-05 | 1 | rose | No hubo ROSE. |  |
| B3-06 | 1 | complicaciones | El procedimiento fue sin incidencias. |  |
| B3-07 | 0 | calibre | Se usó una aguja de 19 G. |  |
| B3-08 | 0 | rose | ROSE fue representativa. |  |
| B3-09 | 0 | estacion | Se puncionó la estación 4R (cuatro derecha). |  |
| B3-10 | 0 | pases | Se hicieron tres pases. |  |
| B3-11 | 0 | complicaciones | Hubo un neumotórax. |  |

### B4

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B4-01 | 1 | indicacion | Se realizó EBUS por linfadenopatía mediastínica. |  |
| B4-02 | 1 | destino | Se envió material. |  |
| B4-03 | 0 | omision | Se especifica qué estación ganglionar se puncionó. |  |
| B4-04 | 0 | omision | Se especifica el número exacto de pases. | ⚠ El guion dice «varios pases»: no es un número |
| B4-05 | 0 | omision | Se especifica el calibre de la aguja. |  |
| B4-06 | 0 | omision | Se documenta si hubo ROSE o su resultado. |  |
| B4-07 | 0 | omision | Se documenta la presencia o ausencia de complicaciones. | ⚠ «Fin del procedimiento» no documenta complicaciones |

### B5

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B5-01 | 1 | pases | En la estación 7N1 se hicieron cuatro pases. |  |
| B5-02 | 1 | tamano | El ganglio de 7N1 mide dieciséis por nueve milímetros. |  |
| B5-03 | 1 | pases | En la estación 7N2 se hicieron tres pases. |  |
| B5-04 | 1 | calibre | En la estación 7N2 se usó una aguja de 25 G. |  |
| B5-05 | 1 | rose | ROSE fue representativa en la estación 7N2. |  |
| B5-06 | 1 | pases | En la estación 4R1 se hicieron cinco pases. |  |
| B5-07 | 1 | via | El ecobroncoscopio se introdujo por vía oral. |  |
| B5-08 | 1 | destino | Se enviaron muestras a bloque celular. |  |
| B5-09 | 1 | calibre | Se usó una aguja de 22 G en la estación 7N1. |  |
| B5-10 | 0 | rose | ROSE fue representativa en la estación 7N1. | ⚠ Atribución por estación: en 7N1 «sin ROSE disponible»; la representativa es de 7N2 |
| B5-11 | 0 | calibre | En la estación 7N2 se usó una aguja de 22 G. | ⚠ Atribución por estación: 7N2 es 25 G; 22 G es de 7N1 y 4R1 |
| B5-12 | 0 | via | El ecobroncoscopio se introdujo por vía nasal. |  |
| B5-13 | 0 | estacion | Se puncionó la estación 4L (cuatro izquierda). |  |
| B5-14 | 0 | pases | En alguna estación se hicieron seis pases. |  |
| B5-15 | 0 | complicaciones | Hubo hemoptisis significativa. | ⚠ El guion dice «sin hemoptisis significativa»: negación |
| B5-16 | 0 | estacion | Se puncionó la estación 10R (diez derecha). |  |

### B6

| id | etiqueta | familia | afirmación | nota |
|---|---|---|---|---|
| B6-01 | 1 | tecnica | Fue un procedimiento combinado EBUS y EUS-B. |  |
| B6-02 | 1 | pases | En la estación 7 se hicieron tres pases por vía endobronquial. |  |
| B6-03 | 1 | estacion | Se exploró la estación 8 por EUS-B. |  |
| B6-04 | 1 | pases | En la estación 8 se hicieron cuatro pases. |  |
| B6-05 | 1 | estacion | Se identificó una adenopatía en el tronco celíaco. |  |
| B6-06 | 1 | pases | En el tronco celíaco se hicieron cinco pases. |  |
| B6-07 | 1 | rose | ROSE fue negativa para malignidad en el tronco celíaco. |  |
| B6-08 | 1 | calibre | Se usó una aguja de 22 G. |  |
| B6-09 | 1 | tamano | El ganglio de la estación 8 mide dieciséis por diez milímetros. |  |
| B6-10 | 0 | via | La estación 7 se puncionó por vía transesofágica (EUS-B). | ⚠ Atribución por vía: la 7 es por EBUS endobronquial |
| B6-11 | 0 | via | El tronco celíaco se puncionó por vía endobronquial (EBUS). | ⚠ Atribución por vía: el tronco celíaco es por EUS-B |
| B6-12 | 0 | calibre | Se usó una aguja de 25 G. |  |
| B6-13 | 0 | rose | ROSE fue positiva para malignidad. |  |
| B6-14 | 0 | estacion | Se puncionó la estación 4R (cuatro derecha). |  |
| B6-15 | 0 | complicaciones | Hubo neumomediastino. | ⚠ El guion dice «sin neumomediastino»: negación |
| B6-16 | 0 | pases | En alguna estación se hicieron siete pases. |  |

## 2. Exclusiones automáticas en transcripciones ASR

535 pares estado×hecho; 509 incluidos, 26 excluidos. Revisar a mano que cada exclusión es real (el ASR perdió la evidencia o escribió el valor falso) y no un patrón demasiado estricto.

| estado | hecho | etiqueta | motivo |
|---|---|---|---|
| A1__gpt4o_mini_transcribe | A1-04 | 1 | evidence_lost |
| A1__gpt4o_transcribe | A1-04 | 1 | evidence_lost |
| A1__whisper_small_jetson | A1-02 | 1 | evidence_lost |
| A1__whisper_small_jetson | A1-04 | 1 | evidence_lost |
| A1__whisper_small_jetson | A1-06 | 1 | evidence_lost |
| A1__whisper_turbo_dgx | A1-02 | 1 | evidence_lost |
| A2__whisper_small_jetson | A2-01 | 1 | evidence_lost |
| A2__whisper_small_jetson | A2-03 | 1 | evidence_lost |
| A2__whisper_turbo_dgx | A2-04 | 1 | evidence_lost |
| A4__whisper_small_jetson | A4-01 | 1 | evidence_lost |
| A4__whisper_small_jetson | A4-03 | 1 | evidence_lost |
| A4__whisper_turbo_dgx | A4-01 | 1 | evidence_lost |
| B1__gpt4o_transcribe | B1-03 | 1 | evidence_lost |
| B1__whisper_small_jetson | B1-05 | 1 | evidence_lost |
| B1__whisper_small_jetson | B1-10 | 1 | evidence_lost |
| B3__gpt4o_mini_transcribe | B3-04 | 1 | evidence_lost |
| B4__gpt4o_mini_transcribe | B4-01 | 1 | evidence_lost |
| B5__gpt4o_mini_transcribe | B5-02 | 1 | evidence_lost |
| B5__gpt4o_transcribe | B5-02 | 1 | evidence_lost |
| B5__gpt4o_transcribe | B5-04 | 1 | evidence_lost |
| B5__gpt4o_transcribe | B5-05 | 1 | evidence_lost |
| B5__gpt4o_transcribe | B5-09 | 1 | evidence_lost |
| B5__gpt4o_transcribe | B5-10 | 0 | evidence_lost |
| B5__gpt4o_transcribe | B5-11 | 0 | evidence_lost |
| B6__gpt4o_mini_transcribe | B6-09 | 1 | evidence_lost |
| B6__whisper_turbo_dgx | B6-01 | 1 | evidence_lost |

## 3. Reparto

Incluidos: 509 (262 verdaderos, 247 falsos); mayoría constante 0.515.

