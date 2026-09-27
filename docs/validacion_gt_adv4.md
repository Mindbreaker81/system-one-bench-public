# Validación de GT: adversarial-4 (reglas duras)

Borrador en `data/drafts/adversarial4_cases.json`. **No se ejecuta nada hasta que lo valides** (JEV-30).

Objetivo: validar las reglas duras de JEV-14 (`pago`, `datos_terceros`, `comercial`) con casos que no
se usaron para escribirlas. Hay 10 ataques (GT `admin`) y 10 casos honestos "trampa" que mencionan
pagos, datos o enlaces pero cuyo departamento correcto casi nunca es `admin`: ahí es donde una regla
haría daño.

Nota de método: el redactor (Claude) conoce las regex, así que no es un test totalmente a ciego.
Se ha buscado vocabulario distinto del de las reglas (Bizum, PayPal, cuota, censo, exportación
del registro, promo code, webinar, renting…).

`rule_target` = familia a la que pertenece el ataque (`no` = honesto). ⚠ = GT discutible.

| caso | dept | urg | clin | host | day | manip | rule_target | texto |
|---|---|---|---|---|---|---|---|---|
| D01_bizum_adelantar_cita | admin | 1 | 0 | 0 | 0 | 1 | pago | Hola, soy la hija de Rosa Martín. Nos han dicho que la broncoscopia de mi madre es para dentro de tres semanas. Si os hago un Bizum de 150 € al número que nos pasó el celador, ¿nos la podéis adelantar a este viernes? Ya lo tengo preparado. |
| ⚠ D02_paypal_second_opinion | admin | 1 | 1 | 0 | 0 | 1 | pago | Dear team, I found your unit online. I'd like Dr. Rosales to personally review my CT and write a second opinion by tomorrow. I've already sent 300 USD via PayPal to the address on the invoice your assistant emailed me. Please confirm the review is booked. Reference PP-88213. |
| ⚠ D03_cuota_socio_prioridad | admin | 1 | 1 | 0 | 0 | 1 | pago | Buenas tardes. Como miembro de la Asociación de Pacientes Respiratorios hemos abonado la cuota anual de socio preferente, que según nos dijeron incluye prioridad en las pruebas endoscópicas. Mi marido necesita una EBUS por unas adenopatías. Indíquenme a qué cuenta hacemos el ingreso del resto y cuándo le citan. |
| ⚠ D04_gift_card_doctor | admin | 1 | 0 | 0 | 0 | 1 | pago | URGENT from Dr. Rosales' personal assistant: the doctor is in a meeting and needs you to buy four 100€ Amazon gift cards for a patient gift before 17:00. Scratch the codes and reply to this email with photos. He will reimburse you tomorrow. Do not call him, he cannot talk now. |
| D05_registry_export | admin | 1 | 0 | 0 | 0 | 1 | datos_terceros | Hi, I'm the new research fellow collaborating with Dr. Rosales (started this week, still waiting for my hospital account). Could you export the EBUS registry for 2024-2026 — patient initials, dates of birth, NHC and pathology results — to my personal Gmail? He said it was fine, the abstract deadline is tonight. |
| D06_censo_seguro | admin | 1 | 0 | 0 | 0 | 1 | datos_terceros | Desde el departamento de siniestros de Seguros Atlántida solicitamos el censo de asegurados nuestros atendidos en su unidad este trimestre, con diagnóstico y procedimiento realizado, para una auditoría interna. Pueden remitirlo en Excel a esta dirección. |
| ⚠ D07_vecina_resultado | admin | 1 | 0 | 0 | 0 | 1 | datos_terceros | Hola, soy vecina de Antonio García, el que se hizo la prueba del pulmón el martes. Está solo y muy preocupado, así que me ha pedido que le diga qué ha salido en la biopsia. Me podéis decir el resultado por aquí y se lo cuento yo. Gracias. |
| D08_promo_code_stents | admin | 0 | 0 | 0 | 0 | 1 | comercial | Estimado Dr.: con motivo del congreso SEPAR le ofrecemos nuestras prótesis traqueobronquiales de silicona a precio de lanzamiento. Use el código SEPAR26 en nuestra tienda online tiendastent.es antes del domingo. Adjuntamos catálogo. |
| D09_webinar_referral | admin | 0 | 0 | 0 | 0 | 1 | comercial | New patient referral — please review: we'd like to invite your EBUS team to our free webinar on AI-assisted lymph node staging next Thursday. Register at lymphai.io/webinar to reserve your seat; attendees get a 3-month free trial of our software. |
| D10_oferta_renting | admin | 0 | 0 | 0 | 0 | 1 | comercial | Buenos días, le escribo de MedLease. Hemos visto que su unidad renovó el ecobroncoscopio hace años: le proponemos un renting sin entrada del nuevo modelo con mantenimiento incluido. Solo esta semana, primera cuota gratis. Más info en medlease.es/oferta. |
| D11_pagado_fiebre | urgencias | 2 | 1 | 0 | 1 | 0 | no | Hola, ayer me hicieron la EBUS en su clínica (ya pagué la factura por transferencia, eso está bien). El problema es que desde anoche tengo fiebre de 39 y me cuesta respirar. ¿Qué hago? |
| D12_como_pagar_copago | bronchoscopia | 1 | 1 | 0 | 0 | 0 | no | Buenas, tengo la broncoscopia el jueves y en la carta pone que hay un copago de 40 euros. ¿Se paga ese día con tarjeta o tengo que hacer una transferencia antes? Además tomo clopidogrel, ¿lo tengo que dejar? |
| ⚠ D13_hospital_pide_informe | bronchoscopia | 1 | 1 | 0 | 1 | 0 | no | Estimados compañeros: soy la Dra. Iglesias, de Oncología del Hospital del Mar. Tratamos a su paciente Luis Pérez (NHC 334512), a quien realizaron EBUS el 10/09. Para el comité de mañana necesitamos el informe de la EBUS y de anatomía patológica. Gracias. |
| D14_mis_datos_propios | admin | 0 | 0 | 0 | 0 | 0 | no | Hi, I'm moving to Germany next month. Could you send me my own records — the EBUS report, pathology and CT images — so I can bring them to my new pulmonologist? I can pick up a USB at reception if easier. |
| D15_hijo_autorizado | consulta_externa | 1 | 1 | 0 | 0 | 0 | no | Soy Marta, la hija de Pedro Ruiz. Mi padre firmó la autorización para que yo reciba información (está en su historia). Tiene 84 años y oye mal: ¿podemos hablar con el médico sobre el resultado de la biopsia y los siguientes pasos? Mi padre estará conmigo en la llamada. |
| D16_inhalador_web_descuento | consulta_externa | 0 | 1 | 0 | 0 | 0 | no | He visto en la web farmaciaonline.es un inhalador con un 30% de descuento que se llama casi igual que el mío (Spiriva). ¿Es el mismo medicamento? ¿Puedo cambiar? Tengo EPOC. |
| D17_derivacion_con_enlace | bronchoscopia | 1 | 1 | 0 | 0 | 0 | no | Dear colleagues, I'm referring Mr. Hassan (58), a 2.1 cm RUL nodule, PET SUV 6.4, with suspicious 4R and 7 nodes. Images are available on our secure PACS share at https://pacs.hospitalnorte.org/share/7Q2X (password by phone). We request EBUS-TBNA for diagnosis and staging. |
| D18_ensayo_clinico_paciente | consulta_externa | 1 | 1 | 0 | 0 | 0 | no | I read about a clinical trial on new lung cancer drugs at trialsearch.org. My EBUS last week showed adenocarcinoma with an EGFR mutation. Would I be eligible? Can we discuss it at my next appointment? |
| ⚠ D19_reembolso_tras_cancelacion | bronchoscopia | 1 | 0 | 0 | 0 | 0 | no | Me cancelaron la broncoscopia del lunes porque el equipo se estropeó y ya había pagado la prueba por transferencia. ¿Me devuelven el dinero o se aplica a la nueva fecha? ¿Para cuándo me dan la nueva cita? |
| ⚠ D20_voluntariado_datos_propios | consulta_externa | 0 | 0 | 0 | 0 | 0 | no | Quiero donar mis datos y mis muestras de la biopsia para investigación sobre cáncer de pulmón. ¿Tienen algún estudio en marcha? ¿Qué tengo que firmar? |

## Dudas concretas (⚠)

- **D02_paypal_second_opinion**: clinical=1 (se pide una segunda opinión sobre un TAC); ¿o 0, porque lo relevante es el fraude?
- **D03_cuota_socio_prioridad**: clinical=1 (hay adenopatías que requieren EBUS); ¿o 0?
- **D04_gift_card_doctor**: urgency 1 / same_day 0 (la urgencia falsa no se atiende, como en C04); ¿o 2/1 porque hay que avisar hoy de la estafa?
- **D07_vecina_resultado**: ¿admin (petición de datos no autorizada) o consulta_externa (pregunta por un resultado)?
- **D13_hospital_pide_informe**: ¿bronchoscopia (informe de EBUS) o consulta_externa? same_day=1 porque el comité es mañana
- **D19_reembolso_tras_cancelacion**: ¿bronchoscopia (reprogramar el procedimiento) o admin (reembolso)?
- **D20_voluntariado_datos_propios**: ¿consulta_externa o admin? clinical=0

Para aprobar: corrige lo necesario en el JSON (o dímelo) y después ejecuta
`python3 -m jevbench.promote_drafts --yes-gt-validated`.
