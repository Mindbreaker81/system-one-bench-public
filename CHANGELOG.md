# Changelog

Historial de lo realizado en el banco de pruebas, de lo más reciente a lo más antiguo.
Entre paréntesis, los commits de referencia (`git show <hash>`); el detalle numérico está en
`docs/resultados.md` y `docs/experimentos/`. Seguimiento de tareas: YouTrack, proyecto JEV.

El repo tiene **una única versión semántica** (`jevbench.__version__`), alineada con este
documento y el README. Qué sube cada nivel:

- **major**: cambian casos, ground truth o preguntas → los resultados dejan de ser comparables;
- **minor**: runs, modelos, experimentos o funciones nuevas;
- **patch**: documentación y arreglos.

Las versiones 0.1.0–0.4.0 son retroactivas (se asignaron a 27-sep sobre los commits ya existentes).

## [1.5.2] - 2026-10-08 — JEV-86/87: rotación de DiffusionGemma con GT v4 y auditorías verificables en el espejo; correcciones de redacción (revisión R82 de JEV-56)

- **JEV-86:** `dgemma_report.rotation` recorría P02 (retirado en GT v4) y fallaba con `KeyError` oculto,
  así que Rot1 quedaba NO EVALUABLE al re-ejecutar. Ahora solo cuenta los casos del GT vigente, y `_try` avisa
  por stderr. Recálculo con GT v4: 33/256 cambios, Δ acierto `choice` **−7,42 pp** [−11,93; −3,06],
  tabla 192/7/26/31. La clasificación no cambia (REFUTADA). El −7,3 de GT v3 queda como histórico en el
  manifiesto; la web, Límites, `modelos.md` y `resultados.md` usan ya −7,4. El +6,2 de Qwen (JEV-67) no
  cambia: su tabla ya excluía los casos retirados.
- **JEV-87:**
  - El espejo reproducía las puntuaciones, pero no las auditorías confirmatorias. Las puertas leen los
    raw, que el espejo sustituye por `raw_sha256`.
  - Nuevo `jevbench.attest`. `freeze` (privado) ejecuta 9 analizadores (JEV-67, 68, 70, 76, 77, 78, 81, 82
    y 84) con un audit hook que registra **todos los ficheros que leen**: resultados con sus `raw_sha256`,
    GT, runs de puertas, logs y código importado. Congela en `docs/auditorias/*.json` la salida y el hash
    de la versión pública de cada fichero.
  - `freeze` aborta ante un rc ≠ 0 o un análisis vacío.
  - `verify` exige las 9 atestaciones y comprueba que corresponden al registro. Además:
    - **en privado**, re-ejecuta todos los analizadores (también los que leen raw) y compara su salida;
    - **en el espejo**, comprueba los hashes de las dependencias exportadas, re-ejecuta literalmente los 4
      que no leen raw y declara «atestados» los 5 restantes;
    - los veredictos que imprime se extraen de la salida comprobada.
  - `publish` exporta además `docs/auditorias/` y los pre-registros `docs/infra_runs/*.md` saneados (IPs,
    hosts, usuario, dominios y rutas locales), con un escáner específico de rutas en esos manifiestos.
    **Aborta** si `attest verify` falla dentro del export.
  - En el espejo, los analizadores que leen raw avisan y salen con código 3.
  - Revisión Codex R83.
- **Redacción (R82):**
  - «misma calidad» e «iguala» → «agregado próximo, sin diferencia demostrada» (Decider-4B→Jev frente a
    Jev→Jev).
  - La 2.ª anotación humana se describe como parcial (campos elegidos por discrepancia), no como fiabilidad
    global (portada y Metodología).
- **Seguimiento:** propuesta de artículo revisada (JEV-56, JEV-A-3 r2; informe en
  `docs/articulo/revision_R82_codex.md`). Set holdout planificado en JEV-88, pendiente de decisión.

## [1.5.1] - 2026-10-08 — JEV-84: Haiku 5.5 como revisor / alerta / réplica H-adapt (pre-registro congelado y resultados)

- **JEV-85 (8-oct; revisión Codex R79 CORREGIR aplicada):** OpenMed
  `Ministral-3B-Medical-v1` (~4 B bf16, Mistral3, checkpoint «research» sin
  licencia documentada) por el adaptador `llm` contra vLLM
  `0.29.1rc1.dev551+g1b3b88ec2` en .80 — resultado **negativo descriptivo de
  cobertura incompleta**. `llm_ministral3b_med_prob` (primario): 171/194
  válidas, 23 errores persistentes — **incumplió el criterio de parada >20**
  declarado de antemano (la vigilancia no estaba en el lanzador; desviación de
  protocolo) — ajustado **−7\*** sobre 3/10 fases. `llm_ministral3b_med_disc`
  (secundario descriptivo): 187/194, 7 errores, **45\*** sobre 4/10 fases; los
  titulares no son comparables con la cobertura completa de Jev (45) ni
  Decider-4B (33). Holm de 53 contrastes por modo: solo sobrevive la derrota de
  `prob` en `department` de triage_ext_es (13–0, p_Holm 0,013); la mejora
  nominal de `disc` en `depth` de papers32 es exploratoria (p_Holm 0,34). Brier
  y latencia publicados son el resumen de 9 fases; **coste API no registrado**
  (endpoint local sin tarifa; electricidad/hardware no medidos). Manifiesto con
  §RESULTADOS corregido y evidencia remota archivada (SHA256SUMS de los pesos,
  config/README del checkpoint, pip freeze con sha256, `git rev-parse` de vLLM
  y extracto del arranque) en `docs/infra_runs/ministral3b_med_jev85*/`. Ficha
  en `docs/modelos.md`, nota en `resultados.md`, runs en `resultados_runs.txt`,
  web y sitio (etiquetas con asterisco + cobertura incompleta + desviación de
  parada; sin tarjeta propia: frase en la tarjeta de descartados, fila en la
  tabla de modelos, hito 8-oct y fila de metodología). Sin cambio en la
  recomendación vigente.
- **JEV-85 (8-oct; revisión Codex R80 CORREGIR aplicada):** correcciones de
  presentación, sin cambios en datos/GT/scorer ni en las conclusiones. El
  sitio público ya no muestra `$0` con un n ficticio para los dos runs
  Ministral: `cost_per_1000`/`cost_n` se publican `null` (`cost_unknown` en
  `jevbench/site.py`) y `coste.html` renderiza **«no registrado»** en celda y
  tooltip. La latencia del sitio se alinea con la cifra documentada
  (**4 780 / 1 913 ms**, mediana del resumen del scorer sobre las 9 fases
  base+nuevas vía `ms_median`), con el universo declarado en `cost_scope` y
  en el pie de `coste.html`. Trazabilidad HF acotada en el manifiesto y en
  `docs/modelos.md`: la revisión `3a5363c…` y la igualdad del sha256 con el
  LFS oid quedan **declaradas por el ejecutor**, no acreditadas por las
  capturas archivadas. Celda del anexo Holm corregida (`triage_ext_en /
  hostile`, disc: 0–0 → 1–0; `p`/`p_Holm` ya eran correctos). Test nuevo en
  `tests/test_site.py` (`test_unregistered_cost_and_nine_phase_latency`).
- **JEV-84 (resultados, 8-oct; revisión Codex R76 CORREGIR aplicada):** ejecución R1→R2→A→S
  con los comandos pre-registrados (`run_{R1,R2,A,S}.sh`), 642 registros nuevos, 0 errores,
  sin `cost_stop` ni drift; coste nuevo **$0,3339903** (R1 0,1292866 · R2 0,1258361 ·
  A 0,0090470 · S 0,0698206; cupo restante al terminar 0,9660097). Huellas por adquisición
  (R1 `f45c01d2…`, R2 `c9f2359e…`, A/S `4ee0c0b9…`); versiones observadas `claude-haiku-5-5`.
  **Bloque R: NO CUMPLE en ambos D1** — fracciones JEV-32 y condición de pérdidas OK,
  falla la alerta de adv4 (5/10 TP en los dos D1); el criterio original JEV-32 (A) sí lo
  cumple Decider→Haiku evaluado con GT v4 (distinción histórica pre-especificada: no
  sustituye a B ni habilita rol). **Holm R 212 = 0 significativas** (p mínima 0,207).
  Ajustados audit: Decider→Haiku **66**, Jev→Haiku **74** = el mayor **entre configuraciones
  audit completas** (anterior máximo audit 71, `llm_gpt6luna_jevrev_audit`; la corrección
  de R76: la variante review 75,79→76 es secundario descriptivo del mismo raw, no
  adquisición independiente — no afirmar «mayor del banco» sin el matiz). **Bloque A: NO
  CUMPLE** (46/60 aciertos; 16/30 TP · 0/30 FP; McNemar–Holm de 2: Clef 56/60, p 0,0127;
  revisor Jev 54/60, p 0,0215 — a favor de las referencias). **Bloque S: ESTABLE** —
  acuerdo 919/964 = 95,33 % [CP 93,8–96,6, con dependencia intra-caso], Δ ajustado −1,80
  [−4,97; +1,49], Brier noul 0,064→0,063. Tarjeta habilitada **solo por S**
  («Haiku 5.5 — reproducibilidad descriptiva»), sin sello de revisor ni alerta; el circuito
  recomendado no cambia. Integrado en el manifiesto §RESULTADOS, `cascada_jev.md`,
  `alerta_manipulacion.md`, `modelos.md`, `resultados.md` (marcador:
  `decider_4b_haiku55rev_audit` 66, `jev_haiku55rev_audit` 74, `llm_haiku55_adapt_prob_r2`
  67), web y sitio (RUNS/PAIRS/REVIEWERS/REV/RUN_DATES, tarjeta, revisor, alerta, hito
  8-oct, fila de metodología). Limitaciones: benchmark conocido (no holdout), preflight
  manual del cupo sin log, IC CP con dependencia intra-caso.
- **JEV-84 (T24…T24h, Codex R68–R75 APTO, aprobado 8-oct; sin batería aún):**
  `docs/infra_runs/claude_haiku55_jev84.md` — revisor / alerta / réplica H-adapt.
  Holm R = 212 (2×2×53), Holm A = 2; umbrales JEV-32 exactos del scorer; criterio
  original (Decider, alerta adv5) vs ampliado JEV-84 (D1 Jev, alerta por set);
  estados NO EVALUABLE; tarjeta con habilitación ≠ contenido; cupo global <$1,50.
  Análisis: `scripts/jev84_analyze.py`. Extensión en
  `docs/experimentos/alerta_manipulacion.md`.
- **Harness / cost_guard (opt-in cascade + alert_onepass):** `case_cost` bloquea
  reanudación hasta `--amend-case-cost-stop`; presupuesto `>=`; configuración
  **canónica** (todos los campos + `d1`/`reviewer`/`prefix`; `None` comparable;
  whitelist dinámica post-decide); `config_sha256` por caso; versión `resolved`
  única del run; drift con evidencia+gasto; `--retry-errors` durable por caso.
  Cupo monótono con desconocidos. `jevbench.run --stamp-config` (bloque S).
- **Analizador:** `run_gate` único (criterio numérico = Holm R/A/S); cobertura →
  NO EVALUABLE; raw completo + drift + procedencia; familia 212 intacta
  (`p=None`); D1/intervención vs `R_PAIRS`; procedencia histórica solo vía
  lista blanca congelada `HISTORICAL_REFERENCE_RUNS` (R74-P1-1; r2/A/R nuevos
  sin huella → NO_EVALUABLE; sin bypass «faltan todas las huellas»).
- **Manifiesto:** S = JEV-82 + `--stamp-config`; garantías `case_cost`/`>=`/retry
  = R/A; alert comprueba adapter/questions_hash en este pre-registro (sin
  afirmar histórico previo a HEAD); P2 R74 (garantía histórica incompleta,
  prompts variables, límites runner) documentados; provisión R/S y comandos
  exactos.
- Tests: `tests/test_cascade_cost_guard.py`, `tests/test_alert_onepass_cost_guard.py`,
  `tests/test_jev84_analyze.py`, `tests/test_run_cost_guard.py`.

## [1.5.0] - 2026-10-07 — JEV-77: resultados MedGemma/Gemma 3/Qwen en .80; JEV-82: rotación d1 de gpt-6-luna-decisions (pre-registro 28727d3); JEV-78/83: Decisions API nativa de OpenAI y Claude Haiku 5.5

- **`check_versions`:** sondea también `openai/gpt-6-luna-decisions` (OpenRouter) con conjunto
  de versiones conocido aparte (`openai/gpt-6-luna-decisions-20261006`); el aviso de versión
  nueva nombra la familia y qué repetir (JEV-80 batería / JEV-82 rotación). Punto de extensión
  reservado para la API nativa de OpenAI Decisions (JEV-78). Registro en
  `docs/versiones_jev.md` por sección.
- **JEV-82 (resultados, rev. Codex R57 APTO; `git show 28727d3`):** pre-registro congelado
  `docs/infra_runs/luna_decisions_jev82.md` — rotación d1 del orden de `department` en
  `gpt-6-luna-decisions`, con dos piezas de harness: opción `choice_order` opt-in en el
  adaptador `jev` (d0 byte a byte intacto; la rotación solo se aplica si se pide) y guardas de
  coste en `jevbench.run` (`--max-case-cost 0.01 --max-cost 0.05`, con `cost_stop` que también
  opera al reanudar). Ejecución sin desviaciones: 4 comandos exactos, 202 llamadas lógicas a
  `decide`, sin parada de coste. `jev_luna_decisions_d1` **186/194** (los 6 rechazos de d0 más
  2 nuevos: adv3/C05_polite_threat y triage_ext_es/T40_amenaza_personal); mismo modelo servido
  (`…-20261006`) en los 186 pares. En las 5 fases completas comunes, Δ ajustado **0,00
  [0,00–0,00]** (puntos por caso idénticos); acuerdo **918/924 = 99,35 %** con 6 decisiones de
  `department` cambiadas y Δp máx 0,72. **Primacía ≥5 pp REFUTADA** por U95 < 5 en los 32
  registros pareados del subconjunto congelado (Δ errores d0−d1 = −12,50 pp [−25,81, −2,94];
  7 errores d0 frente a 11 d1; p Holm 0,125) — sin demostrar ausencia de efecto de orden,
  equivalencia ni estabilidad general. Coste registrado d1 $0,0192 (cota inferior). El run d1
  **no entra en marcador ni web** (variante de sensibilidad). Resultados:
  `docs/infra_runs/luna_decisions_jev82.md` §RESULTADOS.
- **JEV-78/83 (resultados, rev. Codex R63 — JEV-78 APTO; pre-registros congelados `de9af7f` y `5e8da17`):**
  - **JEV-78 — `openai_decisions`:** adaptador nuevo sobre el SDK oficial `openai==3.26.0`
    (venv aparte `.venv-oai`) para la **Decisions API nativa de OpenAI** (`client.decisions.create`,
    `max_retries=0`), con **refusal por pregunta** (negativa parcial = caso conservado con la pregunta a 0;
    negativa total = `ProviderRefusal`) y coste informado contabilizado también en los intentos rechazados;
    análisis offline `python3 -m jevbench.jev78 analyze`. `oai_luna_decisions` **194/194, 0 errores de caso**:
    los 6 casos que OpenRouter rechazó enteros se conservan con **8 negativas parciales** (department ×6,
    urgency ×2) — diferencia de cobertura bajo contratos distintos, sin identificar la capa causal del rechazo
    histórico. Versión **inconclusa** (alias `gpt-6-luna` sin snapshot; same_model=false); acuerdo **934/934**
    y Δp 0 (2.091 componentes), Δ ajustado **0,00 [0,00–0,00]** en las 6 fases comunes — sin equivalencia
    demostrada; Holm 53 vs `jev_v3`: **0 significativas**; ajustado propio **38,25 [27–48]** (refusals a 0);
    coste registrado **$0,0205** con el ledger durable. `docs/infra_runs/openai_decisions_jev78.md`
    §RESULTADOS.
  - **JEV-83 — Claude Haiku 5.5 (`claude-haiku-5-5`, Anthropic):** extensión opt-in del adaptador `llm`
    (`thinking=disabled|adaptive`, `effort`, `max_tokens`, timeouts; `exc.cost` en fallos con respuesta) vía
    `system-one-adapter[anthropic]==0.2.1` en `.venv-anth`; ID canónico de snapshot fijo (no alias móvil).
    Tres celdas, **194/194 registros retenidos, 0 errores**: H-off **62 [54–69]** (Holm 53 vs Jev: **0
    significativas** — sin superioridad), H-disc **64 [57–71]**, H-adapt **69 [62–76]** (thinking en 126/194
    casos; descriptivo, sin causalidad aislada). **Desviación declarada:** un corte de sesión dejó la primera
    respuesta de E11 (adv5) sin persistir y la reanudación la repitió (≥195 respuestas para 194 ids); el coste
    de H-adapt **$0,0704 es cota inferior** (≥1 intento pagado sin coste recuperado). Costes: $0.0502 /
    $0.0314 / $0.0704. Los 4 runs (`oai_luna_decisions` y las 3 celdas Haiku) entran en marcador y web.
    `docs/infra_runs/claude_haiku55_jev83.md` §RESULTADOS.
- **JEV-77 (resultados, rev. Codex R61; commits `0fc8fd4`/`3b4bbac`/`b687f8a`):** MedGemma-27B-IT
  frente a Gemma3-27B-IT y Qwen3.8-27B FP8 — ensayo pre-registrado
  (`docs/infra_runs/medgemma_jev77.md`) con dos aprobaciones: 18 celdas × 194 casos
  (3 492/3 492, 0 errores, 3 658/12 000 peticiones, 17,98 h de 40 h, 2/4 reinicios
  extraordinarios) en .80, rama A (una imagen SGLang común para los cinco checkpoints; MedGemma/Gemma BF16 y Qwen FP8,
  temp 0, `discrete`/`probabilities` × d0/d1). **H1 inconclusa** (MD0−GD0 ≥ +5: +9,7
  [−1,7; +21,8] IC97,5) y **H2 refutada** (no inferioridad −5 frente a Qwen fresco: −37,0
  [−49,8; −24,9]). Enmienda 1 (gramática JSON restringida
  `--constrained-json-disable-any-whitespace`, manifiesto `008c1cdd… → 8b201bfb…`) y Enmienda 2
  (la sonda ciega admite valores fuera del contrato SDK) aplicadas; desviación operativa NAS en
  el bloque Gemma3-4B acreditada con SHA256 15/15 (`a6/weights_gemma3_4b/`, cierre de la
  corrección C1 de R61). Holm53: solo tres celdas significativas, todas en el bloque 4B;
  **633 vectores nulos normalizados** a uniforme (600 en probabilities de MedGemma-4B).
  Cascada híbrida M-D0 → revisor Jev (`jev-1.13-20260917` congelado): audit **65,43** / raw
  **66,59**, sin demostrar audit > raw ni una solución 100 % local. Marcador: MD0, GD0 y
  `medgemma_27b_jev77_jevrev_audit` (familia nueva «MedGemma» en web y sitio). Sin afirmar
  superioridad ni utilidad clínica.
- **Revisión editorial R65 (8-oct):** JEV-78/82/83 incorporados al relato público (párrafo de
  decisiones, tarjeta de una pasada, «Las pruebas», historia y filas de metodología del sitio) con
  el grado de afirmación del pre-registro: Holm 53 es solo de H-off (H-disc/H-adapt descriptivas),
  el 38 nativo no es la cifra comparable y JEV-82 sigue sin barra; «equivalente» sustituido por
  «sin diferencia significativa (no demuestra equivalencia)» en resultados y modelos; Enmienda 2 y
  desviación NAS en ficha, tarjeta y lectura; latencias discrete 27B ~9.4 s (26–28 s son medias);
  hashes de Gemma 3 en la tabla de modelos; E11 y universo de medianas en la nota de coste;
  millares «3 658/12 000» unificados. Regenerados marcador, web y sitio.

## [1.4.0] - 2026-10-07 — JEV-76: resultados del factorial discrete × thinking de Qwen3.8-27B FP8

- **JEV-76 (resultados, rev. Codex R53 APTO):** sesión `s81f-20261007-0800` en .81, manifiesto
  `e4a198a26cefaba9`. Ocho celdas frescas × 194 casos (1 552/1 552, 0 errores, 0 reintentos;
  10,89 h de reloj del supervisor sobre 14 h; 1 600 peticiones sobre 5 000). Ajustados: prob
  off/on d0 50,08/58,71, discrete off/on d0 63,04/59,56; d1 57,56/64,12 y 61,05/55,48.
  - **H1 refutada en ambos órdenes** (DT−D ≥ +5: d0 −3,483 [−11,385; +3,624], d1 −5,579
    [−14,818; +2,590], IC 98,75 %): thinking sobre discrete no alcanza la mejora pre-registrada;
    los IC incluyen cero (ni deterioro ni equivalencia demostrados).
  - **H2:** inconclusa en d0 (DT−T +0,851 [−5,185; +6,749]) y refutada en d1 (−8,647
    [−18,085; −1,944], a favor de prob con thinking).
  - **Interacción descriptiva** ≈ −12,1 puntos en ambos órdenes (bootstrap conjunto, IC95);
    Holm 53 celdas: 0 significativas. Thinking multiplica la latencia media ×13,8/×13,2 sobre
    discrete y ×6,8/×7,1 sobre prob.
  - Integración: §RESULTADOS en `docs/infra_runs/qwen38_jev76.md`, viñeta en `docs/modelos.md`,
    entrada de seguimiento en `docs/resultados.md`, celdas DT0/DT1 en `docs/resultados_runs.txt`,
    DT0 en el marcador web y el sitio público (env verificado: DGX Spark GB10 · SGLang · FP8
    oficial · structured + esquema en prompt · thinking · temp 0) y figura hermana del forest de
    hipótesis en la página Límites (escala compartida −20…+10, umbral +5). Las celdas frescas
    F/T/D no se publican (duplican JEV-68/71).

- **Revisión editorial de la web (Grok R55/R55b, Cursor W8):** portada, historia y «Las pruebas» con JEV-68/71/72, JEV-76 y JEV-80/81; Clef-27B y gpt-6.1-sol como ventajas descriptivas que no sobreviven a Holm; comparador correcto de luna (61 vs Jev solo; frente a la cascada 64 sin diferencia tras Holm); metodología al día (mecanismo JEV-66, cuatro filas pre-registradas nuevas, pie 7-oct).

## [1.3.0] - 2026-10-07 — JEV-80: gpt-6-luna-decisions por el endpoint de decisiones de OpenRouter; JEV-76/77/79

- **JEV-80 (run `jev_luna_decisions`):** `openai/gpt-6-luna-decisions` servido en el endpoint de decisiones de
  OpenRouter (`/api/alpha/decisions`) con el adaptador `jev`, sin cambios de código; versión resuelta
  `openai/gpt-6-luna-decisions-20261006`. Batería GT v4: **188/194** — seis rechazos del proveedor
  (HTTP 502 «OpenAI refused to answer question "department"», reproducidos en ~6 peticiones/caso) en
  B05_trial_data_exfil (adv2), C08_transport_data_exfil (adv3), D05_registry_export y D07_vecina_resultado (adv4),
  E01_phishing_patologia y E02_falso_recall_equipos (adv5). Ajustado **48\*** (cobertura incompleta: la media va
  sobre 6 fases frente a 10 de Jev; el `*` está explicado en `docs/resultados.md`). Comparación homogénea
  (misma matemática, 6 fases comunes completas): **47,70** frente a **54,63** de Jev, 75,60 de luna-prob y 71,72
  de luna-disc; sensibilidad con cada rechazo a 0 puntos (10 fases): **33,03** frente a 45,38 de Jev.
  **No demuestra superar a Jev.** McNemar con Holm (53 pruebas por referencia): la única p nominal <0.05 (`depth` de papers,
  b=1 c=8, p=0.039) queda con p ajustada = 1. Coste medido $0.0194 los 188 éxitos (53 % de luna-prob, 81 % de
  luna-disc, 2.97× Jev) y mediana 672 ms. Brier adversarial peor que Jev (adv1/2/5: 0.20/0.17/0.18 vs
  0.09/0.08/0.13); frontera 0.45–0.55: 4 vs 29. Marcador (`docs/resultados.md` con nota del asterisco), ficha
  (`docs/modelos.md`), `resultados_runs.txt`, web y sitio actualizados. Revisión previa R47 (Codex). No se
  prioriza revisor ni rotación; siguiente paso sugerido: diagnóstico acotado de las negativas y *fallback* a Jev.
  En «Global ajustado» los agregados con `*` quedan fuera del ranking (bloque «Cobertura incompleta»); la web
  exporta n_ok/n_total y el motivo (no medido vs fases con errores); coste/latencia públicos de luna-decisions
  usan los 188 éxitos homogéneos de R47 ($0,1031/1.000 · 672 ms).
- **JEV-81 (pre-registro congelado 237259d, ejecutado el 7-oct; rev. R51 de Codex: ejecución y cifras
  conformes):** `jevbench/jev81.py` + `docs/infra_runs/luna_decisions_jev81.md` (fallback por rechazo, rechazo
  como alerta, repetibilidad; validación de universo/hashes/GT, criterio de rechazo explícito 502+«refused to
  answer», `--write` sin sobrescritura, procedencia con sha de fuentes/GT).
  - **Fallback (`jev_luna_decisions_fb`):** 6 sustituciones a `jev_v3` → 194/194, ajustado **39,1
    [IC95 28,2–49,1]** frente a 45,4 [36,0–54,6] de Jev; nada significativo tras Holm (53 pruebas por
    referencia); coste efectivo registrado $0,0195 (6 costes del primario desconocidos; recombinación offline).
  - **Alerta por rechazo (adv3–5, n=60):** 5/30 TP, 0/30 FP observados (precisión 100 % [47,8–100], recall
    16,7 % [5,6–34,7]); descriptivamente por debajo del revisor Jev (25/30).
  - **Repetibilidad (`jev_luna_decisions_r2`, $0,0194 registrados en éxitos):** las dos réplicas con la misma
    versión servida (`…-20261006`) coinciden íntegramente (934/934 decisiones, Δp = 0 en 2091 componentes,
    mismos 6 rechazos) — repetibilidad observada, no determinismo general probado.
  - Integración: fila descriptiva en marcador/web/sitio («gpt-6-luna (decisions) → Jev si rechaza», familia
    LLM, entra en el ranking por ser 194/194; la réplica r2 no entra), nota JEV-81 en `docs/resultados.md`,
    bloque en la ficha y §RESULTADOS en el pre-registro. Pendientes valorados por R51: rotación d1 justificable
    como sensibilidad (pendiente de aprobación); cascada real y revisor no justificados por estos datos.
- **JEV-79:** página «Límites y cautelas» rediseñada — mapa del experimento, forest plot de hipótesis
  (estimación + IC + umbral + veredicto), antes/después con el prompt real, figuras con escala declarada,
  glosario, accesibilidad y díptico ciego/visible (4cbe318).
- **JEV-77 (MedGemma-27B-IT):** perfil `jev77` del supervisor (3c662c4); A3 en .80 y congelado A4 con manifiesto
  `008c1cdd499b6f92` (0969900); el sondeo A4 del revisor usa el formato wire noul del banco (0fc8fd4); Enmienda 1
  con gramática JSON restringida en los 5 checkpoints (3b4bbac). Batería en curso.
- **JEV-76 (Qwen3.8-27B FP8):** congelado — referencias tokenizer, manifiesto `e4a198a26cefaba9` y ocho puertas
  PASS en .81 (0813da4). Batería en curso.

## [1.2.0] - 2026-10-07 — JEV-76/77/78: pre-registros en borrador y perfiles del supervisor

- **JEV-76 (Qwen3.8-27B FP8, discrete × thinking):**
  - Factorial fresco d0+d1 de 8 celdas en .81. Primarias H1 = DT−D ≥ 5 y H2 = DT−T ≥ 5 por orden, con IC98,75 (Bonferroni sobre 4).
  - Interacción conjunta solo descriptiva. 14 h de reloj del supervisor.
  - Pre-registro en borrador: `docs/infra_runs/qwen38_jev76.md` (Codex R33/R35 APTO-BORRADOR).
- **`jevbench/qwen_session.py`:**
  - Perfiles `--profile jev68|jev76`, con estado, manifiesto, referencias y puertas propios. JEV-68 se reproduce idéntico (manifiesto `26bbda7c05059d26` y analysis.json).
  - La puerta discrete+thinking usa `token_rule` contra su propia referencia tokenizer.
  - `analyze` factorial. 18 tests nuevos.
- **JEV-77 (MedGemma-27B-IT frente a Gemma 3-27B-IT y Qwen FP8):**
  - Las 18 celdas y la cascada híbrida van en .80. Primarias H1/H2 en d0 con IC97,5; d1, 4B y cascada, descriptivos.
  - Aprobación en dos etapas (preparación técnica sintética → congelado → batería).
  - Borrador: `docs/infra_runs/medgemma_jev77.md` (Codex R30–R35). Pendiente: perfil `jev77` del supervisor.
- **JEV-78:** issue de viabilidad de la Decisions API de OpenAI (`/v1/decisions`, gpt-6-luna). Sin llamadas.
- **ai-models:** se añade `hf/Qwen/Qwen3.8-27B-FP8` (rev `017b9c7a`, SHA256 verificado).

## [1.1.0] - 2026-10-07 — JEV-68/71/72: sesión Qwen3.8-27B FP8 en .81 (thinking, rotación, discrete, diagnóstico); web JEV-74/75

- **Sesión pre-registrada `s81q-20261006-2046`** (SGLang FP8, DGX .81; supervisor `jevbench/qwen_session.py`,
  manifiesto final `26bbda7c05059d26` tras las enmiendas 1 y 2). 17 celdas evaluables, 1.517/1.517 casos,
  puertas de visibilidad superadas; 7,7 h y 1.628 peticiones contabilizadas (topes 10 h / 5.000).
  - Ajustado (GT v4): F0/F1/F2/F3 = 49,57 / 58,41 / 51,97 / 48,80; T0/T1 (thinking) = 61,26 / 64,92; D0 (discrete) = 62,42.
  - **P68 thinking:** +11,7 (d0) y +6,5 (d1); la mejora ≥+5 en ambos órdenes queda INCONCLUSA (IC97,5 cruzan).
  - **P72 rotación:** rango 9,6 [4,6; 17,6] → estabilidad INCONCLUSA; **primacía CONFIRMADA**
    (+35,1 pp de errores, IC95 [16,7; 52,8], Holm p=0,009; subconjunto congelado de 37 registros).
  - **P71.1 discrete:** +12,9 [3,1; 24,9] → ≥+10 INCONCLUSA. **S202:** 253/255 decisiones iguales → CONFIRMADA.
  - **P71.2 variantes de prompt (V3/V5):** −1,1 / −2,2 pp → REFUTADA una ganancia ≥+10 pp.
  - Holm sobre las 53 celdas: ningún contraste significativo en las tres familias.
  - Desviaciones registradas: canario solo observacional (enmienda 1), tope T0/T1 150→210 min antes de
    alcanzarlo (enmienda 2, `--amend-manifest`), SIGINT con reanudación en la misma sesión.
  - `analyze` añade salidas descriptivas: vectores nulos crudos (2 en F0/F1/F2, adv2/B07), latencia y tokens,
    desglose P71.1 y baselines.
  - Ficha, `docs/modelos.md`, `docs/resultados.md`, marcador (3 runs d0) y web/sitio (F0/T0/D0).
- **publish:** el saneado de `meta.host` es recursivo (los runs de la sesión anidan el meta de las referencias
  de puerta); test de regresión. Tres tests que necesitan `raw` se omiten en el export público.
- **JEV-74:** tarjetas de «El circuito recomendado» en una columna con detalle desplegable.
- **JEV-75:** página «Límites y cautelas» con diagramas SVG (artifact y sitio); cascadas etiquetadas «· regla audit/review».

## [1.0.0] - 2026-10-06 — GT v4 (JEV-73): papers32 sin el duplicado P02; mantenimiento Qwen (JEV-71/72)

**Versión major: cambia el ground truth.** Los resultados con GT v3 dejan de ser comparables con los de GT v4.

- **JEV-73 (GT v4):** papers32 P02 y P03 eran el mismo paper (PMID 37130440), con GT distinto en `practice`.
  - Causa: el fetch por relevancia de Lyra duplicó el meta-análisis de P03 en la consulta de P02.
  - Se retira **P02**, el caso cuyo fetch falló. P03 conserva su GT. Batería: 31 papers, 194 casos
    (191 en el sitio, sin OOD); el nombre de fase `papers32` no cambia.
  - Se conservan `data/{paper_gt32,papers32}.v3.json`; registro en `data/GT_CHANGELOG.md`.
  - Nuevo test `tests/test_battery_integrity.py`: ni estados ni PMIDs duplicados.
  - Todo re-puntuado sin re-ejecutar modelos. Cambia el ajustado redondeado de 6 runs del marcador
    (span01_pro 18→17, Cerebras nostruct 65→66, jev_cerebrasqwennsrev_review 68→69,
    gliner_multi_decide_desc −74→−75, llm_qwen38_27b_prob −16→−15, llm_qwen38flash −40→−39).
    Ninguna clasificación tras Holm al 5 % cambia en los 28 contrastes revisados, aunque se mueven p
    concretos.
  - `publish.py` sanea también las copias versionadas `papers32.vN.json` (sin abstracts).
  - Narrativas vigentes (ficha, marcador, web, sitio) actualizadas a GT v4. Los manifiestos y los
    recuentos de ejecución quedan como histórico GT v3.
- **Mantenimiento Qwen3.8-27B (revisión R13):**
  - significaciones sin corrección reescritas como p cruda, sin Holm (53 celdas), y familia de 10
    preguntas agregadas declarada en JEV-67;
  - matiz de la gramática (probabilidades);
  - `department` 13 + 1 en vez de 14;
  - addenda «cerrado por JEV-67» en manifiestos antiguos;
  - test de referencia ausente (JEV-72 §1).
- **JEV-71 §3–4:** `jevbench.score --summary --adj-ci` (IC bootstrap estratificado del ajustado; supone
  registros independientes) y `--null-as-error` (sensibilidad: vector crudo nulo como error de formato).
  Ambos son opt-in; el marcador oficial no cambia.
- **JEV-69:** borrador en inglés de la issue para system-one-adapter en `docs/upstream/` (sin publicar).
- Implementación: Codex (T4, T6, tras el traspaso de OpenCode) y Devin (T2, T3, C9). Revisión: Codex
  (R13–R15) y Claude (T4, T6).

## [0.35.0] - 2026-10-06 — JEV-70: DiffusionGemma → revisor Jev, web y saneado del sitio

- **Cascada DiffusionGemma → Jev** (pre-registrada en `c4f8975`; Jev 1.13):
  - S1 → Jev: `audit` **64** / `review` 63, frente a 53 de la D1;
  - P → Jev: 62 / 63;
  - ninguna celda significativa tras Holm frente a la D1, Decider-4B → Jev ni Jev → Jev (subida
    descriptiva);
  - alerta del revisor 25/30 TP · 1/30 FP, cumple; la alerta de una pasada sacó 19/30;
  - 2.ª pasada $0.0098 por cascada, mediana 605 ms. Marcador: `…_s1_jevrev_{review,audit}`.
- **Web (artifact) y sitio regenerados:**
  - familia DiffusionGemma, con S1, P, la ruta TypeSafe discrete, las cascadas con Jev y las alertas;
  - fila en la tabla «Modelos», tarjetas e hito del 6-oct;
  - las significaciones antiguas sin corrección múltiple (Clef vs Jev en depth/urgency, sol como revisor) se
    reescriben como p cruda, no significativa tras Holm.
- **Saneado del sitio público:** `site.py` publicaba en `data/meta.json` la ruta local del GGUF de los runs
  Qwen3.8 de Arc (JEV-67). Ahora reduce rutas a su nombre de fichero, y `tests/test_site.py` prohíbe
  rutas y usuarios y pasa `publish.scan` sobre el sitio. **El despliegue actual de Netlify aún la contiene**
  hasta que se redespliegue.
- Implementación de Devin (W1, C8), revisión de Codex (R11, R12 APTO).

## [0.34.0] - 2026-10-06 — JEV-70: DiffusionGemma-26B-A4B, resultados

- **DiffusionGemma-26B-A4B NVFP4** vía las lecturas estructuradas de vLLM (`1b3b88ec`, interposer
  de la PR #57250), en dos DGX Spark. La puerta de montaje se aprobó en cada batería.
  - **P** (`samples="auto"`): ajustado **53**, 195/195 sin errores, Brier noul 0.095, mediana 318 ms.
  - **S1** (una lectura): 53, Brier 0.101, mediana 122 ms; la regla fijada **recomienda S1**.
  - Frente a jev_v3 (45): sin diferencia demostrada tras Holm. La única celda cruda es
    papers32.depth, p=0.002 → Holm 0.097.
  - Calibración peor que la de Jev (P.b confirmada).
- **Sensibilidad al orden de las opciones** (Rot1): ajustado 45, acierto en `choice` −7.3 pp
  (IC95 −11.8 a −3.0).
- **Reproducibilidad:**
  - misma sesión: 259/260 decisiones iguales (R.a inconclusa);
  - entre hosts: 249/260 (X.a refutada);
  - las probabilidades varían en ambos casos.
- **Ruta del adaptador TypeSafe**, con `--reasoning-parser gemma4`:
  - discrete: ajustado **51**, 0 errores, mediana 516 ms; papers32.depth mejor que Jev tras Holm;
  - probabilities: parada por la regla de errores (7 respuestas que la librería no valida).
- **Revisor no evaluable:** el esquema del revisor de triaje/adv (11 preguntas, formato `indexed` del
  interposer) se rechaza con 422 en las 160 revisiones de esas fases, porque las etiquetas de `hostile`
  no comparten un único hueco.
- **Alerta de una pasada:** 19/30 TP, 0/30 FP; no cumple (adv4 4/10). Clef-27B detecta más
  (8–1, p=0.039).
- **Hallazgo en el banco:** papers32 P02 y P03 son el mismo paper con GT distinto en `practice` (JEV-73).
- Marcador: P y S1 en `docs/resultados_runs.txt`. Ficha en `docs/modelos.md`, fila en AGENTS.md y
  resultados en el manifiesto, en `alerta_manipulacion.md` y en `cascada_jev.md`.
- `dgemma_gate`: atribución conjunta de casos con estado idéntico (Devin C7, revisada por Codex en R8).
  Cifras reproducidas de forma independiente (OpenCode/GLM) y conclusiones revisadas por Codex.

## [0.33.0] - 2026-10-06 — JEV-70 F0: DiffusionGemma-26B-A4B, herramientas y congelado

- **F0 de JEV-70 completada en .80 y .81** (build vLLM `1b3b88ec` idéntica, NVFP4
  `ec4ff3df`, CANVAS 64, MAXLEN 16 384): canario **sigue los criterios** (C+b 5/5,
  C+c 5/5) en ambos hosts; smoke correcto; **puerta de montaje §6.4 aprobada** en
  canarios (15/15) y smokes P, X y Rot1 (6/6, tres familias). Manifiesto congelado:
  `docs/infra_runs/dgemma_26b_a4b_nvfp4.md` (+ evidencias en su carpeta).
- **Revisiones 3–5 del pre-registro** (comentarios de la issue): dos Spark (.81
  P/S1/R; .80 réplica X, rotación Rot1 y ruta TypeSafe); condicional revisor/alerta
  si P ≥ 33. Ruta TypeSafe: **L no ejecutable** (el motor de difusión rechaza
  `temperature`/`seed`) y **L′ no ejecutable** (salida `thought\n{…}` del canal de
  pensamiento de Gemma); se pre-registra L″ con `--reasoning-parser gemma4` en sesión
  aparte. Entorno: `ninja` en el PATH, caché de vLLM propia en .80 (la de
  `~/.cache/vllm` es de root) y `VLLM_LOGGING_LEVEL=DEBUG` (único nivel que registra
  el prompt en esta build).
- **Harness:** `systemone_http` con `extra`, `timeout`, `capture_raw`,
  `rotate_choice` y cuerpo del error HTTP en `diag`; nuevos `jevbench.dgemma_preflight`
  (§6.2–6.3), `dgemma_canary` (§6.5 y calentamiento), `dgemma_gate` (puerta §6.4
  sobre el log DEBUG, atribución por caso), `dgemma_f1` (runner caso a caso con
  reglas de parada, sesión, lock, tope persistente y pasada única de reintento) y
  `dgemma_report` (§8.2 + celdas nuevas, McNemar-Holm); `scripts/serve_dgemma.sh`.
  `rotation.rotate_choice` aplica el residuo por pregunta (idéntico con `shift=1`).
- **Orquestación multiagente:** implementación Devin, revisión independiente Codex
  (R1–R6, todos los hallazgos aceptados y corregidos), consolidación Claude.

## [0.32.0] - 2026-10-04 — JEV-67: Qwen3.8-27B local con preguntas visibles

- **Batería con visibilidad verificada (JEV-67):** Qwen3.8-27B local, thinking
  off, temp 0, con las preguntas en el prompt (ruta struct + inyección),
  195 casos × 11 fases, 0 errores en las 8 celdas: FP8 prob **51**,
  FP8 nostruct temp 0 **51**, NVFP4 prob **50**, NVFP4 discrete **63**,
  GGUF prob **48**, GGUF discrete **63** (A3/A4 y sondas aparte).
- **La gramática no cambia decisiones** en FP8/SGLang con preguntas visibles:
  acuerdo A1↔A2 967/969 (99.8 %, IC95 inferior 99.3 %) y Δ ajustado −0.2.
  El 56/56 de JEV-66 generaliza a la batería completa.
- **Discrete supera a probabilities** (+12 a +15 ajustado, B2.b/C2.b
  refutadas) con preguntas visibles en ambos backends; los timeouts/`length`
  de papers de JEV-65 (a ciegas) desaparecen (0 fallos).
- **Rotación choice (A3):** 24/259 cambios de etiqueta — inconclusa (cota
  superior 13.5 %); 3/24 conservan posición, sin exceso significativo
  (A3.b); el orden sí afecta al acierto pareado (A3.c, +6.2 pp [+2.6, +9.9]
  a favor de rot1).
- **Sonda de inyección (RQ6):** SGLang (.80/.81), llama.cpp (.70), vLLM
  0.29.0 (.81) y Ollama 0.32.14 **no** hacen visibles las preguntas del
  `response_format` (tokens del primer intento + canario conductual,
  concordantes; D-vllm 16/0 y D-ollama 10/0 nulos); usar
  `inject_schema_in_prompt`.
- **Revisión externa (codex) sobre la ejecución:** cifras reproducidas;
  corregidos — la vigilancia de tokens de las celdas discrete (offsets mal
  cargados; comprobación posterior 195/195 OK), identidad e historial de
  puertas (`gate_id` + referencia desde la batería), el análisis de «conserva
  posición» (etiqueta nueva, no la vieja), la reanudación (claves operativas
  separadas de la config congelada, pre-validación de todas las fases,
  contadores reconstruidos), el informe (ausentes ≠ ok, máscaras NO
  EVALUABLE, evidencia real de P+), `git_dirty` en meta y tests de regresión.
- **`adapters/llm.py`:** opción `rotate_choice=<int>` (rota las claves de
  criteria de las choice en prompt y esquema; meta lleva `perm_sha256`).
- **Nuevos módulos:** `jevbench/rotation.py` (helpers movidos de diag65),
  `jevbench/jev67.py` (puerta de visibilidad §5.1, supervisor de batería con
  regla de tokens por caso, informe y clasificación §8.2 con IC en stdlib),
  `jevbench/probe_injection.py` (sonda (T) de tokens + canario (C)).
- **`diag66`:** `--prefix` para runs de diagnóstico JEV-67 (P+live, D-*).
- Manifiesto: `docs/infra_runs/qwen38_jev67.md`.

## [0.31.0] - 2026-10-04 — JEV-66: mecanismo de los vectores nulos confirmado

- **Confirmación causal (JEV-66):** la celda `typesafe_struct` con el esquema
  serializado además en el system prompt (`inject_schema_in_prompt=true`,
  gramática `response_format` intacta) produce **0 vectores nulos** en los 12
  casos JEV-63 × 3 reps en los tres backends locales (NVFP4/SGLang,
  FP8/SGLang, GGUF/llama.cpp), mientras el control sin inyección en la misma
  sesión reproduce la familia del síntoma (8–14 nulos/rep + `length` en T16;
  firma por ID exacta solo en GGUF).
  Predicción pre-registrada cumplida: los runs `structured` locales eran
  **medición a ciegas** (el modelo no veía las preguntas).
- **Revisión externa de JEV-66 (codex):** 4 hallazgos corregidos — los
  informes `diag65`/`diag66` distinguen ahora «sin captura raw» de «captura
  sin nulos» (columna nueva); la firma del control queda descrita como
  familia reproducida, no idéntica, con las variaciones por rep anotadas;
  se documenta la ejecución parcial preservada en nvfp4 r1; y se re-matiza
  que la ablación JEV-65 no comparó las variantes con preguntas visibles, así
  que un posible efecto de las frases en esa condición sigue sin medirse.
- **`adapters/llm.py`:** opción `inject_schema_in_prompt` (opción A del
  pre-registro) — añade al system prompt el mismo apéndice de esquema que la
  librería usa en `structured=false`, conservando la gramática; el texto
  enviado es byte a byte el de la ruta nostruct (test).
  `expected_system_prompt_sha256` reproduce el prompt inyectado sin petición;
  la opción queda en `meta` y en la protección de reanudación.
- **`jevbench/diag66.py` + `diag66_report.py`:** runner de las dos celdas
  pre-registradas (orden alternado, seeds 101/202/303, mismas protecciones
  que diag65) e informe por celda/rep con nulos crudos, tokens de entrada,
  acuerdo de decisiones y acierto diagnóstico.
- **Tests:** `tests/test_diag66.py` (matriz, orden, reanudación, informe) y
  dos tests nuevos del adaptador (payload inyectado = nostruct + gramática;
  validación de la opción). 117 tests en verde.
- **Manifiesto** `docs/infra_runs/diag_qwen38_jev66.md`; runs
  `results/diag_qwen38_jev66_*/` (216 evaluaciones, solo GPU local). JEV-A-2
  actualizado. Sin cambios de GT/scorer/históricos.

## [0.30.1] - 2026-10-04 — correcciones de la revisión externa (JEV-60 + JEV-65)

- **Conclusión JEV-65 matizada** (bloqueante): las frases anti-inyección no
  son *necesarias ni suficientes* — quitarlas baja el conteo de nulos en FP8
  (14→11/rep), así que no se excluye contribución parcial. Texto corregido en
  CHANGELOG 0.30.0, resultados, modelos, manifiesto, web y sitio.
- **`diag65.py`: reanudación estricta** (bloqueante): `_check_resume` compara
  ahora la configuración efectiva completa (modelo, endpoint, límites,
  normalización, `questions_hash` y el sha del system prompt **calculado para
  la fase** — los prompts simples incrustan las preguntas; la familia
  typesafe+nostruct queda marcada como no verificable sin petición) en ambas
  direcciones, y los casos con error se conservan en vez de re-ejecutarse y
  sobrescribirse (`--retry-errors` para repetirlos explícitamente).
- **`diag65_report.py`:** acierto base/rot de la sección C ahora pareado
  sobre la intersección de preguntas respondidas (con respuestas exclusivas
  y casos sin pareja reportados aparte); `missing` cubre fases y
  repeticiones enteras ausentes; la tasa de primera opción de los runs
  rotados se cuenta sobre el orden rotado; la validación del raw exige
  números finitos en [0,1] (los booleanos ya no valen), tolera estructuras
  malformadas y registra min/max de sumas y las fuera de [0.95,1.05].
- **`adapters/llm.py`:** `expected_system_prompt_sha256(questions)` reproduce
  el prompt que se enviará (variantes simple + familia typesafe en struct).
- **Alerta JEV-60:** corregida la afirmación de que el contexto del revisor
  levanta la sensibilidad de sol — una pasada y revisor detectan los mismos
  22/30 con 0 FP (las 60 decisiones coinciden una a una).
- **Discrete JEV-65 matizado:** el agotamiento de salida solo está
  demostrado en NVFP4 (`length` + timeouts); en FP8 solo hay timeouts de
  300 s — texto corregido en todas las superficies.
- **Manifiestos JEV-63/JEV-65:** revisiones HF de pesos verificadas por
  hashes LFS (NVFP4-BF16-LMHead `009632fe…`, DSpark `b9a5dbdf…`, FP8
  `017b9c7a…` con sha256 de pesos/tokenizer iguales a los OID del repo),
  digest completo de la imagen y config efectiva del servidor; lo no
  recuperable (tmux caído) queda marcado como reconstruido.
- **Web:** dos nuevos pasos en «Las pruebas, en orden» narrando JEV-63/JEV-65
  y JEV-60 con ejemplos de la evidencia (vector nulo crudo, frases abladas,
  repetición a `length`, decisiones de alerta idénticas); JEV-A-2 (KB
  YouTrack) actualizado y JEV-65 cerrada tras la revisión.
- **Revisión externa de la web completa (claude, vía Herdr):** 14 afirmaciones
  corregidas (coste Qwen-Cerebras ~64× —no 18×—, «mejor medida» →
  «recomendada» del circuito, luna-revisor no empeora triaje —falla por
  ganancia y alerta—, Strands trunc difiere en una decisión adv5, Clef acotado
  a decisores dedicados, ~3× coste de luna→Jev —no 4×—, −16* parcial del
  histórico NVFP4, matiz «menos ceros ≠ mejor salida» en V3) y 8 de
  estructura (Clef-Flash pintado en la alerta y su revisor en REVIEWERS,
  variante Cerebras con esquema en el dumbbell, listón acotado a los sets del
  criterio, deduplicados los pasos de sol y reordenados por fecha, GGUF y
  latencias DGX en la tabla de hardware, «LLM en claro» en la navegación,
  media de 10 sets —ood excluido—). Las mismas cifras corregidas en
  `cascada_jev.md`, `resultados.md`, `AGENTS.md` y el manifiesto de Strands.
- **Causa raíz de los vectores nulos identificada (claude, 4-oct, verificado
  en código y tokens):** con `structured=true` el `system-one-adapter` envía
  solo el system prompt y el documento; las preguntas van únicamente al
  `response_format`, que SGLang/llama.cpp/vLLM usan solo para la gramática —
  el modelo local responde **a ciegas** (222 tokens de entrada frente a 958
  en Cerebras, que sí inyecta el esquema). Así quedan reexplicados los ceros
  de JEV-63/JEV-65, el −16 NVFP4 y el −40 Flash-Next (medidas inválidas del
  modelo, no del contrato), los timeouts/`length` de `discrete` en papers y
  la ausencia del síntoma en Cerebras. Documentado en los dos manifiestos,
  `modelos.md`, `resultados.md`, web y sitio. Prueba de confirmación
  pendiente de pre-registro (struct con el esquema inyectado en el prompt →
  predicción 0 nulos) y control de posición en `probabilities` (el de
  `discrete` no cubre el empate nulo→uniforme→primera clave del scorer).
  Matices aplicados: las 60 alertas idénticas de sol tienen tres TP con
  probabilidad empujada al borde del umbral; «sin petición viva» queda
  acotado al lado cliente; `capture_raw` guarda cuerpos sin redactar
  (documentado en `run.py`, `llm.py` y la ficha — `publish.py` lo elimina del
  espejo). Marcador: los dos runs struct locales se etiquetan «sin
  preguntas».
- Tests: +11 en `tests/test_diag65.py` cubriendo los fixes.

## [0.30.0] - 2026-10-04 — JEV-65: las frases anti-inyección no son necesarias ni suficientes

- Ablación controlada del prompt (matriz pre-registrada, 720 evaluaciones nuevas
  en NVFP4 .80 + FP8 .81): V3 (V1 sin las dos frases anti-inyección) y V5
  (redacción alternativa) siguen emitiendo vectores nulos bajo esquema —
  NVFP4 9 y 8–14/rep, FP8 11 y 13–16/rep — y V4 (V2 + las frases) sigue sano.
  Las frases no son ni necesarias ni suficientes para la degeneración, aunque
  en FP8 quitarlas baja el conteo de nulos (14→11/rep): la ablación no excluye
  una contribución parcial. El componente necesario queda en otra parte del
  prompt TypeSafe (inconcluso), con los históricos JEV-63 como referencia.
- En `discrete` los vectores nulos no existen por construcción del esquema,
  pero V1 + papers degenera igual: fallo sistemático de salida — `length` y
  timeouts de 300 s en NVFP4, solo timeouts en FP8 (agotamiento demostrado
  solo en NVFP4). Discrete oculta la forma, no la degeneración.
- Control de posición: rotar una posición las claves choice (prompt y esquema)
  apenas cambia decisiones ni acierto — sin sesgo de posición demostrado.
- Adaptador `llm`: nuevas variantes `prompt=sin_antinj|simple_antinj|antinj_alt`
  (transformación literal del prompt de la librería, conserva tail de modo y
  apéndice nostruct) y `system_prompt_sha256` registrado en cada run.
- `jevbench.diag65` + `diag65_report` (missing por ID, validación raw por tipo,
  mediana con fallos, coste desconocido ≠ 0, acuerdo por decisiones) y
  `tests/test_diag65.py`; prompts congelados en `docs/experimentos/`;
  manifiesto `docs/infra_runs/diag_qwen38_prompt_ablacion.md`.
- `battery._load` lee `JEVBENCH_GT` en tiempo de llamada: el orden de imports
  de los tests ya no rompe el rescoring legacy.
- Sin cambios de casos, GT, scorer ni históricos. Diagnóstico de 12/6 casos.

## [0.29.0] - 2026-10-04 — JEV-60: alcance completo de gpt-6.1-sol (mejor revisor medido)

- `llm_gpt61sol_low_disc` (modo `discrete`, 195 casos, $0.38): ajustado **63** —
  ~2 puntos bajo `probabilities` (65), mismo patrón que luna y peor calibrado
  (Brier noul 0.073).
- `decider_4b_solrev_*` (sol como revisor de Decider-4B): **cumple JEV-32** y es el
  primer revisor que supera en ajustado al revisor Jev sobre ese D1 — audit **66** /
  review **68** frente a 64 (136 % de la ganancia en adv3+adv5, 105 % en triaje,
  alerta adv5 9/10 TP · 0 FP). Significativo solo en `relevance` de papers (p = 0.04);
  pasada-2 $1.05, ~100× la de Jev.
- `llm_gpt61sol_jevrev_*` (sol como D1 + revisor Jev): ajustado **66**, por debajo de
  `llm_gpt6luna_jevrev_audit` (71), que sigue siendo la mejor configuración medida.
- `llm_gpt61sol_low_alert_raw` (alerta de una pasada, pre-registrada): **22/30 TP ·
  0/30 FP — no cumple** (adv4 5/10); entre Span-01 (8/30) y Clef-27B (27/30).
- Gasto total JEV-60: ~$1.50 medidos sobre el tope autorizado de $3.

## [0.28.1] - 2026-10-04 — Revisión independiente JEV-63 y protocolo JEV-65

- Verificados 576 casos evaluados, 96 vectores nulos crudos y 3 errores
  NVFP4 por salida agotada; Cerebras $0.17217723 registrado por tokens/tarifas.
- Acotada la conclusión a prompt completo × ruta estructurada en la muestra;
  sin mecanismo interno ni exclusión de efectos de precisión/backend.
- JEV-65 revisado: controles actuales, hipótesis anti-inyección no confirmada,
  sesgo de posición en discrete y límites de seguridad/generalización.
- Corregida regresión de exportación pública: capturas raw privadas se sustituyen
  por hash en el snapshot; predicciones y JSON privados se conservan intactos.

## [0.28.0] - 2026-10-04 — JEV-63: la degeneración era prompt TypeSafe × esquema juntos

- Matriz reducida ejecutada: 12 casos fijados × 2 prompts × 2 rutas × 3 reps en
  cuatro configuraciones (NVFP4 .80, FP8 .81, Cerebras, GGUF Q4_K_M en Intel Arc
  .70 — la extensión opcional se completó también): 576 evaluaciones.
- **Resultado:** los vectores nulos (`0.0` en todas las opciones, leídos del raw
  antes de normalizar) solo aparecen en la celda `typesafe_struct` de los tres
  backends locales — 9/14/9 vectores por rep en NVFP4/FP8/GGUF, deterministas —
  y en ninguna otra celda ni en Cerebras. Mismo esquema con prompt simple: 0;
  mismo prompt sin esquema: 0. Se observa la interacción del prompt completo de
  TypeSafe con la ruta estructurada; no identifica el aviso anti-inyección ni
  excluye efectos de precisión/backend. Segunda forma
  degenerada observada: repetición hasta `max_tokens` (`finish_reason=length`)
  en triage_ext_en/T16, determinista en las 3 reps.
- Adaptador `llm`: nuevas opciones `prompt=typesafe|simple` (sustituye el system
  prompt por la plantilla pre-registrada `docs/experimentos/
  diag_qwen38_prompt_simple.txt`, renderizada con las preguntas del set) y
  `capture_raw` (guarda por caso los intentos del proveedor: payload real y
  respuesta sin normalizar, también en caso de error vía `diag.raw`).
  `reasoning_effort=none` aceptado (solo Cerebras: thinking off verificado).
- Nuevos módulos `jevbench.diag63` (runner de la matriz, runs
  `diag_qwen38_<bloque>_<celda>_r<rep>` reanudables) y `jevbench.diag63_report`
  (resumen por celda/rep: validez, ceros crudos, uniformes normalizadas,
  acuerdo entre reps, tiempos, coste).
- Infraestructura: FP8 oficial (29 GB) e imagen `lmsysorg/sglang:qwen38-27b`
  copiados de .80 a .81 (mismo digest) para servir el bloque FP8 sin tocar el
  servicio NVFP4 del usuario; llama-server SYCL en .70 para el bloque GGUF.
- Coste Cerebras registrado por tokens/tarifas: $0.17218 (presupuesto JEV-63: $1).
- Docs: manifiesto `docs/infra_runs/diag_qwen38_jev63.md`, plan actualizado a
  ejecutado, `modelos.md`/`resultados.md`/webs con el diagnóstico de la interacción.
- Sin cambios de casos, GT, scorer ni históricos. Diagnóstico de 12 casos:
  no es puntuación del marcador.

## [0.27.3] - 2026-10-04 — Adaptador explicado y diagnóstico reducido

- Marcador por set: iconos vectoriales homogéneos para local/API y sus
  cascadas; espacio reservado y elipsis para evitar recortes de etiquetas.
- Leyenda del marcador: reutiliza los mismos iconos vectoriales local/API
  de las filas, en vez de glifos de texto.
- Skill actualizar-web y procedimiento: control de coherencia gráfica entre
  marcas y leyenda, cascadas, etiquetas largas y revisión escritorio/móvil.

- Explicación accesible en ambas webs: ejecución, contenido útil y confianza
  son problemas distintos; conclusiones y límites separados.
- JEV-63 pre-registra 12 casos × dos prompts × dos rutas × tres repeticiones
  en NVFP4, FP8 y Cerebras, con extensión Intel opcional y bóveda ia-models.
- Síntesis añadida a JEV-A-2. Sin nuevas inferencias ni cambios de GT/scoring.

## [0.27.2] - 2026-10-04 — Conclusiones auditadas del adaptador LLM

- Corregidas web/fichas/manifiestos: asociación con salida estructurada,
  sin causa interna aislada ni equivalencia de rutas demostrada. El histórico
  NVFP4 difiere también en límites; vLLM corresponde a otro modelo.
- Cerebras sin esquema: un reintento por malformado en probabilities y otro
  en discrete; cero errores finales. Mínimo McNemar probabilities=0.0625.
- Cobertura del contador explícita: resumen 9 fases, batería completa 11;
  histórico 53/218 vs 67/257. Sin cambios de scoring, GT o JSON históricos.
- JEV-A-2 actualizado y JEV-62 registra integración local/QA; sin nuevas
  inferencias ni push/despliegue. Las conclusiones previas se conservan como
  histórico y quedan revisadas por esta entrada.

## [0.27.1] - 2026-10-04 — Síntesis adaptador LLM en la web (JEV-58+61)

- Tarjeta Qwen retitulada «48–52 sin él» con la ablación cerrada
  (NVFP4 −16→52 misma variable) y la comparación de bandas local↔Cerebras.
- Nota nueva «Salida válida ≠ salida sana»: JSON conforme y degenerado a la
  vez; el esquema valida la forma, no el contenido; guardián `unif choice`.
- Circuito recomendado: alternativa todo-API Jev → revisor Cerebras-Qwen
  (68–69, ~$0.004/caso de pasada-2).
- Entrada «LLM abiertos en los DGX»: el −16 queda como artefacto del protocolo.
- `metodologia.html` cerrada con NVFP4 52 e independencia de esquema en
  Cerebras; `modelos.md` marca JEV-57/58 resuelto con la matriz local.
- JEV-A-2: sección de cierre con matriz, mecanismo y lecciones combinadas.

## [0.27.0] - 2026-10-04 — JEV-58: el mecanismo aislado + batería GGUF (48) y NVFP4-nostruct

- **Mecanismo cerrado (diagnóstico JEV-58 en .80):** la emisión de 0.0 bajo
  esquema la dispara el **contenido difícil del documento**, no la
  anti-inyección del prompt, el tamaño del esquema, la cuantización ni el
  backend. Reproducido con réplica exacta del wire del adaptador
  (system prompt + `<document>` + JSON Schema estricto). Mismo prompt+esquema
  con caso normal → probabilidades reales.
- **Métrica nueva `unif choice`** en `score --summary` y en el marcador:
  decisiones `choice` casi uniformes (máx−mín < 0.05) por run — detecta el
  síntoma en históricos: NVFP4+SGLang 53/218, Flash-Next+vLLM 31/215, todo lo
  demás 0/219.
- Runs nuevos:
  `llm_qwen38_27b_gguf81_nostruct_prob` (llama.cpp/GGUF Q4_K_M en .81,
  ajustado **48**, 0 errores, 0/219 unif — tercer backend reproduce el
  «Qwen local sano» ~48-49);
  `llm_qwen38_27b_nvfp4_nostruct_prob` (SGLang/NVFP4 en .80, la celda
  pre-registrada de JEV-58);
  smokes `smoke_qwen38_gguf81_nostruct`, `smoke_qwen38_nvfp4_struct_v2`.
- Manifiesto `docs/infra_runs/llm_qwen38_27b_gguf81_nostruct_prob.md`;
  tarjeta web y metodología reescritas con el mecanismo aislado.
- **JEV-61 — cuadrícula Cerebras cerrada + revisor Cerebras:** la celda que
  faltaba, `qwen-3.8-27b` en la API de Cerebras con `structured=false`, da
  ajustado **65** (`llm_cerebras_qwen38_27b_nostruct_prob`, $0.40); las celdas
  `discrete` dan 58/58. Las cuatro celdas con 0 vectores degenerados → la
  salida de Cerebras no depende del esquema; la brecha 59↔49 con el FP8 local
  queda en pesos/precisión/backend (descriptiva). Como revisor de `jev_v3`
  (cascada todo-API): ajustado **68/69** en audit — sobre el 64 de Jev→Jev,
  sin significación McNemar — y alerta 23–24/30 con 0 FP. Coste total de la
  sesión: ~$2.51. Manifiestos en `docs/infra_runs/`.
- La marca local/API (⌂/☁) de las cascadas muestra ahora las dos patas
  (`d1_local`→`rev_local`); `run_local` lee también el campo `reviewer` de los
  `_raw`, y el tooltip «Salida LLM solicitada» incluye el modo
  (probabilities/discrete).

## [0.26.1] - 2026-10-04 — Auditoría JEV-57 y salida LLM visible

- Se matizan conclusiones: los smoke SGLang/Ollama señalan structured, pero
  no aíslan modelo, prompt/esquema y servidor ni efectos de precisión.
  FP8 sin esquema da 49; NVFP4 solo smoke. Corrección de «única variable»
  y ranking papers. 0.25.0/0.26.0 se conservan como histórico revisado.
- structured=true/false de metadatos por run/set visible en marcador y
  entorno del sitio. Tests de procedencia/saneado, sin inferir soporte efectivo.
- Cerebras se marca como API externa: una URL compatible OpenAI no implica
  ejecución local. Se añade regresión frente al endpoint propio del DGX.
- JEV-A-2 actualizado con evidencia/límites y Ollama. JEV-58 prepara NVFP4
  completo y controles: sin nuevas inferencias. JEV-59 integra docs y ambas
  webs localmente; sin push/despliegue.

## [0.26.0] - 2026-10-04 — JEV-57, matriz completa: el modelo emite ceros bajo esquema forzado

- **Réplica en Ollama/llama.cpp** (`qwen3.8:27b` GGUF, .80): con `structured=true`
  también emite `0.0` (8/10 uniformes en adv1); con `structured=false`, 0/10
  uniformes y **10/10** dept. Dos motores de gramática independientes (xgrammar
  y llama.cpp) con tres cuantizaciones distintas (NVFP4, FP8, GGUF) producen el
  mismo fallo → **comportamiento del modelo bajo decodificación restringida**,
  no bug de backend ni de cuantización. Cerebras lo evita por su propio camino.
- Smokes `smoke_qwen38_ollama_*`; manifiesto, marcador, fichas y tarjeta web
  corregidos («era el esquema forzado»). Metodología: párrafo nuevo «Structured
  output: la trampa silenciosa» + señal de alarma en `evaluar-modelo-nuevo.md`.
- `MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark` en .80: `git pull` — sin commits
  nuevos (build reciente, pin nightly con el fix sglang#35255).

## [0.25.0] - 2026-10-04 — JEV-57 resuelta: era el structured output de SGLang, no la cuantización

- **Ablación completa:** el FP8 oficial (`Qwen/Qwen3.8-27B-FP8`, vía ModelScope)
  en el mismo SGLang de .80 reproduce la emisión de ceros con `structured=true`
  (5/10 en adv1), y con `structured=false` desaparece en **NVFP4 y FP8 por
  igual** (0/10, 9/10 dept). El culpable es el camino de decodificación
  restringida por esquema de este build de SGLang en la familia híbrida GDN/VL —
  no los pesos, ni el muestreo, ni el thinking.
- Run nuevo `llm_qwen38_27b_fp8_nostruct_prob` (195 casos, 11 fases, 0 errores):
  **ajustado 49**, por encima de Jev (45) — la lectura correcta del Qwen local.
  0/259 decisiones choice uniformes; papers 80.3 (ρ 0.82, mejor de una pasada
  tras sol); gana a Jev en `depth` (p<0.01) y `practice` (p=0.02). El −16 del
  run NVFP4 queda explicado como artefacto de serving.
- Manifiesto `docs/infra_runs/llm_qwen38_27b_fp8_nostruct_prob.md`, smokes
  versionados (`smoke_qwen38_*`), marcador, ficha, tarjeta web y Seguimiento
  actualizados con la resolución.

## [0.24.0] - 2026-10-04 — JEV-57 ejecutado: la abstención del Qwen local no es el muestreo

- Smoke discriminador en .80 sobre el mismo NVFP4/SGLang (`smoke_qwen38_t0`,
  `smoke_qwen38_t0_think`, `smoke_qwen38_t0_nonorm`): la "abstención" es
  **emisión literal de `0.0` en todas las opciones** — el `normalize` del
  adaptador la convierte en uniforme y el desempate cae en la primera opción.
- Ni `temperature=0` ni `enable_thinking` la apagan (6/10 y 8/10 en adv1 — el
  thinking la empeora): no es la configuración de generación sino los pesos
  NVFP4 de la comunidad o el backend. Batería local descartada por el criterio
  pre-registrado; la ablación real (bf16/FP8 oficial) queda como fase 3.
- Docs al día: mecanismo corregido en `resultados.md`, `modelos.md`, tarjeta web
  y Seguimiento. Versión minor por experimento ejecutado.

## [0.23.2] - 2026-10-03 — JEV-57 pre-registrado + docs al día

- **JEV-57 creada**: discriminador config vs cuantización para el Qwen3.8-27B
  local (NVFP4): smoke dirigido con `temperature=0` ± thinking sobre los casos
  donde el run original se abstenía, y batería solo si la abstención en `choice`
  cae por debajo del 5 %. Pre-registro completo en la issue; referencia en la
  sección Seguimiento de `docs/resultados.md`.
- AGENTS.md: añadido `docs/plan_cerebras.md` a la estructura, `plan_gpt61sol.md`
  marcado como ejecutado y fila LLM generalista con Cerebras.

## [0.23.1] - 2026-10-03 — Análisis NVFP4 local vs Cerebras + nota web

- Análisis de la brecha Qwen3.8-27B local (−16) ↔ Cerebras (59): concentrada en
  las preguntas `choice` (department/domain/depth); el run local declara
  distribuciones casi uniformes en el **26 % de las decisiones de elección**
  (0 % en la nube y en cualquier otro run) — el modelo se "abstiene" y el
  desempate cae en la primera opción (en adv1 eligió `bronchoscopia` 7/10 veces,
  6 mal). Documentado en `docs/resultados.md` y `docs/modelos.md`; comparación
  descriptiva, no ablación de cuantización.
- Web (`docs/web/template.html`, propagada a `banco-jev.html` y `site/index.html`):
  tarjeta nueva «El mismo Qwen, de −16 a 59: pesaba cómo se servía», tarjeta
  «Clef-27B lidera» actualizada con Qwen-Cerebras 59, fila LLM generalista con
  los modelos Cerebras, latencias y alcance no medido.
- `docs/site_src/metodologia.html`: la tabla de experimentos ya refleja que
  Clef-27B sí cumple el criterio de revisor abierto (estaba obsoleta) y un
  párrafo sobre los rate limits por modelo de Cerebras y `min_interval`.
- README: «Resultado en una línea» actualizado (Clef-27B como revisor abierto
  que sí cumple; Qwen3.8-27B·Cerebras en una pasada).

## [0.23.0] - 2026-10-03 — Qwen3.8-27B en Cerebras (JEV-54, cierre)

- Run `llm_cerebras_qwen38_27b_low_prob`: `qwen-3.8-27b` en la API de Cerebras con
  el mismo protocolo que el run de GPT-OSS-120B, **sin `min_interval`**: sus
  límites de cuenta son por modelo y mucho más holgados (450 req/min, 27 000 req/h
  frente a 5 y 150), así que su `ms` (~0.77 s) sí es latencia real.
- 195 casos, 11 fases, 0 errores en ~3 min; coste medido **$0.44** (~$0.0022/caso;
  su `low` razona ~3× más tokens de salida que el de GPT-OSS).
- Resultado: ajustado **59**, el mejor LLM generalista tras sol (65) y luna (61),
  por encima de Jev (45) y Clef-27B (52). **Victoria significativa sobre Jev en
  `same_day` de adv5 (6–0, p = 0.03)**; sin derrotas significativas frente a Jev
  ni luna. El mismo tamaño en NVFP4 local daba −16 (comparación descriptiva, no
  ablación). Marcador, ficha y ambas webs actualizadas; manifiesto en
  `docs/infra_runs/llm_cerebras_qwen38_27b_low_prob.md`. Lección registrada en el
  manifiesto y el plan: los rate limits de Cerebras son por modelo.

## [0.22.0] - 2026-10-03 — GPT-OSS-120B en Cerebras (JEV-54) + `min_interval` en el adaptador llm

- Nueva opción `min_interval=<s>` del adaptador `llm` (`provider=openai`): espacia el
  inicio de peticiones HTTP consecutivas — correcciones por JSON mal formado incluidas —
  para respetar límites de peticiones del proveedor. Se registra en `meta`. Test nuevo
  `test_min_interval_spaces_requests`. La cuenta de Cerebras usada tiene topes de
  5 req/min y 150 req/h; sin pacing el smoke recibió 429.
- Run `llm_cerebras_gptoss120b_low_prob`: `gpt-oss-120b` en la API de Cerebras
  (`base_url=https://api.cerebras.ai/v1`, Chat Completions), mismo protocolo
  pre-registrado en `docs/plan_cerebras.md` (`reasoning_effort=low`, `temperature=0`,
  `reasoning_format=parsed`, `max_tokens=8192`, `min_interval=27`). 195 casos,
  11 fases, 0 errores, 0 reintentos, coste medido **$0.12**; manifiesto en
  `docs/infra_runs/llm_cerebras_gptoss120b_low_prob.md`.
- Resultado: ajustado **34**, entre la mayoría (0) y Jev (45)/Clef-27B (52)/luna (61)/
  sol (65); muy por encima del Qwen3.8-27B local NVFP4 (−16, comparación descriptiva).
  Sin diferencias significativas por pregunta frente a Jev ni luna; la brecha agregada
  viene de adv3, ρ relevancia de papers y calibración. Marcador, ficha
  (`docs/modelos.md` §LLM generalista) y ambas webs actualizadas; en las webs el `ms`
  del run se publica como n/a porque incluye el pacing, no la latencia del modelo.
- `docs/procedimientos/evaluar-modelo-nuevo.md`: nuevo paso sobre rate limits de API
  (cabeceras `x-ratelimit-*`, `min_interval`, efecto en `ms`/`usage.latency`).
- `qwen-3.8-27b` en Cerebras queda pendiente de autorización de gasto (JEV-54 sigue
  abierto para esa parte).

## [0.21.2] - 2026-10-03 — Introducción didáctica en la web (JEV-55)

- YouTrack: propuesta editorial JEV-56 (pendiente), base de conocimiento JEV-A-1/A-2
  con metodología, resultados y limitaciones al 3-oct; notas fechadas en HOM-A-2/A-8
  distinguen evaluaciones terminadas de inventario de pesos/NAS no revalidado.
- Nueva sección «Decisiones tipadas, no un chat» en `docs/web/template.html`,
  antes de las conclusiones: explica el contrato System One (estado + preguntas
  tipadas → distribuciones de probabilidad), los tipos `choice`/`score`/`noul`
  con un ejemplo ficticio con barras de probabilidad, y la diferencia entre un
  decisor especializado y un LLM generalista servido con `system-one-adapter`.
- Tarjetas sobre cómo leer una probabilidad declarada (no garantiza calibración),
  la cascada de revisión y qué demuestra —y qué no— el marcador, con enlaces a
  método, lectura de métricas y marcador. Entrada «Qué es» en la navegación.
- Se propaga a las dos salidas (artifact `docs/web/banco-jev.html` y portada
  `site/index.html`) al regenerar con `jevbench.web` y `jevbench.site`.

## [0.21.1] - 2026-10-03 — Historia del marcador legible (JEV-50)

- Referencia fija de Jev en la historia y versión probada en el marcador por set:
  etiquetas compactas Jev 1.13, versión completa `jev-1.13-20260917` en detalle,
  extraída de los resultados y de las fuentes de cascada, no del alias latest.
- Gráfico responsive compacto con solo tres récords diarios y tarjetas de líderes;
  se elimina el scroll horizontal del gráfico y las etiquetas amontonadas.
- Hitos separados en cronología (vertical en móvil) y tabla desplegable con todos
  los runs, fechas y cobertura, incluidos resultados negativos y parciales.
- Tooltips de récord accesibles por ratón, toque y teclado, con cierre al perder
  foco o pulsar Escape. Los récords usan el máximo por fecha, sin inventar orden intradía.
- Alineada la versión por encima de la entrada 0.21.0 ya presente en el changelog.
- Correcciones de la ficha Clef-Flash (JEV-53): el `depth` de papers es una
  victoria frente a Jev (8–1, p=0.04), no una derrota; su ρ 0.90 es la tercera
  mejor relevancia de una pasada, no la mejor; `clefrev_avg` es ajustado 55, no 50;
  añadido su punto débil en adv1+adv2 (bajo la línea trivial). `RUN_DATES` cubre
  `decider_4b_clefflashrev_review` y la entrada del sitio precisa que el revisor
  corrió en la Arc, no en GB10. Nueva entrada de Clef-Flash en «Las pruebas,
  en orden».

## [0.21.0] - 2026-10-03 — Clef-Flash 9B en Intel XPU (JEV-53)

- Nuevo run `clef_flash_9b_xpu`: `Cloudflare/clef-flash` (9B, revisión `17f0b0ad`)
  en el Intel Arc Pro B70 de .70, adaptador `clef` in-process (`device=xpu`, bf16,
  ventana 16384 — los 195 casos caben sin truncado). 195/195, 0 errores.
  Ajustado **41** (Clef-27B 52, Jev 45): única derrota significativa frente al 27B
  en `urgency` de adv2 (p=0.03); ρ relevancia 0.90. ~0,14 s/caso.
- Revisor `decider_4b_clefflashrev_{raw,review,audit,avg}`: ajustado 47 con `audit`;
  recupera 38 % de la ganancia de Jev en adv3+adv5 → no pasa el listón JEV-32
  (2º mejor revisor local). Alerta de una pasada `clef_flash_9b_xpu_alert_raw`:
  7/10 TP · 0 FP por set — cumple el criterio en el límite.
- Manifiesto `docs/infra_runs/clef_flash_9b_xpu.md`, ficha en `docs/modelos.md`,
  secciones en `cascada_jev.md` y `alerta_manipulacion.md`, marcador, web y sitio
  (familia Clef ya existente; fila compartida en la tabla de modelos).

## [0.20.2] - 2026-10-03 — Cuantización de las líneas base Qwen

- Historia del marcador (JEV-50): altura de 920 px también en móvil, etiquetas
  de récord sin solapamiento entre sí y hitboxes alineadas con los puntos;
  se mantiene el desplazamiento horizontal y no cambian los datos.
- Preparado `docs/plan_cerebras.md` (JEV-54): acceso de catálogo confirmado a
  Qwen3.8-27B y GPT-OSS-120B; dos baterías vía adaptador TypeSafe pre-registradas,
  sin inferencias, implementación ni ejecución. Precisión nativa FP16/FP8
  documentada sin confundirla con la etiqueta FP16 del formato OpenRouter.
- Web y sitio: etiquetas NVFP4 para Qwen3.8-27B y Flash-Next; corregida la
  etiqueta errónea BF16 del 27B, cuyo LM head sí conserva BF16.
- Ficha y notas del marcador: la comparación Qwen NVFP4 frente a Clef BF16
  no permite aislar el efecto de la cuantización del entrenamiento y la cabeza.

## [0.20.1] - 2026-10-03 — Regresión web y procedimientos (JEV-52)

- Nuevos tests `WebAssets` (`test_site.py`): cada familia de RUNS tiene color en las
  cuatro ubicaciones (template ×3 temas, site.css, FAM de template y common.js), cada
  familia tiene fila en la tabla «Modelos» de la portada y `run_local` clasifica
  local/API correctamente, cascadas incluidas.
- `evaluar-modelo-nuevo`: pre-registro de la política de ventana (strict primario,
  variante `_trunc` aparte), comprobación de flags de la versión instalada (PyPI vs git)
  y patrón .70 (venv + serve en 127.0.0.1 + túnel SSH); HF token ya persistido en
  .70/.80/.81 (AGENTS.md, sección Secretos).
- `actualizar-web`: checklist con la fila de la tabla «Modelos», la nota de
  hardware/latencias y la marca automática local/API.
- AGENTS.md: filas de CLM y Clef en la tabla de modelos (faltaban).

## [0.20.0] - 2026-10-03 — Web: marca local/API e historia desplazable

- El marcador por set distingue el modo de ejecución: `⌂` local (hardware
  propio/LAN) y `☁` con API externa, en etiquetas, tabla, tooltip y leyenda.
  `web.py` deriva el flag de `meta.adapter` (`llm` con `base_url` propio cuenta
  como local; las fusiones de cascada se clasifican por el revisor de la
  etiqueta).
- «Historia del marcador» se expande en horizontal dentro de su propio contenedor
  con scroll (ancho mínimo por día y por run, más aire entre puntos del mismo
  día) en vez de comprimirse al ancho de la página.

## [0.19.0] - 2026-10-03 — Variante trunc de Strands y token HF persistente

- Nuevo run `strands_2b_hobson_v19_xpu_trunc`: batería completa (195/195, 0 errores)
  sin `--strict-window`, es decir, con el truncado silencioso por defecto del
  servidor. Ajustado **21** (sin `*`); los 194 casos dentro de ventana responden
  idéntico al run estricto y P11 truncado acierta 2/5 preguntas (papers 59.1).
  El run primario del marcador sigue siendo el estricto (`_xpu`, 21*).
- Token HF del repo persistido en `~/.cache/huggingface/token` de .70, .80 y .81
  (a petición del usuario; verificado como `Mindbreaker81`).
- Web/sitio: fila de Strands en la tabla de modelos, latencias de CLM y Strands
  en la nota, hardware con la Arc Pro B70, y `coste.html` corrige que los
  abiertos ya no corren solo en GB10.

## [0.18.0] - 2026-10-03 — Strands Decider 2B Hobson v19 en Intel XPU (JEV-51)

- Nuevo run `strands_2b_hobson_v19_xpu`: `StrandsAgents/strands-decider-2B-hobson-v19`
  (checkpoint `bb282d78`, MANIFEST verificado; base `Qwen/Qwen3.5-2B-Base` `b1485b2f`,
  coincidente con la revisión inferida de `provenance.json`), servido con
  `strands-decider` git `eb89e5c` en Intel Arc Pro B70 (estación .70, backend XPU
  experimental confirmado por `/health`), ventana 4096 estricta y
  `--max-batch 5`; adaptador `systemone_http` por túnel SSH.
- 195 casos / 11 fases, 1 error pre-registrado: P11 excede la ventana (HTTP 422),
  papers32 queda 31/32 y el ajustado lleva `*`. Ajustado **21\***: por debajo de
  Decider-4B (33) y de Jev (45), por encima de la mayoría en casi todas las fases;
  falla en dept de adv1+2 (9/20 frente a 17/20 trivial). Derrotas significativas en
  `same_day` de triaje_ext_es frente a Jev y `relevance` de papers frente a
  Decider-4B (p<0.01); ninguna victoria significativa. Mediana ~0,13 s/caso cliente.
- Primer manifiesto remoto: `docs/infra_runs/strands_2b_hobson_v19_xpu.md`
  (hardware, revisiones, `/health`, comando efectivo, plan de ventana
  pre-registrado). `docs/dgx-spark.md` documenta la estación .70.
- Ficha en `docs/modelos.md` (incluye el inventario de entrenamiento — ContractNLI,
  MuSiQue, BoardgameQA, HelpSteer2, generados — sin solapamiento conocido, y la
  cuarentena de su «JevBench public» de 231 tareas) y marcador, web y sitio con la
  familia nueva "Strands" (color propio).

## [Unreleased]

- Investigación de `Cloudflare/clef-flash` (9B, Apache-2.0): creada JEV-53 para
  evaluar en Intel Arc Pro B70. Pesos ~17.75 GiB, contrato SystemOne compatible
  con el adaptador `clef`; dependencias/imports comprobados, inferencia XPU pendiente.
  El plan exige comprobar ausencia de truncado y comparar con Clef-27B.

## [0.17.1] - 2026-10-03 — Procedimientos y controles de publicación (JEV-52)

- Skills y procedimientos de evaluación/web: evidencia de viabilidad por dispositivo,
  manifiesto remoto, entrega delegada y concurrencia, validación independiente del scorer,
  criterio de cascada con valores sin redondear y McNemar pareado para alertas.
- Cierre por alcance: distinguir batería, integración local y despliegue remoto;
  preservar cambios preexistentes y no exigir despliegues no solicitados.
- Sitio: entorno verificado por run en `extra.env`; un endpoint HTTP genérico no implica
  GPU NVIDIA ni cuantización, y un LLM con endpoint propio no se etiqueta como API OpenAI.
- Regresiones: presencia y familia de runs en ambas webs (con excepciones históricas
  explícitas), etiquetas remotas correctas y ausencia de inferencias desde el host cliente.
- Exportador del espejo: elimina endpoints de metadatos y opciones anidadas, que
  conservaban la IP privada de CLM; regresión que verifica que las predicciones no cambian.
- actualizar-web: «Historia del marcador» documentada — `RUN_DATES` obligatorio para
  fusiones de cascada sin `meta.updated` y `HIST_EVENTS` solo para hitos del relato.

## [0.17.0] - 2026-10-03 — Historial del marcador en la web (JEV-50)

### Añadido
- **Sección «Historia del marcador»** en la web y la portada del sitio
  (`docs/web/template.html`, sección `#historia` + nav): línea temporal con
  cada run como punto (color por familia, tooltip con fecha/tipo/cobertura) y
  tres récords escalonados — decisor dedicado de una pasada (Jev → Clef-27B),
  una pasada incluyendo LLM (Jev → gpt-6-luna → gpt-6.1-sol) y cualquier
  configuración (Jev → Jev→Jev → luna→Jev). Hitos curados como marcadores
  verticales (`HIST_EVENTS` en el template).
- **`RUN_DATES` y `run_date()` en `jevbench/web.py`**: cada run lleva `when` —
  el menor `meta.updated` de sus fases; para las fusiones de cascada (sin sello)
  la fecha va fijada a mano en el mapa.

## [0.16.0] - 2026-10-03 — CLM y revisión de conclusiones de Clef (JEV-49, JEV-48)

### Evaluación de Contrastive-LM CLM-v0.1-8B en Intel Arc Pro B70 (JEV-49)
- **Run `clm_v0.1_8b`** (`results/clm_v0.1_8b/`): batería completa de 195 casos
  (`all+new` + `adv4`/`adv5`), 11 fases y 0 errores, servida mediante vLLM XPU en
  la Arc Pro B70 de 32 GB. Mediana de 80 ms por caso.
- Resultado negativo: ajustado **−35** frente a 0 de la mayoría, triaje ES/EN
  67.9/58.6, papers 50.6, adversarial 1+2 52.5, adv3 59.0, adv4 54.5,
  adv5 59.5 y Brier noul 0.238. No obtiene victorias significativas frente a
  Jev o Decider-4B; no es candidato a recomendación.
- Integrado CLM en marcador, artifact y sitio público, con familia propia y ficha.
- Revisión de JEV-48: el criterio de cascada local de Clef se mantiene. Se retira
  adv2 como evidencia comparativa y se matiza la alerta 27/30 frente a 25/30:
  McNemar p=0.50, sin diferencia significativa. Corregida la nota de la web que
  todavía decía que ningún revisor local superaba el listón.
- Corregida la tabla de cascada Clef: adv4 = **88.0**, no 83.5; ganancia media
  de triaje = 3.93 puntos. Ambos salen de los JSON mediante el scorer.

## [0.15.0] - 2026-10-03 — Clef-27B (Cloudflare) y primera cascada 100 % local (JEV-48)

### Añadido
- **Adaptador `clef`** (`jevbench/adapters/clef.py`): carga `joint_schema_model.py`
  del propio snapshot de HF y llama a `systemone` (API SystemOne nativa).
  `scripts/alert_onepass.py`: alerta de una pasada (solo `manipulation`, umbral 0.5)
  sobre adv3–adv5.
- **Run `clef_27b`** (`results/clef_27b/`): 195 casos, 0 errores, bf16 en DGX .81
  (revisión `2f3de3dd`). Ajustado **52** — el mejor single open-weight, por encima
  de `jev_v3` (45) en agregado: victoria significativa en `depth` de papers
  (p = 0.02), sin derrotas significativas. adv1/adv2 no se usan como evidencia
  comparativa. Mediana ~0.87 s/estado.
- **Cascada `decider_4b_clefrev_*`** (runs `raw/review/audit/avg`): Clef-27B es el
  **primer revisor que cumple el criterio JEV-32 sin ser Jev** — ~89 % de su
  ganancia en adv3+adv5, ~61 % en triaje, sin fase peor >2 puntos y alerta 9/10 ·
  1 FP en adv5. `decider_4b_clefrev_audit` = ajustado **58**, la primera cascada
  100 % local que da la talla.
- **Alerta de una pasada `clef_27b_alert_raw`**: 27/30 TP · 1/30 FP en adv3+4+5,
  cumple el criterio en los tres sets; frente al revisor Jev (25/30), la diferencia
  no es significativa (McNemar exacto p = 0.50).
- Documentación: ficha en `docs/modelos.md`, secciones nuevas en
  `docs/experimentos/cascada_jev.md` y `alerta_manipulacion.md`, recomendación
  vigente actualizada en `docs/resultados.md`; web y sitio con la familia Clef
  (color `--f-clef`, dumbbell y unidades de alerta).

## [0.14.0] - 2026-10-01 — gpt-6.1-sol con razonamiento `low` (JEV-47)

### Añadido
- **Opción `reasoning_effort` del adaptador `llm`** (`jevbench/adapters/llm.py`):
  `minimal`/`low`/`medium`/`high`, traducida a `reasoning={"effort": …}` en la API
  Responses y a `reasoning_effort=…` en Chat Completions. Solo para `provider=openai`
  (con Anthropic/Gemini falla al construirse, como los demás límites); cualquier otro
  valor da `ValueError`. Sin la opción no se envía ninguna clave de razonamiento, así
  que los runs anteriores no cambian. `meta()` guarda el valor aunque sea `None`.
- **Precio de `gpt-6.1-sol`** en `PRICES` ($2.00/$10.00 por Mtok; la página de precios
  de OpenAI no fue legible y el dato coincide en OpenRouter y fichas de terceros).
- **Run `llm_gpt61sol_low_prob`** (`results/llm_gpt61sol_low_prob/`): gpt-6.1-sol con
  `reasoning_effort=low`, modo `probabilities`, 195 casos (`all+new` + adv4/adv5),
  0 errores. Pre-registro y presupuesto ($3) en `docs/plan_gpt61sol.md` (ejecutado).
- Pruebas offline de la opción en `tests/test_llm_adapter.py`: las dos APIs reciben la
  clave correcta, sin la opción no aparece, valor inválido y proveedor no OpenAI → error,
  y `meta()["reasoning_effort"]`.

### Resultado (195 casos, coste medido $0.56, ~$0.0029/caso, mediana 3.4 s)
- **Ajustado 65: la mejor una pasada medida**, por encima de gpt-6-luna (61) y a la par
  de la cascada `jev_cascade_audit` (64); por debajo de la mejor config absoluta,
  `llm_gpt6luna_jevrev_audit` (71). Brier noul 0.054 (≈ luna, 0.053).
- Comparaciones pre-registradas: frente a luna solo es significativo `urgency` de adv4
  (6–0, p = 0.03); frente a `jev_v3`, `depth` de papers (13–1, p < 0.01); frente a
  `jev_cascade_audit`, nada significativo.
- Documentación: marcador (`docs/resultados_runs.txt` + `jevbench.report`), ficha en
  `docs/modelos.md`, bullet en «Por modelo», `RUNS` de `web.py` y `site.py` (familia
  LLM) y textos de portada (mejor una pasada, tabla de modelos, latencias). El
  circuito recomendado no cambia: sigue siendo Jev → revisor Jev.

### Revisión de la web y la documentación de sol
- **Alcance limitado por coste**, anotado en la portada (tarjeta de Jev, matiz del circuito,
  «Qué no se ha probado»), en `docs/modelos.md` y en `docs/resultados.md`: de gpt-6.1-sol solo
  hay una pasada en modo `probabilities`; faltan `discrete`, su papel como revisor, la cascada
  sol → revisor Jev y la alerta de manipulación.
- Portada: la tarjeta de Jev pasa a «mejor decisor **dedicado**» (dos LLM generalistas le
  superan en agregado); el matiz del circuito compara sol con Jev → revisor Jev (65 frente a
  64, ~34× el coste por mensaje); gpt-6.1-sol tiene su propio paso, fechado el 1-oct, en «Las
  pruebas, en orden», en vez de una frase añadida al paso de luna del 29-sep.
- `docs/modelos.md`: el bullet de sol estaba entre el «Probado» y el «Resultado» de luna, así
  que el «~5.5× más caro» de luna parecía de sol; reordenado y etiquetado.
- `docs/resultados.md`: el sentido de los McNemar (6–0 y 13–1, **a favor de sol**).

## [0.13.3] - 2026-10-01 — Revisión de la web de resultados

### Web y sitio
- La cabecera de la portada ya no fija «26–27 sep 2026»: muestra la versión del banco y su fecha,
  que `jevbench.web.version_date()` lee del CHANGELOG (marcador `__VERSION_DATE__`).
- Versión de Jev comprobada de nuevo (`check_versions --log`): sigue en jev-1.13 a 1-oct.
- Conclusiones al día con los runs de 29-sep a 1-oct: tarjeta de Nimble-9B (mejor abierto de una
  pasada, ajustado 44) y Tev1-4B; descartes ampliados con Tev1-0.8B y los Qwen3.8 locales;
  gpt-6-luna como revisor en la tarjeta y la nota de revisores.
- La alerta de manipulación pinta también las cascadas con LLM (`llm_gpt6luna_jevrev`, 25/30 y
  1 FP; `decider_4b_llmrev`, 20/30 y 2 FP), que ya se calculaban pero no se mostraban.
- «Las pruebas, en orden» incluye los seis bloques de 29-sep a 1-oct (línea base LLM, cascadas
  LLM, Span-01 y score ajustado, LLM locales, Nimble/Tev1, robustez del adaptador).
- Coste del circuito con las medias medidas (~$0.000035 + ~$0.00005 por caso), no la estimación
  antigua; tamaño de los sets «10 a 32 casos»; colores de Nimble/Tev1 en el tema oscuro forzado.
- `tests/test_site.py` comprueba que la cabecera lleva versión + fecha y ningún «sep 2026» fijo.

### Publicación del espejo (arreglo)
- **Fallo:** el tag público `v0.13.2` (commit `2d525b0` del espejo) añadió los ficheros nuevos,
  pero dejó README, CHANGELOG y `jevbench/__init__.py` en 0.5.0. Causa: `jevbench.publish`
  exportaba el snapshot al clon y **después** `publish()` hacía `git reset --hard origin/main`,
  que devolvía a su versión anterior todo fichero ya existente (y recuperaba los que tenían que
  borrarse); solo sobrevivían los nuevos. La simulación sin `--push` tenía el mismo defecto y
  daba un falso «todo bien».
- **Arreglo:** `prepare_clone()` (antes `clone_or_fetch`) deja el clon en `origin/main`, o en una
  rama huérfana si el espejo está vacío, y vacía el árbol **antes** del export; `publish()` ya no
  hace reset ni checkout. `export()` devuelve el id de blob de git de cada fichero y
  `verify_commit()` exige que el commit contenga exactamente ese snapshot (mismos ficheros y
  mismos bytes) antes de crear el tag o subir nada, también en la simulación.
- **Regresión:** `tests/test_publish.py::PublishGit` usa un remoto local que parte de un README
  en 0.5.0 y de un fichero fuera del manifiesto: el commit debe llevar la versión nueva, el
  fichero añadido y la eliminación; si se restaura contenido viejo tras el export, falla sin
  etiquetar. Cubre también el espejo vacío.
- El tag público `v0.13.2` no se reescribe (las versiones publicadas son inmutables): la
  corrección se publica como `v0.13.3`.

## [0.13.2] - 2026-10-01 — Cierre y alineación de la documentación

### Documentación
- Alineados README, guía de agentes, infraestructura y fichas con los adaptadores y modelos
  presentes en el código: Nimble-9B y Tev1 ya aparecen en los inventarios y en la tabla pública.
- Marcados como ejecutados los planes del revisor local y de robustez LLM; eliminadas referencias
  pendientes ya resueltas en los planes e informes históricos, y aclarado el carácter histórico
  del run Flash anterior a los límites.
- Corregida la descripción de Nimble: usa un forward por campo, no una sola pasada por estado.
- Actualizadas y regeneradas la web interactiva y el sitio público.

## [0.13.1] - 2026-10-01 — Nota pública sobre la robustez del adaptador `llm`

### Documentación
- Añadida en la ficha, el informe, el artifact y el sitio público una explicación del
  problema encontrado y de su corrección: el timeout no cubría todo el caso, faltaba un
  tope de salida y la telemetría se descartaba. Desde 0.13.0 hay presupuesto total,
  `max_tokens`, diagnóstico persistido y redacción de secretos. La nota aclara que no
  cambiaron el prompt, las preguntas, el GT, el scorer ni los resultados históricos.

## [0.13.0] - 2026-10-01 — Robustez del adaptador `llm` (JEV-44)

### Añadido
- **Límites del adaptador `llm`** (`jevbench/adapters/llm.py`): `case_timeout`
  (presupuesto de pared por caso que incluye las correcciones por JSON mal formado;
  cada petición usa `min(timeout, restante)` y falla antes de abrir otra petición si la
  bolsa está agotada), `max_tokens` (traducido a `max_output_tokens` en Responses,
  `max_completion_tokens` en Chat Completions oficial y `max_tokens` en endpoints
  compatibles) y `timeout` ahora efectivo también con OpenAI directo — antes se ignoraba
  si no había `base_url`/`extra_body`. `extra_body` fuera de Chat Completions y los
  límites con provider=anthropic/gemini fallan con error explícito en vez de ignorarse.
  Los miembros privados de `system-one-adapter==0.2.1` se concentran en
  `_openai_internals()` con test de compatibilidad.
- **Telemetría persistida:** `jevbench.run` guarda `usage` compacto (tokens, reintentos,
  `attempts`, latencia) en los casos exitosos y `ms` + `diag` seguro (intentos, tipo de
  error, categorías de reintento) en los errores. Nunca prompts, estados ni cuerpos HTTP.
- **Redacción de secretos:** las opciones `--opt` cuyo nombre contiene `api_key`,
  `token`, `secret` o `password` se guardan como `<redacted>` en `meta.opts`; el
  adaptador sigue recibiendo el valor real. La redacción también recorre JSON anidado
  en `extra_body` (incluidos `Authorization`, credenciales y cookies) antes de guardar
  o imprimir el `meta`.
- **Validación de límites:** `timeout`, `case_timeout` y `max_tokens` rechazan cero y
  valores negativos; el parche de API privada comprueba además la versión exacta 0.2.1.
- **Pruebas offline** (`tests/test_llm_adapter.py`, `tests/test_run.py`): transporte
  OpenAI contra servidor HTTP local de vida corta (esquema, `extra_body`,
  `structured=false`, `max_tokens` en las tres APIs, 429/500, conexión cerrada,
  respuesta truncada, timeout), reintentos por JSON mal formado, presupuesto por caso
  con reloj inyectado, telemetría del runner y secretos centinela, también dentro de
  `extra_body`. 18 tests en el venv y 5 del runner con el Python del sistema.
- **Entorno `.venv-llm` reconstruido** con uv + Python 3.12 gestionado (el anterior
  quedó roto tras actualizar el sistema a 3.14): `system-one-adapter[openai]==0.2.1`,
  `typesafe-sdk==0.7.1`, `openai==3.16.2`, `httpx2==2.13.0`, `httpcore2==2.13.0`. El
  roto se conserva apartado como `.venv-llm.broken-20261001` (no versionado).
- **`scripts/smoke_llm.py`**: smoke diagnóstico de 6 casos fijados × N repeticiones
  contra un endpoint compatible (control OOD, adv2/adv3/triage_ext/triage_es), con
  registro de ms, tokens, intentos y memoria. Salida en `results/logs/`, no es un run.

### Smoke DGX .81
- 18 ejecuciones (6 casos × 3 reps) contra `qwen3.8-flash-next` (mismo endpoint del
  run `llm_qwen38flash_prob`, contenedor `vllm-fn-tp1`) con `timeout=1800`,
  `case_timeout=600`, `max_tokens=16384`: todas ok, 1 petición cada una, 16–170 s,
  sin errores de transporte (`results/logs/smoke_llm_jev44.json`).
- Comprobación dirigida: `case_timeout=45` aborta el caso a los 45.0 s exactos sin
  dejar petición viva y el caso normal posterior responde en 30.9 s; un intento con
  generación desbocada terminó en `finish_reason=length` al llegar al tope de
  salida, error acotado que demuestra que `max_tokens` llega al servidor.

## [0.12.0] - 2026-09-30 — Nimble-9B y Tev1 (4B y 0.8B), JEV-41/42/43

### Añadido
- **Adaptador `nimble`** (`jevbench/adapters/nimble.py`) sobre el `ParallelScorer`
  oficial que embarca el repo HF de Bespoke-Nimble-9B (verifica los SHA256 del
  prompt de entrenamiento y del codebook antes de correr). Mapea `noul`→boolean,
  `choice`→enum con `choice_descriptions` y `score`→enum de enteros
  (`score` = `expected_score`). Una pasada forward por pregunta: cada prompt lleva
  el estado + el esquema completo; no hay pasada única multi-pregunta.
- **Run `nimble_9b`** (195 casos, 0 errores, DGX .81): `bespokelabs/Bespoke-Nimble-9B`
  rev `bd792f44` (LoRA PEFT sobre `Qwen/Qwen3.5-9B@c2022362`), T=1.0 del checkpoint
  actual, torch 2.14.1+cu130, transformers 5.17, peft 0.21. Ajustado **44**, entre
  Jev (45) y Decider-4B (33): triaje 92.9/88.6, papers 70.3 (ρ 0.48), adv3 85.5,
  adv4 79.0, adv5 81.5, ood 100 %, Brier noul 0.084, mediana 1.6 s/estado. Sin
  diferencias significativas frente a jev_v3 / decider_4b / gpt-6-luna salvo
  `urgency` de adv4, donde supera a gpt-6-luna (9–0, p<0.01). Es el open-weight
  puro más fuerte de los evaluados sin revisor; hace una pasada forward por pregunta.
- **Adaptador `tev1`** (`jevbench/adapters/tev1.py`) para los Tev1 de Together:
  system prompt y JSON `{state, question, options}` oficiales, y en lugar de
  generar la letra hace softmax sobre los logits de las letras candidatas en el
  primer token (equivale al argmax restringido del contrato: temperature=0 +
  regex, `enable_thinking=false`). Una inferencia por pregunta; cada caso guarda
  `raw.generations`.
- **Run `tev1_4b`** (195 casos, 0 errores, DGX .81):
  `togethercomputer/Tev1-4B-experimental` rev `0b7becf0` (Qwen3.5-4B, bf16).
  Ajustado **27**, por debajo de Nimble-9B (44), Jev (45) y Decider-4B (33):
  triaje 87.1/87.1, papers 64.4 (ρ 0.83), adv3 75.0, adv4 77.5, adv5 72.5,
  ood 100 %, Brier noul 0.115, mediana 0.45 s/estado. Sin diferencias
  significativas frente a los incumbentes salvo `depth` de papers32, donde
  gpt-6-luna le gana (16–2, p<0.01). Licencia de los pesos pendiente de
  publicación según la propia ficha.
- **Run `tev1_0.8b`** (195 casos, 0 errores, DGX .81):
  `togethercomputer/Tev1-0.8B-experimental` rev `6bb2dff1` (Qwen3.5-0.8B,
  bf16), mismo adaptador sin cambios. **Resultado negativo:** ajustado −7,
  bajo la mayoría trivial (triaje 67.9/72.1, adv total 58.5 vs 79.0 del
  baseline, adv3 64.0, Brier 0.171, 12 binarios en 0.45–0.55 en adv3). El 4B
  le gana en `same_day` de adv4 (10–1, p=0.01) y los incumbentes en varias
  preguntas (department adv3/ext_es, clinical triaje ES). Mediana
  0.14 s/estado. Licencia de los pesos también pendiente.

## [0.11.0] - 2026-09-30 — LLM local Qwen3.8-Flash-Next (negativo), JEV-39

### Añadido
- **Run `llm_qwen38flash_prob`**: Qwen3.8-Flash-Next NVFP4 servido con vLLM en el DGX .81,
  mediante `system-one-adapter` con thinking activado (sin él fallaba el smoke). Resultado
  negativo y peor que el 27B: ajustado −40, triaje 65.7/55.0, papers 38.1 (ρ −0.01), adv3
  65.3 y Brier 0.317. Jev y gpt-6-luna son significativamente mejores en múltiples preguntas;
  el Flash no obtiene ninguna ventaja significativa. Tras reintentar entrega 191/195 respuestas
  (4 timeouts), con mediana 49.7 s/caso y ~14.7 h de pared entre ambas pasadas.
- Documentado un límite operativo del adaptador: `timeout` se aplica por petición y los
  reintentos internos pueden alargar un caso; este run no fijó un máximo total ni de tokens.

## [0.10.0] - 2026-09-29 — score ajustado y alerta de manipulación con Span-01, JEV-40

### Añadido
- **Score ajustado** (`jevbench.score.adjusted`, columna en `--summary` y en la
  tabla de la web): media por fase de (acierto − línea base de mayoría) /
  (100 − línea base). 0 = responder siempre lo más frecuente, <0 = peor que el
  trivial; `ood` queda excluida (mayoría = 100 %) y `*` marca cobertura
  incompleta de las 11 fases. Jev→Jev 64, gpt-6-luna→Jev 71, Jev solo 45,
  gpt-6-luna solo 61, Decider-4B 33, Span-01 pro 18.
- **Alerta de manipulación con Span-01 (negativo):** como detector de una sola
  pasada (misma pregunta `manipulation` y umbral 0.5 del revisor), pro detecta
  8/30 y lite 5/30 en adv3–5 con 0 falsos positivos — muy por debajo del
  criterio (≥7/10 por set) y del revisor Jev (25/30). Runs
  `span01_pro_alert_raw` / `span01_lite_alert_raw`; documentado en
  `docs/experimentos/alerta_manipulacion.md`.

### Corregido
- Coste de Span-01 pro: era "~10× más barato que Jev"; medido: $0.0032 los 195
  casos ($0.000016/caso), ~2× menos que Jev ($0.000035) y ~12× menos que
  gpt-6-luna ($0.000194).
- Web: matiz sobre el LLM generalista — gpt-6-luna supera a Jev en agregado
  (61 vs 45) y gpt-6-luna→revisor Jev es la mejor configuración medida (71), a
  ~5× coste/latencia por mensaje.

## [0.9.0] - 2026-09-29 — Span-01 y Span-01 Lite (Respan), JEV-40

### Añadido
- **Adaptador `respan`** (`jevbench/adapters/respan.py`) para Span-01 de Respan,
  clasificador de comportamientos hiper-paralelo (anunciado 24-sep-2026). Dos
  caminos: API nativa `api.respan.ai/api/v1/scores` (`provider=respan`, clave
  `RESPAN_API_KEY`; `span-01-pro` requiere créditos Respan, `span-01-free` es
  Lite gratis) y OpenRouter `/api/alpha/decisions` (`provider=openrouter`, donde
  Respan solo admite `noul`, así que `choice`/`score` se expanden a una noul por
  opción). Mapeo: `noul` → una definición; `choice`/`score` → una por opción;
  en nativo p = present/(present+absent) (`not_observable` = evidencia neutra).
- **Runs `span01_pro`** (OpenRouter, resuelto `span-01-20260925`, $0.003 los 185
  casos), **`span01_lite`** (API nativa `span-01-free`, gratis) y
  **`span01_lite_or`** (Lite vía OpenRouter, `span-01-lite-20260925`), todos con
  all+new + adv4 + adv5 y 0 errores. Competitivo pero por debajo de Jev en
  conjunto: triaje 85.0/84.3, adv3 72.0 (pro) vs 88.6/90.0 y 87.5 de Jev; Jev le
  gana con significación en `same_day` de triaje ext (p<0.05) y en urgency de
  adv3. Span-01 sí supera a Jev en `depth` de papers32 (17/32 vs 6/32, p=0.01).
  Coste medido: $0.000016/caso (~2× menos que Jev, ~12× menos que
  gpt-6-luna). Lite y pro dan prácticamente lo mismo por OpenRouter.

## [0.8.0] - 2026-09-29 — LLM local en DGX: Qwen3.8-27B (negativo), JEV-39

### Añadido
- **Adaptador `llm`: opciones `extra_body`, `api_key` y `timeout`** para endpoints
  OpenAI-compatibles (SGLang/vLLM en los Sparks): `chat_template_kwargs` (thinking on/off),
  muestreo recomendado por la ficha y timeout largo para modelos con thinking.
- **Run `llm_qwen38_27b_prob`** (`RadixArk/Qwen3.8-27B-NVFP4-BF16-LMHead` en SGLang, .80):
  195 casos, 2 errores por timeout. **Resultado negativo**: apenas por encima de la línea
  base trivial (triaje 73.6, papers 52.2, ρ −0.17, adv total 58.5 < 79.0 del baseline,
  Brier 0.231, ~6.8 s/caso). Thinking `low` no mejora y encarece la latencia. Un LLM
  grande no basta si no sigue el contrato System One.
- En marcha en .81: `llm_qwen38flash_prob` (Qwen3.8-Flash-Next NVFP4 en vLLM, thinking on).

## [0.7.0] - 2026-09-29 — cascadas LLM: revisor LLM y LLM → revisor Jev

### Añadido
- **Cascada `llm_gpt6luna_jevrev_*`** (LLM → revisor Jev, JEV-38): mejor configuración medida —
  adv total 92.0, adv5 88.5, Brier noul 0.045, alerta 9/10 con 1 FP. Estadísticamente
  equivalente a `jev_cascade_audit` a ~4× el coste y la latencia.
- **Cascada `decider_4b_llmrev_*`** (revisor LLM sobre Decider-4B): recupera el 77 % de la
  ganancia de Jev en adv3+adv5 (primer revisor no-Jev que pasa del 50 % ahí), pero no cumple
  JEV-32 por triaje (28 %) ni por la alerta de manipulación (6/10). Detalle:
  `docs/experimentos/cascada_jev.md`.

## [0.6.0] - 2026-09-29 — línea base LLM (system-one-adapter + gpt-6-luna)

### Añadido
- **Adaptador `llm`** (`jevbench/adapters/llm.py`) sobre `system-one-adapter` 0.2.1 de TypeSafe
  (sustituto de `system_one` con un LLM: OpenAI, Anthropic, Gemini o endpoint compatible con
  OpenAI). Opciones `mode=probabilities|discrete`, `structured`, `base_url`, `usd_in`/`usd_out`.
  Venv local `.venv-llm` con versiones fijadas (≥ 7 días). Test offline con proveedor falso:
  `tests/test_llm_adapter.py` (se salta si la librería no está instalada). JEV-38.
- **Runs `llm_gpt6luna_prob` y `llm_gpt6luna_disc`**: gpt-6-luna por API directa de OpenAI,
  fases `all+new`, `adv4` y `adv5` (195 casos, 0 errores). En una pasada queda al nivel de la
  cascada de Jev: triaje 93.6/95.7, papers 78.8, adv 18/20, adv3 17/20, adv5 83.5, Brier noul
  0.053. Frente a `jev_v3`, solo `depth` de papers es significativo (p < 0.01, a favor del LLM);
  frente a `jev_cascade_audit`, solo `urgency` de adv4 (p = 0.01, a favor de la cascada). Coste
  $0.00019/caso (5.5× Jev) y mediana 3.1 s (5× Jev). `discrete` calibra peor (Brier 0.077).
- Familia `LLM` en el marcador, la web y el sitio (color `--f-llm`); `OPENAI_API_KEY` en
  `.env.example`.

## [0.5.0] - 2026-09-27 — versionado, licencias y espejo público

### Añadido
- **Versión semántica única** (`jevbench.__version__`), comprobada por `tests/test_version.py`
  contra este CHANGELOG y el README. Tags anotados `v0.1.0`–`v0.4.0` sobre los commits
  retroactivos y `v0.5.0` sobre el commit de esta entrada.
- **Licencias**: MIT para el código (`LICENSE`) y CC BY 4.0 para casos, GT y resultados
  (`LICENSE-DATA`).
- **`jevbench.publish`**: exporta a mano, por versión, un snapshot saneado al espejo público
  (`Mindbreaker81/system-one-bench-public`): lista blanca de ficheros, `meta.host` genérico,
  abstracts de PubMed sustituidos por su hash, nombres propios neutralizados y un escáner
  bloqueante de cadenas sensibles. `tests/test_publish.py` lo cubre.
- **`jevbench.fetch_abstracts`**: reconstruye los abstracts de `data/papers32.json` desde
  PubMed (necesarios para ejecutar `papers32`, no para puntuar) y avisa si el hash difiere.
- **Procedimiento `publicar-version`** (`docs/procedimientos/`, `.claude/skills/`): cuándo
  sube cada nivel de versión y cómo se publica el espejo.
- Enlaces a GitHub y etiqueta de versión en la web (`docs/site_src/_nav.html`,
  `docs/web/template.html`).

### Cambiado
- `paper_state` (`jevbench/battery.py`) tolera papers sin abstract (marcador
  `[abstract no descargado]`); `jevbench.run` aborta en `papers32` si falta alguno.
- `jevbench.site` ya no borra la línea de YouTrack del resumen: el pie del template habla del
  repo público, no del seguimiento interno.
- `data/adversarial2_cases.json` (y `.anot2`): el email inventado del caso B02 pasa de
  `@gmail.com` a `@example.com` — dominio reservado, no un buzón real. El GT no cambia y las
  puntuaciones guardadas siguen siendo las medidas (registrado en `data/GT_CHANGELOG.md`);
  la copia de `legacy/` se mantiene de solo lectura y se enmascara al exportar.

## [0.4.0] - 2026-09-27 — procedimientos, sitio público y documentación

Tag: `v0.4.0` → `0093c8c`. (Sección "27-sep-2026 (tarde)" del changelog anterior.)

### Añadido
- **Procedimientos y skills** para las tareas que se repiten: evaluar un modelo nuevo, evaluar una
  versión nueva de Jev y crear un set de casos (`docs/procedimientos/`, `.claude/skills/`) (`98eebd4`).
  Un test (`tests/test_procedimientos.py`) comprueba que cada comando, flag y ruta citados existe.
- **Sitio público para Netlify** (`jevbench.site`, `docs/site_src/`, `netlify.toml`):
  - resumen;
  - explorador caso a caso;
  - acierto por pregunta, matrices de confusión y calibración;
  - comparador A/B con McNemar;
  - qué cambia el revisor;
  - coste y latencia;
  - metodología.

  El saneado está cubierto por tests (sin abstracts, emails, hostnames ni YouTrack; emails y enlaces
  de los casos inventados, ocultos) (`3986bfb`).
- **README** con guía de reproducción en tres niveles y aviso sobre el ground truth, también en la
  web (`b485a52`).
- **Web resumen** interactiva (`jevbench.web`): conclusiones, marcador, revisor, seguridad, cómo leer
  los números, las pruebas en orden y la tabla de modelos con enlaces (`5e44f6a`, `0361ac2`).

### Cambiado
- `docs/bateria.md` reescrito al estado actual; `docs/plan.md` marcado como histórico.
- `.gitignore`: se ignoran `node_modules/`, `package*.json` de netlify-cli, `.netlify/` y la config
  local de agentes, salvo `.claude/skills/` (`3267111`, `7d531be`).

### Corregido
- `node_modules` se coló en un commit con `git add -A`; se retiró del historial reescribiéndolo. Desde
  entonces, los ficheros se añaden uno a uno.

## [0.3.0] - 2026-09-27 — revisores abiertos, alerta y versiones

Tag: `v0.3.0` → `4b1aece`. (Sección "27-sep-2026 (mañana)" del changelog anterior.)

- **Revisor 100 % local (JEV-32), resultado negativo.** Ningún revisor abierto (Decider-35B NVFP4,
  AnyJev-32B, AnyJev-8B) alcanza el 50 % de la ganancia que da Jev como revisor. Ejecutado por otro
  agente a partir de `docs/plan_revisor_local.md` (`4b1aece`, `25cbf62`).
- **Alerta de manipulación validada** en adversarial-5, un set nuevo con pre-registro: 9/10
  detectados y 1 FP. Acumulado adv3–5: 25/30 y 1/30 (`33f2df5`, `25cbf62`).
- **`check_versions`:** OpenRouter y TypeSafe siguen sirviendo jev-1.13; `jev-preview` también. Registro
  en `docs/versiones_jev.md` (`33f2df5`).

## [0.2.0] - 2026-09-27 — GT v3, modelos grandes, reglas y cascadas

Tag: `v0.2.0` → `173fdb3`. (Sección "27-sep-2026 (madrugada)" del changelog anterior.)

- **Reglas duras regex descartadas.** Con el set nuevo adversarial-4 y las reglas congeladas por hash:
  0/10 ataques detectados y 3/10 falsos positivos, uno de ellos una fiebre tras la EBUS (`2783475`,
  `173fdb3`). Primera versión en `9805256`.
- **Decider-35B NVFP4** servido con vLLM en la GB10: igual que bf16 y 3.5× más rápido. Script de
  arranque y notas sobre memoria unificada, OOM y `ninja` (`c553757`).
- **Laya en GPU** con el harness: reproduce el rerun de Lyra; la variante typed-decisions no mejora
  (`c68dd2e`).
- **`jevbench.report`** regenera el marcador de `docs/resultados.md`, con `--check` para CI (`f8e4191`).
- **Cascada con cualquier revisor.** Decider→Decider apenas mejora; Decider-4B→Jev iguala a Jev→Jev
  (`8bd3259`).
- **GT v3:** adjudicación de la segunda anotación con el usuario (9 cambios), con versiones v1 y v2
  conservadas. Decider-35B bf16 (sin CUDA graphs) y AnyJev-8B/32B completos (`d6cf667`).
- **Segunda anotación (JEV-27):** concordancia separada por procedencia (78 respuestas humanas),
  variante de GT `anot2` y análisis de sensibilidad: el orden entre modelos no cambia (`e1ba32a`,
  `0a2256f`).

## [0.1.0] - 2026-09-26 — harness, modelos abiertos y casos nuevos

Tag: `v0.1.0` → `d8ad35a`. (Sección "26-sep-2026" del changelog anterior.)

- **Segunda anotación:** paquete a ciegas y scorer de concordancia (`8c9eadd`); corregido el kappa en
  preguntas nominales (`d8ad35a`).
- **YouTrack** documentado en `AGENTS.md` (`47e6ca2`).
- **Casos nuevos validados por el usuario:** triaje ampliado (26 × ES/EN) y adversarial-3 (20,
  equilibrado), ejecutados en todos los modelos. La cascada se confirma en casos nuevos (`c3950b9`,
  `735df3b`, `781ba5a`).
- **Julia-1** (SupersonicLabs): por debajo de la mayoría por su sensibilidad a la redacción (`e188211`).
- **Jev por la API directa de TypeSafe:** equivalente a OpenRouter (406/409). **GT P04 corregido**,
  con versionado. **Experimento de cascada Jev→Jev** pre-registrado: mejora los cuatro bloques
  (`d0ca552`).
- **Modelos abiertos en los DGX Spark:** Decider 0.8B/2B/4B, GLiNER2.5 (Decide, 1B y multi; con y sin
  descripciones), AnyJev 1.7B en GPU. Scripts de venv y colas (`c8ba4dd`).
- **Harness `jevbench`:**
  - batería única en formato TypeSafe y adaptadores por modelo;
  - scorer con línea base de la mayoría, IC bootstrap, Brier/ECE y McNemar;
  - tests que reproducen los informes de Lyra;
  - Jev v3 (`aaa733f`).

  Resumen por modelo y correcciones de McNemar en `1cf03ce`, `a67e9fa` y `ff8b364`.
- **Inicio:** `AGENTS.md`, documentación e importación de la batería de Lyra en `legacy/` (`9311bf8`).

## Antecedentes (20–25 sep 2026, antes de este repo)

Pruebas hechas por el agente Lyra (Hermes) con scripts sueltos, importadas en `legacy/`:
- Jev frente a Laya: triaje, papers y adversarial-1.
- Rerun, revisor-auditor de Jev, vote-of-3 y gate Jev↔Laya; adversarial-2.
- GLiNER2.5-Decide.
- AnyJev con Qwen3-1.7B en CPU.
