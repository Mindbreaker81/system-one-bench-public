# Enmienda editorial R109 de las atestaciones confirmatorias v4

Las auditorías anteriores se conservan en el historial (e48c790 y v2.0.0).
28796ef cambió únicamente los tres encabezados de baseline de qwen_session.py.
El cálculo es idéntico; los doce stdout reejecutados con el GT congelado v4
coinciden literalmente con sus cierres. Se actualiza solo la ligadura del código
en jev68, jev76, jev77, jev78, jev82 y las tres auditorías jev90.
No cambian pre-registros, criterios, semillas, casos, GT, resultados ni veredictos.
Hash público anterior: 84627d4a0e02237726ae595309da4dba34f5782ef9197883b1c0a2ad30a29d2a
Hash público nuevo: 54b3102f3d630ec07d71125188ed642646349dbecf2f0a99234af525b5344a42
La réplica GT v5 de JEV-100 conserva sus resultados separados.

Revisión: Codex R109; aprobada por el usuario el 12-oct-2026.

Con la versión 2.1.0 (bump de jevbench.__version__) se actualiza también el sha256 de jevbench/__init__.py en las auditorías que lo ligan; es el único cambio de esos documentos. Aprobado por el usuario el 12-oct-2026.

Con la versión 2.2.0 (JEV-101, integración de drex_v15_9b) se repite la misma operación: se re-congela únicamente el sha256 de jevbench/__init__.py (nuevo valor 502ccde436d43430e29736a2130ba87fee1b601824b7b960e57693c7b613df03) en las 12 auditorías que lo ligan; ningún otro campo de esos documentos cambia (comprobado por comparación estructural en la edición). attest verify vuelve a dar 12/12.
