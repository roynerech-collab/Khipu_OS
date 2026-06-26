param(
    [string]$ServerPath = "E:\Khipu_OS"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ServerPath)) {
    throw "No existe la carpeta del servidor: $ServerPath"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$filesToCopy = @(
    "bot.py",
    "README.md",
    "ACTUALIZAR.bat",
    ".env.example"
)

Write-Host "Copiando archivos versionados a $ServerPath"
foreach ($file in $filesToCopy) {
    $source = Join-Path $repoRoot $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $ServerPath $file) -Force
        Write-Host "Actualizado: $file"
    }
}

$botPath = Join-Path $ServerPath "bot.py"
$escapedServerPath = [regex]::Escape($ServerPath)
$escapedBotPath = [regex]::Escape($botPath)

Write-Host "Deteniendo bot anterior si existe"
$botProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -match $escapedBotPath -or
        ($_.CommandLine -match "python" -and $_.CommandLine -match "bot.py" -and $_.CommandLine -match $escapedServerPath)
    )
}

foreach ($process in $botProcesses) {
    Write-Host "Deteniendo PID $($process.ProcessId): $($process.CommandLine)"
    Invoke-CimMethod -InputObject $process -MethodName Terminate | Out-Null
}

Start-Sleep -Seconds 2

$launcher = Join-Path $ServerPath "LANZADOR.bat"
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "No existe LANZADOR.bat en $ServerPath. Ese archivo debe quedarse solo en el servidor con tus credenciales de Telegram."
}

Write-Host "Iniciando bot desde LANZADOR.bat"
Start-Process -FilePath $launcher -WorkingDirectory $ServerPath -WindowStyle Minimized

Write-Host "Despliegue completado."
