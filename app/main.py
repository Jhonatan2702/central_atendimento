# app/main.py
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, Body, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import SessionLocal, Atendente, Cliente, Mensagem, Atendimento, TipoMensagem, StatusAtendimento
from passlib.hash import bcrypt
import requests
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

active_connections = []

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, login: str = Form(...), senha: str = Form(...)):
    db = SessionLocal()
    user = db.query(Atendente).filter(Atendente.login == login).first()
    print(f"Tentando login: {login}")
    if user:
        print("Usuário encontrado!")
        if bcrypt.verify(senha, user.senha):
            print("Senha correta!")
            response = RedirectResponse("/dashboard", status_code=302)
            response.set_cookie("user_id", str(user.id))
            return response
        else:
            print("Senha incorreta!")
    else:
        print("Usuário não encontrado!")
    return RedirectResponse("/", status_code=302)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    db = SessionLocal()
    atendente = db.query(Atendente).filter(Atendente.id == int(user_id)).first()

    # Última mensagem de cada cliente NÃO atribuída
    subq_nao_atr = (
        db.query(
            Mensagem.cliente_id,
            func.max(Mensagem.id).label("max_id")
        )
        .group_by(Mensagem.cliente_id)
        .subquery()
    )

    mensagens_nao_atribuidas = (
        db.query(Mensagem)
        .options(joinedload(Mensagem.cliente))
        .join(subq_nao_atr, Mensagem.id == subq_nao_atr.c.max_id)
        .filter(
            Mensagem.status == StatusAtendimento.aberto,
            Mensagem.atendente_id == None
        )
        .order_by(desc(Mensagem.data_hora))
        .all()
    )

    # Última mensagem de cada cliente ASSUMIDA pelo atendente logado
    subq_assumidas = (
        db.query(
            Mensagem.cliente_id,
            func.max(Mensagem.id).label("max_id")
        )
        .group_by(Mensagem.cliente_id)
        .subquery()
    )

    minhas_mensagens = (
        db.query(Mensagem)
        .options(joinedload(Mensagem.cliente))
        .join(subq_assumidas, Mensagem.id == subq_assumidas.c.max_id)
        .filter(
            Mensagem.status == StatusAtendimento.em_atendimento,
            Mensagem.atendente_id == int(user_id)
        )
        .order_by(desc(Mensagem.data_hora))
        .all()
    )

    db.close()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "atendente": atendente,
        "mensagens": mensagens_nao_atribuidas,  # <-- CERTO
        "minhas_mensagens": minhas_mensagens,
        "nao_atribuidas": len(mensagens_nao_atribuidas),  # <-- CERTO
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.post("/assumir/{mensagem_id}")
async def assumir_atendimento(mensagem_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    db = SessionLocal()
    mensagem = db.query(Mensagem).filter(Mensagem.id == mensagem_id).first()
    if mensagem:
        cliente_id = mensagem.cliente_id  # Salve antes de fechar a sessão!
        db.query(Mensagem).filter(
            Mensagem.cliente_id == cliente_id,
            Mensagem.atendente_id == None,
            Mensagem.status == StatusAtendimento.aberto
        ).update({
            Mensagem.atendente_id: int(user_id),
            Mensagem.status: StatusAtendimento.em_atendimento
        })
        db.commit()
        db.close()
        return RedirectResponse(f"/chat/{cliente_id}", status_code=302)
    db.close()
    return RedirectResponse("/dashboard", status_code=302)

    
#------------------------------------------------------------------------------

from fastapi import HTTPException
from datetime import datetime
from app.database import Cliente, TipoMensagem

@app.get("/simular_mensagem")
async def simular_mensagem(nome_cliente: str = "Cliente Teste", numero: str = "+5581999999999", conteudo: str = "Olá, quero falar com um atendente"):
    db = SessionLocal()

    # Verificar se o cliente já existe
    cliente = db.query(Cliente).filter(Cliente.numero_whatsapp == numero).first()
    if not cliente:
        cliente = Cliente(nome=nome_cliente, numero_whatsapp=numero)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    # Criar a mensagem
    nova_msg = Mensagem(
        cliente_id=cliente.id,
        tipo=TipoMensagem.entrada,
        conteudo=conteudo,
        status=StatusAtendimento.aberto  # <-- garante que volta para não atribuídas
    )
    db.add(nova_msg)
    db.commit()

    # Notificar os WebSocket clients (atualizar a dashboard em tempo real)
    for conn in active_connections:
        await conn.send_text("Nova mensagem!")

    return {"status": "Mensagem simulada com sucesso"}

#------------------------------------------------------------------------------

@app.get("/chat/{cliente_id}", response_class=HTMLResponse)
async def chat_cliente(request: Request, cliente_id: int = Path(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    
    db = SessionLocal()
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    mensagens = db.query(Mensagem).filter(Mensagem.cliente_id == cliente_id).order_by(Mensagem.data_hora).all()

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "cliente": cliente,
        "mensagens": mensagens
    })

#------------------------------------------------------------------------------

@app.post("/enviar_mensagem/{cliente_id}")
async def enviar_mensagem(cliente_id: int, request: Request, conteudo: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    
    db = SessionLocal()
    nova_msg = Mensagem(
        cliente_id=cliente_id,
        atendente_id=int(user_id),
        tipo=TipoMensagem.saida.value,  # CERTO: salva como string "saida"
        conteudo=conteudo,
        status=StatusAtendimento.em_atendimento  # <-- ESSENCIAL!
    )
    db.add(nova_msg)
    db.commit()

    # Notificar os WebSockets abertos (caso queira notificar o dashboard ou outras telas depois)
    for conn in active_connections:
        await conn.send_text("Nova mensagem enviada pelo atendente!")

    return RedirectResponse(f"/chat/{cliente_id}", status_code=302)

#------------------------------------------------------------------------------

@app.post("/mensagem_recebida")
async def mensagem_recebida(
    numero: str = Body(...),
    nome_cliente: str = Body(...),
    conteudo: str = Body(...),
    tipo: str = Body("texto")  # <-- novo campo
):
    db = SessionLocal()

    # Verificar se o cliente já existe
    cliente = db.query(Cliente).filter(Cliente.numero_whatsapp == numero).first()
    if not cliente:
        cliente = Cliente(nome=nome_cliente, numero_whatsapp=numero)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

    # Verificar se existe atendimento em andamento para esse cliente
    msg_em_andamento = db.query(Mensagem).filter(
        Mensagem.cliente_id == cliente.id,
        Mensagem.status == StatusAtendimento.em_atendimento,
        Mensagem.atendente_id != None
    ).order_by(Mensagem.data_hora.desc()).first()

    if msg_em_andamento:
        # Se existe, mantenha o status em_atendimento e o atendente
        nova_msg = Mensagem(
            cliente_id=cliente.id,
            direcao="entrada",           # <-- Adicione isto!
            tipo=tipo,                   # <-- Use o tipo recebido (texto, imagem, audio, pdf)
            conteudo=conteudo,
            status=StatusAtendimento.em_atendimento,
            atendente_id=msg_em_andamento.atendente_id
        )
    else:
        # Se não existe, é uma nova conversa
        nova_msg = Mensagem(
            cliente_id=cliente.id,
            direcao="entrada",
            tipo=tipo,
            conteudo=conteudo,
            status=StatusAtendimento.aberto
        )

    db.add(nova_msg)
    db.commit()

    # Notificar os WebSocket (atualizar dashboard)
    for conn in active_connections:
        await conn.send_text("Nova mensagem recebida!")

    return {"status": "Mensagem recebida e salva"}

#------------------------------------------------------------------------------

@app.post("/enviar_resposta")
async def enviar_resposta(request: Request, numero: str = Form(...), mensagem: str = Form(...)):
    user_id = request.cookies.get("user_id")  # <-- Adicione esta linha!
    if not user_id:
        return RedirectResponse("/", status_code=302)
    print(f"[FastAPI] Enviando para Node: numero={numero}, mensagem={mensagem}")
    try:
        resp = requests.post("http://localhost:3000/enviar_mensagem", json={"numero": numero, "mensagem": mensagem})
        print(f"[FastAPI] Resposta do Node: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[FastAPI] Erro ao enviar mensagem: {e}")

    # Salvar a mensagem enviada no banco
    db = SessionLocal()
    cliente = db.query(Cliente).filter(Cliente.numero_whatsapp == numero).first()
    if cliente:
        nova_msg = Mensagem(
            cliente_id=cliente.id,
            direcao="saida",
            tipo="texto",
            conteudo=mensagem,
            status=StatusAtendimento.em_atendimento,
            atendente_id=int(user_id)
        )
        db.add(nova_msg)
        db.commit()
        return RedirectResponse(f"/chat/{cliente.id}", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)

#------------------------------------------------------------------------------

@app.get("/admin/atendentes", response_class=HTMLResponse)
async def admin_atendentes(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    db = SessionLocal()
    atendente = db.query(Atendente).filter(Atendente.id == int(user_id)).first()
    if not atendente or atendente.acesso != "gerente":
        db.close()
        return RedirectResponse("/dashboard", status_code=302)
    atendentes = db.query(Atendente).all()
    db.close()
    return templates.TemplateResponse("admin_atendentes.html", {"request": request, "atendentes": atendentes})

@app.post("/admin/atendentes/add")
async def add_atendente(request: Request, nome: str = Form(...), login: str = Form(...), senha: str = Form(...), acesso: str = Form("atendente")):
    db = SessionLocal()
    novo = Atendente(nome=nome, login=login, senha=bcrypt.hash(senha), acesso=acesso)
    db.add(novo)
    db.commit()
    db.close()
    return RedirectResponse("/admin/atendentes", status_code=302)

@app.post("/admin/atendentes/delete/{id}")
async def delete_atendente(id: int):
    db = SessionLocal()
    db.query(Atendente).filter(Atendente.id == id).delete()
    db.commit()
    db.close()
    return RedirectResponse("/admin/atendentes", status_code=302)

@app.post("/admin/atendentes/acesso/{id}")
async def alterar_acesso(id: int, acesso: str = Form(...)):
    db = SessionLocal()
    db.query(Atendente).filter(Atendente.id == id).update({"acesso": acesso})
    db.commit()
    db.close()
    return RedirectResponse("/admin/atendentes", status_code=302)

@app.post("/encerrar/{cliente_id}")
async def encerrar_conversa(cliente_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)
    db = SessionLocal()
    db.query(Mensagem).filter(
        Mensagem.cliente_id == cliente_id,
        Mensagem.atendente_id == int(user_id),
        Mensagem.status == StatusAtendimento.em_atendimento
    ).update({
        Mensagem.atendente_id: None,
        Mensagem.status: StatusAtendimento.encerrado
    })
    db.commit()
    db.close()
    return RedirectResponse("/dashboard", status_code=302)

@app.post("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id")
    return response
