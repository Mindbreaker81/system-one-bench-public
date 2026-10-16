| run | ajustado | triaje ES | triaje EN | dept ES+EN | papers | ρ relevancia | skip LOO | adv dept (1+2) | adv total | triaje ext ES/EN | adv3 dept | adv3 total | Brier noul | ms mediana | unif choice |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| decider_4b | 34 | 85.7 | 85.7 | 26/28 | 71.9 | 0.81 | 6/10 | 13/20 | 71.5 | 90.8 / 90.0 | 12/20 | 79.5 | 0.097 | 200 | 0/219 |
| decider_4b_jevrev_audit | 66 | 90.7 | 93.6 | 25/28 | 81.6 | 0.79 | 6/10 | 18/20 | 88.5 | 93.1 / 92.3 | 18/20 | 94.0 | 0.057 | — | 0/219 |
| decider_4b_jev114rev_audit | 63 | 90.7 | 90.0 | 26/28 | 82.3 | 0.81 | 6/10 | 18/20 | 88.5 | 92.7 / 91.5 | 17/20 | 92.0 | 0.060 | — | 0/216 |
| decider_4b_jev114rev_review | 71 | 91.4 | 94.3 | 26/28 | 85.2 | 0.83 | 7/10 | 19/20 | 93.0 | 94.2 / 95.0 | 17/20 | 94.0 | 0.045 | — | 0/216 |
| *mayoría (oráculo)* | 0 | 66.4 | 66.4 | 12/28 | 51.9 | — | 0/10 | 17/20 | 80.0 | 57.7 / 57.7 | 5/20 | 55.5 | — | — | — |

*ajustado: media por fase de (acierto − línea base de mayoría) / (100 − línea base) × 100 (ood queda excluida: la mayoría ya acierta todo). 0 = responder siempre lo más frecuente, <0 = peor que el trivial; `*` = no tiene las 11 fases.*

*`unif choice`: elecciones casi uniformes (máx−mín < 0.05) en las 9 fases base+nuevas; no incluye adv4/adv5. No demuestra vectores nulos crudos ni fallo automático.*
