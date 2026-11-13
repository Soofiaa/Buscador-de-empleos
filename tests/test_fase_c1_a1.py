"""Fuentes con riesgo aceptado (auditoría C1 + A1): LinkedIn pese a robots.txt y Chumi pese a sus Condiciones de Uso,
activas por defecto y apagables con config.LINKEDIN_PESE_A_ROBOTS / config.CHUMI_PESE_A_TOS. Todo sin red: JobSpy se
reemplaza en sys.modules (buscar_ofertas lo importa dentro de la función) y los portales por una función falsa."""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import buscar
import config
import informe
import rellenar_aviso
import servidor
from red import ErrorFuente, pedir

FIX = Path(__file__).parent / "fixtures"
AVISO_CHUMI = "https://chumi-it.com/trabajos/desarrollador-backend-12345"      # el dominio real (chumi.BASE)
AVISO_LINKEDIN = "https://www.linkedin.com/jobs/view/4487295075/"


class RobotsLibre:
    def bloqueo(self, u): return ""
    def no_disponible(self, u): return False
    def permitido(self, u): return True


def _flags(monkeypatch, linkedin=True, chumi=True):
    monkeypatch.setattr(config, "LINKEDIN_PESE_A_ROBOTS", linkedin)
    monkeypatch.setattr(config, "CHUMI_PESE_A_TOS", chumi)


def _corrida(tmp_path, monkeypatch, fuentes=None):
    """Una búsqueda con LinkedIn (JobSpy) y Chumi (portal), ambos falsos. Devuelve (consultas JobSpy, portales, avisos)."""
    consultas, portales = [], []
    def scrape_jobs(**kw):
        consultas.append(kw)
        return pd.DataFrame()
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=scrape_jobs))
    monkeypatch.setattr(config, "SITIOS", ["linkedin", "chumi"])
    monkeypatch.setattr(config, "TERMINOS_LINKEDIN", ["qa"])
    monkeypatch.setattr(config, "UBICACIONES", ["Santiago, Chile"])
    monkeypatch.setattr(config, "INCLUIR_REMOTO", False)
    monkeypatch.setattr(buscar, "_buscar_portal", lambda con, sitio, *a, **k: portales.append(sitio) or 0)
    monkeypatch.setattr(buscar.time, "sleep", lambda s: None)
    monkeypatch.setattr(buscar, "_say", lambda m: None)
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.buscar_ofertas(con) if fuentes is None else buscar.buscar_ofertas(con, fuentes)
    avisos = json.loads(con.execute("SELECT detalle FROM corridas").fetchone()[0])["avisos"]
    return consultas, portales, avisos


# ---- los flags y la lista efectiva de fuentes
def test_los_flags_vienen_encendidos_y_la_lista_es_la_de_siempre():
    assert config.LINKEDIN_PESE_A_ROBOTS is True and config.CHUMI_PESE_A_TOS is True
    assert buscar.fuentes_activas() == config.SITIOS


@pytest.mark.parametrize("linkedin, chumi, fuera", [(False, True, {"linkedin"}), (True, False, {"chumi"}),
                                                    (False, False, {"linkedin", "chumi"})])
def test_fuentes_activas_quita_la_fuente_apagada_sin_tocar_config(monkeypatch, linkedin, chumi, fuera):
    antes = list(config.SITIOS)
    _flags(monkeypatch, linkedin, chumi)
    assert buscar.fuentes_activas() == [s for s in antes if s not in fuera]
    assert config.SITIOS == antes


# ---- búsqueda
def test_con_los_flags_encendidos_la_busqueda_es_la_de_siempre(tmp_path, monkeypatch):
    consultas, portales, avisos = _corrida(tmp_path, monkeypatch)
    assert [c["site_name"] for c in consultas] == [["linkedin"]] and consultas[0]["fetch_description"] is True
    assert portales == ["chumi"]
    assert not any("no se consultó" in a for a in avisos)


def test_linkedin_apagado_no_entra_en_el_plan_y_se_avisa(tmp_path, monkeypatch):
    _flags(monkeypatch, linkedin=False)
    consultas, portales, avisos = _corrida(tmp_path, monkeypatch)
    assert consultas == [] and portales == ["chumi"]
    assert "LinkedIn no se consultó: desactivado en config.py (LINKEDIN_PESE_A_ROBOTS=False)" in avisos
    assert not any("sin resultados" in a and "LinkedIn" in a for a in avisos)      # en pausa, no «sin resultados»


def test_chumi_apagado_no_va_por_el_hilo_de_portales_y_se_avisa(tmp_path, monkeypatch):
    _flags(monkeypatch, chumi=False)
    consultas, portales, avisos = _corrida(tmp_path, monkeypatch)
    assert portales == [] and [c["site_name"] for c in consultas] == [["linkedin"]]
    assert "Chumi no se consultó: desactivado en config.py (CHUMI_PESE_A_TOS=False)" in avisos


def test_una_fuente_apagada_no_se_consulta_aunque_la_pagina_la_marque(tmp_path, monkeypatch):
    _flags(monkeypatch, linkedin=False, chumi=False)
    consultas, portales, avisos = _corrida(tmp_path, monkeypatch, fuentes=["linkedin", "chumi"])
    assert consultas == [] and portales == []
    assert sum("no se consultó: desactivado" in a for a in avisos) == 2


def test_consulta_pide_el_detalle_de_linkedin_solo_con_el_flag(monkeypatch):
    assert buscar.consulta("linkedin", "qa", "Santiago, Chile")["fetch_description"] is True
    _flags(monkeypatch, linkedin=False)
    assert "fetch_description" not in buscar.consulta("linkedin", "qa", "Santiago, Chile")
    assert buscar.consulta("glassdoor", "qa", "Santiago, Chile")["fetch_description"] is True     # los demás, igual


# ---- rellenar aviso
def test_desde_linkedin_usa_el_endpoint_guest_con_el_flag_encendido(monkeypatch):
    visto = {}
    def falsa_pedir(url, c, r, **kw):
        visto.update(url=url, **kw)
        return (FIX / "linkedin_detalle.html").read_text(encoding="utf-8")
    monkeypatch.setattr(rellenar_aviso, "pedir", falsa_pedir)
    assert rellenar_aviso.desde_linkedin(AVISO_LINKEDIN, None, None)["empresa"] == "ACL"
    assert visto["url"].endswith("/jobs-guest/jobs/api/jobPosting/4487295075") and visto["ignorar_robots"] is True


@pytest.mark.parametrize("url", [AVISO_LINKEDIN, "https://CL.LinkedIn.com:443/jobs/view/4487295075", "https://linkedin.com/jobs/"])
def test_linkedin_apagado_pide_pegar_el_texto_y_no_visita_nada(monkeypatch, url):
    _flags(monkeypatch, linkedin=False)
    monkeypatch.setattr(rellenar_aviso, "pedir", lambda *a, **k: pytest.fail("no debía pedir la red"))
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    for leer in (rellenar_aviso.desde_linkedin, rellenar_aviso.desde_url):
        with pytest.raises(ErrorFuente, match="desactivada.*LINKEDIN_PESE_A_ROBOTS=False.*pégalo a mano"):
            leer(url, None, None)


@pytest.mark.parametrize("url", [AVISO_CHUMI, "https://WWW.Chumi-IT.com:443/trabajos/x"])
def test_chumi_apagado_pide_pegar_el_texto_y_no_visita_nada(monkeypatch, url):
    _flags(monkeypatch, chumi=False)
    monkeypatch.setattr(rellenar_aviso, "html_con_navegador", lambda u: pytest.fail("no debía abrir navegador"))
    with pytest.raises(ErrorFuente, match="desactivada.*CHUMI_PESE_A_TOS=False.*pégalo a mano"):
        rellenar_aviso.desde_url(url, None, RobotsLibre())          # sin cliente: ni siquiera llega a pedir()


def test_chumi_encendido_se_lee_respetando_su_robots(monkeypatch):
    visto = {}
    def falsa_pedir(url, c, r, **kw):
        visto.update(url=url, **kw)
        return (FIX / "chumi_detalle.html").read_text(encoding="utf-8")
    monkeypatch.setattr(rellenar_aviso, "pedir", falsa_pedir)
    assert rellenar_aviso.desde_url(AVISO_CHUMI, None, None)["empresa"] == "IT-Talent"
    assert visto["ignorar_robots"] is False        # el robots.txt de Chumi lo permite: aquí no hay nada que saltar


def test_los_demas_portales_siguen_igual_con_los_flags_apagados(monkeypatch):
    _flags(monkeypatch, linkedin=False, chumi=False)
    visto = {}
    def falsa_pedir(url, c, r, **kw):
        visto.update(kw)
        return (FIX / "chumi_detalle.html").read_text(encoding="utf-8")      # cualquier página con JobPosting
    monkeypatch.setattr(rellenar_aviso, "pedir", falsa_pedir)
    rellenar_aviso.desde_url("https://www.bne.cl/oferta/1", None, None)
    assert visto["ignorar_robots"] is True


def test_pedir_sin_cliente_es_un_error_legible():
    with pytest.raises(ErrorFuente, match="cliente"):
        pedir("https://x.cl/a", None, RobotsLibre())
    with pytest.raises(ErrorFuente, match="cliente"):
        pedir("https://x.cl/a", None, None, ignorar_robots=True)


# ---- la página
def test_api_estado_dice_que_fuentes_van_pese_a_robots_o_tos(tmp_path, monkeypatch):
    app = servidor.Aplicacion(ruta_db=str(tmp_path / "t.db"), carpeta_respaldos="")
    assert [(a["fuente"], a["activa"], a["texto"]) for a in app.snapshot()["advertencias_fuentes"]] == [
        ("linkedin", True, "LinkedIn activo pese a robots.txt"),
        ("chumi", True, "Chumi activo pese a sus Condiciones de Uso")]
    _flags(monkeypatch, linkedin=False, chumi=False)
    apagadas = app.snapshot()["advertencias_fuentes"]
    assert [a["activa"] for a in apagadas] == [False, False]
    assert all("en pausa por decisión" in a["texto"] and a["flag"] + "=False" in a["texto"] for a in apagadas)


def test_la_pagina_tiene_donde_mostrar_la_advertencia():
    assert 'id="advertencias-fuentes"' in informe.PAGINA and "advertencias_fuentes" in informe.PAGINA
