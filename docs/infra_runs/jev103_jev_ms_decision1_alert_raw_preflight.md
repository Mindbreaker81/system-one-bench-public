# Preflight JEV-103: `jev_ms_decision1_alert_raw`

Pre-registro: `docs/experimentos/jev103_preregistro.md` (congelado el 14-oct-2026).
Celda: alerta de una pasada (§1). Preflight archivado **antes** de adquirir.

## Versión

- API cerrada por OpenRouter (`/api/alpha/decisions`), adaptador `jev`,
  `provider=openrouter`, `model=microsoft/microsoft-decision-1`, `retries=3`.
- Snapshot del run base: `microsoft/microsoft-decision-1-20261009`. El adaptador guarda el
  `resolved` en `meta` y la versión de cada caso; si el snapshot difiere, se declara (§0).
- Coste autorizado por el usuario el 14-oct-2026. Guardas: `--max-case-cost 0.01` y
  `--max-cost` 0.05 (alerta) / 0.10 (revisor). Cliente: <host>.
