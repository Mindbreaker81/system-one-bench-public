# Procedencia de la segunda anotación

- El usuario respondió originalmente 83 campos, desde `T02_factura_duplicada` hasta `C08_transport_data_exfil`. Sus correcciones expresas durante el cuestionario en `T12_autorizacion_seguro.clinical` y `T30_receta_inhalador.urgency` se conservaron.
- Codex completó 84 campos a petición expresa del usuario el 27-09-2026, desde `C09_guilt_trip_cold` hasta `P32`, usando solo `packet.md`.
- Después, el usuario pidió aplicar las cinco revisiones que Codex había señalado. Codex modificó `T03_disnea_progresiva.urgency` (1→2), `A04_buried_redflag.department` (`consulta_externa`→`urgencias`), `T38_parking_amenaza.urgency` (0→2), `B07_maintenance_spoof.department` (`urgencias`→`admin`) y `A10_polite_lawyer.same_day` (1→0).
- Por tanto, los valores finales incluyen 78 respuestas del usuario sin modificación y 89 valores propuestos por Codex (84 campos completados y 5 revisiones autorizadas). No se consultaron el GT ni los resultados de modelos para rellenar o revisar las respuestas.

`respuestas.json` mezcla ambas procedencias. La concordancia sobre los 167 campos no debe presentarse como segunda anotación clínica humana independiente.
