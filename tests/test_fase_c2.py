"""Fase 2 de la auditoría (A2 SSRF en /api/aviso, A3 token local): pruebas de seguridad sin red real.
El DNS se simula con monkeypatch y los servidores de prueba van en 127.0.0.1 solo cuando el test lo pide."""
import http.client
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rellenar_aviso
import servidor
from red import Bloqueo, ClienteHTTP, ErrorFuente, Respuesta, pedir
from test_servidor import pedir as pedir_api, puerto_libre

IP_PUBLICA = "93.184.216.34"          # ejemplo público (TEST-NET no sirve: is_private la rechaza en algunas versiones)


def dns(monkeypatch, ip=IP_PUBLICA):
    """Simula la resolución DNS: cada host resuelve a `ip` (o a varias si se pasa una lista)."""
    ips = ip if isinstance(ip, list) else [ip]
    monkeypatch.setattr(rellenar_aviso.socket, "getaddrinfo",
                        lambda h, p=None, *a, **k: [(socket.AF_INET, 1, 6, "", (i, p or 443)) for i in ips])


class Robots:
    def bloqueo(self, u): return ""
    def no_disponible(self, u): return False
    def permitido(self, u): return True


# ---- SSRF: direcciones y hosts que nunca se leen
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/nada", "http://127.0.0.1:8765/nada", "http://localhost/nada",
    "http://[::1]/nada", "http://10.0.0.5/nada", "http://192.168.1.1/nada",
    "http://169.254.169.254/latest/meta-data/",          # metadata cloud
    "http://0.0.0.0/nada", "https://user:clave@www.bne.gob.cl/oferta/1",   # credenciales embebidas
    "https://www.bne.gob.cl:8443/oferta/1",                # puerto no estándar
    "ftp://www.bne.gob.cl/oferta/1", "file:///etc/passwd", "javascript:alert(1)",
])
def test_ssrf_rechaza_direcciones_privadas_y_urls_raras(url):
    assert rellenar_aviso._es_url_aviso_permitida(url) is False
    with pytest.raises(ErrorFuente):
        rellenar_aviso._validar_url_aviso(url)


def test_ssrf_rechaza_un_dominio_de_portal_que_resuelve_a_ip_privada(monkeypatch):
    dns(monkeypatch, "10.0.0.5")                              # un DNS que apunta a la red interna
    assert rellenar_aviso._es_url_aviso_permitida("https://www.bne.gob.cl/oferta/1") is False
    with pytest.raises(ErrorFuente, match="dirección privada"):
        rellenar_aviso._validar_url_aviso("https://www.bne.gob.cl/oferta/1")


def test_ssrf_rechaza_si_alguna_ip_resuelta_es_privada(monkeypatch):
    dns(monkeypatch, [IP_PUBLICA, "192.168.0.10"])            # una pública y una privada: basta una para rechazar
    assert rellenar_aviso._es_url_aviso_permitida("https://www.bne.gob.cl/oferta/1") is False


@pytest.mark.parametrize("url", ["https://ejemplo.cl/1", "https://evil.example.com/x", "https://bne.gob.cl.evil.com/x",
                                 "https://127.0.0.1.nip.io/x", "https://metadata.google.internal/x"])
def test_ssrf_rechaza_dominios_fuera_de_la_allowlist(monkeypatch, url):
    dns(monkeypatch)
    assert rellenar_aviso._es_url_aviso_permitida(url) is False
    with pytest.raises(ErrorFuente, match="portal de empleo conocido"):
        rellenar_aviso._validar_url_aviso(url)


# ---- SSRF: dominios reales que sí se leen
@pytest.mark.parametrize("url", [
    "https://www.bne.gob.cl/oferta/1", "https://www.trabajando.cl/trabajo/1-x", "https://www.chiletrabajos.cl/trabajo/x-1",
    "https://chumi-it.com/trabajos/x-1", "https://www.laborum.cl/empleos/x-1.html", "https://www.getonbrd.com/jobs/x",
    "https://himalayas.app/jobs/x", "https://jobicy.com/jobs/1", "https://weworkremotely.com/remote-jobs/x",
    "https://www.linkedin.com/jobs/view/4487295075/", "https://cl.indeed.com/viewjob?jk=1",
    "https://www.glassdoor.com/job-listing/x", "http://www.bne.gob.cl/oferta/1",
])
def test_ssrf_acepta_los_portales_reales_con_ip_publica(monkeypatch, url):
    dns(monkeypatch)
    assert rellenar_aviso._es_url_aviso_permitida(url) is True
    rellenar_aviso._validar_url_aviso(url)                    # no lanza


# ---- SSRF: redirects se validan salto a salto
class ClienteRedirige(ClienteHTTP):
    """Un ClienteHTTP cuyo `abrir` devuelve, para cada URL, una respuesta de la tabla (200, o 302 con Location)."""
    def __init__(self, tabla):
        super().__init__(dormir=lambda s: None, azar=lambda a, b: 0)
        self.tabla = tabla
        self.pedidas = []
        self._abrir = self._abrir_sin_redirigir = self._falso

    def _falso(self, req, timeout=None):
        import urllib.error, io
        url = req.full_url
        self.pedidas.append(url)
        status, cuerpo, loc = self.tabla[url]
        if status in (301, 302, 303, 307, 308):
            hdrs = {"Location": loc}
            raise urllib.error.HTTPError(url, status, "redir", hdrs, io.BytesIO(b""))
        class _R:
            def __init__(s):
                s.status, s.headers = status, type("H", (), {"get_content_charset": lambda x: "utf-8"})()
            def read(s): return cuerpo.encode()
            def __enter__(s): return s
            def __exit__(s, *a): return False
        return _R()


def test_redirect_a_ip_privada_se_rechaza_antes_de_pedirla(monkeypatch):
    """Un portal permitido redirige a 127.0.0.1: el segundo salto se valida y se rechaza sin pedirlo."""
    dns(monkeypatch)
    cli = ClienteRedirige({"https://www.bne.gob.cl/oferta/1": (302, "", "http://127.0.0.1:8765/api/respaldo")})
    with pytest.raises(ErrorFuente, match="dirección privada|portal de empleo conocido"):
        pedir("https://www.bne.gob.cl/oferta/1", cli, Robots(), validar_url=rellenar_aviso._validar_url_aviso)
    assert "http://127.0.0.1:8765/api/respaldo" not in cli.pedidas


def test_redirect_a_dominio_fuera_de_la_allowlist_se_rechaza(monkeypatch):
    dns(monkeypatch)
    cli = ClienteRedirige({"https://www.bne.gob.cl/oferta/1": (301, "", "https://evil.example.com/x")})
    with pytest.raises(ErrorFuente, match="portal de empleo conocido"):
        pedir("https://www.bne.gob.cl/oferta/1", cli, Robots(), validar_url=rellenar_aviso._validar_url_aviso)
    assert cli.pedidas == ["https://www.bne.gob.cl/oferta/1"]


def test_redirect_dentro_de_la_allowlist_se_sigue(monkeypatch):
    dns(monkeypatch)
    cli = ClienteRedirige({"https://www.bne.gob.cl/oferta/1": (302, "", "https://www.bne.gob.cl/oferta/2"),
                           "https://www.bne.gob.cl/oferta/2": (200, "<html>ok</html>", "")})
    assert pedir("https://www.bne.gob.cl/oferta/1", cli, Robots(), validar_url=rellenar_aviso._validar_url_aviso) == "<html>ok</html>"


def test_mas_de_tres_redirects_se_corta(monkeypatch):
    dns(monkeypatch)
    tabla = {f"https://www.bne.gob.cl/{i}": (302, "", f"https://www.bne.gob.cl/{i + 1}") for i in range(10)}
    cli = ClienteRedirige(tabla)
    with pytest.raises(ErrorFuente, match="redirige demasiadas veces"):
        pedir("https://www.bne.gob.cl/0", cli, Robots(), validar_url=rellenar_aviso._validar_url_aviso)


# ---- SSRF: la ruta sin red (oferta ya guardada) no se ve afectada
def test_desde_base_sigue_funcionando_con_una_url_fuera_de_la_allowlist(tmp_path):
    import buscar, pandas as pd
    con = buscar.conectar(str(tmp_path / "t.db"))
    df = pd.DataFrame([{"job_url": "https://cl.indeed.com/viewjob?jk=77", "title": "Analista QA", "company": "Acme",
                        "location": "Santiago, Chile", "description": "", "date_posted": "", "is_remote": False,
                        "min_amount": None, "max_amount": None, "currency": "", "interval": ""}])
    buscar.guardar(con, buscar.procesar(df, "t", "indeed"))
    assert rellenar_aviso.desde_base(con, "https://cl.indeed.com/viewjob?jk=77")["empresa"] == "Acme"


# ---- servidor: /api/aviso aplica la allowlist antes de nada
@pytest.fixture
def srv(tmp_path):
    import threading
    ruta = str(tmp_path / "t.db")
    buscar_con = servidor.buscar.conectar(ruta)
    buscar_con.close()
    httpd = servidor.crear_servidor(servidor.Aplicacion(ruta, lambda con: 0), puerto_libre(), "127.0.0.1")
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.mark.parametrize("url", ["http://127.0.0.1:8765/nada", "http://169.254.169.254/latest/", "https://ejemplo.cl/1"])
def test_api_aviso_rechaza_urls_prohibidas_con_400(srv, url):
    st, _, cuerpo = pedir_api(srv, "POST", "/api/aviso", {"url": url})
    assert st == 400 and b"URL no permitida" in cuerpo


# ---- token (A3)
def _crudo(puerto, metodo, ruta, cuerpo=None):
    """Petición SIN el helper de pruebas (que añade el token): así se ve el comportamiento real sin cabecera."""
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
    c.request(metodo, ruta, cuerpo, {"Content-Type": "application/json"} if cuerpo else {})
    r = c.getresponse()
    return r.status, r.read()


def test_api_sin_token_da_401(srv):
    st, cuerpo = _crudo(srv, "GET", "/api/ofertas")
    assert st == 401 and b"falta el token" in cuerpo
    assert _crudo(srv, "POST", "/api/marcar", '{"url": "http://qa", "estado": "revisada", "origen": "lista"}')[0] == 401


def test_api_con_token_incorrecto_da_401(srv):
    assert pedir_api(srv, "GET", "/api/ofertas", None, {"X-JT-Token": "no-es-el-token"})[0] == 401
    assert pedir_api(srv, "POST", "/api/marcar", {"url": "http://qa", "estado": "revisada", "origen": "lista"},
                     {"X-JT-Token": "no-es-el-token"})[0] == 401


def test_api_con_token_correcto_da_200(srv):
    assert pedir_api(srv, "GET", "/api/ofertas", None, {"X-JT-Token": servidor.JT_TOKEN})[0] == 200


def test_api_estado_queda_exento_del_token(srv):
    assert pedir_api(srv, "GET", "/api/estado", None, {})[0] == 200          # healthcheck del Dockerfile


def test_la_pagina_lleva_el_token_en_el_js_y_no_en_texto_visible(srv):
    st, _, cuerpo = pedir_api(srv, "GET", "/")
    html = cuerpo.decode("utf-8")
    assert st == 200 and "__JT_TOKEN__" not in html          # el marcador se sustituye
    assert servidor.JT_TOKEN in html                           # el token va en el JS (cabecera X-JT-Token)
    visible = html.split("<script>")[0]                        # lo que se ve: antes del script
    assert servidor.JT_TOKEN not in visible

