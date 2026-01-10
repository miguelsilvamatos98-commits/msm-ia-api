from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import time
import os

app = FastAPI(title="Trade Speed AI")

# CORS (para o teu site conseguir chamar a API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "feedback.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        page TEXT,
        outcome TEXT,
        sinal TEXT,
        confianca INTEGER,
        motivo TEXT,
        ativo TEXT,
        duracao_segundos INTEGER
      )
    """)
    conn.commit()
    conn.close()

init_db()

class FeedbackIn(BaseModel):
    ts: int
    page: str | None = None
    outcome: str  # "WIN" or "LOSE"
    sinal: str | None = None
    confianca: int | None = None
    motivo: str | None = None
    ativo: str | None = None
    duracao_segundos: int | None = None

@app.get("/")
def root():
    return {"ok": True, "service": "trade-speed-ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: int = Form(90),
):
    """
    Aqui tens a tua lógica de IA.
    Mantém a tua implementação real e garante que devolve:
      ok, sinal, confianca, motivo, ativo, duracao_segundos
    """

    # EXEMPLO (troca pela tua IA real):
    # - Vamos simular uma resposta só para não dar erro.
    # - Aqui era onde tu lias a imagem, extraías padrões, etc.
    _ = await grafico.read()

    # exemplo simples:
    sinal = "COMPRA"
    confianca = 70
    motivo = "exemplo: reversão após queda"

    return {
        "ok": True,
        "sinal": sinal,
        "confianca": int(confianca),
        "motivo": motivo,
        "ativo": ativo,
        "duracao_segundos": int(duracao),
    }

@app.post("/feedback")
def feedback(data: FeedbackIn):
    # valida outcome
    outcome = data.outcome.upper().strip()
    if outcome not in ("WIN", "LOSE"):
        return {"ok": False, "error": "outcome inválido. Use WIN ou LOSE."}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
      INSERT INTO feedback (ts, page, outcome, sinal, confianca, motivo, ativo, duracao_segundos)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(data.ts),
        data.page,
        outcome,
        data.sinal,
        int(data.confianca) if data.confianca is not None else None,
        data.motivo,
        data.ativo,
        int(data.duracao_segundos) if data.duracao_segundos is not None else None
    ))
    conn.commit()
    conn.close()

    return {"ok": True}

@app.get("/feedback/stats")
def feedback_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM feedback")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM feedback WHERE outcome='WIN'")
    win = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM feedback WHERE outcome='LOSE'")
    lose = cur.fetchone()[0] or 0

    conn.close()
    return {"ok": True, "total": total, "win": win, "lose": lose}
