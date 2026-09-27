# Plan: harness unificado y mejoras de la batería

> **Documento histórico (26-sep-2026).** Recoge la revisión inicial y el plan que se siguió; todos sus
> pasos están hechos. El estado actual está en `docs/resultados.md`, el historial en `CHANGELOG.md`
> y las tareas repetibles en `docs/procedimientos/`.

Revisión de la batería de Lyra hecha el 26-sep-2026. Primero, qué falla en el diseño
actual; después, cómo queda el harness nuevo y en qué orden correr los modelos.

## 1. Problemas encontrados

### Diseño de los tests (afectan a las conclusiones)

1. **Faltan líneas base triviales.** En adversarial, 17 de los 20 casos tienen GT `admin`.
   Un clasificador que respondiera siempre `admin` sacaría **17/20**, más que Jev D1
   (15/20) y a un punto de Jev+revisor (18/20). Lo mismo pasa con `hostile` en triaje
   (13/14 son 0) y con `depth` en papers (siempre `abstract` = 18/32).
2. **n muy pequeño y sin intervalos.** Con 14, 20 o 32 casos, diferencias como 15 vs 14/20
   o 86.4 vs 88.6% son ruido. Hace falta un IC bootstrap y un test pareado (McNemar sobre
   los mismos casos) antes de decir que un modelo "gana".
3. **La calibración no se mide.** El argumento de Jev y de sus clones es que dan
   probabilidades calibradas, pero el scoring umbraliza a 0.5 y tira la distribución.
   Faltan Brier, log-loss y ECE por pregunta.
4. **Sin casos honestos no se puede medir el FP del detector de manipulación.** "16/16,
   0 FP" se apoya en 4 casos honestos.
5. **La cascada usa 2-fold CV con una sola semilla.** Con 32 papers, hay que usar
   leave-one-out o CV repetida.
6. **Un solo anotador de GT** y sin registro de casos dudosos. Ya hay un error confirmado:
   P04 `domain="ild"` no es una opción, y su diseño `cohort` choca con el título
   "Systematic Review".
6b. **adv1 original (20-sep)** usó en `admin` la descripción "…parking, catering, logistics,
   non-clinical", distinta de la estándar, en un set con 9/10 casos `admin`. El rerun v2
   ya usó la estándar.

### Implementación

7. **Hay un script por modelo con las preguntas copiadas y pegadas**
   (`rerun_jev.py`, `decider_run.py`, `anyjev_run.py`, `gliner_decide_run.py`…). Es fácil
   que se desincronicen, y de hecho el revisor usa un `DEPT_CRITERIA` de admin distinto
   (añade "catering, logistics").
8. `BASE` escrito a mano y la clave leída de `/proc/<pid>/environ` de Hermes.
9. **GLiNER se probó con desventaja:** niveles ordinales como `"0"/"1"/"2"` sin
   descripción, y solo el argmax, sin confianzas.
10. **Fuga en el fine-tune de GLiNER:** `gliner_ft/train_triage_v1.jsonl` son los 14 casos
    de la batería.
11. **Decider nunca terminó**: CPU ARM sin bf16, ~240 s/estado.
12. No se guarda la versión del modelo, el hardware ni el dtype junto a cada resultado.

## 2. Harness nuevo (propuesta)

```
jevbench/
  battery.py        carga los datasets; preguntas en formato wire de TypeSafe (una sola fuente)
  adapters/
    jev.py          OpenRouter /api/alpha/decisions
    systemone_http.py  cualquier servidor /v1/systemone (Decider serve.sh / vLLM)
    decider.py      decider.infer.Decider.system_one en proceso
    laya.py         laya.Router.predict (ya acepta el formato dict)
    anyjev.py       traduce el formato wire a anyjev.Question
    gliner.py       traduce a schema de classify_text, con descripciones y confianzas
  run.py            python -m jevbench.run --model decider-2b --phases all
  score.py          métricas actuales + baselines + IC bootstrap + McNemar + Brier/ECE
  report.py         genera docs/resultados.md desde results/*.json
data/               datasets (copiados de legacy, versionados)
results/<modelo>/<fase>.json   con cabecera meta: modelo, versión, hw, dtype, fecha, coste
```

Todos los adaptadores reciben y devuelven **el mismo formato wire de TypeSafe**
(`answers.<q>.choice|score|noul|probabilities`). Así el scorer es uno solo y las preguntas
no se pueden desincronizar. Antes de dar por bueno el harness, hay que re-puntuar los
JSON antiguos con el scorer nuevo y comprobar que salen las mismas cifras.

## 3. Ampliación de la batería (fase 2)

- **adversarial-3**: 20 casos nuevos a ciego, equilibrados (mitad honestos, departamentos
  distintos de admin), con GT fijado antes de ejecutar.
- Triaje: ampliar a unos 40 casos, con más `hostile=1` y `urgencias`.
- Segunda anotación de GT (el usuario u otro clínico) en los casos dudosos.
- Split `train`/`test` explícito si alguna vez se hace fine-tune o calibración L1/L2.

## 4. Orden de ejecución propuesto

| # | Qué | Dónde | Por qué primero |
|---|---|---|---|
| 0 | ✅ Harness + re-score de legacy (tests en `tests/`) | portátil | valida el harness sin gastar |
| 1 | ✅ Jev v3 (`results/jev_v3`, $0.0042) | portátil (API) | línea base de calibración |
| 2 | Decider 2B → 4B → 35B-A3B (bf16) + NVFP4 | DGX .81 | pendiente de verdad y el más prometedor; formato wire idéntico |
| 3 | GLiNER Decide / Decide-1B / multi-Decide (corregido) | DGX .80 | barato, minutos |
| 4 | AnyJev L0 Qwen3-8B / 32B | DGX .80 | la ronda B pendiente |
| 5 | Laya en GPU (solo para confirmar que coincide, es determinista) | DGX .80 | trivial |
| 6 | Revisor-auditor aplicado a los mejores open-weight | DGX | ¿el patrón revisor funciona fuera de Jev? |
| 7 | ✅ adversarial-3 + triaje ampliado → todos (GT validado 26-sep) | — | robustez de las conclusiones |
