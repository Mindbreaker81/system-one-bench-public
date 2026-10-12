# Réplica confirmatoria de los cierres congelados bajo GT v5 (JEV-100)

**Estado: PRE-REGISTRO congelado el 11-oct-2026, antes de ejecutar ningún
analizador con GT v5.** Los resultados se añaden en §RESULTADOS sin modificar
esta parte.

## Motivo y estatus

Los análisis confirmatorios se cerraron con GT v4 (`FROZEN_GT` en
`jevbench/attest.py`); sus veredictos son hechos históricos ligados a ese GT y
no se rescriben. La revisión humana del 11-oct (88 campos, 23 cambios; ver
`docs/validacion_gt_v5.md`) crea GT v5. Este experimento pre-registra una
**réplica nueva**: las mismas hipótesis, con sus criterios verbatim, evaluadas
contra GT v5. El veredicto de esta réplica es el confirmatorio vigente bajo
v5; los cierres v4 quedan como históricos.

Reglas:

- **Sin inferencia.** Se re-analizan los mismos runs almacenados; sus
  respuestas y probabilidades no cambian (3492 JSON verificados por hash).
- **Mismo cómputo.** Se ejecutan los comandos exactos registrados en
  `docs/auditorias/<exp>.json` (campo `command`), sin `JEVBENCH_GT`
  (el GT vigente es v5). Las salidas se guardan íntegras en
  `docs/experimentos/gt_v5_confirmatorio/salidas/`.
- **Criterios verbatim.** Umbrales, subconjuntos congelados (p. ej. el de
  primacía, sha `4e7e2877f27d`), familias Holm y exclusiones heredadas de los
  pre-registros originales, sin ajuste posterior.
- **Se reporta todo.** Toda hipótesis listada abajo se reporta con su
  clasificación (CONFIRMADA / REFUTADA / INCONCLUSA / NO EVALUABLE), igual que
  en el cierre v4; ninguna línea se añade ni se omite tras ver las salidas.
- **Declaración de ceguera.** Las puntuaciones v5 del marcador ya eran
  públicas al fijar este pre-registro; lo que se congela es la lista completa
  de hipótesis y los criterios heredados verbatim. El GT v5 se construyó sin
  mostrar predicciones de modelo (anotación a ciegas + adjudicación humana),
  así que la réplica no está contaminada por los resultados.
- **Verificación independiente.** Un segundo agente (Grok) extrae los
  veredictos de las salidas guardadas y contrasta cada criterio contra este
  pre-registro; discrepancias se documentan en §RESULTADOS.

## Clasificación de hipótesis

Cada hipótesis se etiqueta **GT-dependiente** (su criterio lee etiquetas del
GT: acierto, ajustado, Brier, errores contra GT, TP/FP contra el campo
`manipulation`, McNemar/Holm sobre errores) o **GT-invariante** (acuerdo entre
runs, nulos/malformados, latencia, distribución de respuestas, cambios de
etiqueta entre variantes). Las GT-invariantes se re-ejecutan igualmente: si el
analizador cambiara su valor, sería una señal de que lee GT más de lo creído.

| Exp | Hipótesis GT-dependientes (se re-evalúan) | GT-invariantes (control) |
|---|---|---|
| jev67 | A1.a ajustado; A1.c errores; A2.b Δ ajustado A2−A1; A3.c Δ acierto choice; B1.a, C1.a ajustado vs A1; B2.a/C2.a fallos papers32; B2.b/C2.b ajustado disc vs prob; B2.c/C2.c errores totales | A1.b, B1.b, C1.b nulos; A2.a, A4 acuerdo; A2.c malformados; A3.a, A3.b; P+fix, P+live |
| jev68 | P68 thinking ≥+5 en ambos órdenes; P72 rango d0–d3 ≤5; P72 primacía ≥5pp (subconjunto congelado); P71.1, P71.2; Holm F0/T0, F1/T1, F0/D0 | S202 acuerdo ≥97 % |
| jev70 | P.a ajustado; P.b Brier noul; P.c errores 1.ª pasada; S1.b |Δ ajustado|; S1.c Brier; Rot1.c Δ acierto; L″.c (Lp3/Lr3/Ld3); alerta `manipulation ≥ 0.5` (≥7/10 y ≤1 FP por set, de `alerta_manipulacion.md`) | P.d1, P.d2, P.e; S1.a, S1.d; R.a, R.b; X.a, X.b; Rot1.a, Rot1.b |
| jev76 | H1 d0/d1 DT−D ≥+5; H2 d0/d1 DT−T ≥+5; Holm 53 (4 familias) | — |
| jev77 | H1 M−G ≥+5 y H2 no-inferioridad ≥−5 (primarios solo d0; d1 y 4B son secundarios); Holm 53 (10 familias) | — |
| jev78 | McNemar–Holm 53 vs jev_v3 | — |
| jev81 | ajustado r1↔r2 (lee GT; el criterio es Δ=0) | repetibilidad r1↔r2 (acuerdo, rechazos, Δp) |
| jev82 | primacía Δ errores department (subconjunto congelado sha `4e7e2877f27d`, 37 registros/35 ids; n pareado 32 tras rechazos; Holm) | — |
| jev84 | criterio ampliado JEV-84 (JEV-32 + alerta en adv3/4/5: ≥7/10 y ≤1 FP por set); Holm R 212; Bloque S (Δ ajustado/Brier) | Holm A (2 comparaciones de alertas); Bloque S (acuerdo ≥95 % / stable_ge_95) |
| jev90_primacy | primacía confirmatoria (exclusiones congeladas) | — |
| jev90_holm53 | Holm 53 vs jev_v3 | — |
| jev90_department_discords | — | veredicto fabricante «0 cambios» (etiquetas del propio modelo entre rotaciones) |

*Nota de revisión (antes de redactar §RESULTADOS): la tabla se completó con la
revisión documental de Cursor — jev81 `ajustado` reclasificado como
GT-dependiente; añadidas Holm A y Bloque S de jev84 y la alerta de jev70;
corregido el tamaño del subconjunto de jev82 y precisados los criterios de
jev68/77/84. Las salidas de `salidas/` se capturaron íntegras antes de esta
corrección y el análisis reporta todas las líneas emitidas, así que ninguna
hipótesis entra o sale por su resultado.*

## Salidas

- Comandos por experimento: los del campo `command` de cada
  `docs/auditorias/<exp>.json`.
- Salidas íntegras: `docs/experimentos/gt_v5_confirmatorio/salidas/<exp>.txt`
  con el código de retorno en `salidas/codigos.json`.
- Cualquier analizador que falle o quede NO EVALUABLE se reporta tal cual.

## §RESULTADOS

Ejecutado el 11-oct-2026 por Droid (delegado): los 12 comandos de
`docs/auditorias/<exp>.json` sin `JEVBENCH_GT` (GT vigente = v5), todos con
`returncode 0` (`salidas/codigos.json`). Salidas íntegras en `salidas/*.txt`.
Verificación independiente de veredictos por Grok:
`verificacion_grok.md` — sin discrepancias de criterio.

### Veredictos que cambian respecto al cierre con GT v4

| Exp | Hipótesis | Cierre v4 | Réplica v5 |
|---|---|---|---|
| jev68 | P72 rango d0–d3 ≤ 5 | INCONCLUSA (rango 9,6 [4,6–17,6]) | **REFUTADA** (rango 10,0 [5,2–18,4], media 53,3) |
| jev77 | Holm M4P1_vs_G4P1 (10.ª familia, descriptiva d1/prob, no primaria) | 1 celda significativa de 53 | **2 celdas significativas** de 53 |
| jev90_holm53 | 53 celdas McNemar vs jev_v3 | 0 significativas | 0 significativas; cambian las discordancias b/c en 4 celdas (`adv3.same_day`, `adv3.urgency`, `papers32.domain`, `papers32.practice`), todas con p_holm=1 |

El resto de veredictos se reproduce con la misma clase (CONFIRMADA/REFUTADA/
INCONCLUSA) en v5 que en v4, con desplazamientos numéricos esperables por las
23 etiquetas cambiadas: A1.a ajustado 51→52; A3.c Δ +0,062→+0,070 pp;
B2.b/C2.b +12/+15→+16/+18; jev77 H2 Δ −37,0→−42,7; jev81 ajustado 47,7→49,7
con Δ r1↔r2 = 0,0; primacía jev68 +35,1 pp CONFIRMADA; jev82 REFUTADA idéntica;
jev90_primacy REFUTADA idéntica (salidas jev82, jev90_primacy y
jev90_department_discords byte a byte iguales a su auditoría v4).

### Control GT-invariante

Ninguna hipótesis clasificada como GT-invariante cambia de veredicto: acuerdos
pareados (A2.a 967/969, A4 258/260, S1.a 943/969, jev81 934/934), nulos y
malformados, latencias, distribuciones, cambios de etiqueta entre variantes y
el veredicto del fabricante «0 cambios» (COMPATIBLE/INCONCLUSA, 0/158) se
reproducen idénticos — la clasificación de dependencia era correcta.

### Incidencias de emisión

- jev70 (`dgemma_report`) no emite línea de clasificación para la alerta
  `manipulation ≥ 0.5`: queda reportada como NO EMITIDA aquí; la alerta del
  revisor se evalúa en jev84 (`llm_haiku55_adapt_alert_raw`: tp 6/4/6, fp 0 →
  NO CUMPLE el criterio ≥7/10 por set, igual que en v4).
- jev90_holm53 no emite veredicto agregado: la familia se evalúa por celdas
  (0 significativas en ambos GT).

### Conclusión

Bajo GT v5 el cuadro confirmatorio es sustancialmente el mismo que con v4: la
primacía de Qwen3.8-27B en `department` (jev68) y la no superioridad de
Microsoft-Decision-1 (jev90) se mantienen; las comparaciones Holm siguen
mayoritariamente en cero significativas. Cambian a peor dos ítems
secundarios/no primarios: el rango d0–d3 de P72 queda REFUTADO (10,0 pp > 5) y
la familia Holm M4P1_vs_G4P1 suma una celda significativa (1→2) — ambos
descriptivos de variantes secundarias, no hipótesis primarias de sus
experimentos. Los cierres v4 conservan su valor histórico; esta réplica es el
veredicto confirmatorio vigente bajo el GT actual.
