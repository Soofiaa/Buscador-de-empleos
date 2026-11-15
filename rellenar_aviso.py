"""Rellena una postulación manual a partir del enlace del aviso.

Lee el JSON-LD JobPosting que muchos portales ponen en la página (schema.org).
LinkedIn no lo trae: se lee el HTML público de invitado (linkedin.aviso_formulario).
Si tampoco hay texto usable, hay que completar a mano.
"""
import html as html_mod
import ipaddress
import json
import re
import socket

from bs4 import BeautifulSoup

import chumi
import config
import filtros
import ia
import linkedin
from red import Bloqueo, ErrorFuente, NoEncontrada, USER_AGENT_HTTP, parece_bloqueo, pedir
from urllib.parse import parse_qs, urlsplit

LIMITE_HTML = 1_500_000
MINIMO_TEXTO = 300          # menos que esto: la página llegó vacía y el contenido lo pinta JavaScript
TIEMPO_NAVEGADOR_MS = 20_000
MODALIDADES = ("Remoto", "Híbrido", "Presencial")
# Portales de empleo donde el aviso se pide sin revisar robots.txt (decisión de Sofia). Cualquier otro sitio sí se revisa.
# LinkedIn no pasa por esta lista: va por desde_linkedin, que depende de config.LINKEDIN_PESE_A_ROBOTS. "chumi.cl" no
# es el dominio de Chumi (es chumi-it.com, ver DOMINIO_CHUMI): sus avisos se leen revisando robots.txt, que los permite.
PORTALES_TRABAJO = ("indeed.com", "linkedin.com", "glassdoor.com", "bne.cl", "trabajando.cl", "chiletrabajos.cl",
                    "chumi.cl", "laborum.cl", "getonboard.com")
DOMINIO_CHUMI = urlsplit(chumi.BASE).hostname


# ---- SSRF (auditoría A2): /api/aviso solo lee portales de empleo conocidos y nunca direcciones privadas.
# Allowlist derivada de las fuentes de config.py (SITIOS y los portales de cada módulo) y de PORTALES_TRABAJO.
# Indeed, Glassdoor y LinkedIn van por JobSpy; sus dominios se listan aquí solo para pegar avisos a mano.
# Subdominios: solo los que el portal usa de verdad (www. y cl. donde existen).
DOMINIOS_PERMITIDOS = frozenset({
    "bne.gob.cl", "www.bne.gob.cl",                      # bne.py
    "trabajando.cl", "www.trabajando.cl",                # trabajando.py
    "chiletrabajos.cl", "www.chiletrabajos.cl",          # chiletrabajos.py
    "chumi-it.com", "www.chumi-it.com",                  # chumi.py
    "laborum.cl", "www.laborum.cl",                      # laborum.py
    "getonbrd.com", "www.getonbrd.com",                  # getonboard.py
    "himalayas.app", "www.himalayas.app",                # himalayas.py
    "jobicy.com", "www.jobicy.com",                      # jobicy.py
    "remotefirstjobs.com", "www.remotefirstjobs.com",    # remotefirstjobs.py
    "weworkremotely.com", "www.weworkremotely.com",      # weworkremotely.py
    "arbeitnow.com", "www.arbeitnow.com",                # arbeitnow.py
    "linkedin.com", "www.linkedin.com", "cl.linkedin.com",   # linkedin.py / JobSpy
    "indeed.com", "www.indeed.com", "cl.indeed.com",     # JobSpy (cl. es el de Chile)
    "glassdoor.com", "www.glassdoor.com",                # JobSpy
})
MAX_REDIRECTS = 3


def _es_de(host: str, dominio: str) -> bool:
    return host == dominio or host.endswith("." + dominio)


def _ip_privada(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified


def _es_url_aviso_permitida(url: str) -> bool:
    """True solo si la URL es http(s), sin credenciales, en un dominio de DOMINIOS_PERMITIDOS, con puerto 80/443 y
    resuelve solo a IPs públicas. Una IP literal privada (127.0.0.1, 10.x, ::1, 169.254.169.254) no está en la lista.
    shortcut: la IP se resuelve aquí y la conexión la resuelve de nuevo (DNS rebinding), fijar la IP resuelta en la
    conexión si esto deja de ser de uso local."""
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or p.username or p.password:
            return False
        host = (p.hostname or "").lower()
        if host not in DOMINIOS_PERMITIDOS:
            return False
        if p.port is not None and p.port not in (80, 443):
            return False
        for familia, _, _, _, dir_ in socket.getaddrinfo(host, p.port or 443):
            if _ip_privada(dir_[0]):
                return False
        return True
    except (ValueError, OSError):
        return False


def _validar_url_aviso(url: str):
    """Lanza ErrorFuente con un motivo legible si la URL no se puede leer (allowlist o IP privada)."""
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if host not in DOMINIOS_PERMITIDOS:
        raise ErrorFuente("ese dominio no es un portal de empleo conocido; abre el aviso y pega su texto a mano")
    if not _es_url_aviso_permitida(url):
        raise ErrorFuente("la URL apunta a una dirección privada o no pública; no se visitó nada")


def _limpio(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _texto(desc) -> str:
    t = html_mod.unescape(str(desc or ""))
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", t)
    t = BeautifulSoup(t, "html.parser").get_text() if "<" in t else t
    return "\n".join(_limpio(l) for l in t.replace("\r", "\n").splitlines() if l.strip())


def _sueldo(base) -> str:
    if not isinstance(base, dict) or not isinstance(base.get("value"), dict):
        return ""
    v = base["value"]
    mn, mx = v.get("minValue"), v.get("maxValue")
    if not (mn or mx):
        return ""
    miles = lambda x: f"{int(float(x)):,}".replace(",", ".")
    rango = miles(mn or mx) + (f" a {miles(mx)}" if mx and mn and str(mx) != str(mn) else "")
    unidad = {"MONTH": " al mes", "YEAR": " al año", "HOUR": " por hora"}.get(str(v.get("unitText")).upper(), "")
    return f"{_limpio(base.get('currency'))} {rango}{unidad}".strip()


def _ubicacion(ld: dict) -> str:
    if str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE" and not ld.get("jobLocation"):
        return "Remoto"
    lugar = ld.get("jobLocation")
    if isinstance(lugar, list):
        lugar = lugar[0] if lugar else {}
    if not isinstance(lugar, dict):
        return ""
    dire = lugar.get("address") if isinstance(lugar.get("address"), dict) else {}
    partes = [_limpio(dire.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry")]
    return ", ".join(p for p in partes if p)


def _modalidad(ld: dict, titulo: str, descripcion: str) -> str:
    if str(ld.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        return "Remoto"
    m, _ = filtros.detectar_modalidad(filtros.normalizar(titulo), filtros.normalizar(descripcion), False)
    return m if m in MODALIDADES else ""


def _job_posting(html: str) -> dict | None:
    soup = BeautifulSoup((html or "")[:LIMITE_HTML], "html.parser")
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            ld = json.loads(s.get_text())
        except ValueError:
            continue
        candidatos = ld if isinstance(ld, list) else [ld]
        if isinstance(ld, dict) and isinstance(ld.get("@graph"), list):
            candidatos = ld["@graph"]
        for item in candidatos:
            if isinstance(item, dict) and item.get("@type") in ("JobPosting", ["JobPosting"]):
                return item
    return None


def parsear_aviso(html: str) -> dict:
    """Campos para el formulario manual. Lanza ErrorFuente si no hay JobPosting usable."""
    ld = _job_posting(html)
    if not ld:
        raise ErrorFuente("el aviso no publica datos de empleo (JobPosting); complétalo a mano")
    titulo = _limpio(ld.get("title"))
    org = ld.get("hiringOrganization") if isinstance(ld.get("hiringOrganization"), dict) else {}
    empresa = _limpio(org.get("name"))
    if not titulo or not empresa:
        raise ErrorFuente("el aviso no trae cargo y empresa; complétalo a mano")
    descripcion = _texto(ld.get("description"))
    return {
        "titulo": titulo[:200],
        "empresa": empresa[:200],
        "ubicacion": _ubicacion(ld)[:200],
        "modalidad": _modalidad(ld, titulo, descripcion),
        "sueldo": _sueldo(ld.get("baseSalary"))[:100],
        "descripcion": descripcion[:10000],
    }


def texto_visible(html: str) -> str:
    """El texto que una persona vería en la página (sin scripts ni estilos), recortado para la IA."""
    soup = BeautifulSoup((html or "")[:LIMITE_HTML], "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return "\n".join(_limpio(l) for l in soup.get_text("\n").splitlines() if l.strip())[:8000]


MODALIDADES_DB = ("Remoto", "Híbrido", "Presencial")


def _jk_indeed(url: str):
    """El identificador del aviso de Indeed (parámetro jk o vjk), o None si la URL no es de Indeed."""
    partes = urlsplit(url)
    if "indeed." not in partes.netloc:
        return None
    valores = parse_qs(partes.query)
    return (valores.get("jk") or valores.get("vjk") or [None])[0]


def desde_base(con, url: str):
    """Si la oferta ya está en tu base (la trajo la búsqueda), sus datos guardados. No visita ningún sitio:
    sirve para Indeed, que no permite leer sus avisos. None si la URL no está guardada.
    En Indeed se busca también por el identificador (jk), así un link con otros parámetros igual se reconoce."""
    fila = con.execute("SELECT titulo, empresa, ubicacion, modalidad, sueldo FROM ofertas WHERE url = ?", (url,)).fetchone()
    jk = _jk_indeed(url)
    if fila is None and jk:
        for cand in con.execute("SELECT titulo, empresa, ubicacion, modalidad, sueldo, url FROM ofertas "
                                "WHERE url LIKE '%indeed.%' AND url LIKE ?", (f"%jk={jk}%",)).fetchall():
            if _jk_indeed(cand[5]) == jk:               # el LIKE puede acertar de más: se compara el valor exacto
                fila = cand[:5]
                break
    if fila is None:
        return None
    titulo, empresa, ubicacion, modalidad, sueldo = (fila[k] or "" for k in range(5))
    return {
        "titulo": titulo, "empresa": empresa, "ubicacion": ubicacion,
        "modalidad": modalidad if modalidad in MODALIDADES_DB else "",
        "sueldo": "" if sueldo in ("", "No indicado") else sueldo,
    }


def html_con_navegador(url: str, validar=_validar_url_aviso) -> str:
    """Abre el aviso en un Chromium sin ventana y devuelve el HTML ya renderizado. Solo se llama DESPUÉS de que
    desde_url ya leyó la página. Solo carga recursos del mismo sitio. No revisa robots.txt.
    SSRF: `validar` revisa la URL antes de abrirla y, después, cada salto de sus redirects y la URL final.
    Los tests pasan `validar=lambda u: None` para un servidor local; el validador por defecto rechaza 127.0.0.1."""
    validar(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ErrorFuente("falta Playwright en este equipo; completa a mano o pega el texto del aviso")
    partes = urlsplit(url)
    origen = f"{partes.scheme}://{partes.netloc}"
    with sync_playwright() as p:
        nav = p.chromium.launch()
        try:
            ctx = nav.new_context(user_agent=USER_AGENT_HTTP, locale="es-CL")
            ctx.route("**/*", lambda r: r.abort() if not r.request.url.startswith(origen)
                      or r.request.resource_type in ("image", "font", "media") else r.continue_())
            page = ctx.new_page()
            try:
                respuesta = page.goto(url, wait_until="domcontentloaded", timeout=TIEMPO_NAVEGADOR_MS)
                page.wait_for_timeout(2500)          # tiempo para que el JavaScript pinte el aviso
            except Exception as e:
                raise ErrorFuente(f"el navegador no pudo abrir el aviso ({type(e).__name__})")
            # shortcut: Chromium ya siguió el redirect cuando esto lo rechaza (no se lee su contenido, pero la
            # solicitud salió), bloquearlo en la red del navegador si la app deja de ser de uso local.
            pedido = respuesta.request if respuesta else None
            while pedido is not None:
                validar(pedido.url)
                pedido = pedido.redirected_from
            validar(page.url)
            contenido = page.content()
            marca = parece_bloqueo(contenido)
            if marca:
                raise Bloqueo("página de verificación (%s)" % marca)
            return contenido
        finally:
            nav.close()


def _modalidad_linkedin(criterios: dict, titulo: str, descripcion: str, ubicacion: str) -> str:
    tipo = filtros.normalizar(criterios.get("tipo de empleo", ""))
    if "remoto" in tipo or "remote" in tipo or "remoto" in filtros.normalizar(ubicacion):
        return "Remoto"
    if "hibrido" in tipo or "híbrido" in criterios.get("tipo de empleo", "").lower():
        return "Híbrido"
    m, _ = filtros.detectar_modalidad(filtros.normalizar(titulo), filtros.normalizar(descripcion), False)
    return m if m in MODALIDADES else ""


def desde_linkedin(url: str, cliente, robots) -> dict:
    """El aviso público de LinkedIn no trae JSON-LD. El HTML de invitado sí trae cargo, empresa y texto.
    Se pide pese al robots.txt de LinkedIn solo con config.LINKEDIN_PESE_A_ROBOTS encendido (riesgo aceptado, PRODUCT.md)."""
    if not config.LINKEDIN_PESE_A_ROBOTS:
        raise ErrorFuente("la lectura automática de LinkedIn está desactivada en config.py "
                          "(LINKEDIN_PESE_A_ROBOTS=False); abre el aviso, copia su texto y pégalo a mano")
    jid = linkedin._job_id(url)
    if not jid:
        raise ErrorFuente("ese enlace de LinkedIn no tiene el número del aviso; complétalo a mano")
    try:
        html = pedir("%s/jobs-guest/jobs/api/jobPosting/%s" % (linkedin.BASE, jid), cliente, robots,
                     ignorar_robots=config.LINKEDIN_PESE_A_ROBOTS, validar_url=_validar_url_aviso)
        datos = linkedin.aviso_formulario(html)
        criterios = datos.pop("criterios")
        datos["modalidad"] = _modalidad_linkedin(criterios, datos["titulo"], datos["descripcion"], datos["ubicacion"])
        datos["sueldo"] = ""          # el HTML guest casi nunca trae sueldo en Chile
        return datos
    except Bloqueo:
        # LinkedIn bloquea muchas peticiones automáticas: el navegador podría pasar, pero es lento.
        # Mejor falla limpiamente y pide que pegue el texto del aviso.
        raise ErrorFuente("LinkedIn rechaza las descargas automáticas; abre el aviso, copia su texto y pégalo abajo")


def desde_url(url: str, cliente, robots, navegador=None) -> dict:
    """Saca los datos del aviso, en este orden:
      1. LinkedIn: HTML público de invitado (la página del aviso no trae JSON-LD).
      2. HTML normal (pedir sin revisar robots.txt en portales de empleo, con pausa). Si trae JSON-LD, listo.
      3. Si la página llega vacía (JavaScript), un navegador la renderiza; después se prueba el JSON-LD otra vez.
      4. Lo que quede de texto visible se le pasa a la IA.
    Las fuentes de riesgo aceptado (PRODUCT.md) se revisan ANTES de visitar nada: con su flag apagado, ErrorFuente.
    `navegador` (por defecto html_con_navegador) es inyectable para las pruebas: así no se abre un sitio real.
    Propaga Bloqueo, NoEncontrada y ErrorFuente."""
    host = urlsplit(url).hostname or ""          # hostname ya viene en minúsculas y sin puerto
    if _es_de(host, "linkedin.com"):
        return desde_linkedin(url, cliente, robots)      # rechaza si LINKEDIN_PESE_A_ROBOTS está apagado
    if _es_de(host, DOMINIO_CHUMI) and not config.CHUMI_PESE_A_TOS:
        raise ErrorFuente("la lectura automática de Chumi está desactivada en config.py "
                          "(CHUMI_PESE_A_TOS=False); abre el aviso, copia su texto y pégalo a mano")
    en_portal = any(_es_de(host, d) for d in PORTALES_TRABAJO)
    html = pedir(url, cliente, robots, ignorar_robots=en_portal, validar_url=_validar_url_aviso)     # robots.txt solo se salta en portales de empleo
    try:
        return parsear_aviso(html)
    except ErrorFuente:
        pass
    texto = texto_visible(html)
    if len(texto) < MINIMO_TEXTO:
        html = (navegador or html_con_navegador)(url)
        try:
            return parsear_aviso(html)
        except ErrorFuente:
            pass
        texto = texto_visible(html)
    datos = ia.extraer_aviso(texto)
    if "error" in datos:
        raise ErrorFuente(datos["error"])
    if not datos.get("titulo") and not datos.get("empresa"):      # la IA no encontró nada: no es un éxito
        raise ErrorFuente("no encontré cargo ni empresa en la página; complétalo a mano")
    return datos


def mensaje_error(ex: Exception) -> str:
    if isinstance(ex, Bloqueo):
        return "el sitio rechazó la lectura; complétalo a mano"
    if isinstance(ex, NoEncontrada):
        return "ese enlace no existe (404)"
    if isinstance(ex, ErrorFuente):
        return str(ex)
    return "no se pudo leer el aviso"
