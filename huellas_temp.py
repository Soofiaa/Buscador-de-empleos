import sqlite3, hashlib, json, sys

def extraer(ruta):
    con = sqlite3.connect(ruta)
    q = lambda sql: con.execute(sql).fetchall()
    tablas = {}
    for (nombre,) in q("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        filas = sorted(repr(tuple(f)) for f in q(f'SELECT * FROM "{nombre}"'))
        tablas[nombre] = {'filas': len(filas), 'sha256': hashlib.sha256('\n'.join(filas).encode('utf-8')).hexdigest()}
    out = {
        'version': q('PRAGMA user_version')[0][0],
        'integrity_check': q('PRAGMA integrity_check')[0][0],
        'objetos': [f'{t}:{n}' for t, n in q("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type, name")],
        'tablas': tablas,
        'postuladas': q("SELECT COUNT(*) FROM ofertas WHERE estado = 'postulada'")[0][0],
        'por_verificar': q("SELECT COUNT(*) FROM ofertas WHERE notas LIKE '%POR VERIFICAR%'")[0][0],
        'estados': [f'{c}/{e}: {n}' for c, e, n in q('SELECT categoria, estado, COUNT(*) FROM ofertas GROUP BY 1, 2 ORDER BY 1, 2')],
    }
    con.close()
    return out

antes = extraer(r'C:/Users/sofia/Respaldos/job-tracker-referencias/ofertas_pre_tablero_noseleccionada_20261105.db')
despues = extraer(r'\\?\pipe\docker_datos\ofertas.db') if sys.argv[-1] == 'docker' else extraer(r'C:/Users/sofia/Respaldos/job-tracker/ofertas_auto_20261105-143609.db')

with open('C:/Users/sofia/AppData/Local/Temp/opencode/antes.json', 'w', encoding='utf-8') as f:
    json.dump(antes, f, ensure_ascii=False, indent=1)
with open('C:/Users/sofia/AppData/Local/Temp/opencode/despues.json', 'w', encoding='utf-8') as f:
    json.dump(despues, f, ensure_ascii=False, indent=1)

print("Archivos generados correctamente")
