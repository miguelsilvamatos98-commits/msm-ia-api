from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
import time

# ===============================
# CONFIG
# ===============================

APP_NAME = "Trade Speed AI"
RESET_PASSWORD = os.environ.get("FEEDBACK_RESET_PASSWORD", "msm-reset-123")
DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "feedback.db")

# ===============================
# APP
# ===============================

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# DATABASE
# ===============================

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

# ===============================
# MODELS
# ===============================

class FeedbackIn(BaseModel):
    ts: int
    page: str | None = None
    outcome: str  # WIN | LOSE
    sinal: str | None = None
    confianca: int | None = None
    motivo: str | None = None
    ativo: str | None = None
    duracao_segundos: int | None = None


class ResetIn(BaseModel):
    password: str


# ===============================
# ROUTES
# ===============================

@app.get("/")
def root():
    return {"ok": True, "service": "trade-speed-ai-python"}


# -------------------------------
# IA PREDICT
# -------------------------------
@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: int = Form(60),  # agora default 60s
):
    """
    ⚠️ AQUI entra a tua IA real.
    Este bloco é compatível com o HTML atual.
    """

    # Lê a imagem (obrigatório para não dar erro)
    _ = await grafico.read()

    # 🔁 SIMULAÇÃO (troca pela tua IA real)
    # Dica: nunca devolver confiança alta sempre
    sinal = "SEM SINAL"
    confianca = 72
    motivo = "mercado indefinido / pullback sem confirmação"

    if confianca >= 85:
        sinal = "COMPRA"

    return {
        "ok": True,
        "sinal": sinal,
        "confianca": int(confianca),
        "motivo": motivo,
        "ativo": ativo,
        "duracao_segundos": int(duracao),
    }


# -------------------------------
# FEEDBACK
# -------------------------------
@app.post("/feedback")
def feedback(data: FeedbackIn):
    outcome = data.outcome.upper().strip()
    if outcome not in ("WIN", "LOSE"):
        raise HTTPException(status_code=400, detail="Outcome inválido")

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
        data.confianca,
        data.motivo,
        data.ativo,
        data.duracao_segundos
    ))
    conn.commit()
    conn.close()

    return {"ok": True}


# -------------------------------
# FEEDBACK STATS
# -------------------------------
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

    return {
        "ok": True,
        "total": total,
        "win": win,
        "lose": lose
    }


# -------------------------------
# FEEDBACK RESET (COM SENHA)
# -------------------------------
@app.post("/feedback/reset")
def feedback_reset(data: ResetIn):
    if data.password != RESET_PASSWORD:
        raise HTTPException(status_code=401, detail="Password incorreta")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()

    return {"ok": True, "message": "Feedback resetado com sucesso"}
