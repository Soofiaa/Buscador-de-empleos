# Despliegue automático de job-tracker (lo lanza .github/workflows/desplegar.yml en el runner de este PC).
# Mismos pasos que .claude/skills/desplegar, sin aprobación manual: etiqueta la imagen actual, detiene el contenedor,
# respalda la base (sha256 + integrity_check), reconstruye, espera "healthy" y compara las huellas de la base.
# Si cualquier paso falla vuelve a la imagen anterior. Una migración que crea tablas falla la comparación a propósito:
# esas se despliegan a mano con la skill `desplegar` (que declara las tablas nuevas).
$ErrorActionPreference = "Stop"
$py = Join-Path $env:JT_RUNNER_DIR "venv\Scripts\python.exe"
$tmp = Join-Path $env:RUNNER_TEMP "desplegar"
$refs = "C:/Users/sofia/Respaldos/job-tracker-referencias"
$sello = Get-Date -Format "yyyyMMdd-HHmmss"
$previa = "job-tracker:pre_auto_$sello"
$nombre = "ofertas_pre_auto_$sello.db"
$huellas = ".claude/skills/desplegar/huellas.py"
New-Item -ItemType Directory -Force $tmp | Out-Null
$compose = @("compose", "--env-file", $env:JT_ENV_FILE)

function Volver($motivo) {
    Write-Host "::error::$motivo - se vuelve a la imagen anterior $previa"
    docker tag $previa job-tracker-jobtracker:latest
    docker @compose up -d --no-build
    exit 1
}

docker image inspect job-tracker-jobtracker:latest *> $null
if ($LASTEXITCODE -ne 0) { throw "no hay imagen actual job-tracker-jobtracker:latest: primer despliegue a mano" }
docker tag job-tracker-jobtracker:latest $previa

docker @compose stop jobtracker
$salida = docker inspect jobtracker --format '{{.State.ExitCode}}'
Write-Host "codigo de salida al detener: $salida"

docker run --rm --network none -e "NOMBRE=$nombre" -v job-tracker_jt_datos:/datos -v "${refs}:/ref" `
    -v "$($PWD.Path)\scripts\ref_backup.py:/ref_backup.py:ro" $previa python /ref_backup.py
if ($LASTEXITCODE -ne 0) { Volver "el respaldo de referencia fallo" }

& $py $huellas "$refs/$nombre" > "$tmp\antes.json"
if ($LASTEXITCODE -ne 0) { Volver "no se pudieron leer las huellas de la referencia" }

docker @compose build
if ($LASTEXITCODE -ne 0) { Volver "el build fallo" }
docker @compose up -d
if ($LASTEXITCODE -ne 0) { Volver "no levanto el contenedor" }

$estado = ""
for ($i = 0; $i -lt 60 -and $estado -ne "healthy"; $i++) {
    Start-Sleep 2
    $estado = docker inspect jobtracker --format '{{.State.Health.Status}}'
}
if ($estado -ne "healthy") { Volver "el contenedor no quedo healthy (estado: $estado)" }

docker cp $huellas jobtracker:/tmp/huellas.py
docker exec jobtracker python /tmp/huellas.py /datos/ofertas.db > "$tmp\despues.json"
& $py $huellas --comparar "$tmp\antes.json" "$tmp\despues.json"
if ($LASTEXITCODE -ne 0) { Volver "las huellas de la base cambiaron" }

foreach ($ruta in "/", "/api/estado", "/api/ofertas", "/api/respaldo") {
    $codigo = curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1:8765$ruta"
    if ($codigo -ne "200") { Volver "$ruta respondio $codigo" }
}

# solo se conservan las 10 últimas imágenes y referencias automáticas
docker images job-tracker --format "{{.Tag}}" | Where-Object { $_ -like "pre_auto_*" } | Sort-Object -Descending |
    Select-Object -Skip 10 | ForEach-Object { docker rmi "job-tracker:$_" }
Get-ChildItem $refs -Filter "ofertas_pre_auto_*.db" | Sort-Object Name -Descending | Select-Object -Skip 10 | Remove-Item
docker run --rm -v job-tracker_jt_datos:/datos job-tracker-jobtracker:latest sh -c 'ls /datos/ofertas_pre_auto_*.db 2>/dev/null | sort -r | tail -n +11 | xargs -r rm' *> $null
Write-Host "Despliegue OK: $(git rev-parse --short HEAD), imagen anterior $previa"
