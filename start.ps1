# start.ps1
& "${PSScriptRoot}\yeast_web\Scripts\Activate.ps1"
Set-Location "${PSScriptRoot}\yeastweb"
py manage.py runserver
