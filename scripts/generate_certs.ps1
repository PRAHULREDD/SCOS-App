# Generate Self-Signed Certificate for Local HTTPS Testing
$certPath = Join-Path $PSScriptRoot "..\secrets\ssl"
if (-not (Test-Path $certPath)) {
    New-Item -ItemType Directory -Force -Path $certPath | Out-Null
}

$crtFile = Join-Path $certPath "scos.crt"
$keyFile = Join-Path $certPath "scos.key"

if ((Test-Path $crtFile) -and (Test-Path $keyFile)) {
    Write-Host "Certificates already exist at $certPath."
    Exit 0
}

Write-Host "Generating self-signed certificate using PowerShell..."

# Generate self-signed cert using .NET Security objects for high compatibility without OpenSSL
$name = New-Object -TypeName System.Security.Cryptography.X509Certificates.X500DistinguishedName("CN=localhost")
$key = [System.Security.Cryptography.RSA]::Create(2048)
$req = New-Object -TypeName System.Security.Cryptography.X509Certificates.CertificateRequest($name, $key, [System.Security.Cryptography.HashName]::SHA256, [System.Security.Cryptography.X509Certificates.RSASignaturePadding]::Pkcs1)
$cert = $req.CreateSelfSigned([System.DateTimeOffset]::UtcNow, [System.DateTimeOffset]::UtcNow.AddYears(1))

# Export Public Certificate (CRT)
$certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
[System.IO.File]::WriteAllBytes($crtFile, $certBytes)

# Export Private Key (KEY) in PKCS8 format
$keyBytes = $key.ExportPkcs8PrivateKey()
$pemKey = "-----BEGIN PRIVATE KEY-----`r`n" + [System.Convert]::ToBase64String($keyBytes, [System.Base64FormattingOptions]::InsertLineBreaks) + "`r`n-----END PRIVATE KEY-----"
[System.IO.File]::WriteAllText($keyFile, $pemKey)

Write-Host "Certificates generated successfully at $certPath"
