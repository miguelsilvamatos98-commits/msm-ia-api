import base64
import io
import json
import os
import re
from typing import Optional, Literal, Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from openai import OpenAI

app = FastAPI(title="Trade Speed AI (Python)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # se quiseres, depois restringimos ao teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

ALLOWED_SIGNALS = {"COMPRA", "VENDA", "SEM SINAL"}


def _image_to_data_url(image_bytes: bytes, max_side: int = 1280, quality: int = 85) -> str:
    """
    Normaliza a imagem:
    - converte para RGB
    - redimensiona para não ser gigante (mais rápido/barato)
    - exporta para JPEG
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(out.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Tenta apanhar um JSON mesmo que o modelo responda com texto extra.
    """
    if not text:
        return None
    # procura primeiro bloco { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}


@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form(""),
    duracao: int = Form(90),
):
    # validações básicas
    if not os.getenv("OPENAI_API_KEY"):
        return {"ok": False, "error": "OPENAI_API_KEY em falta no serviço Python."}

    try:
        raw = await grafico.read()
        if not raw:
            return {"ok": False, "error": "Ficheiro vazio."}

        data_url = _image_to_data_url(raw)

        # Prompt focado em Pocket Option
        prompt = f"""
Tu és um analisador de prints do gráfico Pocket Option (candlesticks).
Lê APENAS o que está no print.

Objetivo: sugerir um sinal para expiração curta (binárias) para o ativo {ativo}.
Duração: {duracao} segundos.

Regras:
- Se a imagem não for um gráfico de candlesticks legível, responde SEM SINAL e confiança baixa.
- Se houver ambiguidade (mercado lateral/sem padrão claro), responde SEM SINAL.
- Só responde COMPRA ou VENDA quando houver um padrão bem claro.
- Responde OBRIGATORIAMENTE num JSON puro e válido, sem texto extra.

Formato JSON:
{{
  "sinal": "COMPRA" | "VENDA" | "SEM SINAL",
  "confianca": inteiro 0-100,
  "motivo_curto": "texto curto (1 linha)"
}}
"""

        # Usa um modelo com visão (podes trocar)
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt.strip()},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            # ajuda a manter a saída “limpa”
            max_output_tokens=250,
        )

        text = getattr(resp, "output_text", "") or ""
        data = _extract_json(text)

        if not data:
            return {
                "ok": False,
                "error": "Resposta inválida do modelo (não veio JSON).",
                "raw": text[:500],
            }

        sinal = str(data.get("sinal", "")).upper().strip()
        confianca = data.get("confianca", 0)

        # normaliza SEM SINAL
        if sinal in {"SEMSINAL", "SEM-SINAL", "NONE", "NO SIGNAL"}:
            sinal = "SEM SINAL"

        if sinal not in ALLOWED_SIGNALS:
            return {
                "ok": False,
                "error": f"Sinal inválido retornado: {sinal}",
                "raw": data,
            }

        try:
            confianca_int = int(confianca)
        except Exception:
            confianca_int = 0

        confianca_int = max(0, min(100, confianca_int))

        # saída final padronizada
        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca_int,
            "ativo": ativo,
            "duracao_segundos": int(duracao),
            "motivo_curto": str(data.get("motivo_curto", "")).strip()[:120],
        }

    except Exception as e:
        return {"ok": False, "error": "Erro interno no serviço Python.", "details": str(e)}
