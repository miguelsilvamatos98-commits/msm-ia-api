from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import time
import os
import base64
import json
import re

# OpenAI (Responses API - vision)
from openai import OpenAI

app = FastAPI(title="Trade Speed AI")

# CORS (para o teu site conseguir chamar a API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # se quiseres mais seguro, mete aqui só o teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# DB FEEDBACK
# ----------------------------
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

class ResetIn(BaseModel):
    password: str

# ----------------------------
# OPENAI
# ----------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")  # podes trocar
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = """
És um analisador de prints de gráficos (candlesticks) para opções binárias.
Responde SEMPRE em JSON puro, sem texto extra, no formato exato:
{
  "sinal": "COMPRA" | "VENDA" | "SEM SINAL",
  "confianca": 0-100,
  "motivo": "texto curto e direto"
}

Regras:
- Se não houver padrão claro, usa "SEM SINAL" e confiança baixa.
- Confiança 80+ só quando houver confluência muito clara (tendência, reversão, suporte/resistência, candles).
- Não inventes indicadores que não estão visíveis no print.
"""

def extract_json(text: str) -> dict:
    """
    Tenta extrair JSON mesmo que venha com texto extra.
    """
    text = text.strip()
    # caso venha só JSON
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    # tenta achar um bloco { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("Sem JSON na resposta do modelo.")
    return json.loads(m.group(0))

# ----------------------------
# ENDPOINTS
# ----------------------------
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
    Recebe o print e manda para a OpenAI (vision) analisar.
    Retorna: ok, sinal, confianca, motivo, ativo, duracao_segundos
    """
    if client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não definido no servidor.")

    img_bytes = await grafico.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Imagem vazia.")

    # data URL base64
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    # tenta inferir mime
    mime = grafico.content_type or "image/png"
    data_url = f"data:{mime};base64,{b64}"

    user_prompt = f"""
Ativo: {ativo}
Duração da trade (segundos): {duracao}

Analisa o print e devolve o JSON pedido.
"""

    try:
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[{
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]
            },{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        )

        out_text = (resp.output_text or "").strip()
        data = extract_json(out_text)

        sinal = str(data.get("sinal", "")).upper().strip()
        confianca = int(float(data.get("confianca", 0)))
        motivo = str(data.get("motivo", "")).strip()

        if sinal not in ("COMPRA", "VENDA", "SEM SINAL"):
            sinal = "SEM SINAL"
        confianca = max(0, min(100, confianca))
        if not motivo:
            motivo = "Sem motivo detalhado."

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca,
            "motivo": motivo,
            "ativo": ativo,
            "duracao_segundos": int(duracao),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro OpenAI: {str(e)}")

@app.post("/feedback")
def feedback(data: FeedbackIn):
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

@app.post("/feedback/reset")
def feedback_reset(body: ResetIn):
    """
    Apaga a tabela de feedback. Protegido por senha:
    Env var: FEEDBACK_RESET_PASSWORD
    """
    expected = os.environ.get("FEEDBACK_RESET_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=500, detail="FEEDBACK_RESET_PASSWORD não definido no servidor.")
    if body.password != expected:
        raise HTTPException(status_code=401, detail="Senha inválida.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()

    return {"ok": True, "reset": True}
