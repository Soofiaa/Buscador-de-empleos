"""Validación de las exclusiones editables (exclusiones.py). Sin red ni base."""
import pytest

import exclusiones

VALIDA = {"empresas": ["accenture", "bairesdev"], "titulo": [r"practic", r"\bintern\b"],
          "descripcion": [r"practicante", r"alumno regular"]}


def test_lista_valida_se_devuelve_igual():
    limpias, errores = exclusiones.validar(VALIDA)
    assert errores == [] and limpias == VALIDA


def test_espacios_sobrantes_se_limpian_en_empresas():
    limpias, errores = exclusiones.validar({**VALIDA, "empresas": ["  Accenture   Chile "]})
    assert errores == [] and limpias["empresas"] == ["Accenture Chile"]


def test_listas_vacias_son_validas():
    limpias, errores = exclusiones.validar({"empresas": [], "titulo": [], "descripcion": []})
    assert errores == [] and limpias == {"empresas": [], "titulo": [], "descripcion": []}


def test_faltan_o_sobran_claves():
    for malo in ({"empresas": []}, {**VALIDA, "otra": []}, ["x"], "texto", None):
        limpias, errores = exclusiones.validar(malo)
        assert limpias == {} and errores, malo


@pytest.mark.parametrize("patron", [r"(abierto", r"[sin cerrar", r"a{2,1}", r"*suelto"])
def test_patron_roto_en_titulo_o_descripcion_no_se_guarda(patron):
    _, errores = exclusiones.validar({**VALIDA, "titulo": [patron]})
    assert any("no es un patrón válido" in e for e in errores)
    _, errores = exclusiones.validar({**VALIDA, "descripcion": [patron]})
    assert any("no es un patrón válido" in e for e in errores)


def test_empresa_no_es_regex_asi_que_un_parentesis_es_texto():
    limpias, errores = exclusiones.validar({**VALIDA, "empresas": ["acme (chile)"]})
    assert errores == [] and limpias["empresas"] == ["acme (chile)"]


def test_vacia_y_control_y_largo():
    _, errores = exclusiones.validar({**VALIDA, "empresas": ["   "]})
    assert any("vacía" in e for e in errores)
    _, errores = exclusiones.validar({**VALIDA, "empresas": ["a\x00b"]})
    assert any("no permitidos" in e for e in errores)
    _, errores = exclusiones.validar({**VALIDA, "empresas": ["a" * 81]})
    assert any("como máximo 80" in e for e in errores)


def test_repetidas_ignoran_mayusculas_y_tildes():
    _, errores = exclusiones.validar({**VALIDA, "empresas": ["Acción", "accion"]})
    assert any("repetida" in e for e in errores)


def test_maximo_entradas():
    _, errores = exclusiones.validar({**VALIDA, "empresas": [f"empresa {i}" for i in range(61)]})
    assert any("como máximo 60 entradas" in e for e in errores)


def test_errores_de_varias_listas_se_informan_juntos():
    _, errores = exclusiones.validar({"empresas": ["ok", ""], "titulo": [r"(roto"], "descripcion": ["x\x01"]})
    assert len(errores) == 3


# ---- B1: un patrón que tarda demasiado (cuantificadores anidados) no se guarda; los normales sí (límite de tiempo)
@pytest.mark.parametrize("patron", [r"(a+)+$", r"(a|aa)+$", r"(a+a+)+b"])
def test_patron_patologico_se_rechaza_por_tiempo(patron, monkeypatch):
    """Patrones con cuantificadores anidados que tardan exponencial con el texto de prueba: el validador los rechaza."""
    # Aumentamos la complejidad para asegurar que el timeout se supere incluso en máquinas rápidas
    monkeypatch.setattr(exclusiones, "PLAZO_PATRON_S", 0.001)
    limpias, errores = exclusiones.validar({"empresas": [], "titulo": [patron], "descripcion": []})
    assert errores and any("tarda demasiado" in e for e in errores)


@pytest.mark.parametrize("patron", [r"practic", r"\bintern\b", r"estudiante en practica", r"memorista|alumno",
                                    r"senior|lead|jefe", r"(qa|tester)\s?lead"])
def test_patrones_normales_siguen_pasando(patron):
    _, errores = exclusiones.validar({"empresas": [], "titulo": [patron], "descripcion": []})
    assert errores == []
