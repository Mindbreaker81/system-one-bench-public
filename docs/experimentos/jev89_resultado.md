# JEV-89 paso 3 — resultado: LoRA propio sobre Qwen3.5-9B

**Fecha:** 18-oct-2026. Pre-registro: [`jev89_preregistro.md`](jev89_preregistro.md) (+ enmienda E1).
Ejecución única de la batería; sin re-entrenar ni re-seleccionar después de verla.

## Veredicto (criterios fijados antes de medir)

- **H1 refutada.** El ajustado del modelo entrenado (38) es menor que el del control sin entrenar (48),
  que es una de las dos condiciones de refutación. Ninguna de las 53 celdas sobrevive a Holm en ninguna
  dirección (b = 90 aciertos solo del control, c = 86 solo del entrenado): **sin diferencias
  significativas** celda a celda, pero el criterio pre-registrado del ajustado se cumple en contra.
- **Éxito práctico: no** (38 < 44).
- **Regla de parada:** no se activó (en validación supera la mayoría en todas las preguntas; ver abajo).

## Entrenamiento

| Época | log-loss val | acierto val |
|---|---:|---:|
| 0 (base) | 0,482 | 0,855 |
| 1 | 0,117 | 0,964 |
| **2 (elegida)** | **0,069** | 0,976 |
| 3 | 0,125 | 0,977 |

Por pregunta (val + val_nc, modelo fusionado; `jev89_entrenamiento/val_por_pregunta.json`): department
0,990 (mayoría 0,408), domain 0,969 (0,227), urgency 0,905 (0,443), resto 0,985–1,000. El conjunto
sintético es fácil: la validación no anticipa la batería.

## Batería (194 casos, 0 errores)

| Run | Ajustado [IC95] | Brier noul |
|---|---|---|
| Jev 1.13 (`jev_v3`) | 49 [39–59] | 0,062 |
| Qwen3.5-9B sin entrenar (`qwen35_9b_base_tev1fmt`, control) | 48 [38–57] | 0,083 |
| Nimble-9B (`nimble_9b`) | 47 [37–56] | 0,080 |
| **JEV-89 LoRA (`jev89_qwen35_9b_lora`)** | **38 [25–51]** | 0,108 |
| Mayoría | 0 | — |

Ajustado por fase (control → entrenado):

| Fase | Mayoría % | Control | Entrenado |
|---|---:|---:|---:|
| triage_es | 66,4 | 61,7 | 66,0 |
| triage_en | 66,4 | 51,1 | 74,5 |
| triage_ext_es | 57,7 | 73,6 | 74,5 |
| triage_ext_en | 57,7 | 73,6 | 76,4 |
| papers32 | 51,9 | 45,0 | 34,2 |
| adv1 | 85,0 | 26,7 | −86,7 |
| adv2 | 75,0 | 16,0 | 4,0 |
| adv3 | 55,5 | 66,3 | 42,7 |
| adv4 | 76,5 | 31,9 | 38,3 |
| adv5 | 63,0 | 36,5 | 54,1 |

McNemar + Holm (53 celdas, `dgemma_report.mcnemar_holm`):
- frente al control: mínimo p de Holm 1,0;
- frente a `jev_v3`: mínimo 1,0 (b = 94, c = 67);
- frente a `nimble_9b`: mínimo 0,41 (papers32 `domain`, 8–0 a favor de Nimble, p nominal 0,008).

## Errores con mucha confianza (confianza ≥ 0,99, `scripts/errores_seguros.py`)

| Run | Errores totales / 964 | Errores ≥ 0,99 | % de los errores |
|---|---:|---:|---:|
| control | 200 | 7 | 4 % |
| **entrenado** | 204 | **50** | **25 %** |
| `jev_v3` | 177 | 7 | 4 % |
| `nimble_9b` | 178 | 2 | 1 % |

El número de errores apenas cambia (200 → 204), pero el entrenado los comete con mucha más seguridad:
en noul, 14 errores con confianza ≥ 0,99 frente a 1 del control. Es coherente con la validación (época 3
sobreajusta en log-loss) y con el Brier peor (0,083 → 0,108).

## Lectura (descriptiva, posterior; no es parte del veredicto)

- **Mejora donde hay datos parecidos:** triaje, sobre todo en inglés (+23 puntos de ajustado en
  `triage_en`), y adv4/adv5.
- **Empeora donde el conjunto no tenía cobertura:** adv1 (mensajes con manipulación: department 5/10
  frente a 9/10, clinical 7/10 frente a 10/10) y adv3. El conjunto de entrenamiento no verificó
  ningún ejemplo de manipulación (`manipulation_verified: false`, §8.2 del plan), y los sintéticos
  aceptados son inequívocos: el modelo aprendió a seguir el contenido clínico aparente. adv1 tiene 10
  casos y una mayoría del 85 %, así que pesa mucho en el ajustado.
- **Papers:** baja de 73,5 a 68,4 % (domain, sobre todo). Las etiquetas débiles de MeSH (13 % de
  dominio discutible en la muestra R2) son la explicación más probable, sin comprobar.
- **Consecuencia:** con estos datos, el fine-tune no mejora a la base preguntada en formato Tev1 y la
  vuelve más confiada. Un siguiente intento necesitaría ejemplos adversariales y de manipulación
  verificados y etiquetas de papers más limpias; sería un experimento nuevo, con su propio
  pre-registro, y no puede usar estos resultados para elegir hiperparámetros sin declararlo.

## Lecciones

Las dos primeras están medidas; las tres últimas son interpretaciones posteriores sin comprobar.

1. **El formato de la pregunta pesa más que el ajuste fino (medido).** La base sin entrenar, preguntada
   con el contrato de Tev1 (una letra, probabilidades de la primera posición), ya rinde como los
   decisores dedicados de ~9B. Jev y Nimble, que es un LoRA sobre esta misma base, quedan sin diferencias
   significativas frente a ella. Cualquier decisor ajustado debe compararse con su propia base en este
   formato, no con cero.
2. **El ajuste fino con datos limpios empeora la calibración sin cambiar el acierto (medido).** Los
   errores son casi los mismos (200 → 204), pero los cometidos con confianza ≥ 0,99 pasan de 7 a 50.
   Es el patrón de «error seguro» (`errores_seguros.md`). Para quien use la probabilidad para decidir
   cuándo pedir revisión, es peor que no entrenar.
3. **Aprende lo que hay en los datos y desaprende lo que no está (interpretación).** Mejora en triaje y
   adv4/adv5; empeora en manipulación, que no tenía cobertura. La aceptación por concordancia exacta deja
   solo casos inequívocos y premia fiarse del contenido aparente.
4. **Una validación sintética alta no predice la batería (interpretación).** Un 97,6 % de acierto en
   validación acabó por debajo de la base: la validación medía parecerse al generador. Sin un set real a
   ciego (JEV-88), un entrenamiento propio no tiene con qué validarse.
5. **El pre-registro decidió el veredicto (interpretación).** adv1 (10 casos) es lo que más baja el
   ajustado. Sin el criterio fijado antes, habría sido fácil leer el resultado como un empate quitándolo
   o elegir la época mirando la batería.

## Ficheros

- Resultados: `results/jev89_qwen35_9b_lora/`, control en `results/qwen35_9b_base_tev1fmt/`.
- Entrenamiento: `jev89_entrenamiento/entrenamiento.json`, `jev89_entrenamiento/val_por_pregunta.json`.
- Manifiesto: [`docs/infra_runs/jev89_qwen35_9b.md`](../infra_runs/jev89_qwen35_9b.md).
- Pesos: adaptador de la época 2 y modelo fusionado, solo en local; no se publican porque incluyen datos
  CC BY-NC (hashes en el manifiesto).
