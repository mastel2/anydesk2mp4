# Packs dist\Recording Converter for AnyDesk (from tools/build_exe.py) into an .msix.
#
#   .\tools\pack_msix.ps1 -Version 1.0.0.0            # signed with a local dev cert, for sideload testing
#   .\tools\pack_msix.ps1 -Version 1.0.0.0 -NoSign    # unsigned, which is what Partner Center wants
#   .\tools\pack_msix.ps1 -Version 1.0.0.0 -Install   # sideload it on this PC
#
# Identity/Publisher must match the values Partner Center shows under Product identity
# once the name is reserved; pass them in or edit the defaults below.
param(
  [string]$Version = "1.0.0.0",
  [string]$IdentityName = "KEEPDARK.RecordingConverterforAnyDesk",
  [string]$Publisher = "CN=4EC6DF20-F152-42DE-A29E-EDD18083DAE6",
  [switch]$NoSign,
  [switch]$Install
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$app = "dist\Recording Converter for AnyDesk"
if (-not (Test-Path "$app\Recording Converter for AnyDesk.exe")) {
  throw "no build yet - run: python tools\build_exe.py"
}
$makeappx = Get-ChildItem "tools\sdk\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "makeappx.exe missing - see README (NuGet Microsoft.Windows.SDK.BuildTools)" }
$sdkbin = $makeappx.DirectoryName

# ---- staging -----------------------------------------------------------------
$stage = "build\msix"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$stage\app" | Out-Null
Copy-Item "$app\*" "$stage\app" -Recurse
python tools\make_store_assets.py "$stage\Assets"
if ($LASTEXITCODE -ne 0) { throw "make_store_assets.py failed" }

(Get-Content msix\AppxManifest.xml -Raw).
  Replace("__VERSION__", $Version).
  Replace("__IDENTITY_NAME__", $IdentityName).
  Replace("__PUBLISHER__", $Publisher) |
  Set-Content "$stage\AppxManifest.xml" -Encoding utf8

# ---- pack --------------------------------------------------------------------
$out = "dist\RecordingConverterForAnyDesk-$Version.msix"
Remove-Item $out -ErrorAction SilentlyContinue
& "$sdkbin\makeappx.exe" pack /d $stage /p $out /o | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { throw "makeappx failed" }

# ---- sign (test only; the Store signs its own copy) --------------------------
if (-not $NoSign) {
  $cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $Publisher -and $_.EnhancedKeyUsageList.FriendlyName -contains "Code Signing" } |
    Select-Object -First 1
  if (-not $cert) {
    $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher -KeyUsage DigitalSignature `
      -FriendlyName "Recording Converter MSIX dev" -CertStoreLocation Cert:\CurrentUser\My `
      -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") -NotAfter (Get-Date).AddYears(3)
    Write-Host "created a self-signed certificate $($cert.Thumbprint)"
  }
  $pfx = "build\dev-cert.pfx"
  $pw = ConvertTo-SecureString "dev" -AsPlainText -Force
  Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pw | Out-Null
  Export-Certificate -Cert $cert -FilePath "build\dev-cert.cer" | Out-Null
  & "$sdkbin\signtool.exe" sign /fd SHA256 /a /f $pfx /p dev $out | Select-Object -Last 1
  if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
  Write-Host "to sideload on another PC, import build\dev-cert.cer into Trusted People (Local Machine) first"
}

if ($Install) {
  Add-AppxPackage -Path (Resolve-Path $out)
  Write-Host "installed on this PC"
}
Get-Item $out | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
