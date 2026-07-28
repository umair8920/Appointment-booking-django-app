# Forward Stripe sandbox events to the local Django webhook (Docs/06).
# Keep this running while testing payments.
#
# Usage (from project root, with venv activated optional):
#   powershell -File scripts\stripe_listen.ps1
#
# Requires STRIPE_SECRET_KEY in .env. Writes nothing; prints CLI output.
# Copy whsec_... into .env as STRIPE_WEBHOOK_SECRET if not already set.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$exe = Join-Path $root "tools\stripe\stripe.exe"
if (-not (Test-Path $exe)) {
  Write-Error "Stripe CLI missing at tools\stripe\stripe.exe"
}

$sk = $null
Get-Content .env | ForEach-Object {
  if ($_ -match '^STRIPE_SECRET_KEY=(.+)$') { $sk = $Matches[1].Trim() }
}
if (-not $sk) { Write-Error "STRIPE_SECRET_KEY not found in .env" }

& $exe listen `
  --api-key $sk `
  --forward-to localhost:8000/api/payments/webhook/stripe/ `
  --events payment_intent.succeeded,payment_intent.payment_failed,charge.refunded
