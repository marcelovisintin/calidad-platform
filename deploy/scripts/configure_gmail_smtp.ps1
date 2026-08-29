param(
    [string]$SenderEmail = "marcelo.v@schneider.ar",
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\docker\.env.server.local")
)

$ErrorActionPreference = "Stop"
$resolvedEnvFile = [System.IO.Path]::GetFullPath($EnvFile)
if (-not (Test-Path -LiteralPath $resolvedEnvFile -PathType Leaf)) {
    throw "No se encontro el archivo de configuracion: $resolvedEnvFile"
}

$securePassword = Read-Host "Contrasena de aplicacion de Google (16 caracteres)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer).Replace(" ", "")
    if ($appPassword.Length -ne 16) {
        throw "La contrasena de aplicacion debe tener 16 caracteres, sin espacios."
    }

    $settings = [ordered]@{
        EMAIL_NOTIFICATIONS_ENABLED = "True"
        EMAIL_BACKEND = "config.email_backend.SmtpEmailBackend"
        EMAIL_HOST = "smtp.gmail.com"
        EMAIL_PORT = "587"
        EMAIL_HOST_USER = $SenderEmail
        EMAIL_HOST_PASSWORD = $appPassword
        EMAIL_USE_TLS = "True"
        EMAIL_USE_SSL = "False"
        EMAIL_TIMEOUT = "10"
        DEFAULT_FROM_EMAIL = $SenderEmail
        EMAIL_MAX_RETRIES = "3"
        EMAIL_RETRY_DELAY_MINUTES = "5"
        EMAIL_PROCESSING_TIMEOUT_MINUTES = "10"
    }

    $seen = @{}
    $output = foreach ($line in [System.IO.File]::ReadAllLines($resolvedEnvFile)) {
        $separator = $line.IndexOf("=")
        $key = if ($separator -gt 0) { $line.Substring(0, $separator) } else { "" }
        if ($settings.Contains($key)) {
            $seen[$key] = $true
            "$key=$($settings[$key])"
        } else {
            $line
        }
    }
    foreach ($entry in $settings.GetEnumerator()) {
        if (-not $seen.ContainsKey($entry.Key)) {
            $output += "$($entry.Key)=$($entry.Value)"
        }
    }

    $temporaryFile = "$resolvedEnvFile.tmp"
    [System.IO.File]::WriteAllLines($temporaryFile, $output, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryFile -Destination $resolvedEnvFile -Force
    Write-Host "Google Workspace configurado para $SenderEmail."
    Write-Host "La contrasena no fue mostrada ni registrada en la salida."
} finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $appPassword = $null
    $securePassword = $null
}
