@echo off
REM Ativa o ambiente virtual, se você usa um (ajuste o caminho se necessário)
call venv\Scripts\activate

REM Inicia o backend FastAPI (ajuste o caminho do main.py e a porta se necessário)
start cmd /k uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

REM Aguarda 3 segundos para garantir que o backend subiu
timeout /t 3

REM Inicia o listener do WhatsApp (ajuste o caminho do index.js se necessário)
start cmd /k node whatsapp_listener\index.js

REM Mantém a janela aberta
pause