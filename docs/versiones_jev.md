# Versiones servidas (Jev y gpt-6-luna-decisions)

Registro de `python -m jevbench.check_versions --log`. Cada familia tiene su propio
conjunto de versiones conocidas; el aviso de «NUEVA VERSIÓN» nombra la familia y qué
hay que repetir.

- **Jev:** todos los resultados del repo están medidos con **jev-1.13**
  (`typesafe/jev-1.13-20260917` en OpenRouter = `jev-1.13.0` en TypeSafe; equivalentes,
  ver `docs/resultados.md`). Si aparece una versión nueva → repetir `jev_v3` y la cascada
  (AGENTS.md, regla 4; `docs/procedimientos/evaluar-version-jev.md`).
- **gpt-6-luna-decisions:** medido con **`openai/gpt-6-luna-decisions-20261006`**
  (JEV-80/81/82). Si cambia → re-ejecutar la batería JEV-80 (`jev_luna_decisions`) y la
  rotación JEV-82 (`jev_luna_decisions_d1`); comandos en
  `docs/infra_runs/luna_decisions_jev81.md` y `docs/infra_runs/luna_decisions_jev82.md`.

Cuesta del orden de $0.00002 por pasada de sondas. Punto de extensión reservado para la
API nativa de OpenAI Decisions (JEV-78): aún no se sondea.

Notas (Jev):
- `jev-preview` solo existe en la API de TypeSafe; OpenRouter responde HTTP 400 a
  `~typesafe/jev-preview`.
- `typesafe/jev-router` (OpenRouter) es un router de modelos generativos que usa Jev por dentro;
  no es lo que evaluamos.

## Jev

| fecha | alias → versión resuelta | resultado |
|---|---|---|
| 2026-09-27 | `openrouter:~typesafe/jev-latest` → `typesafe/jev-1.13-20260917` · `typesafe:jev-latest` → `jev-1.13.0` · `typesafe:jev-preview` → `jev-1.13.0` | sin cambios |
| 2026-10-01 | `openrouter:~typesafe/jev-latest` → `typesafe/jev-1.13-20260917` · `typesafe:jev-latest` → `jev-1.13.0` · `typesafe:jev-preview` → `jev-1.13.0` | sin cambios |

## gpt-6-luna-decisions (OpenRouter)

| fecha | alias → versión resuelta | resultado |
|---|---|---|
