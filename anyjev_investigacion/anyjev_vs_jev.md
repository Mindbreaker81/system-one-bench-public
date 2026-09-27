Investigación completada ayer: AnyJev (Nokia Applied Research)
evaluación contra Jev/Laya/GLiNER con la batería completa (triaje ES/EN, papers32,
adversario x2, OOD). Resumen ejecutivo:

Triaje ES/EN Jev 86.4/88.6 > AnyJev 80.0/70.0 > GLiNER 79.3/71.4 > Laya 74/64
Artículos32 Jev 66,2% (rho 0,87) > AnyJev 62,2% (rho 0,50) > GLiNER 45,6%
Adversarial Jev 15/20 (18/20 con revisor) > AnyJev 14/20 > GLiNER/Laya ~3/20
OOD Jev 3/3 = CualquierJev 3/3

VEREDICTO: rechazado como reemplazo de Jev zero-shot, pero es el mejor open
zero-shot que ha pasado por la bateria: barre a Laya en todo ya GLiNER en casi
todo, y su marginalización de permutaciones resiste el relleno de palabras clave (familia
que GLiNER fallaba entera). Advertencia: probado con su modelo más pequeño (Qwen3-1.7B,
L0, cero etiquetas, CPU ARM, determinista, $0/caso).

Decisión pendiente: (A) cerrar y archivar / (B) segunda ronda DGX Spark con
Qwen3-8B o 32B L0 ($0, solo descarga) / (C) quedarnos solo con la idea L0 como
capa antivuelco. Adjunto tarball con informe completo + scripts + resultados JSON.

====================================================================
INFORME COMPLETO
====================================================================

INFORMAR: AnyJev (Nokia Applied Research) vs titulares
Fecha: 2026-09-25 | Batería: /opt/data/laya_vs_jev | Autora: Lyra

=======================================================================
1. QUE ES (verificado desde fuente primaria, github.com/nokia-applied-research/AnyJev )
=======================================================================
- NO es un modelo: es un FRAMEWORK (pip "anyjev", Apache-2.0, ~12.8k LOC,
tests+CI, numpy-only core) que convierte cualquier LLM abierto en un
decisor tipo Jev: preguntas tipadas (choice/score/noul), probabilidades
reales, cero generación (un prefill, lectura de logits).
Autores: J. Zhang, T. Yang (Nokia Sunnyvale) + Y. Shi (Tencent Hunyuan).
- Niveles: raw -> L0 (marginalizacion de permutaciones + lote previo sin
etiquetas; arreglar order-flip 0.23->0.07) -> L1 (escalado de temperatura,
100-500 etiquetas) -> L2 (cabeza lineal forma cerrada sobre estado oculto,
100-300 etiquetas, POR PREGUNTA y POR MODELO, no transferir).
- REAL autoalojado: sin phone-home, sin telemetría. Numpy solo principal.
- Claim propio: L2 con Qwen3-4B (0.786) empata Laya-FT y supera el 0.727
publicado de Jev EN SU SET (oro = profesor LLM, techo 0.735; sin repetición
de Jev). En NUESTRA bateria solo L0 es comparable zero-shot.
- Instalación de Quirka: anyjev[hf] no declara acelerar (necesario para
mapa_dispositivo). Instalado en /opt/data/anyjev_venv; repositorio es
/opt/data/anyjev_repo.

Configuración de prueba: Qwen3-1.7B F32, L0 default (perm+batch prior), CPU ARM
A1 (4 núcleos), ~55-70 s/estado (16 precargas/estado por rotaciones).
Extremos abstractos (P11 23k caracteres) tardan >20 min/estado.

=======================================================================
2. RESULTADOS (misma bateria, mismo GT, mismos goleadores que Jev/Laya/GLiNER)
=======================================================================
TRIAJE 14 casos x 5 preg (ES/EN):
Departamento ES EN ES/EN
Jev 86,4% 88,6% 12/14 12/14
CualquierJev-1.7B 80,0% 70,0% 11/14 12/14
GLiNER-2.5 79.3% 71.4% 8/14 8/14
Laya 74% 64% - -

PAPELES32 (32 papeles x 5 dimensiones):
cascada de Spearman con compuerta de salto directa CV
Jev 66,2% 0,866 6/10 -
CualquierJev-1.7B 62,2% 0,501 4/10 40,6%
GLiNER-2.5 45.6% indefinido 0/10 -
(relevancia con varianza real 0.5-2.0, NO colapsa como GLiNER;
pero profundidad colapsa a "full": 6/32 aciertos)

Enrutamiento departamental adversarial (2 conjuntos, n=20):
Jev D1 sola 15/20 (con revisor-Jev: 18/20)
AnyJev-1.7B 14/20 (8/10 + 6/10)
GLiNER-2.5 3/20
Laya ~3/20

OOD (receta/contrato/codigo): 3/3 limpio (dom=other, clinico ~0,
relevancia ~1.0). Igual que Jev.

Diagnóstico de fallos AnyJev-1.7B:
- urgencia sistemáticamente arrastrada a extremos (8 casos con 0.5 parcial)
- clínica inestable en manipulados (A03/A05/A06/A08/B05/B10 clin=0.0)
- relleno de palabras clave B06 y ​​A01 RESISTENTES (rutea bien a admin; GLiNER
fallaba TODOS los de esta familia) - la marginalizacion de permutaciones
ayuda de verdad contra token-stuffing
- B08 honesto (abuela apixaban+perro): FP de encaminamiento - falla donde Jev D1 acertaba
- Determinista (muestreo cero), distribuciones completas (no argmax como GLiNER)

COSTO: $0 API, ~60 s/estado en CPU ARM. Jev: $0.0003/caso, ~2 s.

=======================================================================
3. VEREDICTO
=======================================================================
RECHAZADO como reemplazo de Jev zero-shot, APROBADO como segunda pieza
mejor clasificada de la historia de esta batería:

1. Barre a Laya en todo. Barre a GLiNER-Decide en casi todo (artículos +17pp,
adversarial 14/20 vs 3/20, enrutamiento departamental 11-12/14 vs 8/14).
2. NO toca a Jev D1 en ninguna métrica (triaje -6/-19pp, Spearman 0.50 vs
0.87, adversarial 14 vs 15, skip-gate 4 vs 6), y el circuito de
produccion Jev->revisor (18/20, manip 16/16) queda lejos.
3. CAVEAT OBLIGATORIO (comparacion justa): esto es su modelo MAS PEQUEÑO
(1.7B; su propio banco: tipificado acc L0 0.494) una etiquetas cero contra un
titular calibrado. Su escalera 4B/8B/32B L0 sube a 0.56-0.70 y su L2
(con 100-300 etiquetas/pregunta que NO tenemos: tenemos 14-32/pregunta)
llega a 0.78-0.80 EN SU SET. La pregunta "sirve como esta?" =NO.
La pregunta "merece segunda prueba con modelo mayor?" = abierto.
4. Ingeniería honesta: documentos regenerables desde JSON comprometido,
registro de investigaciones con resultados negativos, limitaciones declaradas
(incluido que el lote anterior falla en marginales sesgadas - nuestro
"hostile" 13/14 GT=0 es exactamente ese caso: 1 FP en ES... y aun así
13/14 y 12/14 en hostile).

=======================================================================
4. DECISIÓN PENDIENTE
=======================================================================
Opcion A: cerrar aquí (Jev sigue; AnyJev archivado como "mejor open
zero-shot visto, insuficiente").
Opción B: segunda ronda en DGX Spark con Qwen3-8B o 32B L0 (horas, $0,
solo descarga) - su bench sugiere que 8B L0 ganaria ~5-8pp sobre esto
pero seguiria bajo Jev en zero-shot; el salto real requeriria L2 con
etiquetas sintéticas (500-1000 generados+verificados, el mismo cuello de
botella que GLiNER).
Opcion C: quedarse solo con la IDEA L0 (marginalizacion de permutaciones)
como capa anti-flip para cualquier decisión local futura.

Archivos: anyjev_run.py, anyjev_score.py, anyjev_results/*.json