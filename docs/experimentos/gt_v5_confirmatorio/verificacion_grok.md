# Verificación independiente de la réplica confirmatoria GT v5 (JEV-100)

Lectura sola de `docs/experimentos/gt_v5_confirmatorio.md`, de
`docs/experimentos/gt_v5_confirmatorio/salidas/<exp>.txt` y del campo
`output` de `docs/auditorias/<exp>.json`. No se ha reejecutado ningún
analizador. Los 12 procesos de `salidas/codigos.json` terminaron con
código 0.

«Tipo» es D (GT-dependiente) o I (control GT-invariante). «¿Cambia?» se
refiere a la clase del veredicto, no a cada decimal. Si v5 dice
«idéntico», la línea de veredicto coincide con v4 carácter por carácter.

## Tabla

| Experimento | Hipótesis | Criterio | Veredicto v4 | Veredicto v5 | ¿Cambia? |
|---|---|---|---|---|---|
| jev67 | A1.a ajustado (D) | CONFIRMADA si 47–60; REFUTADA si <44 o >63; si no, INCONCLUSA (n_ok<190 → NO EVALUABLE) | CONFIRMADA (51, n_ok=194) | CONFIRMADA (52, n_ok=194) | no |
| jev67 | A1.c errores (D) | CONFIRMADA si ≤2; REFUTADA si ≥5 | CONFIRMADA (0) | idéntico | no |
| jev67 | A2.b Δ ajustado A2−A1 (D) | CONFIRMADA si \|Δ\|≤3; REFUTADA si \|Δ\|>6 | CONFIRMADA (−0) | idéntico | no |
| jev67 | A3.c Δ acierto choice (D) | CONFIRMADA si el IC está en [−0,05, 0,05]; REFUTADA si excluye 0 | REFUTADA (+0,062 [+0,027, +0,101]) | REFUTADA (+0,070 [+0,035, +0,109]) | no |
| jev67 | B1.a ajustado vs A1 (D) | CONFIRMADA si \|Δ\|≤5; REFUTADA si \|Δ\|>10 | CONFIRMADA (−1) | idéntico | no |
| jev67 | C1.a ajustado vs A1 (D) | CONFIRMADA si \|Δ\|≤6; REFUTADA si \|Δ\|>10 | CONFIRMADA (−3) | idéntico | no |
| jev67 | B2.a fallos papers32 (D) | CONFIRMADA si 0; REFUTADA si ≥2 | CONFIRMADA (0) | idéntico | no |
| jev67 | C2.a fallos papers32 (D) | igual que B2.a | CONFIRMADA (0) | idéntico | no |
| jev67 | B2.b ajustado disc vs prob (D) | CONFIRMADA si \|Δ\|≤4; REFUTADA si \|Δ\|>8 | REFUTADA (+12) | REFUTADA (+16) | no |
| jev67 | C2.b ajustado disc vs prob (D) | igual que B2.b | REFUTADA (+15) | REFUTADA (+18) | no |
| jev67 | B2.c errores totales (D) | CONFIRMADA si ≤1; REFUTADA si ≥5 | CONFIRMADA (0) | idéntico | no |
| jev67 | C2.c errores totales (D) | igual que B2.c | CONFIRMADA (0) | idéntico | no |
| jev67 | A1.b nulos (I) | CONFIRMADA si 0; REFUTADA si ≥1 | REFUTADA (2) | idéntico | no |
| jev67 | B1.b nulos (I) | igual | CONFIRMADA (0) | idéntico | no |
| jev67 | C1.b nulos (I) | igual | REFUTADA (2) | idéntico | no |
| jev67 | A2.a acuerdo (I) | CONFIRMADA si p≥0,97 y L≥0,95; REFUTADA si p<0,95 | CONFIRMADA (967/969 p=0,998 L=0,993) | idéntico | no |
| jev67 | A4 acuerdo (I) | CONFIRMADA si p≥0,98; REFUTADA si p<0,95 | CONFIRMADA (258/260 p=0,992) | idéntico | no |
| jev67 | A2.c malformados (I) | CONFIRMADA si malformados A2 ≥ A1 | CONFIRMADA (A2=0, A1=0) | idéntico | no |
| jev67 | A3.a cambios de etiqueta (I) | CONFIRMADA si U≤0,10; REFUTADA si L>0,10 | INCONCLUSA (24/259 U=0,135) | idéntico | no |
| jev67 | A3.b dirección posición (I) | CONFIRMADA si p≥0,05 | CONFIRMADA (p=0,9991) | idéntico | no |
| jev67 | P+fix (I) | CONFIRMADA si la evidencia fija sostiene el arreglo | CONFIRMADA | idéntico | no |
| jev67 | P+live (I) | CONFIRMADA si todas las claves comunes eligen la 1.ª | CONFIRMADA (14/14) | idéntico | no |
| jev68 | P68 thinking ≥+5 (D) | CONFIRMADA si los dos L≥5; REFUTADA si algún U<5 | INCONCLUSA (Δ0=+11,7 [−0,3, +28,0], Δ1=+6,5 [−2,0, +16,6]) | INCONCLUSA (Δ0=+12,9 [−0,2, +30,9], Δ1=+9,3 [+0,5, +19,6]) | no |
| jev68 | P72 rango d0–d3 ≤5 (D) | CONFIRMADA si U≤5; REFUTADA si L>5 | INCONCLUSA (9,6 [4,6, 17,6]) | REFUTADA (10,0 [5,2, 18,4]) | sí |
| jev68 | P72 primacía ≥5 pp (D) | CONFIRMADA si Δ≥5, L>0 y Holm p<0,05, subconjunto sha `4e7e2877f27d`; REFUTADA si U<5 | CONFIRMADA (Δ=+35,1 pp [+16,7, +52,8], n=37, sha ok, p=0,0092) | CONFIRMADA (mismo Δ, n y sha; p=0,0073) | no |
| jev68 | P71.1 discrete ≥+10 (D) | CONFIRMADA si L≥10; REFUTADA si U<10 | INCONCLUSA (+12,9 [+3,1, +24,9]) | INCONCLUSA (+16,6 [+6,7, +29,1]) | no |
| jev68 | P71.2 V3 ≥10 pp (D) | igual que P71.1 | REFUTADA (−1,1 [−3,3, +0,0]) | idéntico | no |
| jev68 | P71.2 V5 ≥10 pp (D) | igual que P71.1 | REFUTADA (−2,2 [−8,9, +0,0]) | idéntico | no |
| jev68 | Holm F0/T0 (D) | celdas con p_holm<0,05 de 53 | 0 significativas | idéntico | no |
| jev68 | Holm F1/T1 (D) | igual | 0 significativas | idéntico | no |
| jev68 | Holm F0/D0 (D) | igual | 0 significativas | idéntico | no |
| jev68 | S202 acuerdo ≥97 % (I) | CONFIRMADA si L≥0,97; REFUTADA si U<0,97 | CONFIRMADA (253/255, IC [0,972, 0,999]) | idéntico | no |
| jev70 | P.a ajustado (D) | CONFIRMADA si 22–48; INCONCLUSA si 15–55; si no, REFUTADA | INCONCLUSA (ajustado 52,6) | INCONCLUSA (ajustado 51,6) | no |
| jev70 | P.b Brier noul (D) | CONFIRMADA si ≥0,085; INCONCLUSA si >0,071 | CONFIRMADA (0,096) | idéntico | no |
| jev70 | P.c errores 1.ª pasada (D) | CONFIRMADA si ≤2; INCONCLUSA si ≤9 | CONFIRMADA (0) | idéntico | no |
| jev70 | S1.b \|Δ ajustado\| (D) | CONFIRMADA si ≤3; INCONCLUSA si ≤6 | CONFIRMADA (\|52,6−53,0\|=0,4) | CONFIRMADA (\|51,6−51,8\|=0,2) | no |
| jev70 | S1.c Brier P<S1 (D) | CONFIRMADA si Brier_S1−Brier_P >0,002 | CONFIRMADA (0,101−0,096) | CONFIRMADA (0,103−0,096) | no |
| jev70 | Rot1.c Δ acierto (D) | REFUTADA si el IC de Newcombe excluye 0 | REFUTADA (−7,4 pp [−11,9, −3,1]) | REFUTADA (−5,9 pp [−10,4, −1,4]) | no |
| jev70 | L″.c Lp3 (D) | CONFIRMADA si errores ≤2; INCONCLUSA si ≤9 | INCONCLUSA (7) | idéntico | no |
| jev70 | L″.c Lr3 (D) | igual | INCONCLUSA (4) | idéntico | no |
| jev70 | L″.c Ld3 (D) | igual | CONFIRMADA (0) | idéntico | no |
| jev70 | P.d1 unif choice (I) | CONFIRMADA si ≤4; INCONCLUSA si ≤20 | CONFIRMADA (0/219) | idéntico | no |
| jev70 | P.d2 auditoría numérica (I) | CONFIRMADA si 0 incidencias; INCONCLUSA si ≤5 | CONFIRMADA (0) | idéntico | no |
| jev70 | P.e latencia mediana (I) | CONFIRMADA si ≤1500 ms; INCONCLUSA si ≤3000 | CONFIRMADA (318 ms) | idéntico | no |
| jev70 | S1.a acuerdo (I) | CONFIRMADA si ≥0,95; INCONCLUSA si ≥0,90 | CONFIRMADA (943/969 = 97,32 %) | idéntico | no |
| jev70 | S1.d latencia S1 (I) | CONFIRMADA si ≤600 ms; INCONCLUSA si ≤1200 | CONFIRMADA (122 ms) | idéntico | no |
| jev70 | R.a acuerdo (I) | CONFIRMADA si =1; INCONCLUSA si ≥0,98 | INCONCLUSA (259/260 = 99,62 %) | idéntico | no |
| jev70 | R.b distribuciones (I) | CONFIRMADA si máx \|Δp\|≤0,001; INCONCLUSA si ≤0,02 | REFUTADA (3,36e−01) | idéntico | no |
| jev70 | X.a acuerdo (I) | igual que R.a | REFUTADA (249/260 = 95,77 %) | idéntico | no |
| jev70 | X.b distribuciones (I) | igual que R.b | REFUTADA (7,62e−01) | idéntico | no |
| jev70 | Rot1.a cambios de etiqueta (I) | INCONCLUSA si el IC cruza 0,10; si X.a no está CONFIRMADA, prefijo «POR HOST» | INCONCLUSA POR HOST (INCONCLUSA) (33/256, IC 9,0–17,6 %) | idéntico | no |
| jev70 | Rot1.b conservan posición (I) | CONFIRMADA si ≥10 cambios y p≥0,05; mismo prefijo de host | INCONCLUSA POR HOST (CONFIRMADA) (p=0,973) | idéntico | no |
| jev76 | H1 d0 DT−D ≥+5 (D) | CONFIRMADA si L≥5; REFUTADA si U<5 (IC98,75) | REFUTADA (−3,5 [−11,4, +3,6]) | REFUTADA (−4,2 [−12,6, +3,3]) | no |
| jev76 | H1 d1 DT−D ≥+5 (D) | igual | REFUTADA (−5,6 [−14,8, +2,6]) | REFUTADA (−6,1 [−16,1, +2,5]) | no |
| jev76 | H2 d0 DT−T ≥+5 (D) | igual | INCONCLUSA (+0,9 [−5,2, +6,7]) | INCONCLUSA (+0,3 [−5,9, +6,3]) | no |
| jev76 | H2 d1 DT−T ≥+5 (D) | igual | REFUTADA (−8,6 [−18,1, −1,9]) | REFUTADA (−8,8 [−19,2, −1,6]) | no |
| jev76 | Holm D0p/DT0, D1/DT1, T0p/DT0, T1p/DT1 (D) | 4 familias de 53 | 0 significativas en las cuatro | idéntico | no |
| jev77 | H1 M−G ≥+5 (D) | CONFIRMADA si L≥5; REFUTADA si U<5 (IC97,5) | INCONCLUSA (+9,7 [−1,7, +21,8]) | INCONCLUSA (+10,0 [−1,7, +22,8]) | no |
| jev77 | H2 no-inferioridad ≥−5 (D) | CONFIRMADA si L≥−5; REFUTADA si U<−5 | REFUTADA (−37,0 [−49,8, −24,9]) | REFUTADA (−42,7 [−55,6, −29,7]) | no |
| jev77 | Holm 53, 9 familias (D) | cuenta de celdas con p_holm<0,05 | 0, 0, 0, 0, 0, 0, 0, 2 (M4P0), 0 | idéntico | no |
| jev77 | Holm M4P1 vs G4P1 (D) | la 10.ª familia | 1 celda significativa de 53 | 2 celdas significativas de 53 | sí |
| jev78 | McNemar–Holm 53 vs jev_v3 (D) | cuenta tras Holm | 53 pruebas, 0 significativas | idéntico | no |
| jev81 | acuerdo, rechazos, Δp (I) | referencia ≥97 % sobre la estimación puntual | 934/934 = 100 % SÍ; mismos rechazos; Δp media 0 máx 0 | idéntico | no |
| jev81 | ajustado r1↔r2 (I) | Δ solo si las fases completas coinciden | 47,7 → 47,7 (Δ 0,0; mismas fases) | 49,7 → 49,7 (Δ 0,0; mismas fases) | no la clase; sí el nivel |
| jev82 | primacía Δ errores, n=32, sha `4e7e2877f27d` (D) | CONFIRMADA si Δ≥5, L>0 y Holm p<0,05; REFUTADA si U95<5 | REFUTADA (−12,50 pp [−25,81, −2,94], p_holm=0,1250) | idéntico | no |
| jev84 | cascada decider vs D1/ref (D) | fracciones ≥50 %, sin fase peor en 2, y alerta ≥7/10 con ≤1 FP | NO_CUMPLE (adv35 1,23; triage 0,61; adv4 tp=5) | NO_CUMPLE (adv35 1,24; triage 0,61; adv4 tp=5) | no |
| jev84 | cascada jev vs D1/ref (D) | igual | NO_CUMPLE (adv35 1,56; triage 1,33; adv4 tp=5 fp=1) | NO_CUMPLE (adv35 1,67; triage 1,33; misma alerta) | no |
| jev84 | alerta de una pasada (D) | ≥7/10 y ≤1 FP en adv3, adv4 y adv5 | NO_CUMPLE (tp 6, 4 y 6; fp 0) | idéntico | no |
| jev84 | Holm R 212 (D) | familia de 212, α=0,05 | 0 no evaluables, 0 significativas | idéntico | no |
| jev90_primacy | primacía confirmatoria (D) | mismas exclusiones y sha; REFUTADA si U95<5 | REFUTADA (Δ=0,0, n=37, sha ok, p_holm=1; sin IC impreso) | idéntico | no |
| jev90_holm53 | Holm 53 vs jev_v3 (D) | 53 celdas; vacías p=1; las cuatro exclusiones | 0 celdas con p_holm<0,05 | igual en significación; cambian b/c en adv3.same_day, adv3.urgency, papers32.domain y papers32.practice, y las cuatro siguen con p_holm=1 | no |
| jev90_department_discords | «0 cambios» (I) | 0 cambios y réplica válida → COMPATIBLE/INCONCLUSA; ≥1 → REFUTADA | COMPATIBLE/INCONCLUSA (0/158) | idéntico | no |

jev82, jev90_primacy y jev90_department_discords son archivos idénticos a
su auditoría v4.

## 4a

Ninguna clase de una hipótesis etiquetada como GT-invariante cambia.
Acuerdo, nulos, malformados, latencia, uniformidad, Δp, rechazos y el
veredicto «0 cambios» salen con el mismo rótulo y, donde la línea trae
cifra, con la misma cifra.

La excepción de valor, no de clase, es jev81, ajustado r1↔r2, puesto en
la columna de control. El contraste sigue en Δ 0,0 con las mismas fases,
pero el nivel pasa de 47,7 a 49,7 en las dos réplicas. El pre-registro
dice que un cambio de valor en un control invariante indica que el
analizador lee el GT. Aquí el ajustado lo lee; el veredicto del
contraste no cambia.

Los dos cambios de clase son GT-dependientes: P72 rango (INCONCLUSA →
REFUTADA) y Holm M4P1 vs G4P1 (1 → 2 celdas significativas).

## 4b

Cada hipótesis del pre-registro tiene en v5 la misma línea que ya tenía
el cierre v4. No aparece ninguna línea de veredicto nueva.

- jev81 y jev90_holm53 no usan CONFIRMADA / REFUTADA / INCONCLUSA / NO
  EVALUABLE / CUMPLE / «significativas». Tampoco las usaba v4: jev81
  dice «SÍ» y Δ; Holm 53 es la tabla de 53 filas, todas con `p_holm=1`.
- P71.2 es una hipótesis en el pre-registro y dos líneas en la salida
  (V3 y V5), igual que en v4.
- El criterio numérico de jev84 es una hipótesis y dos cascadas, igual
  que en v4.
- Cuatro líneas de jev70, «ajustado no evaluable (parcial …)», coinciden
  con el filtro por la palabra «evaluable» y no son hipótesis. Ya
  estaban en v4. Sus parciales sí se mueven (63,9→66,0, 57,3→59,8,
  46,4→37,6; uno queda en 27,6).
- A2.d («descriptivo») y el bloque Holm A / S de jev84 salen en los dos
  cierres y no están en la tabla de hipótesis.

## 4c

Cada rótulo v5 cuadra con la regla y con el número impreso. El único
cambio de clase, P72 rango, también: en v4 el IC es [4,6, 17,6] y L no
supera 5, así que es INCONCLUSA; en v5 es [5,2, 18,4] y L>5, así que es
REFUTADA. Holm de M4P1 pasa de 1 a 2 celdas; la salida no nombra esas
celdas, así que no se puede decir cuál entró.

jev90_primacy imprime REFUTADA con Δ=0,0 y p=1, y no imprime el IC. La
regla REFUTADA exige U95<5. Con p=1 en los dos contrastes es compatible
con un IC degenerado en 0, pero la línea guardada no trae U95. El texto
es idéntico al de v4. No se da por incumplimiento demostrado.

En jev68, jev76 y jev77 el encabezado de baselines sigue diciendo
«GT v4». Las cifras de ese bloque sí cambian respecto del cierre
(papers32 51,3→51,9; adv1 83→85; en adv3 la mayoría de `same_day` pasa
de 0 a 1), así que el cálculo usó el GT vigente y el título es una
cadena fija del analizador.
