@echo off
title mercuriOS - Sistema de Gestion Financiera
echo ===========================================
echo Iniciando entorno virtual...
echo ===========================================

cd /d "%~dp0"

call venv\Scripts\activate

start "" "http://127.0.0.1:5000"

echo ===========================================
echo Iniciando servidor Flask...
echo ===========================================

python app.py

pause