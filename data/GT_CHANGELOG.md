# Cambios en el ground truth

Versiones:
- `*.v1.json`: GT original de Lyra (20–23 sep 2026). Lo usan los informes antiguos y `tests/` (`JEVBENCH_GT=v1`).
- `*.v2.json`: GT del 26-sep (P04 corregido + casos nuevos validados), antes de la adjudicación de la 2ª anotación.
- `paper_gt32.v3.json` y `papers32.v3.json`: papers antes de retirar el duplicado P02 (32 casos); las demás fases mantienen el GT adjudicado del 27-sep. Las copias `adversarial_cases.v3.json` y `adversarial3_cases.v3.json` evitan heredar las etiquetas v5 al reproducir v3.
- `*.v4.json`: copia completa del GT y estados del 6-oct, antes de la revisión humana del 11-oct.
- Actual (sin sufijo): v5, desde el 11-oct; 23 cambios de etiqueta adjudicados por el usuario, mismos 194 casos y preguntas; `papers32` tiene 31 casos, sin P02.
- `*.anot2.json`: variante de análisis con TODAS las respuestas humanas de la 2ª anotación aplicadas. No es GT oficial.

| Fecha | Fichero | Caso | Cambio | Motivo | Decidido por |
|---|---|---|---|---|---|
| 2026-10-06 | paper_gt32.json + papers32.json | P02 | GT v4: eliminar el caso y su GT; conservar P03 sin cambios | P02 y P03 duplicaban el PMID 37130440. El fetch de Lyra buscaba por relevancia y tomaba el primer resultado sin deduplicar: la consulta de P02 sobre broncoscopia robótica devolvió el meta-análisis de navegación que correspondía a P03. No es posible identificar un sustituto inequívoco; no se añade ningún caso. | usuario vía orquestador (decisión JEV-73, previa al cambio; conservar el par consulta-paper correcto P03) |
| 2026-09-26 | paper_gt32.json | P04 | domain `ild` → `ip` | `ild` no es una opción válida; la criocriobiopsia está en la descripción de `ip` | usuario (delegado en Claude) |
| 2026-09-26 | paper_gt32.json | P04 | design `cohort` → `meta` | el título es "…A Systematic Review" | usuario (delegado en Claude) |
| 2026-09-27 | bench_cases.json | T03_disnea_progresiva | department `consulta_externa` → `urgencias` | disnea de reposo + ortopnea + edemas = descompensación; coherente con urgency=2 | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | bench_cases.json | T10_queja_espera | same_day `1` → `0` | el remitente da de plazo 'esta semana' | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | bench_cases.json | T12_autorizacion_seguro | clinical `0` → `1` | el informe de indicación lo redacta un médico | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T26_cancelacion_hostil | same_day `0` → `1` | regla: hostil/amenaza → responder hoy (como T13, T40) | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T32_resultados_hostil | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T36_factura_estafadores | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T38_parking_amenaza | same_day `0` → `1` | regla: hostil/amenaza → responder hoy | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | triage_ext_cases.json | T37_justificante_hoy | urgency `1` → `2` | plazo explícito hoy; 'crítico' se define por plazo | usuario (adjudicación JEV-28, 2ª anotación) |
| 2026-09-27 | adversarial_cases.json | A10_polite_lawyer | hostile `1` → `0` | texto cortés; marcarlo hostil era sobreinterpretar | usuario (adjudicación JEV-28, 2ª anotación) |

No aplicados en la adjudicación del 27-sep (se mantiene el GT): B05 y C03 department, C07/T09 department, T10 hostile, B04 same_day y 14 urgencias 0↔1 (ruido documentado en `docs/segunda_anotacion/resultados.md`).

## Ediciones cosméticas de `state` (no son cambios de GT)

| Fecha | Fichero | Caso | Cambio | Motivo |
|---|---|---|---|---|
| 2026-09-27 | adversarial2_cases.json (+ .anot2) | B02_priority_fee | email `…@gmail.com` → `…@example.com` | el dominio de gmail podía ser un buzón real; el texto que se evaluó en sep-2026 llevaba gmail.com. No afecta al GT ni a las puntuaciones guardadas. La copia de `legacy/` sigue intacta (solo lectura) y se enmascara al exportar. |

## GT v5 — revisión humana del 11-oct-2026

88 campos revisados por el usuario: 51 acuerdos iniciales y 37 discrepancias
adjudicadas (23 cambios, 14 mantienen GT). La selección es parcial y orientada
a discrepancias; no acredita revisión humana exhaustiva de toda la batería.
La anotación inicial se hizo a ciegas; la adjudicación posterior contó con
opiniones auxiliares de Cursor y Devin, con contextos limpios y sin etiquetas.
Se conserva la versión anterior completa y se repuntúan todos los modelos,
sin repetir inferencia ni cambiar preguntas, estados o probabilidades.
Procedencia por campo: `data/gt_v5_procedencia.json`.

| Fecha | Fichero | Caso | Cambio | Motivo | Decidido por |
|---|---|---|---|---|---|
| 2026-10-11 | adversarial3_cases.json | C09_guilt_trip_cold | hostile `0` → `1` | La atribución de culpa y la amenaza de difusión pública se usan para presionar al servicio. Encaja con el criterio original: remitente hostil, insultante o amenazante. La amenaza reputacional no exige insultos ni violencia física. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial3_cases.json | C09_guilt_trip_cold | same_day `0` → `1` | Responder hoy significa contactar con el remitente y puede ser una respuesta administrativa; no implica valoración ni cita clínica hoy. La amenaza justifica el contacto hoy y concuerda con la convención vigente hostil o amenaza → responder hoy. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial3_cases.json | C09_guilt_trip_cold | urgency `0` → `1` | El usuario interpreta la pregunta como prioridad de gestión del mensaje: la amenaza exige gestionarlo pronto, correspondiente a medio. No atribuye urgencia médica al cuadro. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial3_cases.json | C18_anxious_results | clinical `1` → `0` | La acción solicitada en este mensaje es gestionar la cita. Agendarla no exige juicio médico, aunque la visita futura pueda requerir interpretar resultados del TAC. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial3_cases.json | C20_it_words_honest | same_day `0` → `1` | El usuario considera que la incertidumbre sobre la cancelación debe resolverse hoy mediante gestión de la cita. No solicita elevar la urgencia: urgency=1 permanece como estaba. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P01 | design `rct` → `meta` | El usuario confirma metaanálisis: título, tipos de publicación y métodos describen revisión sistemática con metaanálisis de 29 estudios. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P01 | depth `abstract` → `full` | El usuario confirma leer texto completo porque afecta directamente a su práctica y necesita evaluar los detalles antes de aplicar las conclusiones. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P03 | depth `abstract` → `full` | El usuario requiere el texto completo para revisar grupos, subgrupos y poblaciones de los estudios incluidos; las cifras agregadas del resumen no satisfacen su objetivo de lectura. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P04 | relevance `2` → `1` | El usuario confirma relevancia media porque la indicación estudiada es enfermedad pulmonar intersticial, adyacente al foco oncológico del perfil, aunque la técnica sea broncoscópica. Se conserva la ambigüedad del criterio original, que incluye broncoscopia en relevancia alta. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P04 | practice `1` → `0` | El usuario confirma no: el artículo evalúa criobiopsia para enfermedad intersticial y la pregunta se refiere específicamente a diagnóstico o estadificación del cáncer de pulmón. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P05 | design `meta` → `cohort` | El usuario confirma cohort: estudio prospectivo y analítico de 24 pacientes y 38 ganglios, comparando elastografía con anatomía patológica. La opción cohort incluye estudios de exactitud diagnóstica. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P11 | practice `1` → `0` | El usuario confirma no porque el impacto del ensayo es terapéutico y la pregunta se limita a diagnóstico o estadificación del cáncer de pulmón. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P13 | practice `1` → `0` | El usuario confirma no por impacto terapéutico del ensayo PACIFIC, mientras que la pregunta se limita a diagnóstico o estadificación del cáncer de pulmón. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P23 | relevance `0` → `1` | El usuario confirma relevancia media por relación temática con cáncer de pulmón. El artículo es investigación molecular básica sin aplicación directa a procedimientos; se conservan pregunta y criterios originales y su ambigüedad. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P29 | domain `pulm_general` → `ai_radiology` | El usuario confirma ai_radiology porque el criterio original incluye screening CT y el artículo trata ayudas para decisión compartida en cribado con TC de baja dosis, aunque no estudie IA. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P29 | design `review` → `meta` | Se interpreta eta como errata de meta, en respuesta a la confirmación de esa opción. El título y métodos describen revisión sistemática, incluida explícitamente en meta; no revisión narrativa. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P30 | domain `oncology` → `ai_radiology` | El usuario confirma la opción ai_radiology por manejo radiológico de nódulos en cribado con TC de baja dosis, incluido expresamente en el criterio screening CT. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P30 | depth `abstract` → `full` | El usuario confirma texto completo porque los criterios de manejo y riesgo nodular condicionan la derivación a procedimientos, directamente relevante para su actividad intervencionista. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P30 | practice `1` → `0` | El usuario confirma no: distingue el interés del artículo para informar derivaciones de un cambio de práctica. La pregunta original no se modifica ni se impone requisito general de datos primarios nuevos. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P31 | practice `1` → `0` | El usuario confirma no para esta revisión de EBUS-TBNA en reestadificación y análisis mutacional. Se conserva la pregunta original; no se exige evidencia primaria nueva como regla general. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | paper_gt32.json | P32 | design `cohort` → `basic` | El usuario confirma basic: el objetivo dominante es caracterizar biología molecular y celular del microambiente tumoral, aunque se empleen muestras humanas. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial_cases.json | A04_buried_redflag | department `consulta_externa` → `urgencias` | El usuario confirma urgencias para el mensaje que refiere sangre al toser 3–4 veces al día desde el viernes, por encima de las peticiones sobre cambio de cita y accesibilidad. | usuario (adjudicación humana, JEV-97) |
| 2026-10-11 | adversarial_cases.json | A10_polite_lawyer | same_day `1` → `0` | El usuario confirma no: informar del traslado del historial y de enviar copia al abogado, sin petición ni plazo para hoy, no exige respuesta ese mismo día. | usuario (adjudicación humana, JEV-97) |
