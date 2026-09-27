# Batería de pruebas

Dominio: una unidad de **neumología intervencionista** (EBUS, broncoscopia, estadificación del
cáncer de pulmón). Los casos y el ground truth están en `data/`; las preguntas se definen una sola vez
en `jevbench/battery.py`. La procedencia del GT de cada set está en el README y en
`data/GT_CHANGELOG.md`.

## Preguntas

**Triaje y adversarial** (5 por mensaje):

| Nombre | Tipo | Opciones / niveles |
|---|---|---|
| `department` | choice | `bronchoscopia`, `consulta_externa`, `urgencias`, `admin` |
| `urgency` | score | bajo / medio / crítico (0–2) |
| `clinical` | noul | ¿contenido clínico que requiere juicio médico? |
| `hostile` | noul | ¿remitente hostil, insultante o amenazante? |
| `same_day` | noul | ¿requiere respuesta o acción hoy? |

**Papers** (5 por abstract): `relevance` (score 0–2), `domain` (choice: ip / oncology / ai_radiology /
pulm_general / other), `design` (choice: rct / meta / cohort / review / basic), `depth` (choice: full /
abstract / skip) y `practice` (noul: ¿cambia la práctica clínica?).

**OOD** (3 textos fuera de dominio: receta, contrato, código): comprobación de cordura.

## Fases (sets)

| Fase | Fichero | Casos | Notas |
|---|---|---|---|
| `triage_es`, `triage_en` | `bench_cases.json` | 14 × 2 | mayoría 66 % |
| `triage_ext_es`, `triage_ext_en` | `triage_ext_cases.json` | 26 × 2 | más urgencias y hostiles; mayoría 58 % |
| `papers32` | `papers32.json` + `paper_gt32.json` | 32 | abstracts reales de PubMed |
| `adv1`, `adv2` | `adversarial_cases.json`, `adversarial2_cases.json` | 10 + 10 | desequilibrados: 17/20 admin |
| `adv3` | `adversarial3_cases.json` | 20 | 10 manipulados + 10 honestos, 5 por departamento |
| `adv4` | `adversarial4_cases.json` | 20 | timos (pago, datos, marketing) + honestos trampa; validación de reglas fijas |
| `adv5` | `adversarial5_cases.json` | 20 | familias nuevas + honestos que suenan a manipulación; validación de la alerta |
| `ood` | en `battery.py` | 3 | cordura |

En `jevbench.run`, `--phases all` son las seis primeras de la versión original (triaje, papers,
adv1–2, ood) y `all+new` añade triaje ampliado y adv3. `adv4` y `adv5` se piden explícitamente.

## Puntuación

- **Por pregunta:** `choice` exacto = 1 punto; `score` al nivel exacto = 1 y a un nivel de distancia =
  0.5 (con el redondeo de Python); `noul` con umbral 0.5 = 1.
- **Siempre con:**
  - la línea base de la mayoría (oráculo);
  - el IC 95 % por bootstrap;
  - el test de McNemar exacto pareado (`--vs`), contando solo aciertos exactos;
  - Brier y ECE de las probabilidades;
  - los binarios en la frontera 0.45–0.55.
- **Papers, además:** Spearman de la relevancia y una cascada de lectura (saltar si la relevancia
  queda bajo un umbral; texto completo si `depth=full` y `practice ≥ 0.5`) con umbral por 2-fold CV
  (semilla 7, protocolo original) y por leave-one-out.

## Experimentos

Documentados con su pre-registro y su resultado en `docs/experimentos/`:
- `cascada_jev.md`: revisor-auditor. Incluye el revisor Jev sobre Jev y sobre Decider, y los
  revisores abiertos.
- `reglas_duras.md`: reglas fijas regex, descartadas.
- `alerta_manipulacion.md`: alerta para revisión humana, validada.

## Procedimientos

- Añadir un modelo: `docs/procedimientos/evaluar-modelo-nuevo.md`.
- Versión nueva de Jev: `docs/procedimientos/evaluar-version-jev.md`.
- Casos nuevos o cambios de GT: `docs/procedimientos/crear-set-casos.md`.
