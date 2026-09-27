# Versiones de Jev servidas por cada proveedor

Registro de `python -m jevbench.check_versions --log`. Todos los resultados del repo están
medidos con **jev-1.13** (`typesafe/jev-1.13-20260917` en OpenRouter = `jev-1.13.0` en TypeSafe;
equivalentes, ver `docs/resultados.md`). Si aparece una versión nueva, hay que repetir `jev_v3`
y la cascada antes de comparar (AGENTS.md, regla 4). Cuesta menos de $0.01.

Notas:
- `jev-preview` solo existe en la API de TypeSafe; OpenRouter responde HTTP 400 a
  `~typesafe/jev-preview`.
- `typesafe/jev-router` (OpenRouter) es un router de modelos generativos que usa Jev por dentro;
  no es lo que evaluamos.

| fecha | alias → versión resuelta | resultado |
|---|---|---|
| 2026-09-27 | `openrouter:~typesafe/jev-latest` → `typesafe/jev-1.13-20260917` · `typesafe:jev-latest` → `jev-1.13.0` · `typesafe:jev-preview` → `jev-1.13.0` | sin cambios |
