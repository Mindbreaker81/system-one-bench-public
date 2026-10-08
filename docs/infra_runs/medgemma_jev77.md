# JEV-77 — MedGemma-27B frente a Gemma 3-27B-IT, Qwen3.8-27B FP8 y cascada híbrida

**Estado: BORRADOR de pre-registro (7-oct-2026), R31–R34 + host <host>.**
No congelado. Sin inferencia de evaluación, descarga (salvo A2), smoke ni
puerta de batería. Issue: <<tracker>
Fuentes: R30–R34, comentarios YouTrack (acceso + decisiones 7-oct). Formato:
`qwen38_jev67.md` / `qwen38_jev68.md`. Procedimiento:
`docs/procedimientos/evaluar-modelo-nuevo.md`.

**Dos aprobaciones explícitas** (§9). Sin A2 no hay preparación/smoke; sin A5 no
hay puertas/batería. Condicionadas de antemano solo si constan expresamente.

Este fichero es **autónomo**: no remite a «como en R31» ni a secciones de
informes externos como norma operativa.

---

## 1. Resumen

¿MedGemma 1 27B (multimodal, texto solo) rinde ≥ +5 de ajustado frente a
Gemma 3-27B-IT en discrete d0, y no es inferior (margen −5) a Qwen3.8-27B-FP8
discrete d0 fresco (`enable_thinking=false`) bajo la **rama de stack** elegida
en A3–A4 y aprobada en A5 (§4.3)?

Alcance completo desde el principio: d0+d1 M/G/Q, bloque 4B, cascada híbrida
M-D0→Jev audit. Primarios confirmatorios = solo H1/H2 en **d0** (§6); d1/4B/
cascada = descriptivos pre-registrados.

**Host fijado (7-oct):** todo JEV-77 en **<host> `dgx-spark-a`** (§1.1). JEV-76 corre
en paralelo en <host>. Coste: GPU <host> (un modelo a la vez) + API Jev en la cascada
desde <host>. Sin tocar GT, scorer, `battery.py` ni runs históricos.

### 1.1 Host, pesos y convivencia en <host>

| Elemento | Valor |
|---|---|
| Host de **todas** las celdas (27B, 4B, Q-D0′/Q-D1′) | **`<host>` / `dgx-spark-a`** (`user@<host-lan>`) |
| Paralelo | **JEV-76 en <host>** a la vez; no compartir GPU ni confundir sesiones |
| Cascada API Jev | Cliente en **`<host>`** (propuesta adoptada; no el portátil): mismas claves por env, meta.host=<host> |
| ai-models | Montaje **ro** en `<ruta-local>` de <host> |
| Qwen FP8 | Ya en `<ruta-local>` |
| MedGemma / Gemma 3 (27B y 4B) | Descargados en <host> (`<ruta-local>`) el 7-oct con aprobación del usuario (A2), hashes LFS verificados contra HF; copia a ai-models `hf/google/<repo>` |
| Imagen `lmsysorg/sglang:qwen38-27b` en <host> | ID local `sha256:0076dffa60b7…` / digest `lmsysorg/sglang@sha256:febfb971…56b1` (**idéntica** a la de <host>): **candidata a rama A** si en A3 sirve también Gemma 3 BF16; si no, rama B o otra imagen GB10 (§3.1) |

**Antes de cada arranque en <host>** (obligatorio): `nvidia-smi; docker ps; free -g`.
En <host> hay proyectos **SGLang/ComfyUI** (y otros) del usuario: **no** parar,
reconfigurar ni tocar contenedores/servicios ajenos. Si la GPU o el puerto están
ocupados → posponer; no desalojar.

## 2. Modelos y revisiones (API pública HF, 7-oct-2026)

Congelar hashes de shards locales tras verificar acceso a **todos** los shards
(HEAD de `config.json` ≠ acceso completo).

| Papel | Checkpoint | SHA | Arquitectura | Notas |
|---|---|---|---|---|
| Candidato 27B | `google/medgemma-27b-it` | `2d3e00ea38b50018bf5dd3aa1009457cd2d5a48f` | `Gemma3ForConditionalGeneration` | Texto solo; HAI-DEF; acceso 200 |
| Control 27B | `google/gemma-3-27b-it` | `005ad3404e59d6023443cb575daa05336842228a` | `Gemma3ForConditionalGeneration` | Gemma license; acceso 200 |
| Qwen FP8 (H2) | `Qwen/Qwen3.8-27B-FP8` | `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` | Qwen3.8 | `<ruta-local>` en <host> |
| Candidato 4B | `google/medgemma-1.5-4b-it` | `91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b` | `Gemma3ForConditionalGeneration` | MedGemma 1.5 = solo 4B |
| Control 4B | `google/gemma-3-4b-it` | `093f9f388b31de276ce2de164bdc2081324b9767` | `Gemma3ForConditionalGeneration` | Incluido |
| Variante text-only | `google/medgemma-27b-text-it` | `5b667cf2ddcf064085bc90952edb35a0edbfb79c` | `Gemma3ForCausalLM` | **Fuera** (403); no alternar |

### 2.1 Decisiones de modelo

1. Candidato primario = `medgemma-27b-it`, multimodal, **solo texto**.
2. text-it no es primario ni se alterna.
3. MedGemma 1.5 = solo el 4B; el 27B es MedGemma 1.
4. MedGemma↔Gemma3-IT = paquete de adaptación (PT común `gemma-3-27b-pt` **no
   está instruction-tuned** → no es control).
5. Q-D0′/Q-D1′ = FP8 JEV-68, `enable_thinking=false` explícito.
6. Descarga o copia a ai-models de Gemma/MedGemma solo tras A2 (aún no están en
   `<ruta-local>` de <host>); Qwen FP8 ya está.

### 2.2 Memoria (estimación; no prueba de kernels)

| Checkpoint | Lectura |
|---|---|
| medgemma-27b-it | Subtotal BF16 54,86 GB; total publicado 28 842 036 848 → **57,68 GB / 53,72 GiB** si todo BF16; discrepancia pendiente en shards |
| gemma-3-27b-it | 54,86 GB BF16 |
| Qwen3.8-27B-FP8 | ~29 GB disco (histórico); perfil FP8 |
| 4B IT | ≈ 8,60 GB BF16 c/u |

Un checkpoint a la vez. Texto solo no garantiza omitir encoder visual:
documentar residentes. Si BF16 27B no cabe → **NO EJECUTABLE** bajo ese perfil
(nuevo perfil simétrico M/G = pre-registro nuevo).

## 3. Motor (aarch64 / GB10) — pendiente de verificación

### 3.1 Preferencia SGLang

| Elemento | Propuesta | Estado |
|---|---|---|
| Arquitecturas | Gemma3 MM (M/G/4B); Qwen3.8 FP8 | Publicado ≠ imagen concreta |
| Grammar | `--grammar-backend xgrammar` | Congelar log |
| Imagen en <host> (candidata rama A) | `lmsysorg/sglang:qwen38-27b` ID `0076dffa60b7` (= <host>) | **Verificar en A3** si carga Gemma 3 BF16 + Qwen FP8 + xgrammar + `usage` |
| Otras imágenes GB10 | `scitrera/dgx-spark-sglang:0.5.8-t4|t5` o `xomoxcc/dgx-spark-sglang:*-sm121` | Si `qwen38-27b` no sirve Gemma → probar aquí o rama B |
| Imagen Qwen-only (rama B) | Misma `lmsysorg/sglang:qwen38-27b` solo para Q; M/G en otra | Solo si rama B (§4.3) |
| `mem-fraction-static` | **A calcular** (pesos+KV; ≠ util. vLLM) | A4 |
| Contexto / KV / attention / caché / concurrencia=1 | Congelar en A4 | Pendiente |
| Structured + inject | Obligatorios | Gramática ≠ inyección |

### 3.2 Alternativa vLLM

`gpu_memory_utilization ≤ 0.45`, `MAX_JOBS=2` en GB10. Mismos requisitos de
rama §4.3. Motor elegido por **viabilidad** en A3, nunca por aciertos.

### 3.3 Plantilla

- M/G/4B: system antepuesto al primer user; sha12 offline R30 `7de1c58e208e`;
  sin duplicar a mano.
- Qwen: plantilla nativa del checkpoint FP8.
- «Misma plantilla» solo dentro de familia Gemma.

### 3.4 Thinking

| Familia | Regla |
|---|---|
| Gemma (27B y 4B) | Sin modo thinking configurable; capturar si emerge |
| Qwen | `enable_thinking=false` **explícito**; puerta y vigilancia = declaración + evidencia thinking off |

## 4. Configuración de cliente

### 4.1 Familia Gemma (M/G 27B y 4B; d0 y d1)

```
adapter=llm · provider=openai · api_key=none
structured=true · inject_schema_in_prompt=true · normalize=true
capture_raw=true · retries_malformed=2
max_tokens=<T_OUT>   # provisional 8192; acreditar prompt_máx+salida+correcciones
timeout=300 · case_timeout=600 · secuencial · concurrencia 1
extra_body={"temperature":0,"seed":101}
prompt=typesafe · choice_order=department:d0|d1
dtype = BF16
fases (§8.4): triage_es, triage_en, papers32, adv1, adv2, ood,
              triage_ext_es, triage_ext_en, adv3, adv4, adv5
batería GT v4 · 194 casos
```

Host **<host> `dgx-spark-a`** (§1.1). Identidad a congelar: `system-one-adapter`,
`typesafe-sdk`, harness/commit, comandos, dry-run.

### 4.2 Qwen FP8 — Q-D0′ y Q-D1′

| Campo | Valor |
|---|---|
| Checkpoint | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` |
| Pesos | `<ruta-local>` (<host>, ro) |
| Runs | `llm_qwen38_27b_fp8_jev77_d0_disc` (**Q-D0′**), `…_d1_disc` (**Q-D1′**) |
| Modo | discrete; `choice_order=department:d0` / `d1` |
| Thinking | `extra_body={"chat_template_kwargs":{"enable_thinking":false},"temperature":0,"seed":101}` |
| Tokenizer / template | Nativos Qwen |
| Gramática / límites / inject | Mismo contrato TypeSafe; precision=FP8 |
| Nombre servido / cmdline | Congelar en A4 desde `/v1/models` y log |
| Stack | Según **rama** §4.3 |

H2 = no inferioridad frente a **Q-D0′ fresco**. T1 histórico (64,92) y D0
histórico (62,42) son solo descriptivos.

### 4.3 Ramas de stack (elegir en A3–A4; aprobar en A5)

| Rama | Definición | Lectura de H2 |
|---|---|---|
| **A (preferida)** | Un solo build/imagen sirve M/G BF16 **y** Qwen FP8 | Comparación de configuraciones en **stack común** |
| **B (fallback)** | M/G en build BF16; Qwen en stack propio (p. ej. imagen Qwen-only) | H2 = comparación **entre stacks**; etiquetar explícitamente; **H1** sigue exigiendo M y G en el **mismo** build BF16 |

Reglas:

- La rama se fija en el congelado A4 y se aprueba en A5; **prohibido** cambiarla
  tras ver resultados.
- Si la rama A no es viable y B no está autorizada en A5 → Q (y H2)
  **NO EJECUTABLE**; M/G pueden seguir si H1 es viable.
- No presentar B como si fuera la misma comparación controlada que A.

## 5. Lista final de celdas

Temp 0, seed 101, structured + inject. Un modelo cargado a la vez.

### 5.1 Bloque 27B (10 celdas)

| Celda | Run | Checkpoint | Modo | Orden | Papel |
|---|---|---|---|---|---|
| **M-D0** | `llm_medgemma_27b_it_bf16_jev77_d0_disc` | medgemma-27b-it | disc | d0 | H1; entrada cascada |
| **M-P0** | `…_d0_prob` | medgemma-27b-it | prob | d0 | descriptivo |
| **M-D1** | `…_d1_disc` | medgemma-27b-it | disc | d1 | descriptivo robustez |
| **M-P1** | `…_d1_prob` | medgemma-27b-it | prob | d1 | descriptivo |
| **G-D0** | `llm_gemma3_27b_it_bf16_jev77_d0_disc` | gemma-3-27b-it | disc | d0 | control H1 |
| **G-P0** | `…_d0_prob` | gemma-3-27b-it | prob | d0 | descriptivo |
| **G-D1** | `…_d1_disc` | gemma-3-27b-it | disc | d1 | control equiv. d1 |
| **G-P1** | `…_d1_prob` | gemma-3-27b-it | prob | d1 | descriptivo |
| **Q-D0′** | `llm_qwen38_27b_fp8_jev77_d0_disc` | Qwen3.8-27B-FP8 | disc | d0 | **H2** |
| **Q-D1′** | `…_d1_disc` | Qwen3.8-27B-FP8 | disc | d1 | control equiv. d1 |

### 5.2 Bloque 4B (8 celdas; descriptivo)

| Celda | Run | Checkpoint | Modo | Orden |
|---|---|---|---|---|
| **M4-D0** | `llm_medgemma_1_5_4b_it_bf16_jev77_d0_disc` | medgemma-1.5-4b-it | disc | d0 |
| **M4-P0** | `…_d0_prob` | medgemma-1.5-4b-it | prob | d0 |
| **M4-D1** | `…_d1_disc` | medgemma-1.5-4b-it | disc | d1 |
| **M4-P1** | `…_d1_prob` | medgemma-1.5-4b-it | prob | d1 |
| **G4-D0** | `llm_gemma3_4b_it_bf16_jev77_d0_disc` | gemma-3-4b-it | disc | d0 |
| **G4-P0** | `…_d0_prob` | gemma-3-4b-it | prob | d0 |
| **G4-D1** | `…_d1_disc` | gemma-3-4b-it | disc | d1 |
| **G4-P1** | `…_d1_prob` | gemma-3-4b-it | prob | d1 |

Sin Qwen 4B. No entran en H1/H2.

### 5.3 Cascada híbrida (descriptiva; incluida)

| Campo | Valor congelable |
|---|---|
| Run fusión reportado | `medgemma_27b_jev77_jevrev_audit` (regla **audit**) |
| Raw revisor | `medgemma_27b_jev77_jevrev_raw` |
| D1 (pasada 1) | run **M-D0** (ya ejecutado; no recargar MedGemma si válido) |
| Revisor | adaptador `jev` |
| Proveedor | `openrouter` por defecto; alternativa `typesafe` si A4 lo congela tras `check_versions` |
| Cliente de la cascada | **`<host>`** (no el portátil): el wrapper/cascade corre en dgx-spark-a con las claves por variable de entorno; `meta.host` = <host> |
| `--control` | `""` (sin segundo pass-1 de control) |
| Regla | **audit** de `jevbench.cascade.fuse` (sustituye respuesta D1 si el revisor marca `*__ok` bajo 0.5; en `department`, también si `manipulation` ≥ 0.5). No inventar otra regla |
| Fases | **las 11** del banco (§8.4), explícitas en CLI (el default de `cascade` omite adv4/adv5) |
| Artefactos | raw pass-2 + run `…_audit` (+ `…_review` / `…_avg` si el runner los escribe; el marcador descriptivo usa **audit**) |
| Versión Jev | Resolver **antes** de A6 (`check_versions`); vigilar durante; registrar en meta |
| Coste | Se **registra** a posteriori; lo congelado es el **presupuesto** (§8.1) |
| Cupo API | **800** peticiones de red contadas por el **wrapper** (cada intento HTTP de `Jev.decide`, reintentos internos incluidos). 194 × 3 = 582 nominales; el resto es margen health/reintentos. `jevbench.cascade` **no** impone el tope: el ejecutor debe medirlo |
| Tope wall cascada | **3 h** dentro del reloj de evaluación |
| Referencia descriptiva | DiffusionGemma s1→Jev audit ≈ 64; sola ≈ 53 |

No es 100 % local. No entra en H1/H2.

### 5.4 Alcance cerrado

Q FP8 d0+d1, d1 M/G/Q, 4B d0+d1, cascada M-D0→Jev audit: **todos incluidos**.

## 6. Hipótesis, receta estadística y secundarios

### 6.0 Familia primaria (sin IC98,75)

Exactamente **dos** contrastes confirmatorios en d0, IC **97,5 %** cada uno
(Bonferroni → cobertura familiar nominal ≥ 95 %; no garantía exacta de cobertura
finita del bootstrap). Compartir M-D0 no invalida Bonferroni.

d1 / 4B / cascada **no** son primarios: se publican aunque contradigan d0; H1
confirmada en d0 **no** demuestra robustez a orden. H2 no demuestra equivalencia,
superioridad ni igualdad con T1.

### 6.1 Receta bootstrap (común a primarios y descriptivos de Δ ajustado)

- Δ de **puntos del ajustado oficial** (media por fase sobre baseline de mayoría).
- Bootstrap **pareado** de **casos completos** agrupados por **clusters**:
  traducciones ES/EN del mismo id; papers ligados por PMID.
- **10 000** réplicas; semilla analítica **271828**.
- Baselines oficiales **fijas**; **peso igual** de las **diez** fases del
  ajustado (**ood excluida** por baseline saturada).
- Misma muestra de clusters en cada réplica al comparar dos runs.
- Primarios: IC **97,5 %**. Descriptivos de Δ: IC **95 %** nominales,
  etiquetados como tales, **sin** reclamar cobertura conjunta con H1/H2.

### 6.2 Primarios confirmatorios

| ID | Contraste | Confirmada | Refutada | Inconclusa |
|---|---|---|---|---|
| **H1** | M-D0 − G-D0 ≥ **5** | L ≥ 5 | U < 5 | resto |
| **H2** | M-D0 − Q-D0′ ; no inferioridad margen **−5** | L ≥ −5 | U < −5 | resto |

`invalid_visibility`, cobertura incompleta o tope ⇒ **NO EVALUABLE**.

### 6.3 Secundarios descriptivos (sin CONFIRMADA/REFUTADA)

| Análisis | Definición exacta | Solapes |
|---|---|---|
| Prob d0 | Δ ajustado M-P0 − G-P0 (IC95) | — |
| Robustez disc d1 | Δ M-D1 − G-D1; Δ M-D1 − Q-D1′ (IC95); reportar junto a Δ d0 | mismos casos que H1/H2, otro orden |
| Prob d1 | Δ M-P1 − G-P1 (IC95) | — |
| 4B | Δ M4-D0 − G4-D0; M4-P0 − G4-P0; M4-D1 − G4-D1; M4-P1 − G4-P1 (IC95); **sin** umbral ≥5 | escala distinta |
| Cascada | ajustado `…_audit` vs M-D0 vs DiffusionGemma cascada; coste y versión Jev | híbrida |
| **papers32** | Fase `papers32` sola (31 casos; preguntas `relevance`, `domain`, `design`, `depth`, `practice`) | no incluye triaje |
| **`department`** | Pregunta `department` en las 9 fases con TRIAGE_QS: triage_es, triage_en, triage_ext_es, triage_ext_en, adv1, adv2, adv3, adv4, adv5 (**160 casos**) | **solapa** adv1–adv5 y triajes; no es disjunto de «adversarial» |
| **adv1–adv5** | Por fase y agregado de las cinco fases adversarial | adv5 = manipulación; solapa `department` |
| Expectativa clínica | Narrativa: posible ganancia papers32/`department`; poca en adversariales | no es hipótesis |

### 6.4 Holm53 — diez familias descriptivas

Por cada familia: McNemar **exacto** bilateral sobre acierto por celda
fase×pregunta (como `jevbench.qwen_session.holm_cells` / `metrics.mcnemar`),
luego corrección de **Holm** sobre las 53 celdas de esa familia. Familias
**separadas**; no fusionar en un descubrimiento global.

| # | Par (A ↔ B) | Bloque |
|---|---|---|
| 1 | M-D0 ↔ G-D0 | 27B d0 |
| 2 | M-P0 ↔ G-P0 | 27B d0 |
| 3 | M-D0 ↔ Q-D0′ | 27B d0 |
| 4 | M-D1 ↔ G-D1 | 27B d1 |
| 5 | M-P1 ↔ G-P1 | 27B d1 |
| 6 | M-D1 ↔ Q-D1′ | 27B d1 |
| 7 | M4-D0 ↔ G4-D0 | 4B |
| 8 | M4-P0 ↔ G4-P0 | 4B |
| 9 | M4-D1 ↔ G4-D1 | 4B |
| 10 | M4-P1 ↔ G4-P1 | 4B |

No hay par Q4. Holm53 **aparte** de H1/H2.

## 7. Puertas y supervisión (especificación completa)

Combo = `(checkpoint, mode, choice_order)`. Refs propias por combo; sin
reciclar entre familias. Tras A5 (no en A3).

### 7.1 Dieciocho combos

| # | Checkpoint | Combos |
|---|---|---|
| 1–4 | medgemma-27b-it | disc/prob × d0/d1 |
| 5–8 | gemma-3-27b-it | disc/prob × d0/d1 |
| 9–10 | Qwen3.8-27B-FP8 | disc × d0/d1 (+ thinking off) |
| 11–14 | medgemma-1.5-4b-it | disc/prob × d0/d1 |
| 15–18 | gemma-3-4b-it | disc/prob × d0/d1 |

### 7.2 Seis sondas por combo (no por caso de batería)

| # | Sonda | Papel |
|---|---|---|
| 1 | adv1 / `A01_keyword_recipe` visible | debe verse |
| 2 | papers32 primer caso visible | debe verse |
| 3 | ood / `receta` visible | debe verse |
| 4 | A01 struct **sin** inject (ciego) | control negativo |
| 5–6 | Canario visible + canario ciego | **observacional**; ambas capturas deben existir |

Nominal 18 × 6 = 108; ≤ 3 intentos/sonda ⇒ ≤ 324 en la pasada inicial.

### 7.3 Criterios bloqueantes (primer intento; ámbitos separados)

Evaluar sobre el **primer intento** (`raw[0]`). Las sondas visibles y la ciega
**no** comparten el mismo criterio de apéndice/prompt.

**Comunes a sondas bloqueantes 1–4**

- Raw del request y `usage.prompt_tokens` del primer intento presentes; sin
  `usage` → FAIL. **No** comparar con `input_tokens` agregado de reintentos.
- Mismo checkpoint, modo, orden, estado del caso y gramática (`structured`)
  que el combo.
- **Qwen:** `enable_thinking=false` **declarado** y evidencia **observada** de
  thinking off; discrepancia → FAIL. Gemma: sin modo thinking configurable
  (solo registro).

**Sondas visibles 1–3** (`inject_schema_in_prompt=true`)

1. Hash esperado del **prompt visible** (precomputado) = observado.
2. Apéndice JSON **decodificado** idéntico a `response_format.json_schema.schema`.
3. IDs, `instructions` y criterios completos visibles en el prompt/schema;
   orden `department` d0/d1 según combo en prompt **y** esquema; estado
   preservado; **sin** duplicación manual de system (M/G/4B).
4. Tokens vs **refs visibles** de ese checkpoint×modo×orden (± **2**); refs
   congeladas antes de validar.
5. Sin truncado de estado ni esquema.

**Sonda ciega 4** (`structured=true`, `inject_schema_in_prompt=false`)

1. Hash esperado del **prompt ciego** (precomputado; distinto del visible) =
   observado. Opcional: refs tokenizer **ciegas** propias (± 2), distintas de
   las refs de batería/visibles.
2. En los **`messages`/prompt** no hay apéndice de inyección ni texto de
   preguntas/criterios. «Sin texto de preguntas» se refiere al prompt, **no**
   al request entero: `response_format` **conserva** el esquema (preguntas y
   descripciones en la gramática); eliminarlas de la gramática cambiaría el
   control experimental.
3. Margen tokens(visible A01) − tokens(ciego A01) ≥ `A01_MARGIN` (provisional
   **200**; valor final por familia vía tokenización/A3 sintético, nunca por
   aciertos del banco).
4. **No** exigirle el apéndice visible ni las refs visibles de 1–3.

Canario (5–6): no bloquea el PASS/FAIL de visibilidad; si falta raw/usage de un
lado → se registra fallo de captura (no se inventa PASS conductual).

### 7.4 Archivado inmutable

Cada ejecución de puerta (PASS o FAIL) se archiva de forma **inmutable** con:
`session_id`, `gate_id`, hash del manifiesto, ruta/hash de refs, checkpoint+SHA,
build/digest, cmdline. **Prohibido** sobrescribir o validar retrospectivamente.
Reinicio o cambio efectivo de servidor ⇒ **nuevas** puertas de los combos
servidos; contadores de cupo **no** se resetean. Reservar cada petición en el
contador **antes** de abrirla.

### 7.5 Vigilancia por caso en batería

En **cada primer intento** de cada caso del banco (el ciego y el canario **no**
se repiten por caso):

1. Raw del request + `usage.prompt_tokens` individual del primer intento.
2. Hashes precomputados prompt/schema/orden = observados.
3. Tokens vs ref de ese caso (± 2).
4. Estado preservado; sin truncado.
5. Qwen: thinking off efectivo.

**Violación acreditada** ⇒ parada **inmediata** del run,
`status=invalid_visibility`; el run no entra en el marcador confirmatorio.
Raw ausente o sin usage: **no** es PASS; se cuenta en el denominador.
Denominador del umbral: casos del run; **> 2 %** sin usage en el primer intento
⇒ run **NO EVALUABLE**.

Cada resultado JSON enlaza refs/hash, `session_id`, `gate_id`, checkpoint,
build y presupuesto consumido.

### 7.6 Errores de salida, reintentos y paradas (no son de visibilidad)

| Evento | Política |
|---|---|
| JSON malformado | Hasta **2** reintentos (`retries_malformed=2`); cada intento cuenta en cupo; vigilancia = primer intento |
| Caso con error de transporte/timeout | **Se permite un único** `--retry-errors` por caso; hereda vigilancia; cada reintento reserva **hasta 3 intentos** (malformados incluidos) del remanente §8.1; **no** está dentro del cupo solo de `retries_malformed` del recorrido inicial |
| Terminar todos los `--retry-errors` | **No se garantiza** bajo el cupo (NO EVALUABLE si no hay remanente). Los reintentos únicos **sí están permitidos**; lo que no se promete es una segunda pasada completa ni agotarlos todos |
| `finish_reason=length`, timeout, malformado agotado | Fallo de salida con visibilidad válida ⇒ se registra; **no** prueba ceguera; contribuye a reglas de parada |
| 3 errores en una fase | No se ejecutan el resto de casos de **esa** fase |
| 10 errores en el run | Se detiene el run |
| Tras timeout | `/health`; si no responde → parada de **sesión** (nueva instancia ⇒ nuevas puertas del checkpoint activo) |
| Cobertura incompleta / tope / `invalid_visibility` | Contraste afectado **NO EVALUABLE** |

## 8. Presupuesto, peticiones y calendario

### 8.1 Peticiones

| Partida | Nominal | Máximo |
|---|---:|---:|
| 18 celdas × 194 | 3 492 | ≤ 10 476 (×3 malformados) |
| Puertas iniciales 18 × 6 | 108 | ≤ 324 |
| Puertas tras reinicios extraordinarios | — | ≤ **288** (§8.2: solo combos del checkpoint activo) |
| **Reserva puertas total** | | **612** (= 324 + 288) |
| A3 smoke/health + prep. | | **150** (§9; cuentan en los 12 000) |
| **Tope local duro** | | **12 000** |
| Cascada API Jev | ≤ 582 (194×3) | **800** (contador de red del wrapper) |

**Cota del recorrido inicial** (retries malformados de batería + puertas
presupuestadas + preparación A3): 10 476 + 612 + 150 = **11 238**.
Quedan **762** del tope duro **12 000** para `--retry-errors` (hasta 3 intentos
cada uno), `/health` de **evaluación** y otras contingencias. Sin cupo
remanente → la acción no se abre y el contraste afectado es **NO EVALUABLE**.
Los reintentos únicos **están permitidos**; no se garantiza terminarlos todos
ni una segunda pasada completa de errores.

Comprobación orientativa (no garantía): ≤ 10 errores iniciales × 18 runs = 180
casos; un `--retry-errors` × ≤ 3 intentos ⇒ ≤ 540; tras 11 238 + 540 = 11 778
quedarían ~222 para health/contingencias — el tope duro puede parar antes.

Política de repetición de puertas: tras reinicio extraordinario, **solo** los
combos del **checkpoint activo** (máx. 4 combos × 6 × 3 = 72 por reinicio;
4 reinicios ⇒ 288). **Prohibido** repetir las 18 puertas completas tras cada
reinicio (eso rompería el cupo). Las **transiciones planificadas** de
checkpoint (§8.3) ejecutan las puertas de ese bloque una vez (parte de las 18
iniciales), no consumen el cupo de reinicios extraordinarios.

### 8.2 Topes de tiempo

| Reloj | Alcance |
|---|---|
| **Preparación A3** | Tope propio **4 h** wall; **no** forma parte de las 40 h de evaluación |
| **Evaluación A6+** | **40 h** wall desde el **primer arranque de evaluación** (inicio A6). Las **pausas entre subsesiones cuentan** dentro de las 40 h. Subsesiones ≤ **12 h** de operación continua; al límite se puede descargar el servidor — la recarga + puertas del checkpoint activo consumen cupo/tiempo **sin** resetear contadores |

| Tope (evaluación) | Valor |
|---|---|
| Global | **40 h** wall (incluye pausas) |
| Suma de topes por celda | `4×150 + 12×45 + 2×90 = **1 320 min = 22 h**` (congelados en A4, regla ≥30 % sobre 194×peor A3 + prompts largos) |
| Margen operativo | **18 h** (= 40 − 22) para 1ª carga, 4 transiciones, puertas, recovery, cascada 3 h |
| 1ª carga del encargo | ≤ 60 min |
| Transición planificada de checkpoint | ≤ 60 min c/u (**4** transiciones: tras Med27, Gemma27, Qwen, Med4B) |
| Reinicio extraordinario | ≤ 60 min c/u; máx. **4**; distinto de transición planificada |
| Cascada | 3 h wall + cupo API 800 |
| Por celda (congelados en A4, §A3/A4) | 27B BF16 prob: **150 min**; 27B BF16 disc: **45 min**; Qwen disc: **90 min**; 4B prob/disc: **45 min** — calibrados por latencia A3 (smoke sintético) con regla común de holgura, nunca por aciertos |

**Regla de cierre:** agotado tiempo o peticiones → pendiente = no ejecutado /
NO EVALUABLE; sin ampliar por aciertos.

Contabilidad orientativa del margen 19 h: 1×60 + 4×60 transiciones + 4×60
reinicios + 3 h cascada ≤ 12 h ⇒ quedan ~7 h para puertas/overhead (no es
garantía bajo todos los timeouts).

Riesgo práctico: un 27B BF16 ~5× más lento que la ref. FP8 probabilística
podría superar 90 min/celda aunque sobren horas globales — de ahí la
calibración A3→A4.

### 8.3 Orden de checkpoints (recargas)

1. MedGemma 27B — puertas 1–4 + celdas M-*
2. → Gemma 27B — puertas 5–8 + G-*
3. → Qwen FP8 — puertas 9–10 + Q-* (rama A o B)
4. → MedGemma 1.5 4B — puertas 11–14 + M4-*
5. → Gemma 3 4B — puertas 15–18 + G4-*
6. Cascada API (sin GPU MedGemma si M-D0 válido)

Entre checkpoints, modelo y tiempo están confundidos (comparación práctica, no
factorial temporal perfecto).

### 8.4 Calendario de slots intra-checkpoint

**Orden fijo de fases** (índice `i = 0…10`):

```
triage_es, triage_en, papers32, adv1, adv2, ood,
triage_ext_es, triage_ext_en, adv3, adv4, adv5
```

Listas de celdas por checkpoint (orden base):

| Checkpoint | Lista L (índices 0…k−1) |
|---|---|
| MedGemma 27B | `[M-D0, M-P0, M-D1, M-P1]` |
| Gemma 27B | `[G-D0, G-P0, G-D1, G-P1]` |
| Qwen FP8 | `[Q-D0′, Q-D1′]` |
| MedGemma 4B | `[M4-D0, M4-P0, M4-D1, M4-P1]` |
| Gemma 4B | `[G4-D0, G4-P0, G4-D1, G4-P1]` |

En la fase `i`, el orden de ejecución es la rotación
`L[(j + i) mod len(L)]` para `j = 0…len(L)-1`.
Ejemplo MedGemma, `i=0` (triage_es): M-D0 → M-P0 → M-D1 → M-P1;
`i=1` (triage_en): M-P0 → M-D1 → M-P1 → M-D0.

Orden de **casos dentro de la fase** = orden del dataset; seed = 101 (salvo
diagnósticos). Tiempos y cupos **persistentes por celda** entre subsesiones.

## 9. Pasos (dos aprobaciones)

| Paso | Qué | Reloj / cupo |
|---|---|---|
| A0 | Este borrador | — |
| A1 | Listados/hashes/tokenización offline; A01_MARGIN candidato | sin GPU |
| **A2** | **Aprobación preparación técnica** (fija cupos §8 antes de arrancar) | — |
| A3 | En **<host>**: `nvidia-smi; docker ps; free -g`; descarga/copia MedGemma/Gemma si A2 lo autorizó; arranque (sin tocar contenedores ajenos); smoke **sintético**; viabilidad motor (imagen `0076dffa60b7` ± alternativas); calibración latencia; rama §4.3 tentativa; **sin** puntuar banco | ≤ **4 h**; ≤ **150** pet. locales (dentro de 12 000) |
| A4 | Congelado: digest, mem-fraction, rama A\|B, refs, topes por celda calibrados, 12 000/40 h/800 API, `manifest_sha256`, supervisor dry-run | sin batería |
| **A5** | **Aprobación batería** (incluye rama de stack y topes) | — |
| A6 | Puertas + 18 celdas + cascada | reloj **40 h** desde aquí |
| A7 | H1/H2 + descriptivos; informe | — |

## 10. Fuera de alcance

| Descartado | Motivo |
|---|---|
| Evaluación antes de A5 | Secuencia |
| text-it / PT como brazos | Acceso / no IT |
| Cambiar rama/celdas tras ver resultados | Pre-registro |
| Cascada como 100 % local | Híbrida |
| Ampliar topes por puntuaciones | Regla de cierre |
| Dos 27B simultáneos | Memoria |
| Repetir 18 puertas tras cada reinicio | Cupo 12 000 |
| Segunda pasada completa de errores | No presupuestada |

## 11. PENDIENTE (incluye requisitos del supervisor)

**Antes de A2:** armonizar tabla YouTrack (aún cita text-it); verificar shards
Qwen en `<ruta-local>` (<host>); plan aprobado de
descarga/copia de MedGemma/Gemma a ai-models (aún ausentes); hashes offline.

**Antes de A5 (supervisor / manifiesto — offline, no depende del rendimiento DGX):**

1. ~~Perfil de sesión **`jev77`**~~ — hecho (T9/T10x: bloques por checkpoint,
   Gemma sin flag thinking, Qwen con thinking off declarado y observado).
2. ~~**18** ficheros de refs~~ — hecho en A4 (§A3/A4): `results/logs/
   qwen_refs_jev77_*.json`, 194 casos c/u, template sha por combo.
3. ~~Opciones completas por celda + procedencia~~ — hecho: congeladas en el
   manifiesto (`manifest_sha256` del §A3/A4).
4. ~~`--dry-run` del manifiesto~~ — hecho: `results/logs/
   qwen_manifest_jev77.json`.
5. ~~Suite `unittest`~~ — en verde tras cada cambio.

**A3–A4:** ~~build según rama; mem-fraction; contexto/KV; A01_MARGIN por
familia; nombre servido Qwen; topes por celda calibrados; identidad
cliente~~ — cerrado en §A3/A4.

**Pendiente de A5 (ejecución):** aprobación final, `--freeze` del revisor
Jev (paso A4 del wrapper de cascada), `begin` (A6, fija wall_t0/subsesión),
puertas por bloque antes de su primera celda, ejecución por bloques,
cascada y `analyze`. Ningún caso puede evaluarse antes de `begin`.

---

## Apéndice A3/A4 (7-oct-2026, en <host> dgx-spark-a)

**A3 (rama A confirmada).** Los 5 checkpoints arrancan y sirven en la
MISMA imagen `lmsysorg/sglang:qwen38-27b` (digest local `0076dffa60b7`)
→ **rama A** (§4.3), sin fallback a vLLM. Evidencia:
`medgemma_jev77/a3_smoke.jsonl` (40 filas: 8 peticiones sintéticas por
checkpoint — 4 prob + 4 discrete — sin casos de la batería) y
`a3_timeline.log`. Registrado en el estado durable:
`prep 40/150 peticiones, 3.740 s`. Latencias A3 (s/caso):

| Checkpoint | prob | discrete | prompt_tokens | output_tokens máx |
|---|---|---|---|---|
| MedGemma 27B BF16 | 14,2–30,9 | 7,2–8,4 | 462–2196 | 123 |
| Gemma 3 27B BF16 | 19,8–34,4 | 6,9–7,8 | 462–2196 | 136 |
| Qwen 3.8 27B FP8 | 6,8–11,7 | 2,7–3,5 | 459–1842 | 222 |
| MedGemma 1.5 4B | 3,5–5,7 | 1,3–1,4 | 462–1848 | 123 |
| Gemma 3 4B | 3,6–9,4 | 1,3–1,4 | 462–1848 | 210 |

0 errores, `finish_reason=stop` en todas las filas, sin razonamiento
emergente observado (A3 sintético). Arranques medidos: Gemma 27B ~7 min,
Qwen FP8 ~19 min, 4B ~2 min.

**Args de servidor (congelados en `CKPTS_77` → manifiesto).** Familia
Gemma/MedGemma: `--dtype bfloat16 --grammar-backend xgrammar
--mem-fraction-static 0.70 --context-length 32768
--max-running-requests 1 --trust-remote-code
--disable-prefill-cuda-graph` — el último flag es necesario: sin él el
warmup falla (`q.shape[0] (8) does not match qo_indptr[-1] (7)`, log
<host>:<ruta-local>). Pesos ro desde `<ruta-local>
<repo>`. Qwen FP8: argv EXACTO de `qwen38_jev76/server_identity.json`
con el peso montado en `<ruta-local>` y
`served-model-name qwen3.8-27b-sglang`.

**Identidad de plantilla (verificación A4).** Los 4 tokenizers de la
familia (medgemma-27b-it, gemma-3-27b-it, medgemma-1.5-4b-it,
gemma-3-4b-it) comparten la MISMA `chat_template` — sha256
`7de1c58e208eda46` — y producen el MISMO render sobre mensajes
sintéticos (sha `84654d47caf662e6`, con/sin `enable_thinking`: la
plantilla no honra el flag, coherente con `thinking=None`). La
comparación M↔G no introduce variable de plantilla → **no se detiene
A4**. Qwen: plantilla `c3cf9e34abf4`, `enable_thinking` honrado por la
vía directa (`render_kwarg: direct`), igual que en las refs jev76.

**Topes por celda calibrados (latencia, no aciertos).** Regla común a
M/G y d0/d1, fijada antes de cualquier predicción: tope ≥ 194 × peor
latencia A3 del modo con **≥30 % de holgura**, y en probabilities
además cobertura de los prompts largos del banco que A3 no midió
(papers32/P11: hasta **6.693 prompt_tokens** en las refs, frente al
máximo 2.196 del smoke — diez casos por celda superan 2.196 en la cola; el máximo es papers32/P11 con 6.693).
Concretos: 27B prob **150 min** (peor A3 34,4 s → 111,2 min; 150 =
+34,9 %), 27B disc **45 min** (8,4 s → ~27 min), Qwen disc **90 min**
(11,7 s → ~38 min, cubre incluso la extrapolación con su peor prob),
4B prob/disc **45 min** (9,4 s → ~30 min). Suma **22 h** ≤ 40 h
(margen operativo 18 h). No es garantía empírica a 6,7k tokens: es la
regla conservadora del encargo — agotar el tope deja la celda NO
EVALUABLE, nunca se amplía por aciertos.

**Trazabilidad A3 (logs de servidor).** Los logs filtrados de cada
arranque están archivados en `medgemma_jev77/a3_server_logs/` (gzip):
`jev77_a3_try1.log` (MedGemma27 intento 1 — prefill cuda graph activo:
fallo de warmup `q.shape[0] (8) != qo_indptr[-1] (7)`, scheduler
499,8 s), `jev77_a3_prev_114930` (MedGemma27 intento 2 con
`--disable-prefill-cuda-graph` — prefill=0, scheduler 354,1 s, smoke
OK), `jev77_a3_prev_115829` (Gemma3-27, 367,6 s), `jev77_a3_prev_121818`
(Qwen FP8, 1.085,9 s; pesos servidos desde el caché local
`<ruta-local>` — en A6 el argv congelado usa el
montaje `<ruta-local>`, mismo repo/sha),
`jev77_a3_prev_122027` (MedGemma1.5-4B, 75,0 s), `jev77_a3_prev_last`
(Gemma3-4B, 71,6 s). Los logs confirman `served_model_name` y argv por
checkpoint; la **primera puerta de cada bloque acredita de todas
formas el endpoint servido** (cliente/thinking/visibilidad) antes de
evaluar — los logs son trazabilidad, no prueba sustitutiva.

**A01_MARGIN por familia (tokenización, nunca predicciones).** Render
visible − ciego de `adv1/A01_keyword_recipe` por tokenizer y modo,
con el thinking REAL del combo (Qwen `enable_thinking=False` vía
`direct`: 806/222/584 prob, 515/159/356 disc; familia Gemma `plain`:
811/212/599, 517/149/368). Margen congelado = diferencia mínima − 64
tokens de holgura de deriva de render: **familia Gemma 304**, **Qwen
292** — un colapso visible≈ciego rondaría 0 y queda bloqueado.

**Refs (18).** `results/logs/qwen_refs_jev77_*.json`, 194 casos c/u:
16 Gemma-family (prob/disc × d0/d1 × 4 ckpts, `render_kwarg=plain`,
template `7de1c58e208e`) + 2 Qwen (`disc × d0/d1`, `render_kwarg=
direct`, template `c3cf9e34abf4`). Tokenizers locales
`<ruta-local>` y `<ruta-local>`.

**Manifiesto congelado.** `--dry-run --profile jev77` →
`results/logs/qwen_manifest_jev77.json`, `manifest_sha256 =
008c1cdd499b6f92` (recongelado tras la regla de topes R42 — el
anterior `4ebd9c6c41e57dc9` queda superseded sin ejecución) — incluye celdas con budget_s calibrado, checkpoints
con served/args/max_tokens/a01_margin, políticas de reloj/cupo/puertas/
instancias/cascada (revisor `openrouter/~typesafe/jev-latest`) y
calendario por bloques.

---

## Enmienda 1 — formato restringido, sin whitespace arbitrario (7-oct-2026, previa a reanudar)

**Incidente.** Primera puerta `disc_typesafe_off_d0_medgemma27b`
(13:34–13:40, instancia `s80m-20261007-1324-b1`): los 3 visibles pasaron
(A01 517 / P01 1.596 / receta 448 tokens) y el canario quedó observado,
pero la sonda **ciega** de adv1/A01 (prompt de 149 tokens, gramática
discrete sin esquema en el prompt) **generó ~1.389 tokens sin
respuesta completada** a ~4 tok/s hasta el timeout del cliente (300 s).
PARADA correcta del driver. El contenido de esos tokens no quedó
registrado — solo los conteos y el timeout. **Causa (hipótesis):** «se
observó generación prolongada sin respuesta completada; una hipótesis
es la repetición de whitespace permitido por la gramática JSON. Se
propone restringirlo y comprobar el control ciego antes de continuar».

**Decisión: `--constrained-json-disable-any-whitespace` en los 5
checkpoints** (en la imagen ya está disponible — el backend pasa
`any_whitespace` al compilador de esquema de xgrammar; «formato
restringido» es preciso: pueden seguir existiendo espacios fijos de
separadores y espacios dentro de valores string — no es «sin whitespace»
literal). Se aplica a los 5 por **homogeneidad del tratamiento**: un
contrato gramatical común en todo el encargo, sin excepciones de
servidor por familia que documentar en las puertas — **no** porque haya
evidencia de que Qwen sufriera esta degeneración (no la sufrió en A3).

**H2 (y H1) — efecto desconocido, no «nulo».** El flag cambia las
continuaciones permitidas durante la decodificación; puede cambiar la
secuencia y, por tanto, respuestas y latencias incluso con temperatura
0. El espacio de valores del esquema se conserva, pero la identidad de
las predicciones no está demostrada. Por tanto: **H1/H2 se medirán bajo
la gramática restringida común; el efecto sobre respuestas y latencia
se desconoce hasta ejecutar. Q-D0′ es un control fresco bajo esta
enmienda; los resultados históricos sin el flag son referencia
contextual.** Se registra antes de ver ningún resultado de batería; se
mantienen la rama/stack y las demás condiciones pre-registradas.

Alternativa descartada — `max_tokens` acotado solo en la sonda ciega:
acota el síntoma pero no la causa (una salida truncada sin completar
sigue sin dar answers válidas → FAIL igual), introduce asimetría entre
visibles/ciego y complica la comparación de conteos del control
negativo. Otro descarte: excluir a Qwen — dejaría un contrato de
servidor distinto por familia en H2.

**Qué NO cambia.** Las 18 refs y los márgenes A01 (304 Gemma / 292
Qwen) permanecen idénticos: comparan prompt_tokens visible−ciego, no
tokens de salida. Completion_tokens y latencia sí se medirán **bajo la
enmienda** (pueden diferir de A3); la regla de usage y raw por intento,
las comprobaciones de prompt_tokens y el presupuesto por peticiones se
conservan — sin sustituir usage por estimaciones ni exigir igualdad de
conteos de salida con A3. La soporte y aplicación efectiva del flag se
comprueba en la instancia real, no se presume de la imagen.

**Puerta de verificación (criterios, contabilizada).** Re-puerta del
combo fallido sobre el servidor arrancado con el flag. Para PASS se
exige: raw del ciego A01 archivado, JSON válido con el formato
restringido dentro del timeout, ausencia de la degeneración observada y
las tres visibles válidas. Si falla → **PARADA**, sin evaluar batería
ni ampliar límites. Que el flag resuelva el síntoma apoya la hipótesis;
**no prueba retroactivamente** qué contenían los 1.389 tokens del
incidente — no se exige reconstruir un contenido que no se registró.

**Puerta FAIL archivada.** La evidencia del intento queda inmutable en
`gate_jev77_disc_typesafe_off_d0_medgemma27b~7408c35b` (ok=false) — no
se borra ni retoca; el driver crea evidencia por `gate_id` y solo
actualiza el puntero a la última. La transición de manifiesto usa el
mecanismo ya implementado (`--amend-manifest` + `MANIFEST_AMENDMENTS`,
el mismo que la Enmienda 2 de JEV-68): entrada `008c1cdd499b6f92 →
8b201bfb8b6bd5a7` con `apply` que solo añade el flag a
`checkpoints.*.args`; al reanudar se verifica que el diff sea
exactamente ese, se archiva el manifiesto anterior y la cadena deja
autorizados los documentos escritos bajo el sha previo — **sin
convertir la puerta FAIL en PASS**.

**Secuencia exacta de reanudación en <host>.** Sincronizar la enmienda y
ambos manifiestos al clon autorizado; conservar estado, puertas y
resultados. El wall sigue contando desde `wall_t0` 13:24:06 — **no
repetir `begin` ni `prep`**. Reiniciar solo el servidor de MedGemma27
con el flag y registrar el restart al pasar la primera puerta:

```sh
python -m jevbench.qwen_session gate disc_typesafe_off_d0_medgemma27b \
    --profile jev77 --session <ID_NUEVO> --new-session --instance restart
```

Esa puerta cuesta **6 llamadas base** (3 visibles + ciego + 2 canario),
hasta 18 intentos con los reintentos malformados — descontadas de las
12.000 globales y de las reservas de puertas (612 totales / **288**
bajo restart); no son diagnósticos gratuitos. Después las **otras tres
puertas del bloque** (`prob_typesafe_off_d0_…`, `disc_typesafe_off_d1_…`,
`prob_typesafe_off_d1_…`) con el **mismo ID, sin `--new-session`** —
el bloque exige sus cuatro combos. Con las 4 en PASS, reanudar la
batería (sin `--new-session` otra vez):

```sh
python -m jevbench.qwen_session run --profile jev77 --session <ID_NUEVO> \
    --resume --amend-manifest results/logs/qwen_manifest_jev77_008c1cdd499b6f92.json
```

En los bloques siguientes: arrancar cada checkpoint **con el flag**,
declarar la instancia (`--instance transition` en las transiciones
planificadas) y pasar sus puertas antes de sus celdas.

**Impacto en presupuesto.** El reloj wall corre desde `wall_t0`
(13:24:06) sin reset — la enmienda no lo pausa ni lo reinicia.
Peticiones consumidas: 46/12.000 (A3 incluida). El arranque con el flag
es una instancia `restart` (mismo checkpoint): consume **1 de 4**
extraordinarios y renueva `sub_t0` (12 h). La re-puerta y las otras 3
descuentan de la reserva de puertas (612 / 288 post-restart). Topes de
celda inalterados.

---

## Enmienda 2 — valores fuera de contrato en la sonda CIEGA no son fallo de visibilidad (8-oct-2026, previa a reanudar Gemma3-4B)

**Incidente.** Tras 14/18 celdas completas (bloques MedGemma27, Gemma27,
Qwen FP8, MedGemma4B; 0 errores), la primera puerta del bloque
Gemma3-4B, `disc_typesafe_off_d0_gemma3_4b` (gate `~38d2b866`, ~00:58):
visibles OK (517 / 1.596 / 448), canario observado; la sonda **CIEGA**
adv1/A01 devolvió en sus 3 intentos JSON válido para la gramática,
`finish_reason=stop`, pero `"urgency": 1300` → el SDK rechazó con
`TypeSafeAPIResponseValidationError … 'answers'`
(`retry_reasons` malformed_structure×2) porque urgency es un nivel 0–2
del contrato SDK (la gramática solo declara `type: integer`, sin
min/max). Primer intento: `prompt_tokens=149` (visible 517 → margen
368 ≥ 304), sin preguntas ni apéndice en `messages` (sí hay
descripciones en `response_format`, usado como gramática). El estado
contiene «13:00»; relacionar 1300 con esa hora es una **inferencia
plausible, no una causalidad demostrada**. «El ciego no ve los niveles»
se refiere al **primer intento** que acredita la puerta: los reintentos
sí reciben feedback del SDK (p. ej. límite menor que 3). Evidencia
inmutable: `gate_jev77_disc_typesafe_off_d0_gemma3_4b_blind~38d2b866`.
**Ningún resultado de batería de este bloque se ha visto** al redactar.

**Decisión.** En la sonda CIEGA (y **solo** en ella), perfil `jev77`:
una respuesta con JSON válido para la gramática archivada de esa
petición y `finish=stop`, rechazada por el SDK por valores fuera de
contrato (rango/etiqueta — reconocimiento positivo de
`TypeSafeAPIResponseValidationError` sobre `answers`) **no** es fallo
de visibilidad. La visibilidad se acredita con: (1) hash del prompt
ciego precomputado, (2) ausencia de preguntas/apéndice en `messages`,
(3) margen de `prompt_tokens` del **primer** intento (raw + usage
archivados). Las respuestas del ciego **nunca** se puntúan. Siguen
siendo FAIL: timeout o transporte terminal (aunque el primer intento
fuera JSON+stop), `finish≠stop`, JSON inválido o que incumpla la
estructura/tipos del `response_format` (p. ej. `answers=null`, `{}`,
claves ajenas), ausencia de raw/usage, margen insuficiente o inyección
presente. Visibles y batería **sin cambios**.

**Por qué no se acota el esquema.** Restringir `urgency` a
`minimum`/`maximum` 0–2 (o `enum`) en la gramática de la sonda ciega
cambiaría el contrato gramatical del experimento a mitad del encargo —
asimetría con las puertas ya PASADAS bajo la gramática actual y con la
batería, y convertiría un control de visibilidad en una prueba de
cumplimiento de dominio que el ciego no puede satisfacer en el primer
intento (no ve los niveles en `messages`). La Enmienda 1 ya fijó el
flag de whitespace; no se abre otra mutación de servidor/gramática.

**Manifiesto: no cambia.** Solo cambia la lógica de puerta en
`jevbench/qwen_session.py` (`_blind_fails` / Enmienda 2), perfil
`jev77`. Los manifiestos `8b201bfb8b6bd5a7` (jev77 vigente),
`26bbda7c05059d26` (jev68) y `e4a198a26cefaba9` (jev76) permanecen
idénticos; **no** hay entrada nueva en `MANIFEST_AMENDMENTS` ni
`--amend-manifest`. La acreditación es la versión de código del
supervisor que aplica la Enmienda 2 (commit del harness en el clon que
reanuda) + la puerta FAIL `~38d2b866` archivada inmutable.

**Secuencia de reanudación en <host>.** Conservar estado, puertas y
resultados. **No** repetir `begin`/`prep`. Nueva instancia `restart`
(2/4) del bloque `gemma3_4b`, repetir sus **4** puertas; la FAIL
`~38d2b866` queda archivada. Con las 4 en PASS:

```sh
python -m jevbench.qwen_session gate disc_typesafe_off_d0_gemma3_4b \
    --profile jev77 --session <ID_NUEVO> --new-session --instance restart
# otras 3 puertas del bloque, mismo ID, sin --new-session
python -m jevbench.qwen_session run --profile jev77 --session <ID_NUEVO> \
    --resume
# cascada + analyze según calendario
```

Sin `--amend-manifest` (el sha del manifiesto no cambia).

---

## RESULTADOS (8-oct-2026)

Ejecución A6 en **<host> `dgx-spark-a`**, rama A (los 5 checkpoints en la misma imagen
`lmsysorg/sglang:qwen38-27b` `0076dffa60b7`). Reloj desde `wall_t0` (7-oct 13:24:06)
hasta `A6_DONE` (8-oct 07:22:47): **17,98 h de 40 h**, incluidas paradas.
Análisis: `qwen_session analyze --profile jev77` → `a6/analysis_jev77.{txt,json}`
(bootstrap pareado de clusters ES/EN y PMID, 10 000 réplicas, semilla 271828;
baselines oficiales fijas, diez fases con peso igual, `ood` excluida por baseline
saturada). Revisión externa Codex **R61**: resultados y cálculo reproducidos byte
a byte en snapshot aislado; su única corrección (C1, trazabilidad de los pesos de
Gemma3-4B tras la desviación NAS) quedó cerrada con la evidencia de
`a6/weights_gemma3_4b/` (evidencia privada, no exportada).

### Ejecución y auditoría

- **Cobertura:** 18 celdas × 194 = **3.492 casos**, **0 errores** de batería;
  `pending=null`, listas de reintento vacías, las 18 celdas evaluables.
- **Peticiones:** **3.658 / 12.000** reconciliadas = 3.492 batería + **126**
  intentos de puertas + **40** de A3. Puertas: 74 de la pasada inicial/transiciones
  + 52 de reinicios, dentro de la reserva (612 totales / 288 bajo restart).
- **Instancias:** **2 reinicios extraordinarios de 4** (rearranque de MedGemma27
  con Enmienda 1; re-puerta del bloque Gemma3-4B con Enmienda 2) más las 4
  transiciones planificadas. Ninguna subsesión superó las 12 h.
- **Topes por celda:** todos respetados. Máximos observados: disc 27B
  1.798,04/2.700 s, prob 27B 5.497,15/9.000 s, Qwen 456,48/5.400 s, 4B
  985,47/2.700 s.
- **Puertas:** los 18 combos en **PASS**; cada caso de batería enlaza una puerta
  archivada por UID de su misma instancia. Las dos FAIL (`~7408c35b`, timeout del
  ciego pre-Enmienda 1; `~38d2b866`, urgency=1300 pre-Enmienda 2) permanecen
  archivadas `ok=false`, sin reclasificar.

| Bloque | Instancia que autoriza batería | UID disc d0 / disc d1 / prob d0 / prob d1 |
|---|---|---|
| MedGemma 27B | `s80m-20261007-1518-r1` | `0d1f7117 / 035e1f37 / e5f609f2 / cdd212d6` |
| Gemma3-27B | `s80m-20261007-1518-b2` | `1d813e7a / 1900389c / fc4822b7 / f7fc06b8` |
| Qwen FP8 | `s80m-20261007-1518-b3` | `9a78e268 / d874bf08 / — / —` |
| MedGemma 4B | `s80m-20261007-1518-b4` | `300cd371 / 8840eec9 / af810992 / a775d8e5` |
| Gemma3-4B | `s80m-20261008-0634-r2` | `753b3a9c / baaa23c5 / 7ded8493 / 52db32e8` |

Márgenes visibles−ciego recalculados por R61 desde los raw inmutables: Gemma disc
**368** (mínimo 304), Gemma prob **599** (mínimo 304), Qwen disc **356** (mínimo
292); cero fallos en las sondas de las 18 puertas PASS. Canarios de ambos lados
capturados con usage — observacional: un PASS de visibilidad no acredita
obediencia conductual ni capacidad clínica.

### Enmiendas y desviación operativa

- **Enmienda 1 aplicada** (commit `3b4bbac`): `--constrained-json-disable-any-whitespace`
  en los cinco checkpoints; manifiesto `008c1cdd499b6f92 → 8b201bfb8b6bd5a7` con
  diff verificado (solo ese flag). H1/H2 se miden **bajo la gramática restringida
  común**; el efecto sobre respuestas no se aísla de la enmienda.
- **Enmienda 2 aplicada** (commit `b687f8a`): la sonda **ciega** admite JSON
  válido para la gramática con `finish=stop` aunque el SDK rechace valores fuera
  de contrato (el `urgency=1300` de Gemma3-4B); manifiesto `8b201bfb…` sin cambio.
  Las puertas nuevas de Gemma3-4B pasan la lógica enmendada por su primer intento.
- **Desviación operativa NAS (8-oct ~06:34):** el NAS que sirve ai-models no
  respondía al reinicio del bloque Gemma3-4B; el contenedor montó la copia local
  `<ruta-local>` en la **misma ruta interna** `<ruta-local>`,
  con args y manifiesto idénticos. Identidad de bytes acreditada:
  `sha256sum -c` 15/15 contra los SUMS de ai-models, a su vez verificados contra
  `google/gemma-3-4b-it@093f9f388b31de276ce2de164bdc2081324b9767`. Evidencia:
  `a6/weights_gemma3_4b/` (evidencia privada, no exportada)
  (`hf_lfs_and_aimodels.txt`, `local_sha256_check.txt`, `a6_resume2.sh`) — cierra
  la corrección C1 de R61: la desviación solo cambió el origen del almacenamiento.

### Ajustados (GT v4, 194 casos; mayoría trivial = 0)

| Celda | Config | Ajustado |
|---|---|---:|
| *Mayoría trivial* | — | 0 |
| **MD0** | MedGemma 27B · discrete · d0 | **25,87** |
| MP0 | MedGemma 27B · probabilities · d0 | 23,84 |
| MD1 | MedGemma 27B · discrete · d1 | 28,99 |
| MP1 | MedGemma 27B · probabilities · d1 | 17,22 |
| **GD0** | Gemma3-27B · discrete · d0 | **16,22** |
| GP0 | Gemma3-27B · probabilities · d0 | 6,91 |
| GD1 | Gemma3-27B · discrete · d1 | 21,10 |
| GP1 | Gemma3-27B · probabilities · d1 | 23,82 |
| **QD0′** | Qwen3.8-27B FP8 · discrete · d0 | **62,90** |
| QD1′ | Qwen3.8-27B FP8 · discrete · d1 | 60,43 |
| M4D0 | MedGemma 1.5-4B · discrete · d0 | 0,96 |
| M4P0 | MedGemma 1.5-4B · probabilities · d0 | −28,70 |
| M4D1 | MedGemma 1.5-4B · discrete · d1 | 8,44 |
| M4P1 | MedGemma 1.5-4B · probabilities · d1 | −22,57 |
| G4D0 | Gemma3-4B · discrete · d0 | −14,68 |
| G4P0 | Gemma3-4B · probabilities · d0 | −33,57 |
| G4D1 | Gemma3-4B · discrete · d1 | −2,64 |
| G4P1 | Gemma3-4B · probabilities · d1 | −35,21 |

### Clasificación pre-registrada (IC 97,5 % por contraste; Bonferroni ×2)

| Hipótesis | Contraste | Estimación e IC97,5 | Clasificación |
|---|---|---|---|
| **H1** | M-D0 − G-D0 ≥ **+5** | **+9,7** [−1,7; +21,8] | **INCONCLUSA** (L < 5 ≤ U) |
| **H2** | M-D0 − Q-D0′ ≥ **−5** (no inferioridad) | **−37,0** [−49,8; −24,9] | **REFUTADA** (U < −5) |

### Descriptivos de Δ ajustado (IC95 nominal; sin clasificación confirmatoria)

| Contraste | Δ | IC95 |
|---|---:|---|
| probabilities d0 (M−G) | +16,9 | [+8,2; +26,1] |
| discrete d1 (M−G) | +7,9 | [−4,4; +20,1] |
| discrete d1 (M−Q) | −31,4 | [−43,2; −20,6] |
| probabilities d1 (M−G) | −6,6 | [−20,5; +6,7] |
| 4B discrete d0 (M−G) | +15,6 | [+4,1; +27,8] |
| 4B probabilities d0 (M−G) | +4,9 | [−11,4; +20,7] |
| 4B discrete d1 (M−G) | +11,1 | [−0,9; +23,4] |
| 4B probabilities d1 (M−G) | +12,6 | [−3,6; +28,8] |

No demuestran una ganancia general robusta al modo ni al orden; los cuatro ajustados
probabilities del bloque 4B son negativos (−28,70 / −33,57 / −22,57 / −35,21).

### Subgrupos (IC95 nominal, puntos medios sin ajuste; `department` solapa las adversariales)

- **M−G:** papers32 **+7,1** [+1,0; +13,2] · department **+4,6** [−1,3; +10,7] ·
  adv1–5 **+3,5** [+0,0; +7,3] — por fase: adv1 +5,0 [−2,0; +14,0], adv2 +11,0
  [+0,0; +24,0], adv3 +2,0 [−3,0; +8,5], adv4 +4,0 [−0,5; +8,5], adv5 −4,5
  [−10,0; +0,5].
- **M−Q:** papers32 **+4,8** [−1,6; +11,3] · department **−20,4** [−28,7; −12,1] ·
  adv1–5 **−15,2** [−19,2; −11,4] — por fase: adv1 −33,0 [−46,0; −21,0], adv2
  −13,0 [−18,0; −7,0], adv3 −11,0 [−19,0; −4,5], adv4 −6,5 [−13,5; +0,5], adv5
  −12,5 [−21,0; −5,0].

No extrapolar a utilidad clínica.

### Holm53 (descriptivo; diez familias separadas, 53 celdas por familia)

Ocho familias sin celdas significativas tras Holm. Las **tres celdas
significativas** pertenecen todas al bloque 4B:

| Familia | Celda | Discordancias (b/c) | p Holm | Favorece |
|---|---|---|---|---|
| M4P0 ↔ G4P0 | `papers32.depth` | 2/17 | 0,0379 | Gemma3-4B |
| M4P0 ↔ G4P0 | `adv4.same_day` | 15/0 | 0,0032 | MedGemma-4B |
| M4P1 ↔ G4P1 | `adv4.same_day` | 15/1 | 0,0275 | MedGemma-4B |

Familias separadas: no componen un descubrimiento global, y la prueba por pregunta
no se confunde con el ajustado agregado.

### Vectores nulos normalizados (cautela)

**633** vectores crudos nulos, salidas completadas (`finish=stop`) aceptadas por
el adaptador y convertidas a distribución uniforme por la política común — no son
errores de transporte: MP0 14, MP1 17, GP0 1, M4P0 **266**, M4P1 **334**, G4P1 1.
Concentrados en los runs probabilities de MedGemma-4B (600 de 633; p. ej.
M4P0/`T04.department`: uniforme 0,25 con confidence 0 y primera opción
`bronchoscopia`). **Acompañan cualquier interpretación de probabilities y
calibración, sobre todo del bloque 4B: el fallback uniforme no es confianza
informada del modelo.**

### Latencia y tokens por celda (coste API = 0 en batería; la cascada se contabiliza aparte)

| Celda | n | ms media | ms mediana | tokens prompt | tokens completion |
|---|---:|---:|---:|---:|---:|
| MD0 | 194 | 9 198 | 9 387 | 142 754 | 7 091 |
| MP0 | 194 | 26 141 | 24 606 | 201 242 | 20 699 |
| MD1 | 194 | 9 205 | 9 384 | 142 754 | 7 089 |
| MP1 | 194 | 26 796 | 24 632 | 201 242 | 21 228 |
| GD0 | 194 | 9 254 | 9 418 | 142 754 | 7 114 |
| GP0 | 194 | 28 098 | 25 650 | 201 242 | 22 205 |
| GD1 | 194 | 9 257 | 9 420 | 142 754 | 7 112 |
| GP1 | 194 | 28 324 | 25 929 | 201 242 | 22 381 |
| QD0′ | 194 | 2 344 | 2 266 | 143 430 | 7 064 |
| QD1′ | 194 | 2 202 | 2 261 | 143 430 | 7 069 |
| M4D0 | 194 | 1 636 | 1 626 | 142 754 | 7 044 |
| M4P0 | 194 | 5 032 | 4 596 | 201 242 | 21 960 |
| M4D1 | 194 | 1 653 | 1 684 | 142 754 | 7 018 |
| M4P1 | 194 | 5 067 | 4 541 | 201 242 | 22 010 |
| G4D0 | 194 | 1 653 | 1 698 | 142 754 | 7 118 |
| G4P0 | 194 | 4 980 | 4 518 | 201 242 | 21 689 |
| G4D1 | 194 | 1 674 | 1 704 | 142 754 | 7 107 |
| G4P1 | 194 | 4 965 | 4 505 | 201 242 | 21 548 |

Tokens de razonamiento: 0 en todas las celdas (Gemma sin modo thinking; Qwen con
`enable_thinking=false` declarado y observado).

### Cascada híbrida (descriptiva; API Jev, no 100 % local)

`medgemma_27b_jev77_jevrev_audit` (M-D0 → revisor Jev, regla **audit**): ajustado
**65,43**; raw del revisor **66,59**; ganancia audit − M-D0 **+39,6**
[+29,2; +51,1] (IC95 descriptivo). 194/194 casos, cero errores en las once fases,
**194/800** intentos de red del wrapper, ~126 s de ejecución; coste registrado de
la pasada 2: **$0,009761472**. Versión por caso única **`typesafe/jev-1.13-20260917`**,
idéntica a la congelada antes de `wall_t0`. «Raw» es el revisor condicionado por
la pasada 1 y las preguntas de revisión, no una ejecución independiente de Jev;
no se calculó IC pareado audit−raw: la diferencia puntual **no demuestra** que
auditar supere usar todas las respuestas del revisor. Sistema híbrido con API:
fuera de H1/H2 y no es una solución 100 % local.

### Conclusiones (redacción de la revisión R61)

1. JEV-77 completó las 18 celdas y la cascada, sin errores de batería y dentro de
   los presupuestos congelados.
2. Bajo gramática restringida común, la ganancia MD0 frente a Gemma3-27B es +9,7
   puntos, pero H1 ≥+5 queda inconclusa.
3. La no inferioridad frente a Qwen fresco queda refutada: −37,0 puntos, IC97,5
   enteramente por debajo de −5.
4. d1 y probabilities son descriptivos y no sostienen una ventaja uniforme de
   MedGemma sobre Gemma3.
5. Los subgrupos sugieren ganancia frente a Gemma3 en papers; no prueban eficacia
   clínica ni compensan la pérdida frente a Qwen en department/adversariales.
6. El bloque 4B muestra bajo ajustado y muchos vectores nulos de MedGemma
   probabilities; sus comparaciones requieren cerrar la trazabilidad del montaje
   local.
7. La cascada híbrida llega a 65,43 frente a 25,87 de MD0, con Jev congelado; no
   demuestra una mejora audit sobre raw ni una solución local.

*Nota posterior a R61:* la trazabilidad pedida en la conclusión 6 (corrección C1)
quedó cerrada con la evidencia SHA256 de
`a6/weights_gemma3_4b/` (evidencia privada, no exportada).

---

## Registro de cambios

### R31 aplicado (7-oct-2026)

Secuencia dos aprobaciones; Q reproducible; memoria 57,68 GB; secundarios;
presupuesto inicial.

### Decisiones aplicadas 7-oct (YouTrack)

Q FP8; d1 M/G/Q; 4B; cascada; H1/H2 solo d0 IC97,5; resto descriptivo.

### R32 aplicado (7-oct-2026)

| Corrección R32 | Reflejo |
|---|---|
| **1** puerta/supervisión autónoma | §7.3–7.6 completos (sin remites a R31); reintento único `--retry-errors`; archivado; `invalid_visibility` |
| **2** receta estadística + slots | §6.1–6.4 (bootstrap, IC95 descriptivos, subgrupos con solapes, Holm53 × **10** familias McNemar+Holm); §8.4 rotación concreta por índice de fase |
| **3** presupuesto | Suma topes **21 h** / margen **19 h**; transiciones≠reinicios; subsesiones 12 h con pausas **dentro** de 40 h; A3 ≤4 h / 150 pet.; reserva puertas **612**; cascada proveedor/fases/audit/wrapper 800; topes celda A3→A4 |
| **4** rama stack + supervisor | §4.3 ramas A\|B; §11 perfil `jev77`, 18 refs, dry-run/tests antes de A5 |

### R34 aplicado (7-oct-2026)

| Corrección R34 | Reflejo |
|---|---|
| **1** visibles vs ciego | §7.3: criterios separados (1–3 con apéndice/refs visibles; 4 sin inject, hash ciego, margen A01, `response_format` conserva esquema; comunes raw/usage y thinking Qwen) |
| **2** cota 11238 / remanente 762 | §8.1: 11238 = recorrido inicial+puertas+prep.; 762 para `--retry-errors` (≤3 intentos), health de evaluación y contingencias; sin cupo → NO EVALUABLE; §7.6 aclara que los reintentos únicos sí se permiten |

### Host fijado 7-oct

| Decisión | Reflejo |
|---|---|
| JEV-77 completo en **<host>** (`dgx-spark-a`); JEV-76 en paralelo en <host> | §1 / §1.1; §4.1 |
| Todas las celdas (27B, 4B, Q) en <host> | §1.1; §5 |
| Cascada API desde **<host>** (no portátil) | §5.3 |
| Pesos: Qwen en `<ruta-local>`; MedGemma/Gemma vía A2/A3 | §1.1; §2; §11 |
| Imagen `lmsysorg/sglang:qwen38-27b` `0076dffa60b7` (= <host>) candidata rama A | §1.1; §3.1 |
| Preflight `nvidia-smi` / `docker ps` / `free`; no tocar SGLang/ComfyUI ajenos | §1.1; A3 en §9 |
|

### A3/A4 cerrado (7-oct-2026)

| Decisión | Reflejo |
|---|---|
| Rama A confirmada (misma imagen en los 5 checkpoints) | §A3/A4 |
| Args Gemma con `--disable-prefill-cuda-graph`; Qwen = argv jev76 | `CKPTS_77` → manifiesto |
| Plantilla M/G idéntica (sha `7de1c58e208eda46`) — no para A4 | §A3/A4 |
| Topes por celda calibrados: 4×150 + 12×45 + 2×90 = 22 h (R42) | §8.2, `CELLS_77` |
| A01_MARGIN por tokenización: Gemma 304 / Qwen 292 | `CKPTS_77` |
| 18 refs + manifiesto `008c1cdd499b6f92` (R42) | `results/logs/` |

### Enmienda 1 registrada (7-oct-2026)

| Decisión | Reflejo |
|---|---|
| `--constrained-json-disable-any-whitespace` en los 5 ckpts (incidente puerta ciega MedGemma27) | §Enmienda-1, `CKPTS_77`, `MANIFEST_AMENDMENTS` 008c1cdd→8b201bfb |
| Manifiesto recongelado `8b201bfb8b6bd5a7`; anterior archivado | `results/logs/` |
| Puerta FAIL `~7408c35b` inmutable; re-puerta tras restart | §Enmienda-1 |

### Enmienda 2 registrada (8-oct-2026)

| Decisión | Reflejo |
|---|---|
| Sonda ciega: JSON+stop con valores fuera de contrato ≠ FAIL de visibilidad (incidente Gemma3-4B urgency=1300) | §Enmienda-2, `_blind_fails` (solo perfil `jev77`) |
| Manifiesto **sin** cambio (`8b201bfb…`); sin `MANIFEST_AMENDMENTS` nueva | §Enmienda-2 |
| Puerta FAIL `~38d2b866` inmutable; re-puerta tras restart (2/4) del bloque gemma3_4b | §Enmienda-2 ||

### RESULTADOS integrados (8-oct-2026)

| Hecho | Reflejo |
|---|---|
| 18 celdas + cascada completas, 0 errores, 3.658/12.000 pet., 17,98/40 h | §RESULTADOS |
| H1 INCONCLUSA (+9,7 [−1,7; +21,8] IC97,5); H2 REFUTADA (−37,0 [−49,8; −24,9] IC97,5) | §RESULTADOS |
| Enmiendas 1 y 2 aplicadas; desviación NAS acreditada (C1 de R61 cerrada) | §RESULTADOS, `a6/weights_gemma3_4b/` |
| Marcador: MD0, GD0 y la cascada audit | `docs/resultados_runs.txt`, `docs/resultados.md` |
