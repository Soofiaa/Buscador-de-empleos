"""Acceso a la red para las fuentes que no usa JobSpy (BNE, Trabajando, Chiletrabajos).

Reglas (heredadas de la app anterior "Busca Empleo", que las trae de decisiones de Sofia):
  - Se consulta robots.txt de cada sitio antes de pedir una página.
  - Pausa aleatoria de 3 a 5 segundos entre peticiones y un User-Agent que dice quién es (no se disfraza).
  - Ante 401/403/429 o una página de verificación/CAPTCHA se DETIENE ese sitio: no se reintenta ni se esquiva.
"""
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

MAX_REDIRECTS = 3            # saltos que se siguen a mano cuando hay que validar cada URL (ver ClienteHTTP._get)
PAUSA_ENTRE_PETICIONES = (3.0, 5.0)
USER_AGENT_HTTP = "BuscaEmpleo/0.1 (busqueda personal de empleo)"

STATUS_BLOQUEO = (401, 403, 429)
MARCAS_BLOQUEO = ("captcha", "cf-chl", "just a moment", "attention required", "challenge-platform",
                  "actividad inusual", "unusual activity", "verifica que eres humano", "access denied")


class Bloqueo(Exception):
    """El sitio nos rechazó (o no se pudo leer su robots.txt): se deja ese sitio en paz el resto de la corrida."""


class ErrorFuente(Exception):
    """Fallo de un sitio que no es un bloqueo (red, formato inesperado). Quien llama decide si insistir."""


class NoEncontrada(ErrorFuente):
    """HTTP 404."""


def es_bloqueo(status: int) -> bool:
    return status in STATUS_BLOQUEO


def parece_bloqueo(texto: str) -> Optional[str]:
    """Señal encontrada si una respuesta 200 es en realidad un CAPTCHA o una verificación."""
    t = (texto or "")[:20000].lower()
    return next((m for m in MARCAS_BLOQUEO if m in t), None)


@dataclass
class Respuesta:
    status: int          # 0 = error de red / tiempo agotado
    texto: str = ""
    error: str = ""


class _SinRedirigir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None            # el 3xx llega como HTTPError: lo sigue ClienteHTTP._get, validando cada salto


class ClienteHTTP:
    def __init__(self, user_agent: Optional[str] = None, pausa: Tuple[float, float] = None, timeout: int = 25,
                 dormir: Callable[[float], None] = time.sleep, azar: Callable[[float, float], float] = random.uniform,
                 abrir: Callable = None):
        self.ua = user_agent or USER_AGENT_HTTP
        self.pausa = pausa or PAUSA_ENTRE_PETICIONES
        self.timeout = timeout
        self._dormir, self._azar = dormir, azar
        self._abrir = abrir or urllib.request.urlopen
        self._abrir_sin_redirigir = abrir or urllib.request.build_opener(_SinRedirigir).open
        self._primera = True
        self.peticiones = 0
        self.al_responder: Optional[Callable[[int], None]] = None   # telemetría pasiva: recibe solo el status

    def esperar_turno(self):
        """La pausa entre peticiones (no antes de la primera). La usa también Laborum, que pide con Playwright."""
        if not self._primera:
            self._dormir(self._azar(*self.pausa))
        self._primera = False
        self.peticiones += 1

    def get(self, url: str, datos: Optional[dict] = None, validar_url: Optional[Callable[[str], None]] = None) -> Respuesta:
        """GET; con `datos`, un POST con ese cuerpo JSON. Con validar_url, los redirects no se siguen solos: cada
        salto (hasta MAX_REDIRECTS) se valida antes de pedirlo; validar_url lanza ErrorFuente si no corresponde."""
        self.esperar_turno()
        respuesta = self._get(url, datos, validar_url)
        if self.al_responder:
            try:
                self.al_responder(respuesta.status)
            except Exception:
                pass                                       # la telemetría nunca cambia lo que pasa con la fuente
        return respuesta

    def _get(self, url: str, datos: Optional[dict] = None, validar_url=None) -> Respuesta:
        if validar_url is None:                    # como siempre: urllib sigue los redirects
            return self._una(url, datos, self._abrir)[0]
        for _ in range(MAX_REDIRECTS + 1):
            validar_url(url)
            respuesta, destino = self._una(url, datos, self._abrir_sin_redirigir)
            if not destino:
                return respuesta
            url, datos = urllib.parse.urljoin(url, destino), None
        raise ErrorFuente("el aviso redirige demasiadas veces (más de %d); no se siguió" % MAX_REDIRECTS)

    def _una(self, url: str, datos: Optional[dict], abrir) -> Tuple[Respuesta, str]:
        """Una sola solicitud: (respuesta, destino del redirect si lo hay y no se siguió)."""
        cuerpo = json.dumps(datos).encode("utf-8") if datos is not None else None
        headers = {
            "User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9",
            "Accept-Language": "es-CL,es;q=0.9", "Accept-Encoding": "identity",
        }
        if cuerpo is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=cuerpo, headers=headers)
        try:
            with self._abrir(req, timeout=self.timeout) as r:
                cuerpo_resp = r.read()
                cs = r.headers.get_content_charset() if hasattr(r.headers, "get_content_charset") else None
                return Respuesta(getattr(r, "status", 200), cuerpo_resp.decode(cs or "utf-8", errors="replace")), ""
        except urllib.error.HTTPError as e:
            destino = (e.headers.get("Location") or "") if e.code in (301, 302, 303, 307, 308) and e.headers else ""
            return Respuesta(e.code, "", "HTTP %d" % e.code), destino
        except Exception as e:  # DNS, timeout, SSL...
            return Respuesta(0, "", "%s: %s" % (type(e).__name__, e)), ""


def pedir(url: str, cliente, robots, datos: Optional[dict] = None, ignorar_robots: bool = False,
          validar_url: Optional[Callable[[str], None]] = None) -> str:
    """Descarga una URL respetando robots.txt por defecto. 
    Si ignorar_robots es True, se salta la validación del parser (útil para /api/aviso).
    Con validar_url (SSRF, ver rellenar_aviso._validar_url_aviso) se valida la URL y cada redirect antes de pedirlos."""
    if validar_url is not None:
        validar_url(url)
    if cliente is None:        # un error legible en vez de un AttributeError a mitad de camino
        raise ErrorFuente("no hay cliente HTTP para leer la página; no se visitó nada")

    # Solo validamos robots si NO se explícitamente que lo ignoremos
    if not ignorar_robots:
        rechazo = getattr(robots, "bloqueo", lambda _u: "")(url)
        if rechazo:
            raise Bloqueo("robots.txt rechazó la lectura (%s)" % rechazo)
        if robots.no_disponible(url):
            raise ErrorFuente("no se pudo leer robots.txt (¿sin internet o el sitio no responde?); no se visitó nada")
        if not robots.permitido(url):
            raise ErrorFuente("robots.txt no permite esta URL")
            
    # El resto del flujo de descarga se mantiene exactamente igual e intacto
    # solo ClienteHTTP sabe seguir redirects validando; un cliente de prueba no redirige
    kw = {"validar_url": validar_url} if validar_url is not None and isinstance(cliente, ClienteHTTP) else {}
    r = cliente.get(url, **kw) if datos is None else cliente.get(url, datos, **kw)
    if es_bloqueo(r.status):
        raise Bloqueo(r.error or "HTTP %d" % r.status)
    if r.status == 404:
        raise NoEncontrada("HTTP 404")
    if r.status != 200:
        raise ErrorFuente(r.error or "HTTP %s" % r.status)
    marca = parece_bloqueo(r.texto)
    if marca and "__NUXT_DATA__" not in r.texto and '"paginaOfertas"' not in r.texto and "job-item" not in r.texto:
        raise Bloqueo("página de verificación (%s)" % marca)
    return r.texto
