@echo off
REM Script d'installation pour Assistant Juridique Malgache
REM Pour Windows

echo ==========================================
echo Assistant Juridique Malgache - Installation
echo ==========================================

REM Vérifie si Python 3.11+ est disponible
echo.
echo [1/4] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Erreur : Python n'est pas installe ou pas dans le PATH !
    echo    Telechargez-le depuis https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% LSS 3 (
    echo ❌ Erreur : Python 3.11 ou superieur est requis !
    pause
    exit /b 1
)
if %PYTHON_MAJOR% EQU 3 if %PYTHON_MINOR% LSS 11 (
    echo ❌ Erreur : Python 3.11 ou superieur est requis !
    pause
    exit /b 1
)

echo ✓ Python %PYTHON_VERSION% trouve

REM Crée l'environnement virtuel
echo.
echo [2/4] Creation de l'environnement virtuel...
if not exist ".venv" (
    python -m venv .venv
    echo ✓ Environnement virtuel .venv cree
) else (
    echo ℹ Environnement virtuel .venv existe deja
)

REM Active l'environnement et installe les dependances
echo.
echo [3/4] Installation des dependances...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo ✓ Dependances installees

REM Copie .env.example vers .env si nécessaire
echo.
echo [4/4] Configuration de l'environnement...
if not exist ".env" (
    copy .env.example .env >nul
    echo ✓ Fichier .env cree depuis .env.example
    echo.
    echo ⚠️ IMPORTANT : Modifiez le fichier .env avec vos vraies valeurs !
    echo    Variables a configurer :
    echo    - DATABASE_URL
    echo    - JWT_SECRET_KEY
    echo    - LLM_PROVIDER
    echo    - MISTRAL_API_KEY ou GCP_PROJECT_ID
) else (
    echo ℹ Fichier .env existe deja
)

REM Instructions finales
echo.
echo ==========================================
echo ✅ Installation terminee !
echo ==========================================
echo.
echo Pour lancer le serveur :
echo    .venv\Scripts\activate.bat
echo    uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
echo.
echo Documentation API disponible sur :
echo    Production : https://api.mpanolontsaina-ia.duckdns.org/api/docs
echo    Local : http://localhost:8080/api/docs
echo    Production : https://api.mpanolontsaina-ia.duckdns.org/api/redoc
echo    Local : http://localhost:8080/api/redoc
echo.
echo Health check :
echo    Production : https://api.mpanolontsaina-ia.duckdns.org/health
echo    Local : http://localhost:8080/health
echo ==========================================
pause
