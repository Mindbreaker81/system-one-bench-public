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
