# Manifiesto y plan — Base Labs elephant-1 / mammoth-1 en local (JEV-109 fase 2)

**Plan escrito el 25-oct-2026 antes de lanzar las baterías locales** (la única ejecución previa es
una prueba corta de 4 registros, borrada). Mismo procedimiento que los pares local ↔ OpenRouter de
JEV-106 (`docs/experimentos/jev106_preregistro.md` §3).

## Runs

| run | modelo | host | homólogo API |
|---|---|---|---|
| `elephant_1_local` | `baselabs/elephant-1` @ `c54a55c2d362a7e30ff30814d28e39054e954d58` | DGX Spark <host> (GB10) | `elephant_1_or` |
| `mammoth_1_local` | `baselabs/mammoth-1` @ `03007ab3c4481bf01c71ef63adbbbc4b2093d71a` | DGX Spark <host> (GB10) | `mammoth_1_or` |

Fases `all+new` y, aparte, `adv4,adv5`. Pesos copiados de la biblioteca local de modelos
(`hf/baselabs/`, SHA256 verificado contra Hugging Face) al disco de <host>.

## Entorno

- Adaptador `baselabs` (`jevbench/adapters/baselabs.py`): `qev.engine.DecisionEngine` en proceso, igual
  que el `engine.py` del release (incluido su respaldo secuencial ante `32BitIndexMath`).
- Runtime: OneJev @ `81ce62f1597c91e46767d4d02d6ac2e18534fe94` + `serve.patch` del release (idéntico en
  los dos modelos).
- Venv `.venv-baselabs` (`scripts/setup_venv.sh`): torch 2.14.1+cu130, torchvision 0.29.1+cu130,
  transformers 5.19.0, accelerate 1.15.0, safetensors 0.8.0, pydantic 2.14.1,
  flash-linear-attention / fla-core 0.5.2.
- **Desviaciones respecto a `setup.sh`** (pensado para la imagen x86 `pytorch:2.8.0-cuda12.8`):
  torch 2.14.1+cu130 aarch64 en lugar de 2.8.0+cu128; **sin `causal_conv1d`** (transformers usa su
  implementación de referencia en PyTorch: mismo cálculo, más lento); sin `decision-index` ni el
  extra `[train]` (no hacen falta para inferir). Prueba corta sensata (OOD → `other`, factura →
  `admin`, EBUS → `bronch`, cifras próximas a las de la API).
- Modo de bifurcación `batched`, atención `noncausal`, lectura `slot_lm`, sin calibración (leído de
  `readout.json` del checkpoint).

## Comparaciones (fijadas antes de medir)

1. Cada run frente a `jev_v3`: McNemar en las 53 celdas, Holm dentro de la familia; «mejor/peor» solo
   si una celda sobrevive; si no, «sin diferencias significativas».
2. Par local ↔ API: acuerdo de decisiones pareadas con `python3 -m jevbench.jev81 repeat <local> <or>`
   (descriptivo; referencia 97 % de las réplicas de JEV-81; no es prueba de equivalencia) y McNemar
   53 celdas + Holm. Una diferencia se lee como de configuración/servicio, sin atribuir causa.
3. Latencia: mediana en proceso por caso (sin pausa entre peticiones, a diferencia de los runs `:free`).

## Resultados (25-oct-2026)

194/194 casos y 0 errores en los dos runs (11 fases). Mediana en proceso por caso, resumen de 9 fases.

| run | ajustado [IC95] | Brier noul | mediana | acuerdo con su API | McNemar 53 celdas vs API (b/c, Holm) | vs `jev_v3` (b/c, Holm) |
|---|---|---|---|---|---|---|
| `elephant_1_local` | 54 [45–62] | 0,069 | 335 ms | 957/964 = 99,3 % [98,5–99,7] | 2 / 5, mín. p Holm 1,0 | 44 / 50, mín. p Holm 1,0 |
| `mammoth_1_local` | 58 [51–66] | 0,063 | 974 ms | 955/964 = 99,1 % [98,2–99,6] | 3 / 6, mín. p Holm 1,0 | 46 / 57, mín. p Holm 1,0 |
| `elephant_1_or` (API) | 52 [41–63] | 0,067 | (~435 ms sin pausa) | — | — | 46 / 49 |
| `mammoth_1_or` (API) | 57 [49–65] | 0,064 | (~614 ms sin pausa) | — | — | 48 / 56 |

- Acuerdo local ↔ API por encima de la referencia del 97 % en los dos; ninguna celda significativa
  frente a la API ni frente a `jev_v3` (b = solo la referencia acierta, c = solo el run acierta).
  Sin diferencias significativas: no es una prueba de equivalencia.
- Latencia local: 335 ms (9B) y 974 ms (27B) en el GB10 sin `causal_conv1d`; las cifras API llevaban
  una pausa fija de 3,5 s entre peticiones.
