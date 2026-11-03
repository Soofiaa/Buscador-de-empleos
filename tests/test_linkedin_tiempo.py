"""LinkedIn: tope de resultados por consulta y ventana que no se amplía (corrida de 30 min, 2-11)."""
import sqlite3
from datetime import datetime

import buscar
import config
from filtros import ZONA


def test_linkedin_pide_10_resultados_y_las_demas_30():
    assert buscar.consulta("linkedin", "QA", "Santiago, Chile", dias=1)["results_wanted"] == 10
    assert buscar.consulta("indeed", "QA", "Santiago, Chile", dias=1)["results_wanted"] == 30


def test_linkedin_no_amplia_su_ventana_con_huecos():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE corridas (id INTEGER PRIMARY KEY, inicio TEXT, fin TEXT, nuevas INT, detalle TEXT, "
              "origen TEXT, grupo TEXT)")
    c.execute("INSERT INTO corridas (inicio, fin, nuevas, detalle) VALUES ('2026-10-20 10:00', '2026-10-20 10:20', 0, '{}')")
    v = buscar.ventanas_efectivas(c, datetime(2026, 11, 2, 9, 0, tzinfo=ZONA))
    assert v["linkedin"] == config.MAX_ANTIGUEDAD_DIAS["linkedin"] == 1      # no se amplía
    assert v["indeed"] > 1                                                    # las demás sí (hueco de días)
