@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Sempre trabalha na pasta onde este BAT estiver.
cd /d "%~dp0"

set "REPO_URL=https://github.com/spacevipgames/bandit1200turbo.git"
set "BRANCH=main"
set "COMMIT_MSG=%~1"
if not defined COMMIT_MSG set "COMMIT_MSG=Atualiza firmware Bandit 1200 Turbo - %DATE% %TIME:~0,8%"

title Backup GitHub - Bandit 1200 Turbo

echo.
echo ============================================================
echo   BANDIT 1200 TURBO - ENVIO DA FIRMWARE PARA O GITHUB
echo ============================================================
echo Pasta: %CD%
echo Repo : %REPO_URL%
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo ERRO: Git nao foi encontrado no PATH.
    echo Instale o Git for Windows e tente novamente.
    goto :erro
)

if not exist "speeduino\" (
    echo ERRO: pasta "speeduino" nao encontrada ao lado do BAT.
    goto :erro
)

if not exist "reference\speeduino.ini" (
    echo ERRO: "reference\speeduino.ini" nao encontrado.
    goto :erro
)

if not exist ".git\" (
    echo Inicializando repositorio Git nesta pasta...
    git init
    if errorlevel 1 goto :erro
)

rem Mantem os finais de linha originais e evita avisos LF/CRLF neste repositorio.
git config core.autocrlf false
if errorlevel 1 goto :erro

git branch -M "%BRANCH%" >nul 2>&1

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin "%REPO_URL%"
) else (
    git remote set-url origin "%REPO_URL%"
)
if errorlevel 1 goto :erro

echo Atualizando referencia remota e protegendo o README.md...
git fetch origin "%BRANCH%"
if errorlevel 1 (
    echo ERRO: nao foi possivel acessar origin/%BRANCH%.
    echo Verifique internet, login do GitHub e permissao no repositorio.
    goto :erro
)

git cat-file -e "origin/%BRANCH%:README.md" >nul 2>&1
if not errorlevel 1 (
    git checkout "origin/%BRANCH%" -- README.md
) else (
    echo AVISO: README.md nao existe no repositorio remoto.
)

echo.
echo Arquivos locais detectados:
git status --short
echo.
echo O envio substituira o conteudo remoto pela pasta atual,
echo preservando o README.md existente no GitHub.
echo.
set /p "CONFIRMAR=Digite S para confirmar o envio: "
if /I not "%CONFIRMAR%"=="S" (
    echo Envio cancelado. Nenhum push foi realizado.
    goto :fim
)

git add -A
if errorlevel 1 goto :erro

git diff --cached --quiet >nul 2>&1
if errorlevel 1 (
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 (
        echo ERRO: falha ao criar o commit.
        echo Confira se user.name e user.email estao configurados no Git.
        goto :erro
    )
) else (
    echo Nenhuma alteracao nova para criar commit.
)

git rev-parse --verify HEAD >nul 2>&1
if errorlevel 1 (
    echo ERRO: nao existe commit local para enviar.
    goto :erro
)

echo.
echo Enviando para o GitHub...
git push --force-with-lease -u origin "%BRANCH%"
if errorlevel 1 (
    echo ERRO: o GitHub recusou o envio.
    echo Nenhum arquivo remoto foi sobrescrito apos essa falha.
    goto :erro
)

echo.
echo SUCESSO: firmware salva no GitHub.
echo Commit atual:
git log -1 --oneline
goto :fim

:erro
echo.
echo O processo terminou com erro. Revise a mensagem acima.
pause
exit /b 1

:fim
echo.
pause
exit /b 0
