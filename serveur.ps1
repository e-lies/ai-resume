# Lance l'API avec le Python de l'environnement virtuel.
#
# `python -m uvicorn resume_ai.api:app` avec le Python système échoue de façon
# déroutante : uvicorn démarre, réserve le port, puis le worker meurt à l'import
# parce que le projet n'y est pas installé. Le serveur écoute sans jamais répondre.

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Error @'
Environnement virtuel absent. Créez-le d'abord :
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install -e ".[dev]"
'@
    exit 1
}

& $python -m uvicorn resume_ai.api:app --port 8000 --reload
