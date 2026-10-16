| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev_v114_typesafe_preview | 50 | 87.1 | 88.6 | 26/28 | 76.8 | 0.89 | 5/10 | 16/20 | 81.5 | 93.5 / 95.0 | 17/20 | 90.0 | 0.062 | 537 | 0/216 |
| jev114_cascade_review | 68 | 90.0 | 93.6 | 25/28 | 83.9 | 0.83 | 5/10 | 19/20 | 92.0 | 94.2 / 95.4 | 18/20 | 92.0 | 0.044 | — | 0/216 |
| jev114_cascade_audit | 66 | 89.3 | 91.4 | 26/28 | 81.3 | 0.89 | 5/10 | 19/20 | 91.0 | 93.5 / 95.0 | 18/20 | 94.5 | 0.046 | — | 0/216 |
| jev114_cascade_avg | 61 | 89.3 | 94.3 | 26/28 | 80.6 | 0.88 | 5/10 | 16/20 | 87.5 | 94.2 / 95.0 | 17/20 | 92.5 | 0.049 | — | 0/0 |
| jev114_avg2_control | 51 | 87.1 | 90.0 | 26/28 | 76.8 | 0.89 | 5/10 | 16/20 | 81.5 | 93.8 / 95.0 | 17/20 | 90.0 | 0.061 | — | 0/0 |
| jev_v3 | 49 | 88.6 | 90.0 | 26/28 | 76.8 | 0.89 | 5/10 | 15/20 | 81.0 | 95.0 / 92.7 | 17/20 | 90.0 | 0.062 | 657 | 0/219 |
| jev_cascade_audit | 68 | 91.4 | 93.6 | 26/28 | 83.2 | 0.89 | 5/10 | 19/20 | 90.5 | 94.6 / 93.5 | 18/20 | 92.5 | 0.045 | — | 0/219 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.9 | — | 0/10 | 17/20 | 80.0 | 57.7 / 57.7 | 5/20 | 55.5 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
