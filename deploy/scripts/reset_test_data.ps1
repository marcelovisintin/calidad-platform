param(
    [string]$EnvFile,
    [string]$ComposeFile = "deploy/docker/docker-compose.local.yml",
    [string]$AuditUsername = "auditor",
    [string]$AuditEmail = "auditor@example.local",
    [string]$AuditPassword,
    [switch]$SkipAuditUser,
    [switch]$ClearLogs,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param([string]$PathValue)
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
}

function Import-DotEnv {
    param([string]$PathValue)

    $lines = Get-Content -LiteralPath $PathValue
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$key" -Value $value
    }
}

function Assert-ResetPath {
    param([string]$PathValue)

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw "Ruta vacia en archivo de entorno."
    }

    $fullPath = [System.IO.Path]::GetFullPath($PathValue)
    $root = [System.IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.TrimEnd("\", "/") -eq $root.TrimEnd("\", "/")) {
        throw "Ruta insegura para reset: $fullPath"
    }

    if ($fullPath -notmatch "calidad" -and $fullPath -notmatch "CALIDAD") {
        throw "Ruta fuera del espacio esperado de Calidad: $fullPath"
    }

    return $fullPath
}

function Clear-Directory {
    param([string]$PathValue)

    $fullPath = Assert-ResetPath -PathValue $PathValue
    if ($WhatIf) {
        Write-Host "[WhatIf] Se eliminaria: $fullPath" -ForegroundColor Yellow
        return
    }

    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
}

if (-not $EnvFile) {
    $localCandidate = "deploy/docker/.env.server.local"
    $defaultCandidate = "deploy/docker/.env.server"
    if (Test-Path -LiteralPath $localCandidate) {
        $EnvFile = $localCandidate
    } elseif (Test-Path -LiteralPath $defaultCandidate) {
        $EnvFile = $defaultCandidate
    } else {
        throw "No se encontro archivo de entorno. Crea deploy/docker/.env.server.local desde deploy/docker/.env.server.example"
    }
}

if (-not $SkipAuditUser -and [string]::IsNullOrWhiteSpace($AuditPassword)) {
    throw "Indica -AuditPassword o usa -SkipAuditUser."
}

$envPath = Get-AbsolutePath -PathValue $EnvFile
$composePath = Get-AbsolutePath -PathValue $ComposeFile
Import-DotEnv -PathValue $envPath

$resetDirs = @(
    $env:HOST_POSTGRES_DATA,
    $env:HOST_MEDIA_ROOT,
    $env:HOST_TMP_ROOT,
    $env:HOST_STATIC_ROOT
)

if ($ClearLogs) {
    $resetDirs += $env:HOST_LOG_ROOT
}

Write-Host "Deteniendo stack..." -ForegroundColor Cyan
if (-not $WhatIf) {
    docker compose --env-file $envPath -f $composePath down
}

Write-Host "Reseteando datos de prueba..." -ForegroundColor Cyan
foreach ($dir in $resetDirs) {
    Clear-Directory -PathValue $dir
}

if ($WhatIf) {
    Write-Host "Modo WhatIf finalizado. No se levanto el stack ni se modificaron datos." -ForegroundColor Yellow
    exit 0
}

Write-Host "Levantando stack limpio..." -ForegroundColor Cyan
docker compose --env-file $envPath -f $composePath up -d --build

if (-not $SkipAuditUser) {
    Write-Host "Creando usuario auditor..." -ForegroundColor Cyan
    $escapedUsername = $AuditUsername.Replace("'", "\'")
    $escapedEmail = $AuditEmail.Replace("'", "\'")
    $escapedPassword = $AuditPassword.Replace("'", "\'")
    $createUser = "from apps.accounts.models import User; u, _ = User.objects.get_or_create(username='$escapedUsername', defaults={'email':'$escapedEmail','access_level':User.AccessLevel.DESARROLLADOR,'is_staff':True,'is_superuser':True}); u.email='$escapedEmail'; u.access_level=User.AccessLevel.DESARROLLADOR; u.is_staff=True; u.is_superuser=True; u.set_password('$escapedPassword'); u.save(); print('audit_user_ready:$escapedUsername')"
    docker compose --env-file $envPath -f $composePath exec -T backend python manage.py shell -c $createUser
}

Write-Host ""
Write-Host "Reset de prueba completo." -ForegroundColor Green
Write-Host ("Login HTTP:  http://localhost:{0}/login" -f $env:FRONTEND_BIND_PORT)
Write-Host ("Login HTTPS: https://localhost:{0}/login" -f $env:FRONTEND_TLS_BIND_PORT)
if (-not $SkipAuditUser) {
    Write-Host ("Usuario auditor: {0}" -f $AuditUsername)
}
