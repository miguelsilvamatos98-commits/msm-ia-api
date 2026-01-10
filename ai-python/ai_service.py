from fastapi import FastAPI, File, Form, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import time
import os
import base64
import json
from typing import Optional

# OpenAI (server-side)
from openai import OpenAI

app = FastAPI(title="Trade Speed AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # podes restringir ao teu domínio depois
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "feedback.db")
RESET_PASSWORD = os.environ.get("FEEDBACK_RESET_PASSWORD", "")  # define no Render
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


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
    page: Optional[str] = None
    outcome: str  # "WIN" or "LOSE"
    sinal: Optional[str] = None
    confianca: Optional[int] = None
    motivo: Optional[str] = None
    ativo: Optional[str] = None
    duracao_segundos: Optional[int] = None


@app.get("/")
def root():
    return {"ok": True, "service": "trade-speed-ai-python", "openai_enabled": bool(client), "model": OPENAI_MODEL}


def _db():
    return sqlite3.connect(DB_PATH)


def _extract_json(text: str) -> dict:
    """
    Tenta extrair JSON mesmo se o modelo devolver texto com lixo.
    """
    text = (text or "").strip()

    # Se for JSON puro
    try:
        return json.loads(text)
    except:
        pass

    # Tenta achar um bloco {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        return json.loads(candidate)

    raise ValueError("Resposta não é JSON válido.")


@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: int = Form(90),
):
    img_bytes = await grafico.read()

    # Se não houver OPENAI_API_KEY, devolve erro claro (em vez de “simular”)
    if not client:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY não configurada no servidor (Render).",
            "used_openai": False,
        }

    b64 = base64.b64encode(img_bytes).decode("utf-8")
    data_url = f"data:{grafico.content_type or 'image/png'};base64,{b64}"

    prompt = f"""
Analisa a imagem do gráfico (candlesticks) para opções binárias.
Ativo: {ativo}
Duração da trade (segundos): {duracao}

Regras IMPORTANTES:
- Responde APENAS em JSON válido (sem texto extra).
- Campos obrigatórios:
  - ok (true)
  - sinal ("COMPRA" ou "VENDA" ou "SEM SINAL")
  - confianca (0-100 inteiro)
  - motivo (string curta)
  - ativo (string)
  - duracao_segundos (inteiro)

Critérios:
- Se não houver padrão claro, devolve "SEM SINAL".
- Se o mercado estiver “lateral”/confuso/pullback sem confirmação, tende a "SEM SINAL".
"""

    try:
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt.strip()},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )

        # texto final do modelo
        out_text = (resp.output_text or "").strip()
        data = _extract_json(out_text)

        # normaliza e garante campos
        sinal = str(data.get("sinal", "")).upper().strip()
        if sinal not in ("COMPRA", "VENDA", "SEM SINAL"):
            sinal = "SEM SINAL"

        confianca = data.get("confianca", 0)
        try:
            confianca = int(round(float(confianca)))
        except:
            confianca = 0
        confianca = max(0, min(100, confianca))

        motivo = str(data.get("motivo", "")).strip()[:240]

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca,
            "motivo": motivo,
            "ativo": str(data.get("ativo", ativo)),
            "duracao_segundos": int(data.get("duracao_segundos", duracao)),
            # ✅ para tu confirmares no teu site/console que é OpenAI
            "used_openai": True,
            "model": OPENAI_MODEL,
            "openai_response_id": getattr(resp, "id", None),
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Falha ao analisar com OpenAI: {str(e)}",
            "used_openai": True,
            "model": OPENAI_MODEL,
        }


@app.post("/feedback")
def feedback(data: FeedbackIn):
    outcome = data.outcome.upper().strip()
    if outcome not in ("WIN", "LOSE"):
        return {"ok": False, "error": "outcome inválido. Use WIN ou LOSE."}

    conn = _db()
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
    conn = _db()
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
def feedback_reset(x_reset_password: Optional[str] = Header(default=None)):
    """
    Reset protegido por senha.
    Envia um header:  X-Reset-Password: <1337>
    """
    if not RESET_PASSWORD:
        return {"ok": False, "error": "FEEDBACK_RESET_PASSWORD não configurada no servidor."}

    if not x_reset_password or x_reset_password != RESET_PASSWORD:
        return {"ok": False, "error": "Senha inválida."}

    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()
    return {"ok": True, "reset": True}
