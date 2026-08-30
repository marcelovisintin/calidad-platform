param(
    [string]$EnvFile,
    [string]$ComposeFile = "deploy/docker/docker-compose.local.yml",
    [string]$PackageCaCertificate,
    [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param([string]$PathValue)
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
}

function Assert-NativeCommandSucceeded {
    param(
        [int]$ExitCode,
        [string]$Operation
    )

    if ($ExitCode -ne 0) {
        throw "$Operation fallo con codigo de salida $ExitCode."
    }
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
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        Set-Item -Path "Env:$key" -Value $value
    }
}

function Get-PreferredIPv4 {
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254*" -and
            $_.InterfaceAlias -notlike "vEthernet*" -and
            $_.InterfaceAlias -notlike "Loopback*"
        }

    if (-not $candidates) {
        return $null
    }

    return ($candidates | Sort-Object -Property SkipAsSource, InterfaceMetric | Select-Object -First 1).IPAddress
}

$projectRoot = Get-Location

if (-not $EnvFile) {
    $localCandidate = "deploy/docker/.env.server.local"
    $defaultCandidate = "deploy/docker/.env.server"
    if (Test-Path -LiteralPath $localCandidate) {
        $EnvFile = $localCandidate
    } elseif (Test-Path -LiteralPath $defaultCandidate) {
        $EnvFile = $defaultCandidate
    } else {
        throw "No se encontro archivo de entorno. Crea deploy/docker/.env.server (o .env.server.local) desde .env.server.example"
    }
}

$envPath = Get-AbsolutePath -PathValue $EnvFile
$composePath = Get-AbsolutePath -PathValue $ComposeFile

Import-DotEnv -PathValue $envPath

$env:APP_GIT_COMMIT = (& git -C $projectRoot rev-parse HEAD).Trim()
Assert-NativeCommandSucceeded -ExitCode $LASTEXITCODE -Operation "La lectura del commit Git"
$env:APP_GIT_SHORT_COMMIT = (& git -C $projectRoot rev-parse --short HEAD).Trim()
$env:APP_GIT_BRANCH = (& git -C $projectRoot branch --show-current).Trim()
$env:APP_GIT_DIRTY = if ((& git -C $projectRoot status --porcelain)) { "true" } else { "false" }
$env:APP_DEPLOYMENT_ENV = "local"
$gitHistory = (& git -C $projectRoot log -n 30 --date=iso-strict "--pretty=format:%H`t%h`t%aI`t%an`t%s`t%D") -join "`n"
$env:APP_GIT_HISTORY_B64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($gitHistory))

$requiredDirs = @(
    $env:HOST_POSTGRES_DATA,
    $env:HOST_MEDIA_ROOT,
    $env:HOST_TMP_ROOT,
    $env:HOST_STATIC_ROOT,
    $env:HOST_LOG_ROOT,
    $env:HOST_BACKUP_ROOT,
    $env:HOST_TLS_CERTS
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

foreach ($dir in $requiredDirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$port = if ($env:FRONTEND_BIND_PORT) { $env:FRONTEND_BIND_PORT } else { "8088" }
$tlsPort = if ($env:FRONTEND_TLS_BIND_PORT) { $env:FRONTEND_TLS_BIND_PORT } else { "8443" }

if (-not $SkipFirewall) {
    try {
        $httpRuleName = "Calidad HTTP $port"
        if (-not (Get-NetFirewallRule -DisplayName $httpRuleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $httpRuleName -Direction Inbound -Protocol TCP -LocalPort $port -RemoteAddress LocalSubnet -Action Allow -Profile Private,Public | Out-Null
        }

        $httpsRuleName = "Calidad HTTPS $tlsPort"
        if (-not (Get-NetFirewallRule -DisplayName $httpsRuleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $httpsRuleName -Direction Inbound -Protocol TCP -LocalPort $tlsPort -RemoteAddress LocalSubnet -Action Allow -Profile Private,Public | Out-Null
        }

        $dockerRuleName = "Calidad Docker Backend App"
        if (-not (Get-NetFirewallRule -DisplayName $dockerRuleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $dockerRuleName -Direction Inbound -Program "C:\Program Files\Docker\Docker\resources\com.docker.backend.exe" -Action Allow -Profile Private,Public | Out-Null
        }
    } catch {
        Write-Warning "No se pudieron crear reglas de firewall automaticamente. Ejecuta esta consola como Administrador si necesitas acceso desde otros dispositivos."
    }
}

Write-Host "Levantando stack Docker..." -ForegroundColor Cyan
if ($PackageCaCertificate) {
    $packageCaPath = Get-AbsolutePath -PathValue $PackageCaCertificate
    if (-not (Test-Path -LiteralPath $packageCaPath)) {
        throw "No se encontro el certificado CA para dependencias: $packageCaPath"
    }

    docker build --secret "id=pip_ca,src=$packageCaPath" -f deploy/docker/backend.Dockerfile -t docker-backend .
    Assert-NativeCommandSucceeded -ExitCode $LASTEXITCODE -Operation "La construccion del backend"
    docker build --secret "id=npm_ca,src=$packageCaPath" --build-arg "APP_GIT_COMMIT=$env:APP_GIT_COMMIT" --build-arg "APP_GIT_SHORT_COMMIT=$env:APP_GIT_SHORT_COMMIT" --build-arg "APP_GIT_BRANCH=$env:APP_GIT_BRANCH" --build-arg "APP_GIT_DIRTY=$env:APP_GIT_DIRTY" --build-arg "APP_DEPLOYMENT_ENV=$env:APP_DEPLOYMENT_ENV" --build-arg "APP_GIT_HISTORY_B64=$env:APP_GIT_HISTORY_B64" -f deploy/docker/frontend.Dockerfile -t docker-frontend .
    Assert-NativeCommandSucceeded -ExitCode $LASTEXITCODE -Operation "La construccion del frontend"
    docker compose --env-file $envPath -f $composePath up -d --no-build
    Assert-NativeCommandSucceeded -ExitCode $LASTEXITCODE -Operation "El inicio del stack"
} else {
    docker compose --env-file $envPath -f $composePath up -d --build
    Assert-NativeCommandSucceeded -ExitCode $LASTEXITCODE -Operation "La construccion e inicio del stack"
}

$hostname = $env:COMPUTERNAME
$ip = Get-PreferredIPv4

Write-Host ""
Write-Host "Stack listo." -ForegroundColor Green
Write-Host ("Login local HTTP:   http://localhost:{0}/login" -f $port)
Write-Host ("Login host HTTP:    http://{0}:{1}/login" -f $hostname, $port)
Write-Host ("Login local HTTPS:  https://localhost:{0}/login" -f $tlsPort)
Write-Host ("Login host HTTPS:   https://{0}:{1}/login" -f $hostname, $tlsPort)
if ($ip) {
    Write-Host ("Login LAN HTTP:     http://{0}:{1}/login" -f $ip, $port)
    Write-Host ("Login LAN HTTPS:    https://{0}:{1}/login" -f $ip, $tlsPort)
} else {
    Write-Warning "No se pudo detectar IPv4 LAN automaticamente."
}
