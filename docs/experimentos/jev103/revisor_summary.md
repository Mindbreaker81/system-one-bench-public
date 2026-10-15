| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| decider_4b | 34 | 85.7 | 85.7 | 26/28 | 71.9 | 0.81 | 6/10 | 13/20 | 71.5 | 90.8 / 90.0 | 12/20 | 79.5 | 0.097 | 200 | 0/219 |
| decider_4b_jevrev_audit | 66 | 90.7 | 93.6 | 25/28 | 81.6 | 0.79 | 6/10 | 18/20 | 88.5 | 93.1 / 92.3 | 18/20 | 94.0 | 0.057 | — | 0/219 |
| decider_4b_clefrev_audit | 59 | 90.0 | 89.3 | 25/28 | 85.5 | 0.88 | 7/10 | 11/20 | 83.0 | 92.7 / 92.7 | 15/20 | 89.0 | 0.074 | — | 0/219 |
| decider_4b_nimblerev_audit | 46 | 90.7 | 87.1 | 25/28 | 72.6 | 0.82 | 6/10 | 13/20 | 79.0 | 91.9 / 92.3 | 13/20 | 82.0 | 0.086 | — | 0/95 |
| decider_4b_drexrev_audit | 52 | 84.3 | 87.1 | 23/28 | 76.1 | 0.70 | 7/10 | 16/20 | 86.0 | 89.6 / 90.0 | 14/20 | 84.5 | 0.078 | — | 0/216 |
| decider_4b_msrev_audit | 64 | 90.0 | 91.4 | 27/28 | 81.0 | 0.86 | 7/10 | 18/20 | 89.5 | 92.7 / 92.3 | 16/20 | 89.0 | 0.077 | — | 0/216 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.9 | — | 0/10 | 17/20 | 80.0 | 57.7 / 57.7 | 5/20 | 55.5 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
