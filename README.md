
# Central de Atendimento WhatsApp Multiatendente

## Como rodar localmente:

### Instale as dependências:
```bash
pip install -r requirements.txt
pip install python-multipart

```

### Rode o servidor:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Acesse no navegador:
http://localhost:8080/

**Funções básicas:** Login de atendente, dashboard, assumir atendimento, real-time via WebSocket.

Próximos passos: simular mensagens recebidas, integrar com WhatsApp API.
