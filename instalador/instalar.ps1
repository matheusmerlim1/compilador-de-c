# Instala o Compilador de C para o usuario atual.
#
# Nao exige administrador: copia para a pasta do usuario e escreve apenas em
# HKCU. Para desfazer, use desinstalar.ps1 (ou o atalho Desinstalar).

$ErrorActionPreference = "Stop"

$NomeApp   = "Compilador de C"
$NomeExe   = "Compilador-de-C.exe"
$ProgID    = "CompiladorDeC.ArquivoC"
$Destino   = Join-Path $env:LOCALAPPDATA "Programs\CompiladorDeC"
$Origem    = Split-Path -Parent $PSScriptRoot     # pasta do projeto

function Passo($texto) { Write-Host "  $texto" -ForegroundColor Cyan }
function Ok($texto)    { Write-Host "  OK  $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "  !   $texto" -ForegroundColor Yellow }

Write-Host ""
Write-Host " Instalando o $NomeApp" -ForegroundColor White
Write-Host " ---------------------------------------------"

# ---------------------------------------------------------------- arquivos
$exeOrigem = Join-Path $Origem "dist\$NomeExe"
if (-not (Test-Path $exeOrigem)) {
    $exeOrigem = Join-Path $PSScriptRoot $NomeExe          # ao lado do script
}
if (-not (Test-Path $exeOrigem)) {
    Write-Host ""
    Write-Host "  ERRO: nao encontrei o $NomeExe." -ForegroundColor Red
    Write-Host "  Ele deve estar em dist\ ou na mesma pasta deste script."
    Write-Host ""
    Read-Host "  Aperte Enter para fechar"
    exit 1
}

Passo "Copiando o programa para $Destino"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# Se uma versao anterior estiver aberta, o arquivo fica travado.
$exeDestino = Join-Path $Destino $NomeExe
if (Test-Path $exeDestino) {
    Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($NomeExe)) -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
Copy-Item $exeOrigem $exeDestino -Force
Ok "programa copiado"

$icone = Join-Path $Origem "recursos\compilador.ico"
$iconeDestino = Join-Path $Destino "compilador.ico"
if (Test-Path $icone) {
    Copy-Item $icone $iconeDestino -Force
} else {
    $iconeDestino = $exeDestino      # usa o icone embutido no proprio exe
}

# Leva junto os exercicios de exemplo, se existirem.
$exemplos = Join-Path $Origem "exercicios"
if (Test-Path $exemplos) {
    $destExemplos = Join-Path $Destino "exercicios"
    New-Item -ItemType Directory -Force -Path $destExemplos | Out-Null
    Copy-Item "$exemplos\*" $destExemplos -Recurse -Force -ErrorAction SilentlyContinue
    Ok "exercicios de exemplo copiados"
}

# Guarda o desinstalador junto do programa.
$desinstalador = Join-Path $PSScriptRoot "desinstalar.ps1"
if (Test-Path $desinstalador) {
    Copy-Item $desinstalador (Join-Path $Destino "desinstalar.ps1") -Force
}

# ---------------------------------------------------------------- atalhos
Passo "Criando atalhos"
$shell = New-Object -ComObject WScript.Shell

function NovoAtalho($caminho, $alvo, $args, $icone, $descricao, $pastaTrabalho) {
    $lnk = $shell.CreateShortcut($caminho)
    $lnk.TargetPath = $alvo
    if ($args) { $lnk.Arguments = $args }
    $lnk.IconLocation = "$icone,0"
    $lnk.Description = $descricao
    $lnk.WorkingDirectory = $pastaTrabalho
    $lnk.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
NovoAtalho (Join-Path $desktop "$NomeApp.lnk") $exeDestino $null $iconeDestino `
           "Escrever, compilar e testar exercicios em C" $Destino
Ok "atalho na Area de Trabalho"

$menu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$NomeApp"
New-Item -ItemType Directory -Force -Path $menu | Out-Null
NovoAtalho (Join-Path $menu "$NomeApp.lnk") $exeDestino $null $iconeDestino `
           "Escrever, compilar e testar exercicios em C" $Destino
NovoAtalho (Join-Path $menu "Desinstalar $NomeApp.lnk") `
           "powershell.exe" `
           "-NoProfile -ExecutionPolicy Bypass -File `"$Destino\desinstalar.ps1`"" `
           $iconeDestino "Remover o $NomeApp" $Destino
Ok "atalho no Menu Iniciar"

# ------------------------------------------------- associacao "Abrir com"
Passo "Registrando no 'Abrir com' dos arquivos .c"

# ProgID proprio: descreve como abrir um .c com este programa.
$raizProg = "HKCU:\Software\Classes\$ProgID"
New-Item -Path $raizProg -Force | Out-Null
Set-ItemProperty -Path $raizProg -Name "(Default)" -Value "Codigo-fonte em C"
New-Item -Path "$raizProg\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "$raizProg\DefaultIcon" -Name "(Default)" -Value "$iconeDestino,0"
New-Item -Path "$raizProg\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$raizProg\shell\open\command" -Name "(Default)" `
                 -Value "`"$exeDestino`" `"%1`""

# Oferece o programa na lista do "Abrir com" para .c, sem roubar o padrao.
$openWith = "HKCU:\Software\Classes\.c\OpenWithProgids"
New-Item -Path $openWith -Force | Out-Null
New-ItemProperty -Path $openWith -Name $ProgID -Value ([byte[]]@()) `
                 -PropertyType None -Force | Out-Null

# Faz o programa aparecer tambem na lista "Applications" do Explorer.
$app = "HKCU:\Software\Classes\Applications\$NomeExe"
New-Item -Path "$app\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$app\shell\open\command" -Name "(Default)" `
                 -Value "`"$exeDestino`" `"%1`""
Set-ItemProperty -Path $app -Name "FriendlyAppName" -Value $NomeApp
New-Item -Path "$app\SupportedTypes" -Force | Out-Null
Set-ItemProperty -Path "$app\SupportedTypes" -Name ".c" -Value ""
Ok "'Abrir com' registrado"

# ------------------------------------------- entrada em Aplicativos e Recursos
$desinst = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CompiladorDeC"
New-Item -Path $desinst -Force | Out-Null
Set-ItemProperty -Path $desinst -Name "DisplayName"     -Value $NomeApp
Set-ItemProperty -Path $desinst -Name "DisplayIcon"     -Value $exeDestino
Set-ItemProperty -Path $desinst -Name "DisplayVersion"  -Value "1.0"
Set-ItemProperty -Path $desinst -Name "Publisher"       -Value "Matheus Raposo"
Set-ItemProperty -Path $desinst -Name "InstallLocation" -Value $Destino
Set-ItemProperty -Path $desinst -Name "NoModify"        -Value 1 -Type DWord
Set-ItemProperty -Path $desinst -Name "NoRepair"        -Value 1 -Type DWord
Set-ItemProperty -Path $desinst -Name "UninstallString" `
    -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Destino\desinstalar.ps1`""

# Avisa o Explorer que as associacoes mudaram.
Add-Type -Namespace Win32 -Name Shell -MemberDefinition @"
[DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, int flags, IntPtr item1, IntPtr item2);
"@
[Win32.Shell]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)

# ------------------------------------------------------------ compilador C
Write-Host ""
Passo "Conferindo se existe um compilador C na maquina"
$gcc = Get-Command gcc -ErrorAction SilentlyContinue
if (-not $gcc) {
    $palpites = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\*\mingw64\bin\gcc.exe",
        "C:\msys64\ucrt64\bin\gcc.exe", "C:\MinGW\bin\gcc.exe"
    )
    foreach ($p in $palpites) {
        if (Get-Item $p -ErrorAction SilentlyContinue) { $gcc = $true; break }
    }
}

if ($gcc) {
    Ok "compilador C encontrado"
} else {
    Aviso "nenhum compilador C encontrado."
    Write-Host ""
    Write-Host "      O programa precisa do GCC para compilar seus exercicios."
    $r = Read-Host "      Instalar o GCC agora pelo winget? [S/n]"
    if ($r -eq "" -or $r -match "^[sSyY]") {
        winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT `
               --accept-package-agreements --accept-source-agreements
        Write-Host ""
        Aviso "feche e reabra as janelas para o PATH atualizar."
    } else {
        Write-Host "      Depois instale com:" -ForegroundColor Gray
        Write-Host "      winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host " ---------------------------------------------"
Write-Host " Instalado com sucesso." -ForegroundColor Green
Write-Host ""
Write-Host " Para abrir:"
Write-Host "   - o atalho '$NomeApp' na Area de Trabalho, ou"
Write-Host "   - clique com o botao direito em um arquivo .c e escolha"
Write-Host "     'Abrir com' > '$NomeApp'"
Write-Host ""
Read-Host " Aperte Enter para fechar"
