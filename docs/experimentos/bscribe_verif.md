# bscribe_verif — ¿sirve un System One como verificador de BroncoScribe? (JEV-111)

**Estado:** pre-registro redactado el 25-oct-2026 **antes** de ejecutar ningún modelo. GT
validado por el usuario el 25-oct-2026 (JEV-112; decisiones al final) y promovido a `data/`
(`gt_version` v1). Solo se ejecuta después del commit que congela GT y pre-registro.

**Commit del GT congelado:** `b4429e0d` (25-oct-2026).

## Contexto

BroncoScribe (proyecto hermano) genera informes de broncoscopia/EBUS desde un dictado:
ASR → normalización → extracción a JSON con `medgemma:27b` → plantillas. Su plan
`docs/plans/verificador-system-one.md` (BRO-75) propone un **verificador** System One local
que compruebe, hecho a hecho, que el borrador JSON está respaldado por la transcripción y que
solo emita avisos, sin corregir nada. Este set mide si Clef-Flash 9B sirve para esa tarea
**antes** de integrarlo. Es una tarea distinta a la batería (triaje, papers): las cifras de la
batería no la predicen.

## Pregunta

Dado un dictado ficticio en español y una afirmación atómica sobre él («se puncionó la
estación 7», «siete pases», «22 G», «ROSE no disponible»…), ¿decide el modelo correctamente si
la afirmación está respaldada por el texto, también cuando el texto es una transcripción ASR
con errores?

## Datos

- **Hechos (GT):** `data/bscribe_verif_facts.json` — 118 hechos sobre los 10 guiones
  ficticios de BroncoScribe (`benchmarks/asr/fictional_v1`, casos A1–A4 y B1–B6): 63
  verdaderos y 55 falsos cercanos (120 en el borrador; A3-01 y A3-07 retirados en la validación) (estación vecina, número de pases o calibre cambiado, ROSE
  con otro resultado, complicación negada en el texto, vía de abordaje cambiada,
  autocorrecciones de A3 y omisiones de A4/B4). Familias: `estacion`, `pases`, `calibre`,
  `tamano`, `rose`, `complicaciones`, `via`, `tecnica`, `muestras`, `destino`, `hallazgo`,
  `localizacion`, `cantidad`, `indicacion`, `administrativo`, `autocorreccion`, `omision`.
  Redactados **solo a partir de los guiones**, sin ver ninguna salida de modelo.
- **Estados:** `data/bscribe_verif_states.json` — 46 textos: los 10 guiones de
  referencia y 36 transcripciones ASR ya medidas en BroncoScribe (faster-whisper
  large-v3-turbo en DGX, gpt-4o-mini-transcribe, gpt-4o-transcribe y whisper small en Jetson),
  deduplicadas por sha256, con su procedencia (`origin`). El texto enviado (`text`) es la
  transcripción con las **4 reglas de normalización de BroncoScribe** aplicadas (copia
  congelada en `BSCRIBE_NORMALIZATION`), porque es lo que vería el verificador en producción;
  el texto crudo queda en `raw_text`.
- **GT por estado:** cada hecho lleva `evidence` (regex que deben aparecer) y `trap` (regex que
  no deben aparecer) sobre el texto normalizado (minúsculas, sin tildes). En los guiones se
  cumplen siempre (`check` falla si no). En una transcripción ASR que no las cumple, el hecho
  **se excluye** de esa transcripción (el ASR perdió la evidencia o escribió el valor falso):
  nunca se invierte la etiqueta. Con el GT validado: 535 pares estado×hecho, 26 excluidos,
  **509 decisiones** (262 verdaderas, 247 falsas; mayoría constante 0,515).
- Los patrones aceptan variantes de **formulación** («15 x 10», «10 derecha», «lavado bronquio
  alveolar»), no errores de ASR: un error que la normalización de BroncoScribe no corrige
  cuenta como evidencia perdida.

## Sistema evaluado (fijo)

- Una pregunta `noul` por hecho; **todas las del caso en una sola llamada**, en el orden del
  fichero de hechos (como haría el verificador). Las preguntas de un caso son idénticas para
  todos sus estados.
- Texto de la pregunta y `criteria` (constantes `INSTRUCTIONS` y `CRITERIA` de
  `jevbench/bscribe_verif.py`; instrucciones en inglés, como la batería, con la afirmación en
  español). `questions_hash` del set: **`e342efcef902`** tras la enmienda E1 (`cf7434c38aaa` antes).
- Configuraciones:
  1. **Principal:** `Cloudflare/clef-flash`, revisión `17f0b0ad64efb65d273590632833508766b2aae6`,
     bf16, XPU en .70, adaptador `clef`, `max_length=16384` (el estado más largo cabe sin truncar).
  2. **Comparador:** `Cloudflare/clef` (27B), revisión `2f3de3dd`, bf16, DGX, adaptador `clef`.
  3. **Línea base:** mayoría constante.

```bash
python3 -m jevbench.bscribe_verif run clef --run bv_clef_flash_9b_xpu \
  --opt model=Cloudflare/clef-flash --opt revision=17f0b0ad64efb65d273590632833508766b2aae6 \
  --opt device=xpu --opt dtype=bfloat16
python3 -m jevbench.bscribe_verif run clef --run bv_clef_27b \
  --opt model=Cloudflare/clef --opt revision=2f3de3dd --opt device=cuda --opt dtype=bfloat16
python3 -m jevbench.bscribe_verif score bv_clef_flash_9b_xpu bv_clef_27b --vs bv_clef_27b
```

## Métricas

Sobre las decisiones incluidas, con umbral 0,5:

- **sensibilidad** = fracción de hechos falsos con p < 0,5 (el verificador avisaría);
- **tasa de FP** = fracción de hechos verdaderos con p < 0,5 (aviso falso);
- accuracy, Brier, errores seguros por 100 decisiones (conf. ≥ 0,9), y sensibilidad / FP con
  el umbral de aviso seguro p < 0,1;
- IC 95 % por **bootstrap por caso clínico** (10 clústeres: las decisiones de un mismo guion no
  son independientes);
- desglose por fuente (referencia vs. cada ASR) y por familia, descriptivo;
- subgrupo **atribución** (B5-10, B5-11, B6-10, B6-11: el valor existe en el dictado pero
  corresponde a otra estación o vía) informado aparte, descriptivo: su GT depende de la lectura
  humana porque los patrones no comprueban la atribución.
- McNemar Flash vs. 27B sobre las mismas decisiones: **descriptivo** (no corrige el agrupamiento).

## Criterio de éxito (fijado antes de ejecutar)

Clef-Flash **cumple** si, sobre todas las decisiones incluidas:

- sensibilidad **≥ 0,70**, **y**
- tasa de FP **≤ 0,05**.

El FP es estricto a propósito: un borrador típico tiene ~6 hechos verdaderos, y con 5 % de FP
saldría un aviso falso cada ~3 borradores; más que eso agota la atención del médico.
Si Flash no cumple, se mide el 27B con el mismo criterio antes de descartar la vía (BRO-75,
Fase 2). Un resultado negativo se documenta como tal.

**Con 10 guiones, el resultado es una señal de viabilidad, no una validación.** La diversidad
clínica la aportará la ampliación del corpus de BroncoScribe (BRO-38).

## Reglas

- No se ajustan hechos, patrones, preguntas, umbrales ni el criterio después de ver una salida
  de modelo. Una variante (p. ej. instrucciones en español, una pregunta por llamada) se
  pre-registra aparte.
- `run` solo lee los ficheros promovidos a `data/`; nunca los borradores.
- No toca la batería principal ni el marcador, la web o el sitio público.

## Decisiones de la validación (JEV-112, 25-oct-2026)

Validado por el usuario, que aceptó las propuestas de la revisión:

1. **A3, autocorrecciones:** el verificador debe atenerse al valor final; A3-08 («se realizó
   EBUS», corregido a «sin EBUS») mantiene GT 0. **A3-01 y A3-07 se retiran:** «Corrijo:
   dieciocho milímetros en serie previa» admite leer 18 mm como medida de una serie anterior y
   no como corrección de los 17 mm, así que ni «mide 18 mm» ni «mide 17 mm» tienen GT inequívoco.
2. **B4-04** («varios pases» ⇒ número exacto especificado = 0): se mantiene.
3. **B4-07** («Fin del procedimiento» ⇒ complicaciones documentadas = 0): se mantiene (omisión).
4. **Atribución por estación o vía** (B5-10, B5-11, B6-10, B6-11): se mantienen con GT 0 y se
   informan además como subgrupo aparte (ver Métricas).
5. **Negaciones** (A2-07, B1-16, B2-10, B5-15, B6-15): se mantienen.
6. **Exclusiones por ASR** (26, incluidos «22 gauch» y «bronquialvelar»): se mantiene el criterio
   de excluir; mide lo que el verificador vería hoy con la normalización vigente de BroncoScribe.
7. **Idioma:** instrucciones en inglés y afirmación en español, como la batería; una variante en
   español se pre-registraría aparte.

## Enmienda E1 (25-oct-2026, antes de obtener ninguna salida válida)

La prueba corta de Clef-Flash en .70 (2 estados, run `smoke_bv_clef_flash`, borrado) falló en los
dos con `ValueError` antes de producir ninguna probabilidad: `CRITERIA` iba como cadena y el
formato wire de `noul` (código del propio modelo, `joint_schema_model.question_options`) exige un
diccionario `{"true": …, "false": …}`. Corrección de formato: el **mismo texto** pre-registrado se
reparte entre las dos opciones («yes only if the transcript states it explicitly (any wording;
numbers in digits or words)» / «no if it is absent, stated with a different value, negated, or
corrected later in the dictation»). No cambian hechos, etiquetas, estados, umbrales ni criterio de
éxito. `questions_hash`: `cf7434c38aaa` → `e342efcef902`.

## Enmienda E2 (25-oct-2026): variante CUDA de Clef-Flash, pre-registrada antes de ejecutarla

El run principal (`bv_clef_flash_9b_xpu`) terminó con 24 salidas `NaN` (las 8 primeras preguntas de
B6 en sus 3 estados: el caso con más preguntas, 16). Diagnóstico sobre B6__reference: en XPU bf16 se
repite idéntico; en CPU (bf16 y fp32) las 16 preguntas dan probabilidades válidas y deterministas, y
con solo 8 preguntas también en XPU. Es un fallo del backend XPU, no del modelo. El run principal se
informa tal cual, con las dos lecturas (NaN excluidos / NaN contados como aviso).

Se pre-registra, **antes de ejecutarla**, una variante con la misma revisión, preguntas, umbral y
criterio en GPU NVIDIA: run `bv_clef_flash_9b_cuda`, DGX Spark .80 (GB10), `device=cuda`, bf16,
venv `.venv-clef` (torch 2.14.1+cu130, transformers 5.17.0). Se informa junto al principal, sin
sustituirlo; los NaN, si los hubiera, se tratan igual (dos lecturas).

## Enmienda E3 (25-oct-2026): tres variantes más, pre-registradas antes de ejecutarlas

Mismo GT v1, preguntas, umbral, métricas y criterio; se informan junto a las anteriores, sin
sustituir el run principal. `run` admite `--max-questions N` (las preguntas del caso, en su orden, en
llamadas de como mucho N; por defecto, todas en una, como en el pre-registro).

1. `bv_clef_flash_9b_xpu_r2` — la configuración principal repetida en .70 **después de actualizar el
   sistema (10 paquetes, ninguno de Intel/GPU) y reiniciar**: ¿persisten los NaN con 16 preguntas?
2. `bv_clef_flash_9b_xpu_q8` — .70, XPU bf16, **como mucho 8 preguntas por llamada**.
3. `bv_jev114_typesafe` — Jev por la API de TypeSafe (`provider=typesafe`, `model=jev-latest`, que
   resuelve a `jev-1.14.0`; versión registrada en `meta`), adaptador `jev`, `retries=3`, todas las
   preguntas del caso en una llamada. Solo envía los textos del set (guiones ficticios y sus
   transcripciones ASR, sin datos de pacientes).

Los NaN, si aparecen, se tratan igual (dos lecturas).

## Enmienda E4 (25-oct-2026): elephant-1 y mammoth-1 (Base Labs), pre-registrados antes de ejecutarlos

Mismo GT v1, preguntas, umbral, métricas y criterio; se informan junto a los anteriores. DGX Spark
.81 (GB10), adaptador `baselabs` (OneJev qev @81ce62f + `serve.patch`, en proceso; el mismo entorno
que `docs/infra_runs/baselabs_local.md`), todas las preguntas del caso en una llamada (el motor pasa
solo a modo secuencial si una petición desborda el índice de 32 bits):

1. `bv_elephant_1_local` — `baselabs/elephant-1` @ `c54a55c2d362a7e30ff30814d28e39054e954d58`.
2. `bv_mammoth_1_local` — `baselabs/mammoth-1` @ `03007ab3c4481bf01c71ef63adbbbc4b2093d71a`.

Los NaN o rechazos por longitud, si aparecen, se tratan igual (dos lecturas).

## Hallazgo lateral para BroncoScribe

Al construir el set aparece que la regla `gauge` de `TRANSCRIPT_NORMALIZATION_RULES` no cubre
«22 gauch» (gpt-4o-transcribe y gpt-4o-mini-transcribe en B1, B3, B5): falta `gauch\b` en el
patrón.

## Resultados (25-oct-2026)

GT v1, `questions_hash` `e342efcef902`, 46 estados por run, 0 errores de ejecución; 509 decisiones
incluidas (262 verdaderas, 247 falsas; mayoría constante 0,515). IC 95 % por bootstrap de casos.

| run | hardware | acierto | sensibilidad | FP | Brier | salidas NaN | mediana/estado |
|---|---|---|---|---|---|---|---|
| `bv_clef_flash_9b_xpu` (principal) | Intel Arc Pro B70, XPU bf16 | 0,943 | 1,000 [1,000–1,000] | 0,023 [0,000–0,042] | — | **24** (B6, 8 preguntas × 3) | 479 ms |
| `bv_clef_flash_9b_cuda` (E2) | DGX Spark .80, CUDA bf16 | 0,988 [0,978–1,000] | 1,000 [1,000–1,000] | 0,023 [0,000–0,042] | 0,013 | 0 | 797 ms |
| `bv_clef_27b` (comparador) | DGX Spark .81, CUDA bf16 | 0,998 [0,994–1,000] | 0,996 [0,986–1,000] | 0,000 [0,000–0,000] | 0,007 | 0 | 2.369 ms |
| mayoría constante | — | 0,515 | — | — | — | — | — |

- **Criterio pre-registrado** (sensibilidad ≥ 0,70 y FP ≤ 0,05): **cumplen los tres.** En el run
  principal el FP 0,023 excluye los 24 NaN (el scorer no los cuenta); **contándolos como aviso al
  médico** el FP sube a **30/262 = 0,115 y no cumple**. Las dos lecturas se informan: el NaN es un
  fallo del backend XPU (diagnóstico en E2), no una decisión del modelo.
- **XPU frente a CUDA:** en las 486 decisiones sin NaN, **misma decisión en las 486** (|Δp| ≤ 0,031).
  En CUDA las 24 decisiones de B6 que fallaban en XPU salen válidas y correctas.
- **Errores de Clef-Flash (CUDA):** 6 avisos falsos sobre hechos verdaderos, ningún hecho falso sin
  aviso: B1-10 «se documenta el consentimiento informado» (en 3 estados de B1), A1-05 «150 ml en el
  BAL» (gpt-4o), B3-01 «se puncionó la estación 7» (referencia) y B3-02 «ganglio de 16 mm» (gpt-4o).
  Ninguno con confianza ≥ 0,9 (0 errores seguros). **Clef-27B:** un único error, A3-09 «biopsias en el
  lóbulo inferior izquierdo» (falso) aceptado con p = 0,76 en la transcripción whisper-turbo.
- **Subgrupo de atribución** (B5-10/11, B6-10/11): 12/12 aciertos en Flash CUDA y en 27B.
- McNemar Flash CUDA vs 27B (descriptivo, sin corregir el agrupamiento): b = 1, c = 6, p = 0,125.
- **Lectura:** con 10 guiones ficticios es una señal de viabilidad, no una validación. Clef-Flash en
  GPU NVIDIA cumple con margen; en la GPU Intel hace falta limitar las preguntas por llamada o
  tratar cualquier NaN como fallo con aviso. El 27B no se equivoca en ningún hecho verdadero.
### Variantes E3 (25-oct-2026)

| run | configuración | acierto | sensibilidad | FP | Brier | NaN | mediana/estado | coste |
|---|---|---|---|---|---|---|---|---|
| `bv_clef_flash_9b_xpu_r2` | XPU, 16 por llamada, tras actualizar y reiniciar | — | — | — | — | **24** (los mismos de B6) | — | — |
| `bv_clef_flash_9b_xpu_q8` | XPU, ≤ 8 preguntas por llamada | 0,986 [0,973–1,000] | 1,000 [1,000–1,000] | 0,027 [0,000–0,052] | 0,014 | 0 | 442 ms | — |
| `bv_jev114_typesafe` | Jev `jev-1.14.0`, API TypeSafe | 0,984 [0,967–0,998] | 0,992 [0,975–1,000] | 0,023 [0,003–0,056] | 0,012 | 0 | 470 ms | $0,0032 (46 estados) |

- **La actualización y el reinicio no arreglan el NaN** en XPU: mismos 24 NaN en B6 (el resto de
  decisiones difiere del run principal en 110/486 a nivel de probabilidad, sin cambiar el criterio).
- **Con ≤ 8 preguntas por llamada desaparece el NaN** en XPU y Clef-Flash **cumple**: misma decisión
  que en CUDA en 508/509 (repartir las preguntas cambia algo las probabilidades, |Δp| ≤ 0,33). Un
  aviso falso más que en CUDA (7: B1-10 en 4 estados, A1-05, B3-01, B3-02), ninguno con confianza ≥ 0,9.
- **Jev 1.14 por TypeSafe cumple**: 6 avisos falsos (A1-05 «150 ml en el BAL» en 4 estados, B2-07
  «nueve pases en 11R», B3-02 «ganglio de 16 mm») y **2 hechos falsos sin aviso** (B2-13 «se puncionó
  la estación 11L» con p = 0,85 y 0,57), ninguno con confianza ≥ 0,9.
### Variantes E4 (25-oct-2026): Base Labs en local

| run | modelo | acierto | sensibilidad | FP | Brier | NaN | mediana/estado |
|---|---|---|---|---|---|---|---|
| `bv_elephant_1_local` | elephant-1 (9B), .81 | 0,992 [0,980–1,000] | 1,000 [1,000–1,000] | 0,015 [0,000–0,041] | 0,006 | 0 | 684 ms |
| `bv_mammoth_1_local` | mammoth-1 (27B), .81 | 0,996 [0,990–1,000] | 0,996 [0,986–1,000] | 0,004 [0,000–0,012] | 0,004 | 0 | 2.203 ms |

- **Los dos cumplen**, sin NaN ni errores de ejecución, con las 16 preguntas en una llamada.
- **elephant-1** detecta todos los hechos falsos; 4 avisos falsos (A1-05 «150 ml en el BAL» en 3 estados y
  B3-02 «ganglio de 16 mm», p = 0,05, el único error con confianza ≥ 0,9 de las variantes válidas).
- **mammoth-1**: 1 aviso falso (B3-02) y 1 hecho falso sin aviso (A3-09 «biopsias en el lóbulo inferior
  izquierdo», p = 0,85, el mismo que falla Clef-27B). Junto a Clef-27B, el mejor resultado del set.
- Atribución: 12/12 en los dos. McNemar descriptivo frente a Clef-27B: elephant-1 b = 1, c = 4,
  p = 0,375; mammoth-1 b = 0, c = 1, p = 1,0.
- Manifiesto: [`docs/infra_runs/bscribe_verif.md`](../infra_runs/bscribe_verif.md).
