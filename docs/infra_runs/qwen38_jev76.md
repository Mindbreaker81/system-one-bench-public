# JEV-76 — Factorial discrete × thinking de Qwen3.8-27B FP8 en <host> (8 celdas, d0+d1)

Manifiesto del experimento: **BORRADOR — SIN CONGELAR**. Este texto fija el
diseño para revisión (Codex) y aprobación del usuario; los valores que dependen
de ejecución quedan marcados PENDIENTE y se añadirán como apéndice al congelar,
sin alterar lo aprobado. **Nada de esto se ejecuta sin aprobación**: ni smoke,
ni puertas, ni inferencia.

Issue: <<tracker> (decisión del
usuario del 7-oct-2026 en su comentario: **alcance (b)**). Diseño revisado:
`<ruta-local>` §JEV-76. Precedente directo de formato,
stack y lecciones: `docs/infra_runs/qwen38_jev68.md` (resultados en su sección
RESULTADOS).

## Estado del congelado

- **BORRADOR.** Pendiente de: revisión de Codex, aprobación del usuario,
  dry-run con las referencias tokenizer ya construidas (§11), commit del
  manifiesto por el operador y arranque autorizado de <host>.
- Base del repo: misma batería congelada que JEV-68 (GT v4; la versión
  1.0.0 es la **histórica de la batería** con la que se midió JEV-68): la
  **versión efectiva del harness** al ejecutar es `jevbench.__version__`
  (actualmente **1.1.0**, con el perfil `jev76`; se congela la efectiva en
  el manifiesto, no se infiere de la etiqueta histórica). **194 casos**,
  `papers32` = 31, `questions_hash` por fase sin cambios.
- Harness: `jevbench/qwen_session.py` ampliado con el **perfil `jev76`**
  (celdas, calendario, estado, manifiesto, puertas, referencias y análisis
  propios). La sesión JEV-68 (`results/logs/qwen_session.json`,
  `qwen_manifest*.json`, `gate_qwen_*`, sus runs) **no se toca**: no es una
  reanudación ni una extensión de su Enmienda 2.

## 1. Resumen

JEV-68/71 midió tres casillas del factorial modo×thinking en d0 más prob+on
en d1: F0 49.57, T0 61.26, D0 62.42, T1 64.92 (ajustado GT v4). Faltaba
**discrete + thinking (DT)** y, confirmada la primacía de `department` (P72:
el ajustado no es invariante al orden), un factorial solo en d0 dejaría la
conclusión coja. Alcance elegido **(b)**: factorial fresco completo en **d0
y d1 — 8 celdas** en la misma sesión, con controles frescos; los datos de
JEV-68/71 se conservan solo como referencia descriptiva.

Hipótesis primarias (umbral +5, por orden, falsables):

- **H1:** `DT − D ≥ 5` puntos de ajustado.
- **H2:** `DT − T ≥ 5` puntos de ajustado.

Es decir: ¿añadir thinking a discrete mejora ≥5 sobre discrete, y ≥5 sobre
prob+thinking?

Coste: **0 USD de API externa**. Electricidad/hardware **no medidos** (se
informarán tiempo de sesión y tokens; nunca «coste total cero»).

## 2. Decisiones fijadas en este borrador

1. **Batería GT v4 idéntica** (194 casos, mismas once fases, mismo orden de
   fases que JEV-67/68, mismas preguntas, criterios y scorer — regla 1 del
   repo). Sin entrenamiento ni selección con los resultados nuevos.
2. **Host único <host> (`dgx-spark-b`, GB10) — fijado el 7-oct por el usuario**
   dentro del reparto paralelo de servidores: **JEV-77 corre a la vez en
   <host>** (`dgx-spark-a`). Mismo stack que JEV-68 §3; la imagen
   `lmsysorg/sglang:qwen38-27b` es **idéntica en <host> y <host>** (mismo ID y
   digest). Sin recursos compartidos entre los dos experimentos salvo el
   **NAS de solo lectura** (datos/pesos); el lock del supervisor
   (`results/logs/qwen_session.lock`) es **local a cada repo/host**, así
   que ambas sesiones avanzan en paralelo sin contendérselo. Si <host> está
   ocupado por otros servicios, se pospone (no desalojar nada ajeno ni
   mover el bloque sin revisar este documento).
3. **Sin API externa.** JEV-68/71 no se repite ni se reanuda: es descriptivo.
4. **Sesión nueva, no reanudación.** Estado `qwen_session_jev76.json`,
   manifiesto `qwen_manifest_jev76.json`, puertas `gate_qwen76_<combo>*`,
   referencias `qwen_refs_jev76_<combo>.json` y runs `*_jev76_*` propios.
5. **Sin diagnósticos** (P71.2 pertenece a JEV-68) ni celda S202 en esta
   sesión; el canario sigue en las puertas como observación.

## 3. Servidor: identidad y verificaciones previas

Misma identidad congelada que JEV-68 §3 (cualquier divergencia se documenta
antes de inferir y los históricos quedan como referencia descriptiva):

| Elemento | Valor |
|---|---|
| Host | **<host> `dgx-spark-b`** (fijado 7-oct), aarch64, NVIDIA GB10, 128 GB memoria unificada |
| Imagen | `lmsysorg/sglang:qwen38-27b` — ID `sha256:0076dffa60b7…`, digest `sha256:febfb971…` (idéntica en <host> y <host>) |
| Pesos | `Qwen/Qwen3.8-27B-FP8` @ `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` |
| Copia local | `<ruta-local>` en <host> (67/67 LFS verificados el 6-oct); también disponibles en ai-models `hf/Qwen/Qwen3.8-27B-FP8` |
| Cliente | túnel 18001→8000; `base_url http://127.0.0.1:18001/v1`; modelo servido `qwen3.8-27b-sglang`; `api_key none` |

Antes de arrancar (obligatorio): `nvidia-smi; docker ps; free -g` en <host> —
JEV-77 corre en <host> en paralelo y no le disputa la GPU ni el lock (es
local a cada repo/host), pero no debe haber nada más corriendo en <host>;
verificar que el digest de la imagen sigue siendo `sha256:febfb971…` (si
difiere, parar y documentar el cambio antes de inferir); congelar snapshot
completo (digest, sha256 de `start.sh`, cmdline y config efectiva,
versiones de SGLang/torch/xgrammar/CUDA, `system-one-adapter`/
`typesafe-sdk`, KV/Mamba/MTP y sha del chat template). Espacio reservado
≥ 2 GB para raw/results.

## 4. Configuración común de cliente (bloque congelado de JEV-68 §4)

```
adapter=llm · provider=openai · model=qwen3.8-27b-sglang
base_url=http://127.0.0.1:18001/v1 · api_key=none
structured=true · inject_schema_in_prompt=true · normalize=true
capture_raw=true · retries_malformed=2
max_tokens=16384 · timeout=300 · case_timeout=600 · secuencial
extra_body={"chat_template_kwargs":{"enable_thinking": false|true},
            "temperature":0, "seed":101}
prompt=typesafe · choice_order=department:d0|d1
```

Mismos límites y bloque de cliente en todas las celdas (la comparación
causal es entre celdas frescas de la misma sesión). Thinking **true
explícito**, nunca por omisión; sin `top_p`/`presence_penalty` distintos ni
`reasoning_effort`. Rotación solo de `department` (d0/d1) en prompt y
esquema a la vez; etiquetas, criterios, `score` y GT intactos.

## 5. Celdas y runs (nombres congelados en el borrador)

| Celda | Run | Config | Tope | Puerta |
|---|---|---|---:|---|
| **F0′** | `llm_qwen38_27b_fp8_jev76_off_d0_prob` | prob, off, d0, seed 101 | 90 min | `prob_typesafe_off_d0` |
| **F1′** | `llm_qwen38_27b_fp8_jev76_off_d1_prob` | = F0′ con d1 | 90 min | `prob_typesafe_off_d1` |
| **T0′** | `llm_qwen38_27b_fp8_jev76_on_d0_prob` | = F0′ con thinking true | 210 min | `prob_typesafe_on_d0` |
| **T1′** | `llm_qwen38_27b_fp8_jev76_on_d1_prob` | = F1′ con thinking true | 210 min | `prob_typesafe_on_d1` |
| **D0′** | `llm_qwen38_27b_fp8_jev76_off_d0_disc` | discrete, off, d0, seed 101 | 90 min | `disc_typesafe_off_d0` |
| **D1** | `llm_qwen38_27b_fp8_jev76_off_d1_disc` | = D0′ con d1 | 90 min | `disc_typesafe_off_d1` |
| **DT0** | `llm_qwen38_27b_fp8_jev76_on_d0_disc` | discrete, thinking true, d0 | 210 min | `disc_typesafe_on_d0` |
| **DT1** | `llm_qwen38_27b_fp8_jev76_on_d1_disc` | discrete, thinking true, d1 | 210 min | `disc_typesafe_on_d1` |

Las 8 celdas son **frescas**: aunque F0′/T0′/D0′/F1′/T1′ repitan la
configuración de JEV-68, se ejecutan de nuevo intercaladas en esta sesión
(los contrastes primarios nunca usan los runs históricos). **No se elegirá
el mejor orden ni la mejor celda como marcador oficial.**

## 6. Puertas de visibilidad (bloqueantes) — 8 combos

Una puerta por combo **modo×prompt×thinking×orden** (8 en total), al inicio
de la sesión y tras cualquier reinicio/deriva del servidor. Casos: A01
(adv1), P01 (papers32), receta (ood) visibles, control negativo ciego en A01
y canario conductual (observación). Criterios sobre el primer intento —
mismos que JEV-68 §6 con la corrección de R30:

1. **Cliente**: sha256[:12] del system prompt **precomputado antes de
   responder** igual al observado; apéndice JSON **decodificado** idéntico
   al `response_format.schema`; IDs, instrucciones y criterios completos;
   orden esperado de `department` en prompt **y** esquema.
2. **Motor**: `usage` del primer intento contra la referencia de su combo:
   - prob/off d0 → histórica `llm_qwen38_27b_fp8_nostruct_prob` ±2;
   - prob/off d1 → histórica ±10;
   - **prob/on y discrete/on** → **referencia tokenizer propia** del combo
     (194 casos, ±2), precalculada con `qwen_session refs <combo>
     --tokenizer <checkpoint>` **antes de su puerta**, congelada por hash
     en el manifiesto y archivada íntegra por `gate_id` — nunca derivada
     de la respuesta que valida;
   - **discrete/off** → **offsets por familia medidos por SU puerta** en
     esta sesión (±2 por caso). D1 mide los suyos: **no hereda los de
     D0′** ni los de la puerta de JEV-68.
3. **Control negativo**: A01 struct sin inject, mismo modo/prompt/thinking;
   visible−ciego ≥ 200 tokens y raw del ciego sin preguntas.
4. **Canario**: ambas peticiones acreditadas (raw + usage + cliente +
   thinking), registrado como **observación** (Enmienda 1 de JEV-68).
5. **Thinking efectivo**: declarado en `chat_template_kwargs` == observado
   en el raw (razonamiento crudo o telemetría). En DT la gramática debe
   seguir devolviendo la respuesta discrete válida **y** razonamiento
   observable: una ausencia real de thinking en el raw **no** se etiqueta
   como éxito (falla la puerta/el caso).

Sin `usage` o sin raw → puerta FAIL. Cualquier violación **por caso** durante
la batería invalida el run (`status=invalid_visibility`). Los offsets
históricos de off aplicados a DT serían una puerta contra el prompt
equivocado (R30): la implementación ya aplica `token_rule` con la
referencia tokenizer en discrete+on, y los offsets por familia quedan
reservados a discrete/off (en DT los offsets históricos solo podrían
publicarse como descriptivos, nunca como criterio).

Evidencia inmutable por ejecución de puerta, ligada a su `gate_id` y sesión
(`results/gate_qwen76_<combo>[_blind]~<uid>/`), incluida la referencia de
tokens que la autorizó. `> 2 %` de casos sin `usage` en un run ⇒
**NO EVALUABLE**.

## 7. Calendario intercalado (congelado en el borrador)

Bloque de batería: en la fase i el orden de celdas es la rotación `i mod 8`
de `[F0p, DT1, D0p, T1p, F1p, DT0, D1, T0p]` — alterna orden, modo y
thinking para repartir la deriva temporal entre las ocho celdas.
**88 slots** (11 fases × 8 celdas); sin S202 ni diagnósticos. Una sola carga
de pesos y un solo escritor/supervisor; cada celda conserva su run,
presupuesto, `gate_id` y metadatos. Sesiones: id `s81-<fecha-hora>`;
tras un reinicio del servidor, `--new-session` (puertas nuevas; el
presupuesto global **no** se amplía).

## 8. Hipótesis, umbrales y análisis pre-registrado

Método común (idéntico a JEV-68 §8): Δ de ajustado pareado con bootstrap de
**casos completos** agrupados por cluster (traducciones ES/EN por id; papers
por PMID), pesos iguales de fase, baselines originales fijas, **10.000
remuestreos, semilla 271828**. Diez fases del ajustado (ood excluida por
baseline saturada). Una rama con visibilidad inválida, cobertura insuficiente
o tope agotado es **NO EVALUABLE**, nunca «refutada».

| Hipótesis | Contraste | Confirmada | Refutada | IC |
|---|---|---|---|---|
| **H1 d0** | DT0 − D0′ ≥ 5 | L ≥ 5 | U < 5 | 98,75 % |
| **H1 d1** | DT1 − D1 ≥ 5 | L ≥ 5 | U < 5 | 98,75 % |
| **H2 d0** | DT0 − T0′ ≥ 5 | L ≥ 5 | U < 5 | 98,75 % |
| **H2 d1** | DT1 − T1′ ≥ 5 | L ≥ 5 | U < 5 | 98,75 % |

**Multiplicidad: IC98,75 por contraste.** Cuatro afirmaciones primarias;
98,75 % por contraste = Bonferroni sobre 4 ⇒ cobertura familiar ≥ 95 %.
Elegido frente a una corrección simultánea por ser **simple, auditable y
válido bajo dependencia arbitraria** entre los cuatro contrastes (comparten
celdas y clusters); la alternativa solo ganaría algo de amplitud a costa de
congelar un método más complejo. INCONCLUSA en cualquier otro caso.

**Interacción** `I = (DT − T) − (D − F)` por orden: **bootstrap conjunto**
de las cuatro celdas — los mismos clusters remuestreados en cada réplica
(`joint_stat_boot`), IC 95 %, **descriptiva**. Nunca la resta de extremos
de ICs por separado, y sin concluir aditividad porque I cruce el cero (no
hay margen de equivalencia fijado; querer probarla exigiría otro diseño).

**Holm53 aparte**: las 53 celdas fase×pregunta de los cuatro pares de los
primarios (D0′vsDT0, D1vsDT1, T0′vsDT0, T1′vsDT1), descriptivas.

**JEV-68/71 solo descriptivo**: los históricos se reportan bajo el mismo
GTv4 como contexto (F0/T0/D0/T1 junto a los frescos); los contrastes
primarios usan exclusivamente controles frescos porque la sesión/arranque
y el contexto temporal son distintos — el GT es el mismo.

**Evaluabilidad** (auditoría automática, `analyze --profile jev76`):
NO EVALUABLE ante violaciones de tokens/cliente/thinking, casos sin
ejecutar o con error, casos sin puerta válida de su propia sesión,
manifiesto no autorizado, `status=invalid_visibility` o > 2 % sin usage.
Todo el análisis sale del subcomando `analyze` del supervisor.

## 9. Presupuesto, topes y reglas de parada

| Tope | Valor |
|---|---|
| Sesión | **14 h de tiempo acumulado por el supervisor** (`elapsed_s`: suma de las invocaciones `gate`/`run` + la conciliación de peticiones interrumpidas) |
| Arranque | **externo al reloj del supervisor**, acotado a **≤ 45 min por arranque**, registrado aparte en el informe y sujeto a aprobación — el contador no lo carga por sí solo (R33 §P2) |
| Peticiones | **5000 duras**, contabilizando cualquier intento (reintentos, canarios, sondas, `/health`) y reservadas **antes** de abrir cada petición |
| Errores | **3 por fase** y **10 por run**; tras timeout, `/health` (si no responde, parada de sesión) |
| Por celda | off (F0′, F1′, D0′, D1): **90 min**; on (T0′, T1′, DT0, DT1): **210 min** |
| Reintento | único por caso con error (`--retry-errors`); los casos no ejecutados no se rellenan |
| Sin usage | > 2 % de casos del run ⇒ NO EVALUABLE |

**Reloj (política inequívoca, R33 §P2).** El reloj del encargo es el que
implementa el supervisor: `elapsed_s` arranca en 0 en la primera invocación
que toma el lock (`session_begin` de la primera puerta) — **ese es el
evento inicial** — y solo crece durante las invocaciones `gate`/`run` y con
la conciliación de peticiones interrumpidas a media llamada. **No descuenta
el arranque/verificación del servidor ni los intervalos entre comandos o
pausas del operador**: ese tiempo queda fuera del reloj y se registra
aparte. Tras un reinicio del servidor, `--new-session` conserva lo
acumulado (el tope **no** se amplía) y exige puertas nuevas. La parada por
tope la impone el supervisor sobre el acumulado; del arranque externo y de
cualquier interrupción wall responde el operador, que los acota (45 min por
arranque) y los documenta. La semántica del perfil jev68 no cambia.

**Estimación** (con los tiempos medidos en JEV-68 y DT ≈ T como hipótesis
provisional — DT emitir menos JSON no acredita menos razonamiento):
F off ≈ 22 min ×2 + D off ≈ 9 min ×2 + T on ≈ 150–157 min ×2 + DT ≈ 157 min
×2 ≈ **680 min ≈ 11,4 h de casos**; + 8 puertas (≈15–30 min acumulados) ⇒
≈ 11,7–11,9 h contra el tope de 14 h de supervisor. El arranque/verificación
(≤ 45 min por arranque, externo) no carga ese reloj. El margen es fino: si
DT resulta más lento que T o un reinicio consume tiempo acumulado, alguna
celda puede topar su tope y quedar como tal (NO EVALUABLE sus contrastes),
**sin ampliar ningún tope a posteriori**. La suma de topes por celda
(4×90 + 4×210 = 20 h) excede el global: el tope de sesión puede parar antes
de que todas las agoten — resultado incompleto aceptado, publicado como tal.

**Calendario de peticiones** (contra el tope duro de 5000):

| Partida | Cuenta |
|---|---|
| Primarias | 8 celdas × 194 = **1552 evaluaciones** |
| Sondas de puerta | 8 puertas iniciales × 6 (3 visibles + ciego + canario ×2) = **48** |
| Nominal | **1600** |
| Recorrido inicial + puertas iniciales | con reserve de 3 intentos por evaluación (`retries_malformed=2` + 1) ⇒ **≤ 4800**, máximo antes de `--retry-errors`/health/puertas repetidas (R33 §P2) |
| Remanente compartido | **~200** lo comparten `--retry-errors`, sondas `/health` y puertas repetidas (6 sondas nominales cada una, **hasta 18 intentos** con los retries configurados); cada petición se reserva antes de abrirse — sin remanente que permita terminar ⇒ **NO EVALUABLE sin ampliar el tope** |

El «~200» es **ilustrativo** (equivale a ≈16 eventos de timeout × ≤12 sondas
de 10 s en 120 s de espera **solo si no hay otro gasto adicional**): no
garantiza capacidad para todos los errores permitidos ni para una repetición
completa de puertas tras reinicio. Si el remanente no basta, el tope para la
sesión — nunca se amplía.

Parada adicional por memoria insegura o pérdida de visibilidad. Si thinking
agota repetidamente 16384 tokens o el timeout, se publica la limitación sin
subir topes. Celdas incompletas se publican como tales.

## 10. Lo que no se ejecuta (y por qué)

| Descartado | Motivo |
|---|---|
| Reusar celdas de JEV-68/71 como controles | Mezcla sesión/arranque distintos (R30 §1); son referencia descriptiva |
| DT1 aislado sin D1/F1′/T1′ | No permite la interacción ni los contrastes de d1 (R30 §2) |
| Elegir el mejor orden como marcador | La primacía ya está confirmada; el orden se reporta por separado (R30 §2) |
| Probar aditividad | Requeriría margen de equivalencia fijado para I; aquí I es descriptiva (R30 §4) |
| Subir topes o peticiones a posteriori | Regla de parada congelada (R13 §6 y este §9) |
| Réplica en <host>/<host> u otros backends | Fuera de esta sesión |
| API externa de cualquier tipo | Coste USD 0 congelado |
| Entrenamiento o selección con resultados nuevos | Regla 9 del repo |

## 11. PENDIENTE (se congelan al cerrar el dry-run previo a la ejecución)

Sin valores inventados; se añaden como apéndice al congelar:

1. **Comandos exactos** de la sesión (refs ×4 → gate ×8 → run → analyze,
   con `--profile jev76`), tal como los imprime y valida `--dry-run`.
2. **`manifest_sha256`** del plan congelado (cubre opts por celda, 88
   slots con casos, 8 combos, canario y topes).
3. **Referencias tokenizer de los 194 casos** para `prob_typesafe_on_d0`,
   `prob_typesafe_on_d1`, `disc_typesafe_on_d0` y `disc_typesafe_on_d1`
   (`results/logs/qwen_refs_jev76_<combo>.json`: tokenizer, forma de
   render que honra `enable_thinking`, sha del chat template y sha256 de
   cada fichero). Los valores de las referencias prob_on se compararán
   con las archivadas de JEV-68 (mismo render esperado): una diferencia
   se documenta antes de inferir.
4. **`expected_system_prompt_sha256` por fase × combo** y `perm_sha256`
   por orden × familia.
5. **Offsets discrete por familia** de las puertas `disc_typesafe_off_d0`
   y `disc_typesafe_off_d1` (se miden en la puerta en <host> y viajan con
   cada run).
6. **Identidad efectiva del servidor** recreado (§3: digest, versiones,
   cmdline, config, sha del template).
7. **Id de sesión**, `gate_id` de las 8 puertas y conteo real de sondas.

## 12. Implementación del supervisor (hecha; R33: APTO)

`jevbench/qwen_session.py` (perfil `jev76` + corrección R30) y
`tests/test_qwen_session.py` — revisada en R33: **APTO**, sin cambios:

- Perfiles de sesión (`PROFILES`, `--profile`): celdas, calendario base,
  topes, estado, pausa, manifiesto, referencias y directorios de puerta
  propios por perfil; el lock de `qwen_session.lock` se comparte a
  propósito (un solo escritor sobre el mismo servidor). jev68 queda
  byte-idéntico: su `_plan_manifest` sigue dando `26bbda7c05059d26` y su
  `analyze` el mismo `analysis.json`.
- Puerta discrete+thinking: `token_rule` contra la referencia tokenizer
  del combo (±2); los offsets por familia solo se miden en discrete/off.
- Referencias tokenizer de 194 casos por combo `on` (`refs <combo>
  --profile jev76`), archivadas por `gate_id` y congeladas por hash.
- Thinking observado en DT (declarado == observado en el raw, como en
  cualquier combo `on`).
- Análisis factorial (`analyze --profile jev76`): H1/H2 con IC98,75,
  interacción con bootstrap conjunto, Holm53 aparte, JEV-68 descriptivo.
- Tests offline nuevos (puerta DT, D1/off, interacción, procedencia,
  dry-run del calendario, no regresión jev68) — suite en verde.

## 13. Apéndice de congelado (7-oct-2026, preparación técnica aprobada por el usuario)

Resuelve los pendientes del §11 **antes de abrir ninguna petición de batería**. La aprobación de la preparación no autoriza la batería; esa necesita una aprobación aparte.

1. **Servidor (§11.6).**
   - SGLang propio en <host> (`dgx-spark-b`), imagen `0076dffa60b7…` = `lmsysorg/sglang@sha256:febfb971…`, `sglang 0.0.0.dev0+qwen38.27b.g561c8f3`, `torch 2.13.0+cu130`.
   - Pesos `Qwen/Qwen3.8-27B-FP8` @ `017b9c7a…`, desde la copia local de <host>.
   - Mismo comando de arranque que JEV-68 (`QUANT=fp8 PORT=8000 EXTRA_ARGS="--model-path <ruta-local>" ./start.sh`).
   - Arranque: de 07:54:30 a 08:00:04 (5,6 min ≤ 45), fuera del reloj del supervisor.
   - Argumentos completos en `qwen38_jev76/server_identity.json`. Túnel 18001→8000.
2. **Referencias tokenizer (§11.3).** Generadas con `<ruta-local>` (venv-refs, transformers 5.x):
   - `disc_typesafe_on_d0` `8b4237c9bdbe`;
   - `disc_typesafe_on_d1` `b6a695de5b68`;
   - `prob_typesafe_on_d0` `ff48c6a19f93`;
   - `prob_typesafe_on_d1` `a41ebb07ee08`.

   Las `prob_on` coinciden íntegramente con las archivadas de JEV-68 (11/11 entradas): el render no ha cambiado.
3. **Manifiesto (§11.2):** `manifest_sha256 = e4a198a26cefaba9` (`results/logs/qwen_manifest_jev76.json`), sin cambios entre la construcción de las referencias y el cierre de las puertas.
4. **Sesión y puertas (§11.7).**
   - Sesión `s81f-20261007-0800`. Las ocho puertas dan **PASS** (08:00–08:23). Log en `qwen38_jev76/gates.log`.
   - `gate_id`:

     | Combo | `gate_id` |
     |---|---|
     | prob off d0 | `~85623aa4` |
     | prob off d1 | `~2950ae4c` |
     | disc off d0 | `~9af8648d` |
     | disc off d1 | `~35e447cd` |
     | prob on d0 | `~f3d2377c` |
     | prob on d1 | `~6332a9c4` |
     | disc on d0 | `~5a642df0` |
     | disc on d1 | `~d5936383` |

     Prefijo completo: `gate_qwen76_<combo>@2026-10-07T08:..`.
   - **Tokens visibles** (A01 / P01 / receta):

     | Combo | A01 | P01 | receta |
     |---|---|---|---|
     | prob off | 806 | 1946 | 669 |
     | disc off | 515 | 1606 | 453 |
     | prob on | 842 | 1982 | 705 |
     | disc on | 551 | 1642 | 489 |

     Prob off y prob on son iguales a JEV-68.
   - **Canario (observacional, Enmienda 1):**
     - prob: el ciego se separa (1,0 / 0,0);
     - discrete: el ciego elige el canario, igual que en JEV-68;
     - disc on d1: la visible eligió `ruta_admin`.

     Solo se registra; no bloquea.
5. **Contadores al congelar:** `elapsed_s = 1809` (30,2 min de puertas) y 48 peticiones (8 × 6 sondas) de los 14 h / 5.000.
6. **Comandos (§11.1)**, tal como los imprime `run --profile jev76 --dry-run`:
   - `python3 -m jevbench.qwen_session run --session s81f-20261007-0800 --profile jev76`
   - después, `analyze --profile jev76`.

## Registro de cambios

- **Borrador inicial** (7-oct-2026, T8): alcance (b), 8 celdas, H1/H2,
  IC98,75, I conjunta, topes 14 h/5000.
- **R33 aplicado** (7-oct-2026): §9 — el reloj de 14 h es tiempo
  acumulado del supervisor (evento inicial, pausas/reinicios y
  responsable de la parada definidos; arranque externo ≤45 min por
  arranque, registrado aparte); calendario de peticiones — «≤4800»
  rotulado como máximo del recorrido inicial y las puertas iniciales,
  con `--retry-errors`/health/puertas repetidas compartiendo el
  remanente hasta 5000 (≈16×12 health solo ilustrativo); §8 — los
  históricos se reportan bajo el mismo GTv4 como contexto (los
  contrastes usan controles frescos por sesión/contexto, no por GT);
  cabecera — distinguida la versión histórica de la batería (1.0.0) de
  la efectiva del harness (1.1.0, a congelar). Sigue en **BORRADOR —
  SIN CONGELAR**.
- **Host fijado 7-oct** (decisión del usuario, reparto paralelo):
  §2/§3 — **JEV-76 en <host>** (`dgx-spark-b`) y JEV-77 a la vez en <host>;
  imagen idéntica en ambos, pesos locales en <host> (también en ai-models
  `hf/Qwen/Qwen3.8-27B-FP8`); sin recursos compartidos salvo el NAS de
  solo lectura; el lock del supervisor es local a cada repo/host.
- **Congelado 7-oct** (§13): manifiesto `e4a198a26cefaba9`, ocho puertas PASS, sesión `s81f-20261007-0800`.

# RESULTADOS (post-ejecución, 7-oct-2026)

Sesión `s81f-20261007-0800` en <host> (SGLang FP8 propio; identidad del servidor congelada en §13,
sin divergencias). Batería intercalada ~08:47 → ~19:00 (hora del host cliente); servidor parado al
terminar. Análisis: `qwen38_jev76/analysis.{txt,json}` (`qwen_session analyze --profile jev76`,
10 000 réplicas, semilla 271828).

**Revisión.** Codex R53: **APTO** — sin correcciones bloqueantes en resultados, procedencia ni
análisis; auditó los 1 552 casos y las 8 puertas (raw requests/responses), reconstruyó el
manifiesto congelado (`e4a198a26cefaba9`) y reprodujo `analysis.json` byte a byte como objeto JSON
con una copia aislada del código (`<ruta-local>`).

## Ejecución y auditoría

- **Cobertura:** 1 552/1 552 casos (8 celdas × 194; 88 slots = 8 celdas × 11 fases), 0 errores,
  0 reintentos; commit `0813da4` declarado en los 88 JSON.
- **Peticiones:** 1 600 contabilizadas = 1 552 de batería + 48 de puertas (3 visibles + 1 ciego +
  2 de canario por cada una de las 8 puertas). Por debajo del tope duro de 5 000.
- **Reloj del supervisor:** `elapsed_s = 39 188,05` (**10,89 h**, frente al tope de 14 h). Las celdas
  acumulan 37 373,98 s; los 1 814,07 s restantes corresponden a tiempo contabilizado fuera de las
  celdas (es el reloj acumulado del supervisor, no horas de pared ni consumo eléctrico).
- **Thinking:** declarado on/off en cada petición y coincidente con lo observado en raw/telemetría;
  los 1 552 intentos terminan en `stop`, sin truncado. Temperatura 0, seed 101, máximo 16 384.
- **Vectores crudos nulos:** 2 en un único caso de F0′ (`adv2/B07_maintenance_spoof`, `department`
  y `urgency`), mismo caso que en JEV-68; recogidos por el análisis, no son errores de ejecución.
  Ningún vector crudo uniforme.
- **Estado final:** `pending=null`, una sola sesión, listas de reintentos vacías. El canario queda
  como observación conforme a la Enmienda 1 (en discrete el ciego elige el canario, como en JEV-68;
  no invalida las comprobaciones de visibilidad).

## Ajustado por celda (GT v4, 194 casos; mayoría trivial = 0)

| Celda | Config | Ajustado | Minutos | Tope min |
|---|---|---:|---:|---:|
| *Mayoría trivial* | — | 0,00 | — | — |
| F0′ | prob · off · d0 | 50,08 | 23,05 | 90 |
| T0′ | prob · on · d0 | 58,71 | 155,80 | 210 |
| D0′ | discrete · off · d0 | 63,04 | 8,98 | 90 |
| **DT0** | discrete · on · d0 | **59,56** | 123,38 | 210 |
| F1′ | prob · off · d1 | 57,56 | 22,90 | 90 |
| T1′ | prob · on · d1 | 64,12 | 161,84 | 210 |
| D1 | discrete · off · d1 | 61,05 | 8,99 | 90 |
| **DT1** | discrete · on · d1 | **55,48** | 117,96 | 210 |

## Clasificación pre-registrada (IC 98,75 % por contraste; Bonferroni ×4)

| Hipótesis | Contraste | Estimación e IC98,75 | Clasificación |
|---|---|---|---|
| H1 d0 | DT0 − D0′ ≥ +5 | −3,483 [−11,385; +3,624] | **REFUTADA** (U < +5) |
| H1 d1 | DT1 − D1 ≥ +5 | −5,579 [−14,818; +2,590] | **REFUTADA** (U < +5) |
| H2 d0 | DT0 − T0′ ≥ +5 | +0,851 [−5,185; +6,749] | **INCONCLUSA** (el IC incluye +5) |
| H2 d1 | DT1 − T1′ ≥ +5 | −8,647 [−18,085; −1,944] | **REFUTADA** (U < +5) |

Ambos intervalos de H1 incluyen cero: no demuestran deterioro por thinking sobre discrete ni
equivalencia entre tratamientos. H2 d1 tiene además todo su intervalo por debajo de cero, referido
exclusivamente a discrete frente a prob cuando thinking está activado en d1.

**Interacción** `I = (DT − T) − (D − F)` (bootstrap conjunto de las cuatro celdas, mismos
remuestreos; descriptiva, fuera de la familia confirmatoria): d0 **−12,112** [IC95 −26,220; −0,655];
d1 **−12,146** [−24,898; −1,350]. No se calcula restando extremos de intervalos separados.

**Holm 53 celdas** (descriptivo, aparte): 0 celdas significativas en cada uno de los cuatro pares
(D0′vsDT0, D1vsDT1, T0′vsDT0, T1vsDT1).

## Latencia y tokens por celda (coste API = 0: local sin facturación)

| Celda | n | ms media | ms mediana | tokens prompt | tokens completion | tokens razonamiento |
|---|---:|---:|---:|---:|---:|---:|
| F0′ | 194 | 7 119 | 6 426 | 201 178 | 29 720 | 0 |
| T0′ | 194 | 48 176 | 43 606 | 208 162 | 164 627 | 138 909 |
| D0′ | 194 | 2 771 | 2 708 | 143 430 | 10 352 | 0 |
| DT0 | 194 | 38 150 | 26 737 | 150 414 | 120 497 | 114 953 |
| F1′ | 194 | 7 072 | 6 422 | 201 178 | 29 589 | 0 |
| T1′ | 194 | 50 041 | 44 872 | 208 162 | 170 315 | 143 809 |
| D1 | 194 | 2 773 | 2 712 | 143 430 | 10 352 | 0 |
| DT1 | 194 | 36 475 | 27 222 | 150 414 | 116 355 | 110 745 |

Thinking multiplica la latencia media: ×13,77 (d0) / ×13,15 (d1) sobre discrete y ×6,77 / ×7,08
sobre prob. Descomposición de los tokens de completion: DT0 emite 120 497 (114 953 de razonamiento
+ 5 544 restantes) frente a 10 352 de D0′ — Δcompletion +110 145 = +114 953 de razonamiento − 4 808
restantes; en d1, DT1 emite 116 355 (110 745 + 5 610) frente a 10 352 de D1 — Δ +106 003 =
+110 745 − 4 742.

## Controles frescos y referencia histórica (descriptiva)

Los contrastes primarios usan exclusivamente las ocho celdas frescas de esta sesión. JEV-68/71
(mismo GT v4, otra sesión/arranque) solo como contexto: d0 F/T/D = 49,57 / 61,26 / 62,42 y d1 F/T =
58,41 / 64,92 — en la misma zona que los controles frescos de JEV-76 (50,08 / 58,71 / 63,04 en d0;
57,56 / 64,12 en d1). No sustituyen controles ni sirven para elegir un orden ganador.

## Conclusiones

1. El factorial fresco se completó en ambos órdenes: 8×194 casos, sin errores y dentro de los
   presupuestos.
2. Thinking sobre discrete no alcanza la mejora pre-registrada de ≥5 puntos en d0 ni d1; ambas H1
   quedan refutadas.
3. Los intervalos de H1 incluyen cero: no permiten afirmar que thinking empeore discrete ni que
   ambos sean equivalentes.
4. Discrete frente a prob con thinking es inconcluso para ≥5 en d0; en d1 se refuta ese umbral y el
   contraste favorece prob.
5. La interacción estimada es aproximadamente −12,1 puntos en ambos órdenes, como resultado
   descriptivo del factorial.
6. Thinking aumenta la latencia media observada: ×13,77/×13,15 sobre discrete y ×6,77/×7,08 sobre
   prob; facturación API local cero no implica coste total cero.
7. Las referencias históricas y Holm son descriptivos; las conclusiones se limitan a estos casos,
   modelo, sesión y dos órdenes fijados.

**Evidencias:** `docs/infra_runs/qwen38_jev76/analysis.{txt,json}`, `gates.log`, `run.log`,
`server_identity.json`; runs `results/llm_qwen38_27b_fp8_jev76_{off,on}_d{0,1}_{prob,disc}/` y
puertas `results/gate_qwen76_*/`. Revisión: `<ruta-local>` (APTO).
