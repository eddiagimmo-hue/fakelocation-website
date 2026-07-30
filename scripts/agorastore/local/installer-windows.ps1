# Installation de la veille Agorastore sur Windows.
#
# Clic droit sur ce fichier > « Exécuter avec PowerShell ».
# Si Windows refuse, ouvrez PowerShell et lancez :
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#     .\installer-windows.ps1

$ErrorActionPreference = 'Stop'
$Dossier = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Dossier

Write-Host ''
Write-Host '  Veille Agorastore - installation' -ForegroundColor Cyan
Write-Host '  ================================'
Write-Host ''

# ---------------------------------------------------------------- Python ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host 'Python 3 est introuvable.' -ForegroundColor Red
    Write-Host ''
    Write-Host '  Installez-le depuis https://www.python.org/downloads/'
    Write-Host '  IMPORTANT : cochez « Add python.exe to PATH » pendant l''installation.'
    Write-Host ''
    Read-Host '  Appuyez sur Entree pour fermer'
    exit 1
}
Write-Host "Python detecte : $(python --version)"

Write-Host "Creation de l'environnement isole..."
python -m venv .venv
$Py = Join-Path $Dossier '.venv\Scripts\python.exe'

Write-Host 'Installation des bibliotheques (une minute environ)...'
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet requests openpyxl Pillow
Write-Host '  fait.'

# ------------------------------------------------------------ Identifiants ---
if (Test-Path '.env') {
    Write-Host ''
    Write-Host 'Un fichier .env existe deja, les identifiants sont conserves.'
    Write-Host 'Pour les changer : supprimez .env puis relancez ce script.'
} else {
    Write-Host ''
    Write-Host '  Envoi du rapport' -ForegroundColor Cyan
    Write-Host '  ----------------'
    Write-Host '  Le rapport part d''une adresse Gmail vers ed.diagimmo@gmail.com.'
    Write-Host ''
    Write-Host '  Gmail refuse le mot de passe habituel du compte pour ce type d''envoi.'
    Write-Host '  Il faut un « mot de passe d''application », qui se cree ici :'
    Write-Host '      https://myaccount.google.com/apppasswords' -ForegroundColor Yellow
    Write-Host '  (la validation en deux etapes doit etre active sur le compte)'
    Write-Host ''

    $SmtpUser = Read-Host '  Adresse Gmail qui envoie'
    $Secure   = Read-Host '  Mot de passe d''application' -AsSecureString
    $SmtpPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure))
    $MailTo   = Read-Host '  Adresse qui recoit [ed.diagimmo@gmail.com]'
    if ([string]::IsNullOrWhiteSpace($MailTo)) { $MailTo = 'ed.diagimmo@gmail.com' }

    # Gmail affiche le mot de passe par groupes de quatre ; les espaces
    # colles depuis la page Google feraient echouer l'authentification.
    $SmtpPass = $SmtpPass -replace '\s', ''

    @(
        "SMTP_USER=$SmtpUser"
        "SMTP_PASSWORD=$SmtpPass"
        "MAIL_TO=$MailTo"
    ) | Set-Content -Path '.env' -Encoding UTF8

    # Acces restreint a l'utilisateur courant.
    $acl = Get-Acl '.env'
    $acl.SetAccessRuleProtection($true, $false)
    $regle = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $env:USERNAME, 'FullControl', 'Allow')
    $acl.SetAccessRule($regle)
    Set-Acl '.env' $acl

    Write-Host ''
    Write-Host '  Identifiants enregistres dans .env (lisible par vous seul).'
}

# ------------------------------------------------------- Script quotidien ---
$Lanceur = Join-Path $Dossier 'veille_quotidienne.bat'
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do set "%%a=%%b"
echo. >> veille.log
echo ======== %date% %time% ======== >> veille.log
python scrape.py       >> veille.log 2>&1 || goto :echec
python enrich.py       >> veille.log 2>&1 || goto :echec
python dedup.py        >> veille.log 2>&1 || goto :echec
python add_postal.py   >> veille.log 2>&1 || goto :echec
python get_population.py >> veille.log 2>&1 || goto :echec
python get_surfaces.py >> veille.log 2>&1 || goto :echec
python get_images.py   >> veille.log 2>&1 || goto :echec
python make_xlsx.py    >> veille.log 2>&1 || goto :echec
python send_email.py   >> veille.log 2>&1 || goto :echec
echo Termine. >> veille.log
exit /b 0
:echec
echo ECHEC - voir ci-dessus. >> veille.log
exit /b 1
"@ | Set-Content -Path $Lanceur -Encoding ASCII

# ------------------------------------------------------------ Planification ---
Write-Host ''
Write-Host 'Programmation de l''execution automatique...'

schtasks /Delete /TN 'Veille Agorastore' /F 2>$null | Out-Null
schtasks /Create /TN 'Veille Agorastore' /TR "`"$Lanceur`"" `
         /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 18:00 /F | Out-Null

Write-Host '  Programme via les Taches planifiees (lun-ven, 18 h).'
Write-Host '  Pour arreter : schtasks /Delete /TN "Veille Agorastore" /F'

Write-Host ''
Write-Host '  Installation terminee.' -ForegroundColor Green
Write-Host ''
Write-Host '  Le rapport partira automatiquement du lundi au vendredi a 18 h,'
Write-Host '  a condition que l''ordinateur soit allume et connecte a cette heure-la.'
Write-Host ''

$essai = Read-Host '  Faire un essai maintenant ? (environ 5 min) [o/N]'
if ($essai -match '^[oOyY]') {
    Write-Host ''
    & $Lanceur
    if ($LASTEXITCODE -eq 0) {
        Write-Host ''
        Write-Host '  Envoye. Verifiez votre boite de reception.' -ForegroundColor Green
    } else {
        Write-Host ''
        Write-Host '  L''essai a echoue. Le detail est dans veille.log :' -ForegroundColor Red
        Get-Content veille.log -Tail 20
    }
} else {
    Write-Host '  Vous pourrez tester plus tard en lancant veille_quotidienne.bat'
}
Write-Host ''
Read-Host '  Appuyez sur Entree pour fermer'
