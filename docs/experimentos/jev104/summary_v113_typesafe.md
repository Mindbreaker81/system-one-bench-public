| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v113_typesafe | 50 | 88.6 | 90.7 | 26/28 | 76.8 | 0.89 | 5/10 | 15/20 | 81.0 | 95.0 / 92.7 | 17/20 | 90.5 | 0.063 | 540 | 0/216 |
| jev_v114_typesafe_preview | 50 | 87.1 | 88.6 | 26/28 | 76.8 | 0.89 | 5/10 | 16/20 | 81.5 | 93.5 / 95.0 | 17/20 | 90.0 | 0.062 | 537 | 0/216 |
| jev_v3 | 49 | 88.6 | 90.0 | 26/28 | 76.8 | 0.89 | 5/10 | 15/20 | 81.0 | 95.0 / 92.7 | 17/20 | 90.0 | 0.062 | 657 | 0/219 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.9 | — | 0/10 | 17/20 | 80.0 | 57.7 / 57.7 | 5/20 | 55.5 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
