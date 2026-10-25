# System One en una Jetson Orin Nano (8 GB) — pre-registro

**Estado:** escrito el 25-oct-2026 **antes** de medir ninguna batería en la Jetson. Antes solo hubo una prueba
corta del 9B (5 casos, borrada) que colgó el equipo con un abstract largo (ver «Incidencia previa»).

## Pregunta

¿Qué decisores System One caben y funcionan en una **Jetson Orin Nano Super** (8 GB de memoria unificada,
JetPack 6, CUDA 12.6) y cuánto se pierde frente a la misma configuración en el DGX Spark?

## Configuraciones (fijas)

| run | modelo | ejecución en la Jetson | control en DGX (mismo contrato) |
|---|---|---|---|
| `qwen35_4b_q4km_jetson` | `Qwen/Qwen3.5-4B` @ `851bf6e8…` → GGUF Q4_K_M (2,78 GB) | llama.cpp `df9beac`, `llama-server -ngl 99 -c 8192 -np 1` | `qwen35_4b_base_tev1fmt` (bf16, adaptador `tev1`, .81) — nuevo |
| `qwen35_9b_q3km_jetson` | `Qwen/Qwen3.5-9B` @ `c2022362…` → GGUF Q3_K_M (4,74 GB) | igual | `qwen35_9b_base_tev1fmt` (JEV-89, ya medido) |
| `decider_2b_jetson` | `Mapika/decider-2b` @ `533964da…` (copia de la biblioteca local de modelos; el run `decider_2b` no registró revisión) | adaptador `decider`, PyTorch para JetPack, bf16 | `decider_2b` |
| `decider_0.8b_jetson` | `Mapika/decider-0.8b` @ `a0a01d6f…` (ídem) | igual | `decider_0.8b` |

- Los Qwen se preguntan con el **contrato de Tev1** (una letra por decisión, probabilidad del primer token
  restringida a las letras), como `qwen35_9b_base_tev1fmt`. Adaptador nuevo `tev1_gguf`: el prompt se
  renderiza con el tokenizador HF de la base (misma plantilla, `enable_thinking=false`) y se envía como ids
  a `/completion` (`n_predict=1`, `n_probs=100`); las letras fuera del top-100 reciben la probabilidad mínima
  devuelta y se cuentan. Cliente en el DGX .81 por la LAN.
- GGUF convertidos con `convert_hf_to_gguf.py` del mismo commit de llama.cpp (bf16 → `llama-quantize`),
  sin matriz de importancia; sha256 verificados en la SSD de la Jetson.
- Fases `all+new` y, aparte, `adv4,adv5`.

## Seguridad del equipo (antes de cada batería)

Prueba de estrés con el caso más largo (papers32 P03) vigilando la memoria libre. Si el servidor no
responde o la memoria disponible baja de 300 MB, **no se lanza esa batería**, el modelo se da por «no cabe»
y se informa así. **Variante solo si el 9B Q3_K_M no cabe:** `qwen35_9b_iq4xs_jetson_c4096` (IQ4_XS,
`-c 4096`): los casos que excedan el contexto se registran como rechazo, no se truncan (estricta).

## Comparaciones (fijadas antes de medir)

1. Cada run frente a su control en el DGX: acuerdo de decisiones pareadas
   (`python3 -m jevbench.jev81 repeat <jetson> <control>`; referencia descriptiva 97 %) y McNemar en las 53
   celdas con Holm. Una diferencia se lee como efecto de configuración (cuantización, motor, hardware), sin
   atribuir causa concreta.
2. Cada run frente a `jev_v3`: McNemar 53 celdas + Holm; «mejor/peor» solo si una celda sobrevive.
3. Ajustado con IC (bootstrap) y Brier, con la mayoría como línea base; latencia mediana por caso (cliente
   en el DGX, incluye la LAN).

## Incidencia previa

Con el 9B en IQ4_XS (5,36 GB, `-c 8192`) la Jetson respondió bien en triaje y en un primer paper (2,5–15 s
por caso) y **se colgó** con P03 (fin abrupto del registro del sistema a las 14:04:41 del 25-oct; arranque
siguiente a las 14:14). Q4_K_M (5,78 GB) no llegó a cargar (`cudaMalloc` sin memoria).

## Resultados (25-oct-2026)

| run | ¿cabe? | casos | ajustado [IC95] | Brier | mediana/caso | acuerdo con su control DGX | McNemar vs control (b/c, Holm) |
|---|---|---|---|---|---|---|---|
| `qwen35_4b_q4km_jetson` | **sí** | 194/194 | 35 [23–45] | 0,089 | ~3,5 s | 888/964 = **92,1 %** [90,2–93,7] | 44 / 27, mín. p Holm 1,0 |
| `qwen35_4b_base_tev1fmt` (control, DGX bf16) | — | 194/194 | 37 [25–48] | 0,090 | 0,46 s | — | — |
| `decider_0.8b_jetson` | **sí** | 194/194 | 15 [3–27] | 0,123 | ~0,8 s | 959/964 = **99,5 %** [98,8–99,8] | 0 / 5, mín. p Holm 1,0 |
| `decider_0.8b` (control, DGX) | — | 194/194 | 13 [1–26] | 0,123 | 43 ms | — | — |
| `decider_2b_jetson` | **no del todo** | 142/194 (12 errores de memoria; adv4/adv5 sin cargar) | 12* | 0,116 | ~1,3 s | — (incompleto) | — |
| `decider_2b` (control, DGX) | — | 194/194 | 20 [7–33] | 0,118 | 79 ms | — | — |
| `qwen35_9b_*_jetson` | **no** | — | — | — | — | — | — |
| `jev_v3` (referencia) | — | 194/194 | 49 [39–59] | 0,062 | 657 ms | — | — |

Mayoría constante: 0. Frente a `jev_v3`, 0 celdas tras Holm en `qwen35_4b_q4km_jetson` (b = 104, c = 44) y en
`decider_0.8b_jetson` (b = 154, c = 64); son resultados descriptivos (ningún «peor» demostrado celda a celda).

- **Qwen3.5-4B Q4_K_M** cabe y es estable en 15 W con `--cache-ram 0`: la cuantización cambia el 7,9 % de las
  decisiones frente al bf16, sin celdas significativas; todas las letras estaban en el top-100 (0 rellenos).
- **Decider-0.8B** cabe y reproduce al DGX (99,5 %), ~19× más lento por caso.
- **Decider-2B** no cabe de forma estable: con los abstracts más largos y al cargar el modelo por segunda vez el
  asignador de CUDA de PyTorch falla (`NVML_SUCCESS == r INTERNAL ASSERT FAILED`), también tras un reintento en
  procesos limpios. Se informa como incompleto, sin ajustado comparable.
- **Qwen3.5-9B** no cabe: Q4_K_M no carga; IQ4_XS cargó una vez (`-c 8192`, MAXN) pero colgó el equipo con el
  abstract más largo; después ni Q3_K_M ni IQ4_XS (también con `-c 4096`) pudieron reservar la caché de contexto.

## Incidencias y desviaciones

- **Tres reinicios de la Jetson** el 25-oct (14:04, 14:40, 14:46) con cortes abruptos bajo carga. Causa
  identificada después: la caché de prompts de llama-server (`--cache-ram`, 8 GiB por defecto) crece en RAM
  hasta agotar los 8 GB (en 15 W el OOM-killer la mató en lugar de colgar el equipo). Corregido con
  `--cache-ram 0` y vaciando la caché de páginas antes de cada arranque (`cudaMalloc` no la reclama).
  Los runs afectados se descartaron enteros y se repitieron desde cero (no se mezclaron).
- **Modo de energía:** las baterías válidas se midieron en **15 W** (`nvpmodel -m 0`), no en MAXN_SUPER.
- **Decider en la Jetson:** venv propio con PyTorch 2.8.0 para JetPack 6 (cu126), triton 3.4.0, transformers
  5.17.0, flash-linear-attention 0.5.2 y decider-ai 1.5.0 instalado sin dependencias porque declara Python ≥ 3.11
  y la Jetson solo tiene ruedas de PyTorch para 3.10 (en el DGX: torch 2.14 cu130). `torch.compile` se
  desactiva solo en 3.10.
- Control nuevo `qwen35_4b_base_tev1fmt` en el DGX .81 (adaptador `tev1`, bf16, `Qwen/Qwen3.5-4B` @ `851bf6e8…`).
