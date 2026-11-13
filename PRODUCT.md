# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Sofia, buscando empleo en Chile y remoto. Usa la página local mientras trabaja en su búsqueda. También la quiere poder compartir con otras personas a futuro (no confirmado cuándo ni con quién).

## Product Purpose
Buscador y seguimiento personal de ofertas de empleo. Trae ofertas de 14 fuentes, las clasifica por tipo de cargo (A/B/S/M, SAP/ERP, soporte), filtra por experiencia, ubicación y exclusiones, y permite seguir cada postulación en un tablero Kanban con historial de estados. Éxito: encontrar ofertas relevantes sin revisar todo a mano y no perder el hilo de ninguna postulación.

## Positioning
Lo que una hoja de cálculo o un tablero genérico no hace: buscar en muchas fuentes a la vez, descartar automáticamente lo que no corresponde (por experiencia, nivel, ubicación, empresa excluida) y dejar trazado cada cambio de estado de cada postulación.

## Operating Context
Se usa en una página local (`127.0.0.1:8765`) dentro de Docker. La búsqueda corre por lotes; la revisión y el seguimiento se hacen en la página, a ratos, mientras se trabaja en otras cosas.

## Capabilities and Constraints
- Fuentes activas: BNE, Trabajando, Chiletrabajos, Laborum, Get on Board, Himalayas, Jobicy, Remote First Jobs, We Work Remotely, Arbeitnow, Indeed y Glassdoor. LinkedIn y Chumi son opt-in, activo por defecto: se consultan solo mientras su flag de `config.py` esté en `True` (ver «Decisiones de riesgo aceptado»). Indeed, Glassdoor y LinkedIn van vía JobSpy.
- Computrabajo y Empleos Públicos rechazan el acceso: solo enlaces «Buscar a mano».
- Ofertas sin texto completo (LinkedIn, Glassdoor) van a la pestaña «Sin texto» para revisión manual.
- Base de datos SQLite; cambios de esquema y de datos reales requieren aprobación explícita.
- **Análisis con IA**: Herramienta de apoyo opcional para evaluar la compatibilidad de ofertas (requiere `GROQ_API_KEY`).
- Terminología: «postulada», «entrevista», «POR VERIFICAR», «soporte TI», «Sin texto».
- Sin decisión aún: si la página se comparte con otras personas, qué se muestra y cómo se controla el acceso.

## Decisiones de riesgo aceptado
Dos fuentes se consultan pese a una regla del propio sitio. Decisión explícita de Sofia (2026-11-12): **ambas quedan ACTIVAS**. Cada una tiene un flag en `config.py`, en `True` por defecto; mientras esté encendido, la página lo advierte.

| Fuente | Regla que se pasa por alto | Riesgo aceptado | Flag en `config.py` |
|---|---|---|---|
| LinkedIn | Su `robots.txt` dice `Disallow: /` | Bloqueo de la IP o de la cuenta de LinkedIn | `LINKEDIN_PESE_A_ROBOTS` |
| Chumi | Sus Condiciones de Uso (punto 2) | Infracción de esas condiciones | `CHUMI_PESE_A_TOS` |

- Responsable: Sofia. Fecha de la decisión: 2026-11-12.
- Cómo apagar una fuente: poner su flag en `False`. Deja de consultarse en la búsqueda y de leerse desde un enlace pegado; la página la muestra «en pausa por decisión» y cada búsqueda lo anota en sus avisos.
- Alternativa segura: abrir el aviso en el navegador y pegar su texto a mano (pestaña «Sin texto»).
- Revisión sugerida: 2027-02-12 (3 meses), o antes si LinkedIn o Chumi cambian sus condiciones o su `robots.txt`.

## Brand Commitments
Ninguno definido. El nombre del proyecto es `job-tracker`.

## Evidence on Hand
Pruebas automatizadas y el tutorial en `TUTORIAL.md`. No hay métricas de uso ni testimonios; no inventar ninguno.

## Product Principles
- Nunca postular, escribir cartas ni contactar empresas en nombre de Sofia: la app solo registra lo que ella hace.
- No leer correos ni ingresar credenciales de terceros.
- Respetar `robots.txt` y las condiciones de cada fuente; no usar User-Agent de navegador para sortear bloqueos. Excepciones explícitas: las de «Decisiones de riesgo aceptado».
- Cambios en producción solo con aprobación explícita y procedimiento documentado.

## Accessibility & Inclusion
Contraste reforzado disponible en Ajustes. La interfaz debe funcionar con teclado para las acciones principales; no hay otro requisito de accesibilidad confirmado.
