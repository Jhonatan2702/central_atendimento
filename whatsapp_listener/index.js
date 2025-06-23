const venom = require('venom-bot');
const axios = require('axios');
const fs = require('fs');

venom
  .create({
    session: 'central_atendimento'
  })
  .then((client) => start(client))
  .catch((error) => console.log(error));

if (!fs.existsSync('static/uploads')) {
  fs.mkdirSync('static/uploads', { recursive: true });
}

function start(client) {
  client.onMessage(async (message) => {
    if (message.isGroupMsg === false) {
      console.log(`📩 Nova mensagem de ${message.from}: ${message.body}`);
      console.log('Tipo da mensagem:', message.type);

      try {
        // Verifica se a mensagem contém um arquivo de áudio
        if (message.type === 'audio' || message.type === 'ptt') {
          // Faz o download do arquivo de áudio
          const buffer = await client.decryptFile(message);
          if (!buffer) {
            console.error('❌ Falha ao baixar o áudio!');
            return;
          }

          // Salva o arquivo de áudio na pasta 'uploads'
          const filePath = `static/uploads/audio_${message.id}.ogg`;
          fs.writeFileSync(filePath, buffer);

          // Envia os dados da mensagem para a API FastAPI
          await axios.post('http://localhost:8080/mensagem_recebida', {
            numero: message.from,
            nome_cliente: message.sender.pushname || "Sem Nome",
            conteudo: `uploads/audio_${message.id}.ogg`,
            tipo: 'audio'
          });
        } else if (message.type === 'image') {
          const buffer = await client.decryptFile(message);
          if (!buffer) {
            console.error('❌ Falha ao baixar a imagem!');
            return;
          }
          // Detecta extensão pelo mimetype
          let ext = 'jpeg';
          if (message.mimetype === 'image/png') ext = 'png';
          if (message.mimetype === 'image/webp') ext = 'webp';
          const filePath = `static/uploads/img_${message.id}.${ext}`;
          fs.writeFileSync(filePath, buffer);

          await axios.post('http://localhost:8080/mensagem_recebida', {
            numero: message.from,
            nome_cliente: message.sender.pushname || "Sem Nome",
            conteudo: `uploads/img_${message.id}.${ext}`,
            tipo: 'imagem'
          });
        } else {
          await axios.post('http://localhost:8080/mensagem_recebida', {
            numero: message.from,
            nome_cliente: message.sender.pushname || "Sem Nome",
            conteudo: message.body,
            tipo: message.type === 'chat' ? 'texto' : message.type
          });
        }

        console.log('✅ Mensagem enviada para a API FastAPI.');
      } catch (err) {
        console.error('❌ Erro ao enviar para FastAPI:', err.message);
      }
    }
  });

  const express = require('express');
  const bodyParser = require('body-parser');
  const app = express();
  app.use(bodyParser.json());

  app.post('/enviar_mensagem', async (req, res) => {
    const { numero, mensagem } = req.body;
    try {
      await client.sendText(numero, mensagem);
      console.log(`✅ Mensagem enviada para ${numero}: ${mensagem}`);
      res.json({ status: 'Mensagem enviada' });
    } catch (error) {
      console.error('❌ Erro ao enviar mensagem:', error);
      res.status(500).json({ status: 'Erro', detalhe: error.toString() });
    }
  });

  app.listen(3000, '0.0.0.0', () => {
    console.log('🚀 API rodando na porta 3000');
  });
}

