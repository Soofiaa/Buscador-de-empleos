"""Glassdoor busca solo en Santiago (config.UBICACIONES_SOLO); Indeed sigue con todas las ubicaciones (corrida de 17 min, 3-11)."""
import pandas as pd

import buscar
import config


def _plan_con(monkeypatch, sitios):
    capturadas = []

    def scrape_jobs(**kw):
        capturadas.append((kw["site_name"][0], kw["location"]))
        return pd.DataFrame()
    import sys, types
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=scrape_jobs))
    monkeypatch.setattr(config, "SITIOS", sitios)
    monkeypatch.setattr(config, "TERMINOS_SECUNDARIOS", ["qa"])
    monkeypatch.setattr(config, "UBICACIONES", ["Santiago, Chile", "Viña del Mar, Chile"])
    monkeypatch.setattr(config, "INCLUIR_REMOTO", True)
    monkeypatch.setattr(buscar.time, "sleep", lambda s: None)
    monkeypatch.setattr(buscar, "_say", lambda m: None)
    return capturadas


def test_glassdoor_solo_en_santiago(tmp_path, monkeypatch):
    capturadas = _plan_con(monkeypatch, ["glassdoor"])
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.buscar_ofertas(con)
    assert capturadas and all(s == "glassdoor" for s, _ in capturadas)
    assert {loc for _, loc in capturadas} == {"Santiago, Chile"}


def test_indeed_sigue_con_todas_las_ubicaciones(tmp_path, monkeypatch):
    capturadas = _plan_con(monkeypatch, ["indeed"])
    con = buscar.conectar(str(tmp_path / "t.db"))
    buscar.buscar_ofertas(con)
    assert {loc for _, loc in capturadas} >= {"Santiago, Chile", "Viña del Mar, Chile"}
