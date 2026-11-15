"""rellenar_aviso con navegador: se abre solo si la página llegó vacía (JavaScript). Pedir el aviso no revisa robots.txt."""
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rellenar_aviso
from red import Bloqueo, ErrorFuente, Respuesta

PAGINA_JS = b"""<html><body><div id="x"></div><script>
document.getElementById('x').innerHTML = '<h1>Analista de Datos Junior</h1><p>Empresa Acme, Santiago, Chile. ' + 'Buscamos profesional con SQL y Python para reportes de gestion. '.repeat(8) + '</p>';
</script></body></html>"""


class Robots:
    def __init__(self, bloqueado=False):
        self.bloqueado = bloqueado

    def bloqueo(self, url):
        return "HTTP 403" if self.bloqueado else ""

    def no_disponible(self, url):
        return False

    def permitido(self, url):
        return not self.bloqueado


class Cliente:
    def __init__(self, html):
        self.html = html

    def get(self, url, datos=None):
        return Respuesta(200, self.html)


def test_portal_de_empleo_no_consulta_robots_txt(monkeypatch):
    """En un portal de empleo, el aviso se lee aunque robots.txt lo prohíba (decisión de Sofia; ver desde_url)."""
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso", lambda t: {"titulo": "X", "empresa": "Y"})
    html = "<body>" + "<p>texto suficiente del aviso</p>" * 20 + "</body>"
    r = rellenar_aviso.desde_url("https://cl.indeed.com/viewjob?jk=1", Cliente(html), Robots(bloqueado=True))
    assert r["empresa"] == "Y"


def test_otro_sitio_sigue_respetando_robots_txt():
    # Un dominio fuera de la allowlist se rechaza por SSRF (ErrorFuente) antes de mirar robots.txt: es lo correcto.
    with pytest.raises(ErrorFuente, match="portal de empleo conocido"):
        rellenar_aviso.desde_url("https://ejemplo.cl/1", Cliente("<body>x</body>"), Robots(bloqueado=True))


def test_robots_txt_sigue_rechazando_un_portal_de_la_allowlist(monkeypatch):
    # Dentro de la allowlist, robots.txt manda: un portal bloqueado sigue siendo Bloqueo, no un error genérico.
    # El DNS se simula (sin red real): bne.gob.cl resuelve a una IP pública de ejemplo.
    import socket
    monkeypatch.setattr(rellenar_aviso.socket, "getaddrinfo",
                        lambda h, p, *a, **k: [(socket.AF_INET, 1, 6, "", ("93.184.216.34", p or 443))])
    with pytest.raises(Bloqueo):
        rellenar_aviso.desde_url("https://www.bne.gob.cl/oferta/1", Cliente("<body>x</body>"), Robots(bloqueado=True))


def test_pagina_vacia_usa_navegador_y_luego_la_ia(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda u, c, r, **_: "<html><body><div id=x></div></body></html>")
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador",
                        lambda u: "<html><body><h1>Analista QA</h1>" + "<p>texto del aviso</p>" * 30 + "</body></html>")
    visto = {}
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso",
                        lambda t: visto.setdefault("t", t) and {"titulo": "Analista QA", "empresa": "X"})
    r = rellenar_aviso.desde_url("https://ejemplo.cl/1", None, Robots())
    assert r["titulo"] == "Analista QA" and "Analista QA" in visto["t"]


def test_pagina_con_texto_no_abre_navegador(monkeypatch):
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda u, c, r, **_: "<body>" + "<p>texto suficiente del aviso</p>" * 20 + "</body>")
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    monkeypatch.setattr(rellenar_aviso.ia, "extraer_aviso", lambda t: {"titulo": "X", "empresa": "Y"})
    assert rellenar_aviso.desde_url("https://ejemplo.cl/1", None, Robots())["empresa"] == "Y"


def test_navegador_real_renderiza_javascript():
    """Playwright de verdad contra un servidor local: el texto aparece solo después de ejecutar el JavaScript."""
    pytest.importorskip("playwright.sync_api")

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGINA_JS)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/aviso"
    try:
        try:
            # 127.0.0.1 no está en la allowlist de producción: el test usa un validador no-op solo para su servidor local.
            html = rellenar_aviso.html_con_navegador(url, validar=lambda u: None)
        except ErrorFuente as ex:
            if "Executable doesn't exist" in str(ex) or "playwright install" in str(ex):
                pytest.skip("Chromium de Playwright no instalado en este equipo")
            raise
    finally:
        srv.shutdown()
        srv.server_close()
    assert "Analista de Datos Junior" in html


def test_el_navegador_rechaza_una_ip_privada_con_el_validador_por_defecto():
    """Con el validador por defecto, 127.0.0.1 se rechaza sin abrir el navegador: no está en la allowlist de producción."""
    with pytest.raises(ErrorFuente, match="portal de empleo conocido"):
        rellenar_aviso.html_con_navegador("http://127.0.0.1:9/aviso")

