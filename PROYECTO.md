# Job tracker: documentación del proyecto

Buscador personal de empleo para Chile (perfil TI junior y roles puente). Busca ofertas en varias plataformas, las
clasifica según tu perfil, y te deja gestionar tus postulaciones desde una página local.

> Estado: documento de referencia. Describe lo que hay en el código a la fecha de escritura. No reemplaza a
> `README.md` (instalación) ni a `TUTORIAL.md` (uso paso a paso).

---

## 1. Qué hace

1. **Busca** ofertas en 15 plataformas (ver §4).
2. **Filtra y clasifica** cada oferta: categoría, tipo de cargo, prioridad, modalidad, contrato, sueldo, experiencia.
3. **Guarda** todo en una base SQLite local.
4. **Muestra** las ofertas en una página web local (`http://127.0.0.1:8765`), donde gestionas estado, fase, notas y fechas.
5. **Exporta** a CSV y JSON, y **respalda** la base.

Solo atiende peticiones desde el propio equipo (Host y Origin locales). No se publica en la red.

---

## 2. Arquitectura

```
                  ┌──────────────────────── web/pagina.html (UI, JS vanilla)
                  │  fetch /api/*
┌─────────────────▼─────────────────┐
│ servidor.py                        │  ThreadingHTTPServer
│  - rutas GET/POST                  │  Aplicacion: hilos de búsqueda,
│  - límites de cuerpo por ruta      │  respaldo diario, cierre ordenado
└──┬──────────────┬──────────────┬───┘
   │              │              │
┌──▼───┐    ┌─────▼─────┐   ┌────▼──────────────────────────┐
│buscar│    │ rellenar_ │   │ fuentes                        │
│ .py  │    │ aviso.py  │   │  JobSpy (scrape_jobs):         │
│ núcleo│   │ autocompl.│   │   indeed, glassdoor, linkedin  │
│ BD   │    └─────┬─────┘   │  APIs: getonboard, himalayas,  │
└──┬───┘          │         │   jobicy, remotefirstjobs,     │
   │              │         │   jooble, weworkremotely,      │
┌──▼───────┐  ┌───▼────┐    │   arbeitnow                    │
│filtros.py│  │ red.py │    │  Portales (HTML/JSON-LD):      │
│clasifica │  │robots  │    │   bne, trabajando,             │
└──────────┘  │pausas  │    │   chiletrabajos, chumi,        │
              └───┬────┘    │   laborum (Playwright)         │
                  │         └────────────────────────────────┘
              ┌───▼────┐
              │robots  │   lector de robots.txt (comodines, cache)
              └────────┘
```

Además: `ia.py` (Groq), `respaldo.py` (copias de la base), `telemetria.py` (contadores de corrida),
`config.py` (todo lo ajustable), `exclusiones.py` y `puestos.py` (validación de ajustes), `geo.py`
(normalización de ubicaciones), `informe.py` (la página HTML en una cadena).

### Archivos principales

| Archivo | Responsabilidad |
|---|---|
| `servidor.py` | Servidor HTTP, rutas `/api/*`, hilos de búsqueda, cierre ordenado, respaldo diario |
| `buscar.py` | Núcleo: base de datos y migraciones, búsqueda, exploración de remotos, historial de estados, postulaciones manuales, exportación |
| `filtros.py` | Clasificador: reglas de tu perfil, experiencia, nivel, estafas, prácticas, remoto |
| `config.py` | Términos de búsqueda, plataformas, límites, pausas, reglas (regex) |
| `red.py` | Cliente HTTP con robots.txt, pausas aleatorias, detención ante bloqueos |
| `robots.py` | Lector de robots.txt con comodines (`*`, `$`) |
| `rellenar_aviso.py` | Autocompletar la postulación manual desde un link |
| `ia.py` | Llamadas a Groq: análisis de compatibilidad y extracción de datos de un aviso |
| `respaldo.py` | Copias de la base con verificación (sha256) |
| `web/pagina.html` | Interfaz completa (un solo archivo, sin frameworks) |

---

## 3. Flujo de una búsqueda

«Buscar empleos» (`POST /api/buscar`) abre **dos hilos a la vez**:

- **Búsqueda normal** (`buscar.buscar_ofertas`): consulta las plataformas marcadas con sus términos y ubicaciones.
- **Exploración de remotos** (`buscar.explorar_remotos`): roles remotos fuera de tu perfil, en Indeed y en las APIs
  remotas (Himalayas, Jobicy).

Cada plataforma se consulta en serie dentro de su hilo. Entre consultas hay pausas (`config.PAUSA_JOBSPY`,
`config.PAUSA_ENTRE_BUSQUEDAS`). Antes de guardar:

1. Se aplican las exclusiones guardadas (`filtros.fijar_exclusiones`).
2. Se descartan ofertas antiguas según la ventana de días de cada fuente (`ventanas_efectivas`).
3. Cada oferta pasa por `filtros.clasificar`.
4. `guardar` inserta solo las nuevas (deduplica por URL y por clave título+empresa+ciudad).
5. Se registra una fila en `corridas` con contadores por fuente y avisos.

El estado de la búsqueda (`/api/estado`) incluye `inicio` (para el cronómetro de la página) y, al terminar,
un mensaje con el tiempo que tardó.

**Plataformas por corrida:** la página manda la lista marcada en `fuentes`. El servidor valida que cada una
exista en `config.SITIOS`. Si no mandas nada, corre todas.

---

## 4. Plataformas

| Clave | Nombre | Cómo se lee | Notas |
|---|---|---|---|
| `indeed` | Indeed | JobSpy | Usa todos los términos de «Qué busco» |
| `glassdoor` | Glassdoor | JobSpy (glassdoor.com) | Trae descripción |
| `linkedin` | LinkedIn | JobSpy | Sin descripción. Pausas largas; se intercala con otras |
| `getonboard` | Get on Board | API | Requiere respetar robots |
| `himalayas` | Himalayas | API | Remoto |
| `jobicy` | Jobicy | API | Remoto |
| `remotefirstjobs` | Remote First Jobs | API | Remoto |
| `jooble` | Jooble | API | Requiere `JOOBLE_KEY` |
| `weworkremotely` | We Work Remotely | RSS | Remoto |
| `arbeitnow` | Arbeitnow | API | Remoto |
| `bne` | BNE | HTML (portal chileno) | Detención ante 401/403/429 |
| `trabajando` | Trabajando | HTML | Páginas `/trabajo-<término>` |
| `chiletrabajos` | Chiletrabajos | HTML + JSON-LD | |
| `chumi` | Chumi | HTML + JSON-LD | Sin búsqueda: lee páginas del listado |
| `laborum` | Laborum | Playwright | Abre un Chromium sin ventana por término |

Plataformas que rechazan la lectura (Computrabajo, Buscojobs, Empleos Públicos): no se consultan. Se buscan a mano
desde la sección «Buscar a mano» de la página.

---

## 5. Clasificación

`filtros.clasificar` decide para cada oferta una **categoría**:

| Categoría | Significado |
|---|---|
| `principal` | Pasa tu perfil (tipo A: TI, o tipo B: rol puente con señales suficientes) |
| `sin_descripcion` | Llegó sin texto: no se puede revisar experiencia ni nivel |
| `explorar` | Rol remoto fuera de tu perfil (tipo E) |
| `fuera_perfil` | Soporte, mesa de ayuda, u otros que no calzan |
| `sospechosa` | Señales de estafa: pago previo, datos bancarios, solo WhatsApp |
| `descartada` | No cumple: senior, práctica, experiencia alta, ubicación, plazo fijo |

Las reglas viven en `config.py` como listas de patrones (`ROLES_A_*`, `ROLES_B_*`, `SENIORITY_*`,
`EXPERIENCIA_*`, `SOSPECHOSA_DESC`, etc.). Los patrones se aplican a texto normalizado (minúsculas, sin tildes).

Reglas de experiencia: se descarta si el mínimo exigido es 2 años o más, o si el rango supera 2. Se mantienen
«1 año», «0 a 2» y «1 a 2».

---

## 6. Estados y seguimiento

- **Estado** de una oferta: `nueva`, `revisada`, `postulada`, `entrevista`, `descartada`.
- **Fase** (solo con estado en proceso): postulación, RRHH, técnica, final, oferta.
- **Fecha de postulación**: se pone sola al pasar a postulada o entrevista, si estaba vacía. No puede ser futura.
- **Historial** (`historial_estados`): cada cambio queda con origen (tablero, lista, modal, manual, deshacer).
  Solo `buscar._cambiar_seguimiento` escribe estado, fase y fecha (hay un test que lo verifica).
- **Deshacer** restaura el estado anterior con el mismo mecanismo.

Campos manuales de cada oferta: notas (≤ 5000), sueldo anotado, prioridad manual (Alta, Media, Baja).

---

## 7. Postulación manual

«Agregar postulación manual» crea una oferta que no vino de la búsqueda (`POST /api/oferta/manual`).

- Si la URL ya existe, o la misma oferta (cargo + empresa + ciudad) ya está con otra URL: 409 con la existente.
  Puedes «Guardar de todas formas», y la clave se sufija.
- Si la existente estaba descartada, se **revive** (vuelve a «principal» con el estado del formulario).
- Sin URL, la clave es sintética (`manual:<uuid>`).

### Autocompletar desde el link (`POST /api/aviso`)

Orden de lo que se intenta:

1. **Base de datos:** si el link ya está guardado (lo trajo una búsqueda), se usan esos datos. No se visita nada.
2. **HTML normal** con `robots.txt` y pausa. Si trae JSON-LD `JobPosting`, se usa.
3. **Navegador (Playwright)**, solo si la página llegó vacía (contenido pintado con JavaScript) y `robots.txt`
   lo permitió. Se abre sin ventana, solo carga recursos del mismo sitio.
4. **IA (Groq)** lee el texto visible de esa página y devuelve cargo, empresa, ubicación, modalidad y sueldo.
   Si no encuentra cargo ni empresa, es error.
5. **Pegar el texto** (`POST /api/aviso/ia`): si todo lo anterior falla, pegas el aviso y la IA lo ordena.

Límite que no se cruza: si `robots.txt` prohíbe la URL (Indeed, LinkedIn y otros), no se lee el sitio.

---

## 8. Ajustes (`POST /api/ajustes/*`)

| Ajuste | Qué guarda | Dónde se usa |
|---|---|---|
| Puestos | Lista de términos para Indeed (máx. validado) | próxima búsqueda |
| Ubicaciones | Lista (máx. 10) y si incluye remoto | próxima búsqueda |
| Exclusiones | Empresas, patrones de título y descripción | clasificación |
| Soporte | Si la categoría soporte se muestra en Ofertas | página |
| Plataformas | Cuáles marcar en cada corrida: se guarda en el navegador (`localStorage`) | cada corrida |

---

## 9. Base de datos

SQLite en `config.DB_PATH` (fuera de OneDrive). En Docker: `/datos/ofertas.db` dentro del volumen `jt_datos`.

- Modo WAL, `busy_timeout` de 15 s.
- Escrituras con `transaccion` (`BEGIN IMMEDIATE`).
- Versión del esquema en `PRAGMA user_version` (`VERSION_DB = 7`). Migraciones: `_migrar_v2`, `_migrar_v3`, `_migrar_v4`.
  Una base de versión desconocida se respalda como `*_antigua_<fecha>.db` antes de crearla de nuevo.

Tablas: `ofertas`, `corridas`, `terminos_no_disponibles`, `ajustes`, `alertas`, `pruebas_fuentes`,
`historial_estados`.

---

## 10. Respaldos

- Automático: una vez por día, si `JT_RESPALDOS` está configurado. Revisa cada hora.
- Manual: «Respaldar ahora» (como mucho uno por minuto).
- Cada copia tiene su `.sha256`. Una copia sin verificación queda como temporal, nunca como válida.
- Se guardan los últimos 30.
- Al apagar: espera un respaldo en curso (5 s) y consolida el WAL (3 s).

---

## 11. Ejecución

### Docker (la forma normal)

```
docker compose up -d --build
```

- Puerto publicado solo en `127.0.0.1:8765`.
- Variables en `.env` (no se sube a git): `JOOBLE_KEY`, `GROQ_API_KEY`, `JT_RESPALDOS_HOST`.
- Chromium viene en la imagen para Laborum y el autocompletar con navegador.

### Local

```
pip install -r requirements.txt
python servidor.py
```

Abre `http://127.0.0.1:8765`. Para buscar desde la línea de comandos: `python buscar.py`.
Para reclasificar lo guardado sin buscar: `python buscar.py --reclasificar`.

### Pruebas

```
python -m pytest -q
```

~900 pruebas. Usan base temporal, JobSpy falso y HTTP local. Una prueba abre Chromium de verdad (se salta si no está
instalado).

---

## 12. Reglas de conducta de las búsquedas

Estas reglas vienen de decisiones previas y no se cambian sin acuerdo:

- Se consulta `robots.txt` de cada sitio antes de pedir una página. Si prohíbe la URL, no se pide.
- Pausa aleatoria entre peticiones (3 a 5 s en portales; más en LinkedIn y Glassdoor).
- Ante 401, 403, 429 o un CAPTCHA, el sitio se detiene por la corrida. No se reintenta ni se esquiva.
- User-Agent que dice quién es (no se disfraza).
- La IA solo recibe texto que tú pegas o que la app ya leyó legalmente. No navega por su cuenta.

---

## 13. Pendiente

- **Límite total de 10 minutos por búsqueda.** Hoy no existe: la constante se quitó porque no tenía uso.
- **Paralelizar plataformas dentro de la búsqueda normal.** Hoy corren en serie dentro de un hilo.
- **Límite de frecuencia para `/api/aviso`** (cada autocompletar con navegador tarda unos segundos).
- **Bloquear IPs privadas** en `/api/aviso` si algún día el servidor sale de localhost.
- **Prueba real de autocompletar** con avisos de cada portal: hasta ahora solo con HTML de ejemplo y links
  de tus ofertas guardadas.
- **Cronómetro y plataformas por corrida**: verificados con tests, no con una búsqueda completa real.
- **Limpieza de `terminos_no_disponibles`** y de historial antiguo: no hay rotación automática de esas tablas.

---

## 14. Documentos relacionados

- `README.md`: instalación.
- `TUTORIAL.md`: uso de la página.
- `PRODUCT.md`: qué problema resuelve y para quién.
- `NOTAS.md`, `NOTAS_HISTORIAL.md`: decisiones y observaciones por fecha.
- `CLAUDE.md`: instrucciones para el asistente.
- `SAAS_ROADMAP.md`: evolución posible hacia servicio multiusuario.
- `INFORME_PLATAFORMA.md`: informe técnico de la plataforma.
