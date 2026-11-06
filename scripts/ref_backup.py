import hashlib
import os
import sqlite3

NOMBRE = os.environ["NOMBRE"]
for destino in ("/datos/" + NOMBRE, "/ref/" + NOMBRE):
    origen = sqlite3.connect("file:/datos/ofertas.db?mode=ro", uri=True)
    copia = sqlite3.connect(destino)
    origen.backup(copia)
    copia.execute("PRAGMA journal_mode = DELETE")
    ic = copia.execute("PRAGMA integrity_check").fetchone()[0]
    copia.commit()
    copia.close()
    origen.close()
    with open(destino, "rb") as f:
        print(destino, "integrity_check:", ic, "sha256:", hashlib.sha256(f.read()).hexdigest())
    if ic != "ok":
        raise SystemExit(1)
