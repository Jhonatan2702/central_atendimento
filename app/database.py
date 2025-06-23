from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Enum as SqlEnum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum

Base = declarative_base()
engine = create_engine("sqlite:///central_atendimento.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class TipoMensagem(enum.Enum):
    entrada = "entrada"
    saida = "saida"

class StatusAtendimento(enum.Enum):
    aberto = "aberto"
    em_atendimento = "em_atendimento"
    encerrado = "encerrado"

class Atendente(Base):
    __tablename__ = "atendentes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    login = Column(String, unique=True, nullable=False)
    senha = Column(String, nullable=False)
    acesso = Column(String, default="atendente")  # <-- Adicione esta linha

class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    numero_whatsapp = Column(String, unique=True, nullable=False)

class Atendimento(Base):
    __tablename__ = "atendimentos"
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    atendente_id = Column(Integer, ForeignKey("atendentes.id"))
    status = Column(String, default="em_andamento")
    inicio = Column(DateTime, default=datetime.utcnow)
    fim = Column(DateTime, nullable=True)

class Mensagem(Base):
    __tablename__ = "mensagens"
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    atendente_id = Column(Integer, ForeignKey("atendentes.id"), nullable=True)
    direcao = Column(String, default="entrada")  # "entrada" ou "saida"
    tipo = Column(String, default="texto")       # "texto", "imagem", "audio", "pdf"
    conteudo = Column(Text, nullable=False) # pode ser texto ou URL do arquivo
    data_hora = Column(DateTime, default=datetime.utcnow)
    status = Column(SqlEnum(StatusAtendimento), default=StatusAtendimento.aberto)
    cliente = relationship("Cliente")

Base.metadata.create_all(bind=engine)
