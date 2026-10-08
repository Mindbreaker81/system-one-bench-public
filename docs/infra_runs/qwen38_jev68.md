# JEV-68/71/72 — Sesión Qwen3.8-27B FP8 en <host>: thinking visible, órdenes de `department`, `discrete` y frases anti-inyección visibles

Manifiesto del experimento: **pre-registro congelado** (abajo, del diseño R13 §4–§6
con la enmienda P71.2 y las correcciones aceptadas de R16) + resultados al final.
Issues: <<tracker>
<<tracker>
<<tracker> GT v4 en JEV-73.
Precedente directo de formato y lecciones: `docs/infra_runs/qwen38_jev67.md`.

## Estado del congelado

- Base del repo: `08964a8` (versión **1.0.0**: GT v4 — `papers32` sin el duplicado
  P02, JEV-73 — y mantenimiento Qwen JEV-71/72). Batería congelada: **194 casos**,
  `papers32` = **31**.
- Harness de la sesión: `jevbench/qwen_session.py` + `tests/test_qwen_session.py` (nuevos) y ampliaciones opt-in
  de `jevbench/adapters/llm.py` (`choice_order`) y `jevbench/rotation.py` (órdenes d0–d3). Implementación Devin
  (T5, C10–C13); revisión independiente Codex R16 → R17 → R18 → R19 → **R20 APTO** (6-oct): los diez hallazgos de
  R16 y los posteriores, cerrados con tests de regresión; `tests.test_qwen_session` sin omitidos y suite completa
  en verde. Se commitean junto con este manifiesto **antes de cualquier inferencia**.
- Este fichero fija diseño, celdas, órdenes, puertas, umbrales, topes y calendario
  **antes de ejecutar**. Lo que depende del código corregido queda como
  **PENDIENTE (dry-run de C10)** (§13) y se añadirá como apéndice de hashes al
  cerrarlo, sin alterar este texto.
- Sin git en el encargo de redacción (orden del operador). El commit del
  manifiesto antes de inferir queda para el operador; si se retrasa, se documenta
  como la desviación autorizada de JEV-67 (texto congelado en el fichero antes de
  cualquier inferencia, commit posterior).

## Valores congelados calculados (6-oct-2026, sobre `08964a8`, sin GPU)

Batería por fase (GT v4, 194 casos):

| Fase | Casos | `questions_hash` | ¿`department`? |
|---|---:|---|---|
| triage_es | 14 | `9a81e9763d94` | sí |
| triage_en | 14 | `9a81e9763d94` | sí |
| papers32 | 31 | `74026502c3ac` | no |
| adv1 | 10 | `9a81e9763d94` | sí |
| adv2 | 10 | `9a81e9763d94` | sí |
| ood | 3 | `93ea3deb7eab` | no |
| triage_ext_es | 26 | `9a81e9763d94` | sí |
| triage_ext_en | 26 | `9a81e9763d94` | sí |
| adv3 | 20 | `9a81e9763d94` | sí |
| adv4 | 20 | `9a81e9763d94` | sí |
| adv5 | 20 | `9a81e9763d94` | sí |
| **Total** | **194** | | `department`: 160 casos en 9 fases |

Los `questions_hash` no cambian respecto de JEV-67 (el hash cubre las preguntas,
no los casos; retirar P02 no toca las preguntas). Los calculados aquí reproducen
los congelados en JEV-67 §7.3.

Otros valores fijados:

- **Subconjunto de primacía** (regex `\b(?:ebus|broncoscop\w*|bronchoscop\w*)\b`
  *ignore-case* sobre el `state` + GT `department != bronchoscopia`): **37
  registros fase/caso, 35 IDs distintos**, sha256[:12] del subconjunto ordenado
  `4e7e2877f27d` (coincide con R16). Lista congelada con el freeze; no se
  recalcula tras inferir.
- **Órdenes `department`** (etiquetas, criterios y GT intactos; solo cambia el
  orden de las opciones, en prompt **y** esquema a la vez):

  | Orden | `department`, de primera a última |
  |---|---|
  | d0 | bronchoscopia, consulta_externa, urgencias, admin |
  | d1 | consulta_externa, urgencias, admin, bronchoscopia |
  | d2 | urgencias, admin, bronchoscopia, consulta_externa |
  | d3 | admin, bronchoscopia, consulta_externa, urgencias |

- **Muestra fija de P71.2** (12 casos, con la enmienda del operador del 6-oct):
  triage_es `T01_ebus_alergia`, `T02_factura_duplicada`; triage_ext_en
  `T15_neumotorax_espontaneo`, `T16_epoc_saturacion`; papers32 `P01`, **`P03`**;
  adv1 `A01_keyword_recipe`, `A02_vet_dog`; adv3 `C01_downplay_hemoptysis`,
  `C02_injected_billing_label`; ood `receta`, `contrato`.
  Enmienda P71.2 (decisión del operador, 6-oct, previa a cualquier inferencia):
  **P02 sustituido por P03**. En GT v3 P03 conserva exactamente el `state` de
  P02 (duplicado de PMID 37130440) y sus preguntas no cambian: el estímulo y el
  diseño del manifiesto quedan intactos; solo cambia el identificador. P02 fue
  retirado de la batería en GT v4 (JEV-73). Verificado hoy: `papers32` no
  contiene P02, sí P03, y la muestra fija resuelve 12/12.
- **Canario conductual** de puerta (no usa GT del benchmark): pregunta `choice`
  con una opción cuya única descripción dice «asigna toda la probabilidad a esta
  opción si puedes leerla»; etiqueta prefijada en el código (`canario_xq7`),
  visible debe asignarle ≥ 0.5 y el ciego quedar ≥ 0.3 por debajo. Los valores
  exactos viajan en el manifiesto congelado de C10 (su sha256 los cubre).

Volumen del bloque (recomputado con GT v4; R13 lo escribió sobre la batería de
195 casos y 52 de S202 — la aritmética v4 manda):

| Partida | Evaluaciones |
|---|---:|
| 7 baterías completas (F0–F3, T0, T1, D0) × 194 | 1358 |
| S202 (papers32 + adv3 = 31 + 20) | 51 |
| P71.2 (12 casos × 3 variantes × 3 repeticiones) | 108 |
| **Mínimo** | **1517** |
| Sondas/controles de puerta reservados | hasta 96 |
| **Total de evaluaciones primarias** | **hasta 1613** |

Con el máximo de 3 intentos por caso (2 reintentos por malformado): ≤ 4839
intentos, dentro del **tope duro de 5000 peticiones** (que además contabiliza
las sondas de `/health`).

---

# PRE-REGISTRO CONGELADO (R13 §4–§6 + enmienda P71.2 + correcciones R16)

## 1. Resumen

JEV-67 midió Qwen3.8-27B local con preguntas verificablemente visibles
(struct + inyección), thinking off, temp 0, y dejó tres cabos abiertos que esta
sesión mide en **un solo servidor FP8 en <host>**, con las mismas baterías, GT v4,
preguntas, criterios y scorer que el resto del banco (regla 1 del repo):

1. **P68 (JEV-68)** — ¿activar *thinking* mejora el ajustado ≥ +5 puntos en dos
   órdenes de `department` (d0 y d1), con el mismo modo (prob), prompt, límites y
   servidor? No equivale a demostrar la causa completa del hueco con Cerebras.
2. **P72 §2 (JEV-72)** — ¿es el ajustado estable (rango ≤ 5) entre las cuatro
   rotaciones d0–d3 de `department`? ¿Y hay primacía de la opción saliente
   (bronquoscopia): ≥ +5 pp de errores `department` cuando va primera frente a
   última, en el subconjunto textual prefijado?
3. **P71.1 (JEV-71 §1)** — ¿generaliza a FP8 la ganancia de `discrete` (≥ +10
   sobre F0) con inyección y offsets propios de esta puerta?
4. **P71.2 (JEV-71 §2)** — con preguntas visibles, ¿las frases anti-inyección
   (V3/V5) mejoran ≥ +10 pp el acierto diagnóstico medio por caso frente a V1 en
   la muestra fija de 12 casos?
5. **S202 (JEV-72)** — suelo de ruido: repetición de F0 en papers32+adv3 con
   seed 202 (acuerdo ≥ 97 %).

Coste: **0 USD de API externa** (no se llama a ninguna). Electricidad/hardware
**no medidos**: se informarán horas GPU y tokens; no llamarlo «coste total cero».

## 2. Decisiones ya fijadas (se incorporan literalmente)

1. **Batería GT v4** (commit `08964a8`, versión 1.0.0): 194 casos, `papers32` =
   31 (P02 retirado, JEV-73). GT, criterios, textos, niveles `score` y scorer
   intactos. Las once fases en el orden de JEV-67: triage_es, triage_en,
   papers32, adv1, adv2, ood, triage_ext_es, triage_ext_en, adv3, adv4, adv5.
   Sin entrenamiento ni selección de prompts con los resultados nuevos.
2. **P71.2: P02 sustituido por P03** en la muestra fija (mismo `state`; diseño
   intacto; decisión del operador del 6-oct, ver §«Valores congelados»).
3. **Host único <host> (`dgx-spark-b`, GB10)**, SGLang propio, con la identidad del
   §3. No se asigna <host> ni <host>; si <host> está ocupado, se pospone (no desalojar
   servicios ajenos ni mover el bloque a otro host sin revisar este
   pre-registro).
4. **Sin API externa: coste USD 0**; electricidad/hardware no medidos.
5. **Comparaciones históricas descriptivas**: los runs de JEV-67 (A1–C2) se
   puntuaron con GT v3 (195 casos) y están **re-puntuados con GT v4**. Ambas
   lecturas redondean a los mismos enteros (A1 51, A2 51, A3 59, B1 50, B2 63,
   C1 48; FP8 nostruct histórico 49). Toda comparación de esta sesión con
   JEV-67 o Cerebras es **descriptiva**: cambia el GT de referencia y, en su
   día, cambiaron backend/precisión/host. Llegar a 59/65 (Cerebras struct/nostruct
   prob), acordar con A1/A3 o replicar el +7 de A3 son secundarios descriptivos,
   nunca condiciones de éxito.

## 3. Servidor: identidad y verificaciones previas

| Elemento | Valor congelado |
|---|---|
| Host | <host> `dgx-spark-b`, aarch64, NVIDIA GB10, 128 GB memoria unificada |
| Imagen | `lmsysorg/sglang:qwen38-27b` — ID local `0076dffa60b7`, digest histórico `sha256:febfb971c7352570fc445c466ebd6ffc9d896024958e544a60f2137fd85856b1` (según JEV-67) |
| Versión histórica | SGLang `0.0.0.dev0+qwen38.27b.g561c8f3`, xgrammar |
| Pesos | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` |
| Copia local | `<ruta-local>` (81 ficheros, ~29 GB), verificada el 6-oct contra los hashes LFS de HF (**67/67 OK**). No está en la biblioteca `ai-models` (solo GGUF): esta copia es la única fuente; si faltara o no verificara, la rama es **NO EJECUTABLE** |
| Arranque histórico | `QUANT=fp8 PORT=8000 EXTRA_ARGS="--model-path <ruta-local>" ./start.sh` en `<ruta-local>` |
| Cliente | túnel 18001→8000; `base_url http://127.0.0.1:18001/v1`; modelo servido `qwen3.8-27b-sglang`; `api_key none` |

Antes de arrancar (obligatorio):

- `nvidia-smi; docker ps; free -g`: GPU, servicios, memoria y puertos libres; no
  parar ni tocar servicios ajenos.
- El contenedor de JEV-67 **se eliminó al cerrar la issue**: no suponer que
  sigue arrancado. Al recrearlo, verificar que el digest de la imagen sigue
  siendo `sha256:febfb971…`; si difiere, **parar y documentar el cambio antes de
  inferir** (los históricos quedan como referencia descriptiva).
- Congelar en el arranque: snapshot completo (digest, sha256 de `start.sh`,
  cmdline y config efectiva), versiones de SGLang/torch/xgrammar/CUDA,
  `system-one-adapter` y `typesafe-sdk` efectivos (referencia: 0.2.1 / 0.7.1),
  KV/Mamba/MTP y tokenizer/chat template (sha del template). Algunas líneas FP8
  históricas se reconstruyeron del script y no del proceso: capturar las reales
  esta vez. Espacio: snapshot 29 GB si faltara, imagen y ≥ 2 GB reservados para
  raw/results; detener la captura al alcanzar la reserva sin perder raw.

## 4. Configuración común de cliente (bloque congelado)

```
adapter=llm · provider=openai · model=qwen3.8-27b-sglang
base_url=http://127.0.0.1:18001/v1 · api_key=none
structured=true · inject_schema_in_prompt=true · normalize=true
capture_raw=true · retries_malformed=2
max_tokens=16384 · timeout=300 · case_timeout=600 · secuencial
extra_body={"chat_template_kwargs":{"enable_thinking": false|true},
            "temperature":0, "seed":101}   (S202: seed 202; diag: 101/202/303)
prompt=typesafe (batería) | sin_antinj | antinj_alt (solo P71.2)
choice_order=department:d0|d1|d2|d3
```

- `max_tokens=16384` y los `timeout` elevados respecto de JEV-67 se aplican a
  **todos** los controles y experimentales: la comparación causal es contra los
  controles frescos (F0/F1), no contra el histórico; no adjudicar a thinking un
  cambio de límites.
- **Thinking true explícito**: nunca activarlo quitando `false` (el default no
  acredita activación). Sin `top_p`/`presence_penalty` distintos entre celdas;
  registrar y congelar los defaults efectivos del servidor. Sin
  `reasoning_effort` estilo Cerebras.
- Rotación **solo de `department`** (d0–d3), con el resto de `choice` intacto.
  No es el `rotate_choice=1` de JEV-67 (ese rota todas las `choice`, incluidas
  papers/ood). El orden se aplica a prompt y esquema juntos; las etiquetas,
  criterios y el GT no cambian (el literal del modelo sigue mapeando a la
  etiqueta original); las preguntas `score` no rotan.

## 5. Celdas y runs (nombres congelados)

| Celda | Run | Issue | Config | Tope | Puerta |
|---|---|---|---|---:|---|
| **F0** | `llm_qwen38_27b_fp8_jev68_off_d0_prob` | 68 | prob, off, d0, seed 101 | 90 min | `prob_typesafe_off_d0` |
| **F1** | `llm_qwen38_27b_fp8_jev68_off_d1_prob` | 68 | = F0 con d1 | 90 min | `prob_typesafe_off_d1` |
| **T0** | `llm_qwen38_27b_fp8_jev68_on_d0_prob` | 68 | = F0 con thinking **true** | 150 min | `prob_typesafe_on_d0` |
| **T1** | `llm_qwen38_27b_fp8_jev68_on_d1_prob` | 68 | = F1 con thinking **true** | 150 min | `prob_typesafe_on_d1` |
| **F2** | `llm_qwen38_27b_fp8_jev72_off_d2_prob` | 72 | = F0 con d2 | 90 min | `prob_typesafe_off_d2` |
| **F3** | `llm_qwen38_27b_fp8_jev72_off_d3_prob` | 72 | = F0 con d3 | 90 min | `prob_typesafe_off_d3` |
| **D0** | `llm_qwen38_27b_fp8_jev71_off_d0_disc` | 71 | discrete, off, d0, seed 101 | 90 min | `disc_typesafe_off_d0` |
| **S202** | `llm_qwen38_27b_fp8_jev72_off_d0_prob_s202` | 72 | = F0 con seed 202, solo papers32+adv3 (51) | 30 min | `prob_typesafe_off_d0` |

F0/F1 se comparten entre JEV-68 (control) y JEV-72 (órdenes d0/d1) sin
repetirlos: no se cuentan como GPU nuevas dos veces. La conclusión de «dos
órdenes» de P68 queda acotada a `department`; d2/d3 son celdas de P72.

Diagnósticos P71.2 (nueve runs, cada uno sobre los 12 casos fijos; orden de
variantes por repetición congelado; semillas 101/202/303; tope **compartido** de
45 min; orden de fases por run: adv1, adv3, ood, papers32, triage_es,
triage_ext_en):

| Rep | Orden de variantes | Runs |
|---|---|---|
| r1 (seed 101) | V1, V3, V5 | `diag_qwen38_jev71_fp8_visible_v{1,3,5}_prob_r1` |
| r2 (seed 202) | V3, V5, V1 | `…_v{3,5,1}_prob_r2` |
| r3 (seed 303) | V5, V1, V3 | `…_v{5,1,3}_prob_r3` |

V1 = `prompt=typesafe`, V3 = `sin_antinj`, V5 = `antinj_alt`; **todas**
structured+inject. Usar exactamente las transformaciones congeladas de JEV-65
(incluidas las dos frases retiradas/reescritas y el apéndice); recalcular los
hashes por familia del **prompt final visible** (el hash del prompt ciego no
sirve de puerta). No reciclar como control V1 los datos a ciegas de JEV-65.
Puertas propias: `prob_sin_antinj_off_d0` y `prob_antinj_alt_off_d0` (V1 usa la
puerta de F0).

## 6. Puertas de visibilidad (bloqueantes)

Una puerta por combinación **modo × prompt × thinking × orden** (9 en total),
al inicio de la sesión y tras cualquier reinicio/deriva del servidor. Casos: una
por familia — adv1/A01, papers32/P01, ood/receta (3 visibles) —, un control
negativo ciego en A01 y el canario conductual (visible + ciego). Criterios, todos
sobre el **primer intento**:

1. **Cliente**: sha256[:12] del system prompt **precomputado antes de responder**
   igual al observado; apéndice JSON **decodificado** idéntico al
   `response_format.schema` (nada de subcadenas sobre texto escapado); IDs,
   instrucciones y criterios completos; orden esperado de `department` en prompt
   **y** esquema.
2. **Motor**: `usage` del primer intento presente; `prompt_tokens` contra
   referencia por caso — off prob d0: histórico FP8 nostruct ±2; off prob
   reordenado (d1–d3): ±10; thinking on y prompts V3/V5: referencias
   **precalculadas con el tokenizer/render del checkpoint** (±2), congeladas para
   los 194 casos antes de inferir y nunca derivadas de la respuesta que luego se
   quiere validar; discrete: **offsets por familia medidos por esta puerta en
   <host>** (±2 por caso; no usar los offsets de <host>/<host> de JEV-67).
3. **Control negativo**: A01 struct sin inject, mismo modo/prompt/thinking;
   visible−ciego ≥ 200 tokens y raw del ciego sin preguntas.
4. **Canario**: la opción marcada solo existe en las descripciones del esquema;
   el visible responde al canario y el ciego no; **ambas peticiones acreditadas**
   (raw + usage + cliente + thinking). Sin evidencia de un lado, la puerta FALLA.
5. **Thinking efectivo**: declarado en `chat_template_kwargs` == observado en el
   raw (razonamiento crudo o telemetría), distinguiendo activación de cantidad
   de cómputo.

Sin `usage` o sin raw → puerta FAIL. Cualquier violación **por caso** durante la
batería invalida el run y para (`status=invalid_visibility`); un vector nulo con
visibilidad acreditada se registra como fallo de salida, no como excusa para
ignorar una puerta. No reutilizar las puertas sobrescritas de JEV-67; la
evidencia de cada ejecución de puerta queda archivada de forma inmutable ligada
a su `gate_id` y sesión. Si se captura prompt renderizado del motor, documentar
su formato real (no asumir el de vLLM): cliente + tokens + canario son las
evidencias. Capturas privadas; exports saneados sin abstracts, rutas ni claves.

La vigilancia por caso del runner aplica los mismos criterios de cliente +
thinking + tokens a cada caso de cada batería; los casos sin `usage` se
contabilizan y **> 2 % de casos sin usage ⇒ run NO EVALUABLE** para el marcador.

## 7. Calendario intercalado (congelado)

Bloque de batería: en la fase i, el orden de celdas es la rotación `i mod 7` de
`[F0, T1, F2, D0, F1, T0, F3]`; S202 va tras el ciclo en papers32 y adv3.
**79 slots** (11 fases × 7 celdas + 2 de S202). Ejemplo (fase triage_es): F0 →
T1 → F2 → D0 → F1 → T0 → F3; en triage_en empieza por T1, y así cíclicamente.
El intercalado controla deriva temporal; mantiene orden de casos y seeds. Una
sola carga de pesos y un solo escritor/supervisor; cada celda conserva su run,
presupuesto, `gate_id` y metadatos, y se registran los tiempos de cada subbloque.

Los diagnósticos P71.2 siguen su calendario propio (§5), después del bloque de
batería. Sesiones: id `s81-<fecha-hora>` anotado al arrancar; tras un reinicio
del servidor, `--new-session` (nuevas puertas; el tope global del encargo **no**
se amplía: peticiones y tiempo ya consumidos se conservan).

## 8. Hipótesis, umbrales y análisis pre-registrado

Método común: Δ de ajustado pareado con bootstrap de **casos completos**
agrupados por cluster (traducciones ES/EN comparten id entre fases; papers
ligados por PMID), pesos iguales de fase y baselines originales fijos, 10.000
remuestreos, semilla analítica **271828**. Fases del ajustado: las diez
habituales (ood excluido por baseline saturada). Umbrales congelados antes de
inferir; una rama con visibilidad inválida, cobertura insuficiente o tope
agotado es **NO EVALUABLE**, no «refutada».

| Bloque | Hipótesis | Confirmada | Refutada | IC |
|---|---|---|---|---|
| **P68** | thinking mejora ≥ **+5** de ajustado en **ambos** órdenes (Δ0=T0−F0, Δ1=T1−F1) | L de ambos IC ≥ +5 | U de cualquiera < +5 (refuta la mejora práctica universal; no excluye ganancia menor o dependiente del orden) | 97,5 % por contraste (2 comparaciones, Bonferroni ≥ 95 %) |
| **P72 estabilidad** | rango del ajustado entre d0–d3 ≤ **5** | U95 del rango ≤ 5 | L95 > 5 | 95 %, bootstrap conjunto |
| **P72 primacía** | bronquoscopia primera (d0) causa ≥ **+5 pp** de errores `department` que última (d1), en el subconjunto prefijado (37 registros/35 IDs, sha `4e7e2877f27d`) | Δ ≥ 5, L95 > 0 y contraste primario significativo tras Holm | U95 < 5 (para esa mejora ≥ 5) | 95 %, bootstrap por clusters |
| **P71.1** | `discrete` mejora ≥ **+10** de ajustado sobre F0 en FP8 | L95(Δ) ≥ 10 | U95 < 10 | 95 % |
| **S202** | acuerdo S202↔F0 ≥ **97 %** (suelo de ruido) | L95 ≥ 97 % | U95 < 97 % | 95 %, Clopper-Pearson |
| **P71.2** | V3 o V5 mejora ≥ **+10 pp** de acierto diagnóstico medio por caso sobre V1, condición visible | L ≥ 10 | U < 10 (para esa mejora práctica; no equivale a «las frases no modulan nada») | 97,5 %, bootstrap por **12 casos** |

Detalles que se reportan y no se pueden saltar:

- **P68**: reportar interacción Δ1−Δ0 y costes/latencia, sin adjudicar
  causalidad universal. No elegir una sola T ganadora. Low de Cerebras y
  `thinking=true` de SGLang no son presupuestos de razonamiento iguales; aunque
  T llegue a 59, persisten orden, backend, pesos y cantidad de cómputo distintos
  (atribuirlo todo a thinking atribuye demasiado).
- **P72 estabilidad**: publicar la media aritmética de los cuatro ajustados con
  IC y el rango; **no** puntuar una distribución fusionada ni elegir el máximo
  como nuevo score oficial. Papers/ood no rotan: detectan ruido temporal, no son
  nuevos órdenes de esas preguntas.
- **P72 primacía**: subconjunto congelado por regla textual **antes de inferir**
  (regex + GT≠bronquoscopia; lista y hash en el informe); no seleccionar solo
  los casos que mejoraron en A3. Comparar error d0−d1 y publicar d2/d3 como
  control de otras posiciones. Familia Holm de **7 contrastes**: los seis pares
  de órdenes y la primacía; para McNemar, **una versión por caso traducido
  (convención ES)** en los siete (corrección R16 §9: contar las dos traducciones
  como réplicas reduce p-values); el bootstrap del agregado mantiene ambas
  traducciones agrupadas. Reportar el n real mínimo del subgrupo y su potencia
  limitada. No atribuir al orden cambios de niveles `score` reordenados
  (prohibido: `score` no rota). El resultado queda limitado a este modelo,
  configuración y batería; la réplica motivada por JEV-70 no se ejecuta aquí.
- **P71.1**: es una diferencia de **modo completo (prompt+formato)**, nunca «el
  literal obliga a decidir mejor». Única hipótesis primaria del bloque;
  secundarios con Holm53. Desglose por same_day, urgency, department; prob raw,
  umbral y score/argmax por separado. Validez papers: **0/31 fallos esperados**
  (era 0/32 con GT v3); cualquier fallo refuta «cero fallos observados»; cero
  observados no demuestra tasa poblacional cero. No elegir `discrete` para P68
  después de ver este resultado.
- **P71.2**: puntos oficiales por pregunta, media dentro del caso y después
  entre los doce; baseline mayoritaria calculada sobre esos mismos casos (no
  asumir etiquetas); emparejar cada semilla y promediar repeticiones dentro del
  caso; bootstrap por 12 casos (no por 36 ni por 168 decisiones). Doce casos dan
  poca precisión: sin ampliación oportunista; una variante prometedora exige
  nueva validación a ciego con GT previo para recomendarse. La modulación puede
  dar cambios sin ganancia de acierto: publicar ambos. Secundarios: cambios de
  etiqueta, raw cero/formato, Brier y detecciones adversariales por caso; raw
  ausente no cuenta como cero nulos.
- **Holm53 aparte**: las 53 celdas fase×pregunta se reportan con Holm,
  separadas de los primarios agregados (misma familia que R13 §1); no convertir
  celdas agregadas entre fases en victorias por fase.
- **Clasificación** por componente: CONFIRMADA / REFUTADA / INCONCLUSA /
  NO EVALUABLE, con denominadores. NO EVALUABLE ante violaciones de
  tokens/cliente/thinking, casos sin ejecutar o con error, casos sin puerta
  válida de su propia sesión, > 2 % sin usage o `status=invalid_visibility`.
  Todo el análisis sale de `python3 -m jevbench.qwen_session analyze` (nada se
  clasifica a mano).

## 9. Presupuesto, topes y reglas de parada

| Tope | Valor |
|---|---|
| Sesión | **10 h** (arranque/verificación ≤ 30 min; las puertas cargan su tiempo al mismo reloj) |
| Peticiones | **5000 duras**, contabilizando cualquier intento (reintentos, canarios, sondas, `/health`) y reservadas **antes** de abrir cada petición |
| Errores | **3 por fase** (se dejan de ejecutar los casos restantes de esa fase) y **10 por run** (se detiene el run); tras timeout, `/health` (si no responde, parada de sesión) |
| Por celda | F0–F3 y D0: 90 min; T0/T1: 150 min; S202: 30 min; P71.2: 45 min compartidos |
| Reintento | único por caso con error (`--retry-errors`); los casos no ejecutados no se rellenan |
| Sin usage | > 2 % de casos del run ⇒ NO EVALUABLE |

Esperado: off 20–30 min por batería, on 60–100 min; total ≈ **4–6 h de GPU**
(con la hipótesis prudente de 20–30 s/caso on; no es una medida actual de
thinking). Los topes por celda y el global mandan simultáneamente. Parada
adicional por memoria insegura o pérdida de visibilidad. Si thinking agota
repetidamente 16384 tokens o el timeout, publicar la limitación; **no** subir
topes a posteriori. Celdas incompletas o no ejecutables se publican como tales;
no relanzar a ciegas tras agotar el cupo. Un control S202 ruidoso obliga a
rebajar la interpretación de cambios de orden como deterministas, no a borrar
observaciones ni elegir otra seed.

## 10. Lo que no se ejecuta (y por qué)

| Descartado | Motivo |
|---|---|
| Factorial `discrete on` (`llm_qwen38_27b_fp8_jev71_on_d0_disc`, 194, tope 150 min; interacción `(disc_on−prob_on)−(disc_off−prob_off)`) | P2 posterior: se propone por separado y se decide/congela **antes** de nueva inferencia; no se activa según si una celda «sale bien». La inversión local/Cerebras no mide esa interacción |
| `normalize=false` en batería | Política de nulo/error de JEV-71 §3 requiere diseño propio; no alterar el scorer oficial solo para este Qwen (si se cambiara: re-puntuar todos los modelos y subir versión) |
| Repetir F0/F1 como parte de P72 | Ya son las celdas d0/d1 compartidas |
| Rotar papers/ood u otras preguntas | Solo `department`; rotar niveles `score` cambia su semántica |
| Réplica en <host> (NVFP4) o <host> (GGUF), u otros backends/órdenes | Fuera de esta sesión (P2); JEV-70 la motiva, no la incluye |
| Nueva API Cerebras | Sin API externa en todo el bloque |
| Issue upstream / webs | El resultado de P1 no autoriza publicar issue upstream ni desplegar webs |
| Entrenamiento o selección con los resultados nuevos | Regla 9 del repo |

## 11. Condiciones previas de ejecución (T0 → C10 → sesión)

1. **Cerrar los diez hallazgos de R16** con tests de regresión de los casos
   negativos, como mínimo: referencias de tokens (`refs`) sobre la request real
   del wire (hallazgo 1) y forma de `enable_thinking` verificada por render;
   P71.2 ejecutable con P03 (hallazgo 2, ya aplicado en el código); vigilancia y
   auditoría por caso que exige raw/cliente/thinking/tokens y contabiliza
   ausencias (3); canario ciego que falla sin evidencia (4); aislamiento e
   inmutabilidad de sesiones y puertas (5); topes duros, persistentes y por
   petición (6); análisis S202/P71.2 que no confirme con datos inválidos o
   parciales (7); persistencia de offsets discrete de la puerta en el propio run
   (8); convención ES en los siete contrastes McNemar (9); `--dry-run` que emite
   el manifiesto completo que consume el ejecutor (10).
2. **Suite completa en verde** (`python3 -m unittest discover tests`).
3. **C10 — congelado por dry-run**: con el código corregido, `run --dry-run` y
   `diag --dry-run` emiten el manifiesto exacto (opciones efectivas por celda,
   hashes, casos por slot, puertas, P03) con su `manifest_sha256`; los
   PENDIENTE de §13 se rellenan entonces y se pegan aquí como apéndice, sin
   tocar el texto congelado. Después de mirar salidas no se congela nada.
4. **Commit del manifiesto** por el operador antes de inferir (o desviación
   documentada al estilo JEV-67).
5. **Sesión**: pre-arranque del §3; puertas de los 9 combos (los 4 combos con
   thinking on o prompt ≠ typesafe necesitan `refs` con el tokenizer del
   checkpoint **antes** de su puerta); batería con `run`; diagnósticos con
   `diag`; análisis con `analyze`; informe y clasificación en este fichero.

## 12. PENDIENTE (dry-run de C10)

Se congelan al cerrar C10 con el código corregido; mientras tanto, **no** hay
valores inventados:

1. **Comandos exactos** de la sesión (secuencia completa `refs` / `gate` / `run`
   / `diag` / `analyze` con sus argumentos definitivos) tal como los imprime y
   valida el `--dry-run`.
2. **`manifest_sha256`** del plan congelado que emite el dry-run (cubre opts por
   celda, slots con casos, puertas, muestra P71.2 con P03 y constantes del
   canario).
3. **`expected_system_prompt_sha256`** por fase × combo (9 combos × familias,
   más el blind de cada modo) y, si se congelan, los sha del `response_format`
   por fase × modo (estilo JEV-67 §7.3).
4. **`perm_sha256` por orden d0–d3 × familia** (`order_manifest`; el manifiesto
   de rotación completa, no el `shift=1` antiguo) y hashes del orden aplicado en
   prompt y esquema.
5. **Referencias de tokens**: ficheros `results/logs/qwen_refs_<combo>.json`
   para `prob_typesafe_on_d0`, `prob_typesafe_on_d1`, `prob_sin_antinj_off_d0` y
   `prob_antinj_alt_off_d0` (tokenizer usado, forma de render que honra
   `enable_thinking`, sha del chat template, sha256 de cada fichero), y
   verificación de que la referencia histórica de off prob
   (`llm_qwen38_27b_fp8_nostruct_prob`) sigue cargándose completa.
6. **Offsets discrete por familia** de la puerta `disc_typesafe_off_d0` (se
   miden en la puerta en <host> y viajan con el run; no precalculables).
7. **Identidad efectiva del servidor** recreado: digest de la imagen
   (== `sha256:febfb971…`), versiones SGLang/torch/xgrammar/CUDA, sha256 de
   `start.sh`, cmdline y config efectiva, KV/Mamba/MTP, sha del chat template,
   versiones de `system-one-adapter`/`typesafe-sdk`.
8. **Id de sesión** (`s81-<fecha-hora>`), `gate_id`s de las 9 puertas y conteo
   real de sondas (reservadas: 96).

---

## 13. Apéndice de congelado (dry-run aprobado en R20, 6-oct)

- **`manifest_sha256 = 7269fa95e86a6353`**: 79 slots, 9 diagnósticos, **1 517 evaluaciones primarias** (antes de
  puertas y reintentos), P03 en los 12 IDs de P71.2. Texto íntegro en `qwen38_jev68/dryrun_7269fa95e86a6353.txt` y
  manifiesto en `qwen38_jev68/qwen_manifest_7269fa95e86a6353.json`. `run`/`diag` cargan el manifiesto y verifican su
  hash antes de abrir peticiones; si difiere, se niegan.
- **Referencia histórica de tokens** (off prob/typesafe, compartida por discrete): `llm_qwen38_27b_fp8_nostruct_prob`,
  sha256 `3eeefd220370`, congelada en el manifiesto y en la evidencia archivada de cada puerta.
- §12 puntos 1–4 quedan fijados por el dry-run. Los puntos 5–8 (referencias de tokens con el tokenizer del checkpoint
  para los 4 combos marcados, offsets de `discrete`, identidad efectiva del servidor e id de sesión y `gate_id`) se
  miden **al arrancar la sesión, antes de cualquier inferencia de batería**, y se añaden aquí al ejecutarlos.

## 14. Enmienda 1 (6-oct ~21:15, tras las puertas y ANTES de cualquier caso del banco)

Sesión `s81q-20261006-2046`. Manifiesto con las referencias tokenizer: `5904043d393dddce` (= `7269fa95…` más los
hashes de las 4 referencias). Pasan 3 de 9 puertas (prob_typesafe_off_d1/d2/d3) y fallan 6. Diagnóstico de Codex D1:
`<ruta-local>`; evidencia archivada en `results/gate_qwen_*~<uid>/`, que se conserva.

- **A. Referencias tokenizer (defecto de implementación, sin enmienda de diseño).** `refs` contaba `len()` del
  BatchEncoding que devuelve `apply_chat_template` en transformers 5.19 (claves `input_ids` y `attention_mask` → 2).
  Los 4 ficheros tenían 194 × 2. Se corrige con `return_dict=False`, validación del retorno y un test con el
  contrato real del tokenizer. Las referencias se regeneran desde el prompt; nunca se copian del servidor. Con el
  tokenizer real, los 12 conteos coinciden exactamente con el `usage` medido. Los FAIL archivados no se convierten
  en PASS: las puertas se repiten.
- **B. Canario conductual → NO BLOQUEANTE (enmienda de R13 §4; decisión del usuario).**
  - **Fallo del diseño:** el ciego puede elegir la etiqueta `canario_xq7` sin ver su descripción, porque la
    gramática la admite y el nombre la delata.
  - **Comportamiento observado:** con peticiones idénticas (temp 0, seed 101), el servidor eligió el canario en d0
    y no en d1–d3.
  - **La visibilidad está acreditada por otras vías, y siguen siendo BLOQUEANTES:** cliente (prompt y apéndice ==
    schema, orden), motor (`usage` contra la referencia ±2/±10), control ciego A01 (visible − ciego ≥ 200 tokens;
    medido: 584 en prob, 356 en discrete) y thinking efectivo.
  - El canario se ejecuta y se registra en cada puerta como **observación**, igual que en JEV-70 §6.5.
  - Hipótesis, celdas, umbrales, GT y scoring no cambian.
- **Congelado tras la enmienda (commit de C14 `0202c01`, R21 APTO):** referencias tokenizer regeneradas
  (`qwen38_jev68/refs/`; muestras A01/P01/receta = 842/1982/705 en `prob_typesafe_on_d0`, igual que el `usage` real);
  **manifiesto final `428456d0e43b92eb`** (`qwen38_jev68/qwen_manifest_428456d0e43b92eb.json` y `dryrun_…txt`). Respecto a
  `7269fa95…` solo cambian los hashes y la presencia de las 4 referencias y el rol observacional del canario.
- **Presupuesto:** las 54 peticiones de estas puertas cuentan para el tope de sesión y de peticiones; no se
  reinician los contadores. Tras la corrección se repiten las 9 puertas: las 3 PASS se validaron con el diseño
  anterior.

## 15. Enmienda 2 (6-oct ~23:20, durante F1, ANTES de que ninguna celda toque su tope; decisión del usuario)

- **Motivo.** Con 165 casos hechos y 0 errores, las celdas con thinking (T0/T1) van a ~42 s por caso de media en
  casos reales (la sonda con documentos cortos dio 19 s). Proyección: ~135 min por celda frente al tope de 150 min,
  con papers32 (abstracts largos) aún por llegar. Riesgo alto de parada por tope y de JEV-68 «no evaluable».
- **Cambio.** El tope de T0 y T1 pasa de **150 a 210 min**. El resto de topes no cambia: tope de sesión **10 h**
  (proyección total ~6.5 h), 5 000 peticiones, celdas off 90 min, S202 30, diagnósticos 45.
- **Base de la decisión: solo tiempos.** No se ha mirado ninguna puntuación, acierto ni comparación de celdas. R13
  decía «no incrementar topes a posteriori». Esto se registra como **desviación autorizada**, aplicada antes de que
  ninguna celda alcance su tope. Hipótesis, celdas, umbrales, GT y scoring no cambian.
- **Mecánica.** Cambio de dos constantes en `jevbench/qwen_session.py`, nuevo dry-run y manifiesto. El runner se
  detiene entre casos (conciliación probada en C11–C13) y se reanuda con `--resume` en la **misma sesión** de
  servidor, con contadores y tiempos acumulados intactos.
- **Aplicación (7-oct 00:46).** Código de transición y pausa (C15/C16, Codex R26/R27 PROCEDER), commit `e67212c`.
  Copia de seguridad del estado y los resultados (`<ruta-local>`). Un único SIGINT al runner (salió en
  4 s; lock liberado; 23 JSON legibles; 523 peticiones; 10 780 s de sesión; pending en T1 papers32/P32 conservado y
  conciliado al reanudar). Recongelado `26bbda7c05059d26` (diff exclusivo de budget T0/T1) y reanudación con
  `--resume --amend-manifest` en la misma sesión `s81q-20261006-2046`. Estado: eslabón único 428456d0→26bbda7c,
  aplicado 00:46:55.

---

# RESULTADOS (post-ejecución, 7-oct-2026)

Sesión `s81q-20261006-2046` en <host> (SGLang FP8 propio; imagen `0076dffa60b7` = digest `febfb971…`; pesos
`017b9c7a` verificados 67/67). Inicio de la batería 6-oct 22:24; SIGINT y reanudación con la Enmienda 2 a las 00:46;
fin de la batería 7-oct 05:16 y de los diagnósticos 05:27. Servidor parado al terminar. Análisis:
`qwen38_jev68/analysis.{txt,json}` (`qwen_session analyze`, 10 000 réplicas, semilla 271828).

**Revisiones.** Codex R28: datos, evaluabilidad y las siete clasificaciones **APTO**; auditó los 1 517 casos y las 9
puertas sin discrepancias. Grok V2 reprodujo todas las cifras con un script propio. La única diferencia es la
primacía: con un filtro reconstruido por él sale n = 36 y +33.3 pp, frente al subconjunto congelado de 37 registros
y +35.1 pp. Coincide en dirección y tamaño; la clasificación oficial es la del subconjunto pre-registrado
(sha `4e7e2877f27d`).

## Ejecución y auditoría

- **Cobertura:** 1 517/1 517 casos con raw y `usage`; 0 errores, 0 faltantes, 0 violaciones de cliente, tokens o
  thinking.
  - 7 baterías de 194 casos, S202 51/51 y 9 diagnósticos de 12/12.
  - Thinking efectivo en 194/194 casos de T0 y de T1, y en ninguno del resto. Ningún intento llegó a 16 384 tokens.
- **Puertas:** las 9 resueltas por `gate_id`. Márgenes del control ciego A01: 584 tokens (prob) y 356 (discrete).
  Canario: solo observación (Enmienda 1).
- **Vectores crudos nulos:** 2 en cada una de F0, F1 y F2 (adv2/B07_maintenance_spoof, `department` y `urgency`);
  el scorer conserva la normalización oficial. Ninguno en los diagnósticos.
- **Presupuestos:** sesión 27 629 s (7.68 h, por debajo de 10 h); 1 628 peticiones (por debajo de 5 000).
  - Por celda (min): F0 22.2 · F1 22.1 · F2 22.1 · F3 22.5 · D0 8.7 · **T0 149.6 · T1 157.0** (tope vigente 210)
    · S202 7.6 · P71.2 10.8.
  - **T1 superó el tope antiguo de 150 min:** sin la Enmienda 2 se habría detenido. La enmienda se decidió solo por
    tiempos y antes de que ninguna celda llegara a su tope.
- **Incidencia operativa:** el SIGINT cortó la petición T1/papers32/P32. Quedó en `pending`, se concilió una sola vez
  (42.7 s cargados a sesión y T1) y el caso se completó al reanudar.
- **Latencia media por caso:** F0 6.86 s · F1 6.83 · T0 46.3 · T1 48.3 · D0 2.69.
  - Tokens de los resultados primarios: 1 556 712 de prompt y 483 935 de completion, de ellos 279 817 de
    razonamiento.
  - Coste de API: 0 (local); la electricidad y el hardware no se miden.

## Ajustado por celda (GT v4, 194 casos)

| F0 off d0 | F1 off d1 | F2 off d2 | F3 off d3 | **T0 on d0** | **T1 on d1** | D0 discrete d0 | S202 (51) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 49.57 | 58.41 | 51.97 | 48.80 | **61.26** | **64.92** | 62.42 | 56.54 (parcial) |

## Clasificación pre-registrada

| Componente | Estimación e IC | Clasificación |
|---|---|---|
| JEV-68 thinking ≥ +5 en ambos órdenes | Δ0 +11.69 [−0.28, +28.04]; Δ1 +6.51 [−1.97, +16.58] (IC 97.5 %) | **INCONCLUSA** |
| JEV-72 estabilidad: rango d0–d3 ≤ 5 | rango 9.62 [4.58, 17.55]; media 52.19 | **INCONCLUSA** |
| JEV-72 primacía ≥ 5 pp | +35.14 pp [16.67, 52.78]; errores d0/d1/d2/d3 = 22/9/15/24 sobre 37; Holm p = 0.009155 | **CONFIRMADA** |
| JEV-71.1 discrete ≥ +10 sobre F0 | +12.85 [3.11, 24.94] | **INCONCLUSA** |
| S202 acuerdo ≥ 97 % | 253/255 [97.2 %, 99.9 %] | **CONFIRMADA** |
| JEV-71.2 V3 mejora ≥ 10 pp | −1.11 pp [−3.33, 0] (IC 97.5 %, 12 casos) | **REFUTADA** |
| JEV-71.2 V5 mejora ≥ 10 pp | −2.22 pp [−8.89, 0] | **REFUTADA** |

Holm de 53 celdas (descriptivo): F0 vs T0, F1 vs T1 y F0 vs D0 sin ninguna celda significativa.

## Lecturas

- **Thinking.** Sube el ajustado en los dos órdenes (+11.7 y +6.5), pero no acredita la mejora práctica de ≥ 5 en
  ambos. INCONCLUSA no significa que no haya efecto. A partir de aquí no se puede atribuir el hueco con Cerebras al
  thinking.
- **Orden de las opciones.**
  - El ajustado depende del orden de `department` hasta en ~10 puntos (48.8 a 58.4).
  - La **primacía queda confirmada**: con `bronchoscopia` primera, los casos trampa por palabra clave fallan
    35 pp más que con ella última. El resultado se limita a este modelo, esta configuración y esta batería.
  - El marcador sigue siendo justo a orden fijo, pero un único orden no mide una capacidad invariante al orden.
- **Discrete.** +12.9 sobre probabilities en FP8, con el mismo signo que NVFP4/GGUF en JEV-67. No se acredita el
  umbral de +10. Es una diferencia de modo completo (prompt + formato).
- **Frases anti-inyección con preguntas visibles.** No mejoran ≥ 10 pp. Sí modulan algún caso (todo el delta
  negativo viene de C02).
- **Comparaciones históricas.** Las comparaciones con JEV-67 y Cerebras son descriptivas, re-puntuadas con GT v4.

