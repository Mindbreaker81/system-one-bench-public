# JEV-82 — `gpt-6-luna-decisions`: rotación d1 del orden de `department` (sensibilidad al orden)

**BORRADOR pre-registrado el 7-oct-2026, antes de ejecutar nada contra la
API.** Es la prueba pendiente que R51 (revisión de JEV-81) consideró
justificable como test de sensibilidad al orden y que el usuario aprobó en
JEV-82. Datos de partida: run `jev_luna_decisions` (JEV-80, orden canónico
**d0**, 188/194 casos, 6 rechazos del proveedor 502 «refused to answer») y
la primacía confirmada de Qwen3.8-27B en JEV-72 (+35,14 pp, subconjunto
congelado `4e7e2877f27d`). Script de análisis: `jevbench/jev82.py` (solo
stdlib, offline sobre `results/`, no escribe nada). Adaptador: opción
`choice_order` nueva en `jevbench/adapters/jev.py` (misma semántica que en
`llm`; `d0` = cuerpo byte a byte idéntico a no pasarla).

Qué cambia y qué no: solo el **orden de las claves de
`criteria`** de la pregunta `department` en el JSON `questions` de la
petición (d1 = consulta_externa, urgencias, admin, bronchoscopia).
Etiquetas, textos de criterio, casos y GT intactos; la respuesta se sigue
leyendo por etiqueta — el `choice` devuelto mapea al literal original sin
conversión. En el endpoint de decisiones el orden viaja en el payload; el
render del prompt es interno del proveedor (no hay puerta de visibilidad
posible: la procedencia del orden la acredita el `perm_sha256`/`choice_order`
que el adaptador guarda en `meta`, verificado por fase en la validación).

## 1. Validación previa (obligatoria; aborta sin computar)

- Ambos runs cubren las 11 fases con todos los ids vigentes (la excepción
  declarada de `P02` aplica igual que en JEV-81: extra permitido, nunca
  evaluado). Ausencias o ids ajenos = error de entrada.
- `questions_hash` de cada fase igual al vigente en ambos runs — el hash
  ordena claves (`sort_keys`), así que **no** distingue d0 de d1; el orden
  aplicado se acredita aparte:
  - run d1: `meta.opts.choice_order == "department:d1"`,
    `meta.choice_order` resuelto al orden d1 y `meta.perm_sha256` igual al
    de la rotación aplicada sobre las preguntas vigentes — valores por fase
    (congelados ahora): `15f6174736a0` en las 8 fases con `department`
    (triage_es/en, triage_ext_es/en, adv1–5), `c68c21f92897` en papers32 y
    `e54d4e3d2038` en ood (sin department: no-op, hash del orden canónico);
  - run d0 (`jev_luna_decisions`): `opts.choice_order` ausente o
    `department:d0`; si declara `perm_sha256`, debe ser el canónico
    (`c656cec9e1d1` triaje/adv, `c68c21f92897` papers32, `e54d4e3d2038` ood).
- El run d1 declara en **cada fase** `meta.cost_guard = {"max_case_cost":
  0.01, "max_cost": 0.05}` — la guarda de adquisición es parte del
  protocolo, no una métrica post hoc (el run d0 es histórico, anterior a
  la guarda, y se admite sin ella).
- Vectores pareados completos (contrato de la batería por pregunta, como en
  la repetibilidad de JEV-81): incompletos simétricos o tipo cambiado =
  error de entrada.
- El subconjunto de primacía se recalcula por su regla congelada (regex
  `\b(?:ebus|broncoscop\w*|bronchoscop\w*)\b` ignore-case sobre `state` +
  GT `department != bronchoscopia`) **solo para verificar** que su sha256
  sigue siendo `4e7e2877f27d` (37 registros / 35 ids). Si difiere, se aborta:
  el GT o los casos cambiaron y el subconjunto no se redefine tras inferir.

## 2. Adquisición (política fija; misma que JEV-80/81)

1 pasada completa + **1** `--retry-errors` por bloque. La API de decisiones
no admite temperature ni seed. Si aparecen rechazos nuevos no se decide
reintentar más después de verlos.

**Pasadas frente a intentos HTTP (fijado en R56):** cada `decide` del
adaptador `jev` hace hasta `retries` peticiones HTTP ante errores de
transporte o HTTP (incluido el 502 «refused to answer»). Se fija
`--opt retries=3` **explícito**, igual al valor por defecto con el que se
adquirió d0 en JEV-80 — cambiarlo haría distinta la política de
adquisición entre los dos lados del contraste. Así, un caso de una pasada
= 1 decide = 1–3 intentos HTTP, y `--retry-errors` es una pasada sobre los
casos almacenados con error (no un intento HTTP más dentro del mismo
decide): un rechazo persistente puede costar 3 intentos en la pasada
inicial y 3 más en el reintento. **Contabilidad:** el registro final de un
caso solo guarda el coste del intento que respondió; los intentos fallidos
y el error sustituido por `--retry-errors` no dejan coste registrado, así
que la suma de registros finales es una **cota inferior** del coste real
de adquisición, no su total.

**Guarda de coste efectiva** (desigualdades exactas; las aplica
`jevbench.run` DESPUÉS de registrar cada caso y ANTES de abrir el
siguiente — y también ANTES del primer caso de cada fase con trabajo
pendiente, porque el acumulado durable del run ya puede venir superado de
una invocación anterior):

- caso con coste registrado > $0,01 → parada (`--max-case-cost 0.01`);
- coste acumulado registrado del run —todas las invocaciones: los dos
  bloques y sus reintentos— > $0,05 → parada (`--max-cost 0.05`).

La parada conserva el progreso (los resultados se guardan por caso) y deja
la causa en `meta.cost_stop`; cada fase declara `meta.cost_guard` con los
topes. **Qué hacer tras una parada por presupuesto agotado:** repetir el
mismo comando **no elude** el presupuesto — la comprobación previa abre 0
peticiones nuevas y solo renueva `meta.cost_stop`. Continuar exige
ampliar los topes, lo que requiere **nueva aprobación** y re-pre-registro
del cambio; no está contemplado en esta política. Una parada por tope por
caso sí permite reanudar el resto si el coste anómalo fue puntual — pero
solo tras documentarlo. **Costes desconocidos:** un caso cuyo registro no
informa coste no dispara ninguna de las dos desigualdades ni suma al
acumulado; se cuentan y se listan aparte en el análisis (§3.7) —
limitación declarada si el endpoint dejara de informar `usage.cost`.
Estimación ~$0,02 total (la pasada JEV-80 costó $0,0194).

```sh
python3 -m jevbench.run jev --run jev_luna_decisions_d1 \
    --opt provider=openrouter --opt model=openai/gpt-6-luna-decisions \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new
python3 -m jevbench.run jev --run jev_luna_decisions_d1 \
    --opt provider=openrouter --opt model=openai/gpt-6-luna-decisions \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5
python3 -m jevbench.run jev --run jev_luna_decisions_d1 \
    --opt provider=openrouter --opt model=openai/gpt-6-luna-decisions \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases all+new --retry-errors
python3 -m jevbench.run jev --run jev_luna_decisions_d1 \
    --opt provider=openrouter --opt model=openai/gpt-6-luna-decisions \
    --opt choice_order=department:d1 --opt retries=3 \
    --max-case-cost 0.01 --max-cost 0.05 --phases adv4,adv5 --retry-errors
```

## 3. Contrastes y reglas de lectura (congeladas)

Contraste d1 (`jev_luna_decisions_d1`) frente a d0 (`jev_luna_decisions`):

```sh
python3 -m jevbench.jev82 analyze            # imprime el informe
python3 -m jevbench.jev82 analyze --json /ruta/jev82_analysis.json
```

1. **Cobertura y rechazos:** casos por run; errores por `error_kind`
   (rejection/timeout/transport/local, desglosados — criterio de JEV-81);
   listas `both` / `only_d0` / `only_d1`. **Regla fijada para rechazos
   distintos:** un caso con error en cualquiera de los dos runs sale de
   todos los contrastes pareados (acuerdo, Δp, primacía) y la fase deja de
   ser completa para el ajustado; las listas se publican explícitas. No se
   imputan rechazos a 0 puntos en este análisis (esa sensibilidad fue la de
   JEV-80 y queda fuera).
2. **Δ ajustado (d1 − d0)** sobre las **fases completas en ambos runs**
   (intersección; `paired_delta` de `qwen_session`: peso igual por fase,
   baselines fijas, bootstrap pareado por clusters ES/EN + PMID, 10 000
   réplicas, semilla 271828, IC95). Si los conjuntos de fases completas
   difieren, el Δ sigue saliendo de la intersección y la diferencia se
   declara (`same_phases=false`); los ajustados por run sobre sus propias
   fases se reportan aparte. **Lectura: descriptiva** — no hay umbral de
   «demasiada sensibilidad» fijable a priori; se reporta magnitud e IC95 y
   se compara descriptivamente con el rango d0–d3 medido en Qwen (9,6
   puntos, JEV-72). Un IC que incluye 0 no prueba estabilidad (no hay
   margen de equivalencia fijado).
3. **Acuerdo de decisiones pareado** (decisión por criterio del scorer,
   misma convención que S202/JEV-81) con IC95 Clopper-Pearson. Referencia
   **descriptiva** ≥ 97 % sobre la estimación puntual — es la convención de
   repetibilidad, no un umbral de veredicto: la sensibilidad al orden no es
   una afirmación con umbral sino una magnitud.
4. **Primacía (única afirmación con umbral, regla JEV-72 intacta):** Δ de
   errores de `department` (d0 − d1) en el subconjunto congelado, en pp,
   sobre los registros respondidos por ambos runs; IC95 bootstrap por
   clusters + McNemar con convención ES (una versión por caso traducido) y
   Holm sobre la familia {d0vsd1 en todos los casos, primacía}.
   **CONFIRMADA** si Δ ≥ 5 pp ∧ L95 > 0 ∧ primacía significativa tras Holm;
   **REFUTADA** si U95 < 5; en otro caso **INCONCLUSA**. Justificación del
   umbral: es la misma pregunta instrumental ya validada en JEV-72 (¿la
   opción-trampa primera cuesta errores?), así que reproduce la regla tal
   cual en vez de inventar otra — el resultado dice si luna-decisions
   muestra la firma de primacía que confirmó Qwen.
5. **Δ de probabilidades:** media y máximo |Δp| sobre los componentes
   escalares comunes de los éxitos pareados, alineados **por etiqueta**
   (las probabilities llevan la etiqueta, no la posición — invariante al
   orden). Descriptivo.
6. **Versión servida:** los éxitos **pareados** se identifican primero con
   el universo validado (sin error en ninguno de los dos runs) y se toma el
   `model` de cada lado; las versiones **ausentes se conservan y se listan
   por id** (`unknown`), no se omiten. `same_model` solo es true si hay
   ≥ 1 par con versión conocida e igual y **cero** ausencias ni
   discrepancias; en otro caso el contraste se reporta como «entre
   versiones» o «versión desconocida», no como sensibilidad del mismo
   modelo.
7. **Coste:** suma de lo registrado por run (desconocidos aparte, nunca
   cero) y máximo por caso; casos > $0,01 marcados en `over_cap`. Es una
   **cota inferior** del coste de adquisición (los intentos fallidos no
   dejan coste registrado, §2); la guarda efectiva ya es responsabilidad
   de la adquisición (`meta.cost_guard`/`meta.cost_stop`).

Todo lo no fijado aquí (otros órdenes d2/d3, rotación de otras preguntas,
subconjuntos alternativos) es **EXPLORATORIO** y se dirá así.

## 4. Lo que no se hace en esta prueba

| Descartado | Motivo |
|---|---|
| d2/d3 u otras preguntas | La sensibilidad se acota a una rotación; los demás órdenes de Qwen no se replican |
| Cascada o uso como revisor | Fuera del alcance aprobado (R51 ya los valoró no justificados por los datos) |
| Puerta de visibilidad/tokens | El endpoint de decisiones no expone el prompt renderizado; la procedencia la acredita perm_sha256 |
| Repetir d0 | `jev_luna_decisions` + su réplica r2 ya miden ese punto (934/934 decisiones iguales) |

## Registro de cambios

| Fecha | Cambio |
|---|---|
| 7-oct-2026 | Pre-registro inicial + `choice_order` en el adaptador `jev` (tests offline: d0 byte a byte, d1 rotado) + `jevbench/jev82.py` con tests sintéticos |
| 7-oct-2026 | Correcciones R56 (Codex): versiones ausentes conservadas y listadas por id sobre los éxitos pareados (`same_model` exige ≥ 1 par conocido y 0 desconocidos/discrepancias); guarda de coste **efectiva** `--max-case-cost 0.01` / `--max-cost 0.05` en `jevbench.run` (parada tras registrar cada caso y antes del siguiente, con `meta.cost_guard`/`meta.cost_stop` y política explícita de costes desconocidos); política de intentos HTTP fijada (`--opt retries=3`, igual que d0) y nota de cota inferior de coste |
| 7-oct-2026 | Corrección R56b (Codex): la guarda acumulada se comprueba también **antes** del primer caso de cada fase con trabajo pendiente — reanudar o entrar al segundo bloque con el run ya sobre el tope abre **0 peticiones** (`cost_stop.before_requests`); instrucción post-parada aclarada: repetir el comando no elude el presupuesto y ampliarlo exige nueva aprobación |

> **Errata (7-oct, R57):** hay **nueve** fases con `department` (triaje ES/EN, triaje ext ES/EN, adv1–5), no ocho
> como dice el §1; papers32 y ood completan las once. Los hashes se validaron en las once fases y la rotación se
> aplicó en las nueve correspondientes. Sin efecto en la ejecución ni en el análisis; el texto congelado de arriba
> no se reescribe.

## RESULTADOS (7-oct)

Ejecución T18 (rev. R57 de Codex: adquisición, datos y clasificación **aptos y reproducibles**; su `analyze` offline
reprodujo el JSON exacto). Sin desviaciones: 4 comandos exactos del §2 en orden, 202 llamadas lógicas a `decide`
(154+40+4+4), sin `cost_stop`; validaciones de universo, hashes, procedencia del orden y subconjunto de primacía
pasadas sin esquivarlas. Salidas completas en `<ruta-local>`; informe corregido `T18_corrected.md`.

- **Cobertura y rechazos:** d0 188/194, d1 **186/194**. Compartidos B05, C08, D05, D07, E01, E02; **solo d1:
  adv3/C05_polite_threat y triage_ext_es/T40_amenaza_personal** (both=6, solo d0=0, solo d1=2; todos 502
  «refused to answer»). Los 8 casos fuera de los contrastes pareados, sin imputación; fases completas: d0 seis
  puntuables, d1 cinco (`same_phases=false`).
- **Versión:** 186 pares conocidos, 0 discrepancias, 0 ausencias → `same_model=true`
  (`openai/gpt-6-luna-decisions-20261006` en ambos lados).
- **Δ ajustado (d1−d0): 0,00 [IC95 0,00–0,00]** en las cinco fases completas comunes (triage_es, triage_en,
  papers32, adv1, triage_ext_en; 10 000 réplicas, semilla 271828) — los puntos por caso coinciden; no demuestra
  estabilidad ni equivalencia general. Ajustados propios: d0 47,70 (6 fases), d1 42,15 (5 fases) — conjuntos
  distintos, sin contraste.
- **Acuerdo: 918/924 = 99,35 %** [IC95 CP 98,59–99,76] sobre los 186 éxitos pareados; ≥97 % puntual superado
  (descriptivo). Discordancias: `department` en B01, B07, C03, D01, D09 y D20.
- **Primacía (≥5 pp, subconjunto congelado `4e7e2877f27d`, 32 registros pareados): Δ errores d0−d1 = −12,50 pp
  [IC95 −25,81 a −2,94] → REFUTADA por U95 < 5.** Observados 7 errores (d0) frente a 11 (d1); McNemar b=4, c=0
  (30 unidades, convención ES), p=0,125; Holm {todos, primacía} = 0,0625/0,125. La falta de significación no
  prueba ausencia de efecto de orden; 7/11 es descripción, no deterioro general demostrado.
- **Δp por etiqueta:** media 0,0082, máx 0,72 (2071 componentes).
- **Coste registrado (cota inferior):** d0 $0,0193778 (188), d1 $0,0192143 (186); máx $0,000669/caso; rechazos sin
  importe; guarda no disparada.

**Conclusión (las 6 líneas de R57):** (1) la adquisición d1 siguió las cuatro pasadas previstas sin parada de coste
y respondió 186/194, frente a 188/194 en d0; (2) persisten seis rechazos compartidos y aparecen dos nuevos en d1,
y los ocho casos se excluyen de los contrastes pareados; (3) en las cinco fases completas comunes los puntos por
caso coinciden y Δ ajustado es 0,00 [0,00; 0,00] — sin demostrar estabilidad ni equivalencia general; (4) entre los
186 éxitos pareados del mismo identificador de modelo coinciden 918/924 decisiones, seis de `department` cambian y
Δp máx 0,72; (5) en los 32 registros pareados del subconjunto, la primacía ≥5 pp queda REFUTADA por U95<5, y los
7/11 errores y p Holm=0,125 no prueban ausencia de efecto de orden ni deterioro general; (6) el coste registrado d1
es $0,0192143, cota inferior — sin comparar directamente 47,70 con 42,15 ni atribuir causalmente los rechazos
nuevos al orden.
