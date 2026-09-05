# Remove o Compilador de C instalado por instalar.ps1.
# Desfaz exatamente o que a instalacao criou: arquivos, atalhos e registro.

$ErrorActionPreference = "Continue"

$NomeApp = "Compilador de C"
$NomeExe = "Compilador-de-C.exe"
$ProgID  = "CompiladorDeC.ArquivoC"
$Destino = Join-Path $env:LOCALAPPDATA "Programs\CompiladorDeC"

function Ok($t)    { Write-Host "  OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  !   $t" -ForegroundColor Yellow }

Write-Host ""
Write-Host " Desinstalando o $NomeApp" -ForegroundColor White
Write-Host " ---------------------------------------------"
$r = Read-Host " Remover mesmo? [s/N]"
if ($r -notmatch "^[sSyY]") { Write-Host " Cancelado."; exit 0 }

# Fecha o programa, se estiver aberto.
Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($NomeExe)) -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

# Atalhos
$desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item (Join-Path $desktop "$NomeApp.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$NomeApp") `
            -Recurse -Force -ErrorAction SilentlyContinue
Ok "atalhos removidos"

# Registro
Remove-Item "HKCU:\Software\Classes\$ProgID" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Classes\Applications\$NomeExe" -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Classes\.c\OpenWithProgids" -Name $ProgID `
                    -Force -ErrorAction SilentlyContinue
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CompiladorDeC" `
            -Recurse -Force -ErrorAction SilentlyContinue

# A escolha do usuario no "Abrir com" fica guardada em outro lugar; limpa tambem.
$fileExt = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.c"
Remove-ItemProperty -Path "$fileExt\UserChoice" -Name "ProgId" -Force -ErrorAction SilentlyContinue
Ok "registro limpo"

# Arquivos (a pasta guarda so o que a instalacao colocou)
if (Test-Path $Destino) {
    Remove-Item $Destino -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $Destino) {
        Aviso "nao consegui apagar $Destino (algum arquivo em uso). Apague na mao."
    } else {
        Ok "arquivos removidos"
    }
}

Add-Type -Namespace Win32 -Name Shell2 -MemberDefinition @"
[DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, int flags, IntPtr item1, IntPtr item2);
"@
[Win32.Shell2]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host ""
Write-Host " Desinstalado." -ForegroundColor Green
Write-Host " O GCC, se foi instalado junto, continua na maquina."
Write-Host " Para remove-lo:  winget uninstall BrechtSanders.WinLibs.POSIX.UCRT"
Write-Host ""
Read-Host " Aperte Enter para fechar"
