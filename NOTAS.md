# Notas del proyecto: estado actual

Este archivo solo lleva el estado vigente, la línea base y lo pendiente. El historial completo de despliegues,
hallazgos y decisiones (desde el 13-10-2026) está en `NOTAS_HISTORIAL.md`. Si algo aquí no cuadra con ese historial,
manda lo más reciente y corrige la nota.

## Estado actual (se actualiza en cada despliegue; leer al empezar cada sesión)

### Producción y base
- **Vigente: verificación de condiciones de empleo con IA y estado «No seleccionada» (04-11-2026)**, commit `9667f39`
  (fusionado en `main` con el PR #6). Desplegado según confirmó Sofia el 05-11-2026. Sin registrar en esta nota: sha256 de
  la imagen, etiqueta de la imagen anterior, referencia de la base y huellas ANTES/DESPUÉS. Completar desde el registro del
  despliegue (skill `/desplegar`) o `REVERSION_FASE_A.md`.
- Anterior: autocompletado de LinkedIn por HTML de invitado (04-11-2026), commit `bf88ece` (rama `feat/unificar-ofertas`, con push).
  Imagen `job-tracker-jobtracker:latest` = `sha256:4d94baf33fa637963d3fbfa6b594327e5d54a6e3f01c75c92e1853e6a1401aa0`, healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás: `job-tracker:pre_autocompletado_linkedin_20261104` (`sha256:32804954f45c6002208c8b1fe4cb697f7e33d5f64fe45010d1dd02e44cfb8361`).
  Referencia: `ofertas_pre_autocompletado_linkedin_20261104.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `6D905D90340FB11CBC90DC2392010F601F293874F51905A3884E9A4E46A459EA`, integrity_check ok. Huellas ANTES y DESPUÉS: RESULTADO OK. Salida al detener: 0. Sin cambios de esquema.
  Pendiente: LinkedIn e Indeed siguen rechazando la lectura automática en algunos casos; el pegado de texto es la vía segura.
- Anterior: Vigente sin Viña del Mar en las ubicaciones de Indeed y Jooble (03-11-2026), commit `3e806ef`. Imagen `sha256:32804954…`, etiqueta `job-tracker:pre-vina-20261103`, referencia `ofertas_pre_vina_20261103.db` (`sha256:3d14f868…`).
- Anterior: Glassdoor solo en Santiago (03-11-2026), commit `259828e`. Imagen `sha256:e3759802…`, etiqueta `job-tracker:pre-glassdoor-santiago-20261103`.
- Anterior: LinkedIn con 10 resultados por consulta y ventana fija de 1 día (03-11-2026), commit `74bf1b1`. Imagen `sha256:a2784e23…`, etiqueta `job-tracker:pre-linkedin-10-20261103`.
- Anterior: sin «Explorar remotos» ni Jooble (02-11-2026), commit `4916a33`. Imagen `sha256:45890e25f7558239669b08f5571309ccd03fae469c674b70065e4fb5e1dad4f8`, etiqueta `job-tracker:pre-quitar-remotos-20261102`.
- Anterior: avisos ⚠ por término y lista de Trabajando sin 404 (02-11-2026), commit `f862ee9`.
  Imagen `job-tracker-jobtracker:latest` = `sha256:eaf44072515b99e41ffefe29f9044d5e114c995b9766915b49c9bbfd3f29a4c6`, healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás: `job-tracker:respaldo-20261102`. Reversión en `REVERSION_FASE_A.md`.
  Referencia: `ofertas_pre_trabajando_terminos_20261102.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `24e3ed80986999750c2e841ee235d9e938230e5d51bdb1f93986c072e354b84d`, integrity_check ok. Huellas ANTES y DESPUÉS: RESULTADO OK. Salida al detener: 0. Sin cambios de esquema.
- Anterior: aviso de robots.txt solo en portales de empleo (02-11-2026), commit `2eaa620`.
  Imagen `job-tracker-jobtracker:latest` = `sha256:d040818e4403cfc928d44a8386c23939656b14ceccbab66cc45aeb8531d69d97`. Imagen anterior: `job-tracker:pre-rellenar-robots-20261102` (`sha256:e99910a9473a205c2b65cb9924aa1b2901ac88da4710384bc18f8ade7cc3006a`).
  Referencia: `ofertas_pre_rellenar_robots_20261102.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `41AA85F9471AC98CF7088C5FFFD854160671B51B5CF803AB4C55C06BE2C1879C`, integrity_check ok. Huellas ANTES y DESPUÉS: RESULTADO OK. Salida al detener: 0. Sin cambios de esquema.
- Anterior: avisos y errores por fuente en cada búsqueda del historial (02-11-2026), commit `6a83fab`.
  Imagen `job-tracker-jobtracker:latest` = `sha256:e99910a9473a205c2b65cb9924aa1b2901ac88da4710384bc18f8ade7cc3006a`,
  healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás: `job-tracker:pre-avisos-historial-20261102` (`sha256:70ff4f4e6aed1d5dd9f10c852062fd42f4bcc97f28eac33d7420bb08239b1876`).
- Referencia: `ofertas_pre_avisos_historial_20261102.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `21192B62C912A42B241A065CDA81C58EC636F8B90774277E9333E551C9723E45`, integrity_check ok.
  Huellas ANTES y DESPUÉS: RESULTADO OK, ninguna tabla cambió. Salida al detener: 0. Sin cambios de esquema.
- Anterior: remotos a la derecha de Ofertas y una sola búsqueda en el historial (02-11-2026), commit `e9ef00f`.- **Vigente: remotos a la derecha de Ofertas y una sola búsqueda en el historial (02-11-2026)**, commit `e9ef00f`
  (rama `feat/unificar-ofertas`, con push). Imagen `job-tracker-jobtracker:latest` = `sha256:70ff4f4e6aed1d5dd9f10c852062fd42f4bcc97f28eac33d7420bb08239b1876`,
  healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás: `job-tracker:pre-unificar-20261102` (`sha256:cb958d1f…`).
- Referencia: `ofertas_pre_unificar_20261102.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, sha256 `1799E7F7…`, integrity_check ok.
  Huellas ANTES y DESPUÉS: la base de datos igual, salvo `corridas`, que tiene la columna nueva `grupo` (99 filas, sin
  valor en las anteriores; el contenido de las columnas viejas es idéntico). Salida al detener: 0.
  Cambio de esquema: `corridas.grupo` (ALTER TABLE idempotente, sin subir la versión).
- Anterior: ubicaciones editables (31-10-2026), commit `aeaae27`.
  Imagen `job-tracker-jobtracker:latest` = `sha256:729b662fffb18afb81c79ffe3b64eadc740fa8c7694c018741c3b9849ac4f64f`,
  healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás: `job-tracker:pre-ubicaciones-20261031` (`sha256:6d225a25…`).
- Referencia: `ofertas_pre_ubicaciones_20261031.db` en `C:\Users\sofia\Respaldos\job-tracker-referencias\`, integrity_check ok.
  Huellas ANTES y DESPUÉS: OK, base sin cambios (v7, 7406 ofertas, 95 corridas, 471 en historial, 44 postuladas, 6 POR VERIFICAR).
  Salida al detener: 0. Sin cambios de esquema ni reclasificación.
- Anterior: textos de «Sin texto» (30-10-2026).
  Imagen `job-tracker-jobtracker:latest` = `sha256:6d225a25…` **sin cambio de imagen respecto a la anterior en el
  registro: la reconstrucción dio el mismo id**; healthy en `127.0.0.1:8765`. Imagen anterior para volver atrás:`n  `job-tracker:pre-ubicaciones-20261031` (`6d225a2500ce`).
- Referencia: `ofertas_pre_ubicaciones_20261031.db` (copia también en el volumen, borrada tras la prueba), integrity_check ok.
  Huellas ANTES y DESPUÉS: OK, base sin cambios (v7, 7406 ofertas, 95 corridas, 471 historial, 44 postuladas, 6 POR VERIFICAR).
  Salida al detener: 0. Sin cambios de esquema ni reclasificación.
- Despliegue previo: textos de «Sin texto» (30-10-2026), commit `7042206` sobre la descripción de LinkedIn (`2492207`,
  `f348b48`; rama `feat/unificar-ofertas`, con push). Imagen `job-tracker-jobtracker:latest` =
  `sha256:6d225a2500ce12ec49a064bda0decc682baec8d0a9b1f6634ce4d1039d9e976d`, healthy en `127.0.0.1:8765`.
- Imagen anterior para volver atrás: `job-tracker:pre-textos-sintexto` (`sha256:6ed8d23e…`).
- Referencia: `ofertas_pre_textos_sintexto_20261030.db`, sha256 `6b498bdd64ec816f857325a8a0237ada8c8246b858b505777d3b4d21bc6c923c`,
  integrity_check ok. Procedimiento de reversión en `REVERSION_FASE_A.md`.
- Cambios: LinkedIn trae la descripción con JobSpy (`fetch_description`, decisión de Sofia pese a robots.txt); modelo
  de Groq `qwen/qwen3.8-27b`; se quitó la regla «Sin push»; la página y el tutorial ya no dicen que LinkedIn nunca
  trae descripción. Sin cambios de esquema ni reclasificación.
- Línea base vigente (30-10-2026): v7; 7125 ofertas, 82 corridas, 460 filas en `historial_estados`, 6 ajustes, 27
  `terminos_no_disponibles`; 44 postuladas; 6 POR VERIFICAR. Salida al detener: `0`.
- **Cambio de base (30-10-2026, commit `33653be`):** `rellenar_linkedin.py` guardó la descripción en las 14 postuladas
  de LinkedIn de «Sin texto», solo en `raw.description`, sin reclasificar (siguen en `sin_descripcion`). Huella de
  `ofertas` ahora `b091d8ea…`; el resto de la línea base igual. Referencia de ese cambio:
  `ofertas_pre_rellenar_linkedin_20261030.db`. Reversión en `REVERSION_FASE_A.md`.
- Respaldos: cualquier cambio de base se hace con referencia sha256, huellas antes y después, y reversión probada en
  copia (puerto 8767), según el skill `/desplegar`.

### Sin desplegar
- Ninguno.
- **A vigilar:** si LinkedIn empieza a responder 429 seguido (una petición extra por oferta), bajar
  `RESULTADOS_POR_BUSQUEDA` o `TERMINOS_LINKEDIN`.

## Pendientes

- **«informático junior» (activo desde 14-10):** criterio de salida: si en unas 10 corridas no llega ninguna oferta
  útil con el motivo «rol: informático junior», se quita el término. Detalle en el historial.
- **Diagnóstico de términos (15-10):** el plan de tres fases (contadores, retiros de términos y ubicaciones, términos
  nuevos) tiene la primera fase aprobada y las otras dos sin decidir. Detalle en el historial.
- **Falso positivo «Desarrollador de Negocios» → «rol: desarrollo»:** se revisa solo si el patrón se repite.
- **Avisos reales del sistema (notificaciones del navegador):** no se han probado con el navegador real; el flujo se
  probó simulado.
- **Pregunta abierta:** «Ofertas 0» con «2 relevantes nuevas» en la página (ya pasaba antes del despliegue de avisos).
- **Papelera de OneDrive:** los originales borrados el 14-10 siguen en la nube hasta que Sofia la vacíe a mano.
- **Base local en OneDrive:** `ofertas.db` en la carpeta del proyecto está dentro de OneDrive. Sin decisión aún.




