# Ling-3.0-flash-Sante — preparación de la biblioteca (JEV-113)

Fecha: 25-oct-2026. Alcance pedido: descargar Q4_K_M a la biblioteca y estudiar si Q6_K
puede ejecutarse en uno o dos DGX Spark. **No hay carga, inferencia ni batería ejecutadas.**

## Descarga Q4_K_M (completada y verificada)

- Repo: `bartowski/Ling-3.0-flash-Sante-GGUF`.
- Revisión fijada: `d59f495f375857452f47ee56b1b0a37f4491f93c`.
- Base declarada: `inclusionAI/Ling-3.0-flash-Sante`; licencia MIT declarada por el repo.
- Biblioteca: `<host-lan>:<ruta-local>`, carpeta
  `gguf/ling3-sante/124B-A5.1B/`.
- Escritor: Spark <host>; montaje temporal propio `<ruta-local>`.
  No se modifica el montaje permanente de solo lectura ni los servicios existentes.
- Total: **80.394.181.504 bytes (80,39 GB decimales)**; tres partes necesarias.

| Archivo (prefijo `Ling-3.0-flash-Sante-Q4_K_M-`) | Bytes | SHA256 LFS de Hugging Face |
|---|---:|---|
| `00001-of-00003.gguf` | 39487782336 | `6fc8e83b64e97d0bc396709c509561dea94b3167f142ce8c46c70cb54a57fa3c` |
| `00002-of-00003.gguf` | 39759067840 | `aeef63c966e46315183a8cb94757534bd3eb793877f5cc31142767948c43af33` |
| `00003-of-00003.gguf` | 1147331328 | `f72506ba3cf097485144f9a31572f5b54f9135f0ab6ef0862f4e69e79abb8456` |

La descarga escribe `.part`, permite reanudar y contrasta tamaño y SHA256 antes de renombrar.
Solo al completar las tres partes genera `SHA256SUMS`, `ORIGEN.txt`, `HF_METADATA.json`,
`README.upstream.md` y actualiza `MANIFEST.tsv` y la tabla GGUF del README de la biblioteca.
El montaje temporal se desmonta al salir, tanto con éxito como con error.

Un segundo proceso espera la finalización y ejecuta desde **<host>**:

```bash
cd <ruta-local>
sha256sum -c SHA256SUMS
```

Registros persistentes en <host>:

- `<ruta-local>`, `download.pid`, `exit_code` (0 = descarga y registro completos).
- `<ruta-local>`, `verify.pid`, `verified_on_81` (solo aparece si las tres
  verificaciones cruzadas son correctas).
- Scripts: `<ruta-local>`, `<ruta-local>` y
  `<ruta-local>`; metadatos `<ruta-local>`.

Consulta de estado, sin interferir con la descarga:

```bash
ssh user@<host-lan> 'tail -3 <ruta-local>; cat <ruta-local>'
```

Ritmo inicial observado ~11,3 MB/s: del orden de dos horas de transferencia, más la
relectura cruzada. La descarga terminó el 25-oct a las **17:25:33 +01:00** (exit_code=0).
La relectura independiente desde <host> terminó a las **17:37:58 +01:00**: SHA256 **3/3 OK**.
Comprobados los tres GGUF (80.394.181.504 bytes), la documentación y los índices de la
biblioteca; no quedan `.part`. Los procesos propios han terminado y el montaje temporal
de escritura está desmontado. JEV-113 cerrado con el alcance de descarga y plan cumplido.
No se ha descargado Q6_K ni se ha instalado otro backend.

## Q6_K: capacidad estimada, sin inferencia

El Q6_K de bartowski suma **111.426.788.224 bytes (111,43 GB; 103,77 GiB)** en tres partes.
Antes de iniciar la descarga, ambos Spark estaban sin procesos de GPU; solo estaba activo
el contenedor de monitorización existente. Memoria disponible observada:

| Spark | Disponible (bytes) | Margen tras descontar solo los pesos Q6_K |
|---|---:|---:|
| <host> | 125255933952 | 13,83 GB |
| <host> | 125309251584 | 13,88 GB |

En una sola Spark es plausible con contexto moderado, comenzando por 8K; faltan la caché,
los buffers y las asignaciones reales del backend. **No se afirma que cargue ni que quepa a
contexto máximo.** En memoria unificada no se suman 128 GB de RAM a otros 128 GB de VRAM.

Los dos enlaces directos de cada Spark (`10.100.232.1/.2` y `10.100.233.1/.2`)
estaban activos y `ethtool` reportó 200.000 Mb/s por enlace. Eso acredita negociación,
no mide rendimiento ni acredita agregación de los enlaces o RDMA funcionando.

llama.cpp permite distribuir pesos y caché entre dispositivos locales y remotos mediante
RPC (`--rpc`, `--tensor-split`); la documentación actual también describe RDMA cuando
ambos extremos lo soportan. La memoria disponible conjunta da margen para repartir Q6_K,
pero no acredita rendimiento ni la compatibilidad de esta arquitectura en ejecución distribuida.
No se promete aceleración ni contexto completo.

La compilación presente en <host>, `<ruta-local>`, declara
commit `0693dbfb915f33233818373b5f6969396658d02c`, build 448, CUDA ON y **RPC OFF**.
Una prueba distribuida requiere una compilación aparte con CUDA y RPC en ambos equipos,
sin reemplazar la usada por otros proyectos. No se ha lanzado ningún servidor.

Fuentes:

- https://huggingface.co/bartowski/Ling-3.0-flash-Sante-GGUF
- https://huggingface.co/AtomicChat/Ling-3.0-flash-Sante-GGUF
- https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md
- Comprobaciones SSH de memoria, GPU, contenedores, red y configuración de compilación
  realizadas el 25-oct-2026; metadatos HF contrastados con la API pública del repo.

## Alcance confirmado durante la descarga

El usuario ha precisado: **ahora solo descargar y dejar plan/issue; no implementar ni
ejecutar modelos**. No hay ningún arranque de modelos programado. Únicamente están
activos el descargador y la espera de verificación SHA256 desde <host>.

Plan posterior en JEV-113, pendiente de nueva indicación: comprobar la descarga 3/3,
copiar a NVMe cuando proceda, verificar soporte del runtime, fijar configuración antes
de medir y solo entonces smoke/batería. La Q6_K y una compilación CUDA+RPC quedan
como posibilidades documentadas, sin descargar ni implementar.
