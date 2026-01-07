import os
import base64
import json
import re
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

app = FastAPI(title="AI Python", version="1.0.0")

# CORS (podes restringir depois ao teu domínio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def to_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def extract_json(text: str) -> Dict[str, Any]:
    """
    Tenta extrair JSON mesmo que o modelo devolva texto extra.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Resposta vazia.")

    # 1) Se já for JSON puro
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) Tentar apanhar o primeiro bloco {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Não encontrei JSON na resposta.")
    return json.loads(m.group(0))

@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form(""),
    duracao: int = Form(90),
):
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY em falta no servico Python."}

    # Ler imagem
    try:
        img_bytes = await grafico.read()
        mime = grafico.content_type or "image/png"
        data_url = to_data_url(img_bytes, mime)
    except Exception as e:
        return {"ok": False, "error": "Falha ao ler imagem", "details": str(e)}

    ativo_txt = (ativo or "").strip()

    # Prompt: devolve SÓ JSON
    prompt = (
        "Analisa a imagem do gráfico (candlesticks) para opções binárias.\n"
        "Devolve APENAS um JSON válido (sem texto fora do JSON) com:\n"
        '{ "sinal": "COMPRA|VENDA|SEM SINAL", "confianca": 0-100, "motivo": "curto" }\n'
        f"Ativo: {ativo_txt}\n"
        f"Duração (segundos): {duracao}\n"
        "Regras:\n"
        "- Se não houver padrão claro: SEM SINAL.\n"
        "- confianca tem de ser inteiro.\n"
        "- motivo curto (1 frase).\n"
    )

    try:
        client = OpenAI(api_key=api_key)

        # ✅ AQUI fica o client.responses.create(...)
        r = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        # ✅ CORRETO: image_url (data URL)
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            max_output_tokens=220,
        )

        text = (getattr(r, "output_text", "") or "").strip()
        data = extract_json(text)

        sinal = str(data.get("sinal", "")).upper().strip()
        confianca = data.get("confianca", None)
        motivo = str(data.get("motivo", "")).strip()

        # validações mínimas
        if sinal not in ("COMPRA", "VENDA", "SEM SINAL"):
            return {"ok": False, "error": "Sinal inválido vindo do modelo.", "raw": text}
        try:
            confianca_int = int(confianca)
        except Exception:
            return {"ok": False, "error": "Confiança inválida vinda do modelo.", "raw": text}

        confianca_int = max(0, min(100, confianca_int))

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca_int,
            "motivo": motivo,
            "ativo": ativo_txt,
            "duracao_segundos": int(duracao),
        }

    except Exception as e:
        return {"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)}
