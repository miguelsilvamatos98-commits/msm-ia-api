import os
import base64
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI

app = FastAPI(title="AI Python", version="1.0.0")

# CORS (podes apertar depois)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _to_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form(""),
    duracao: int = Form(90),
):
    # 1) Key
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY em falta no servico Python."}

    # 2) Ler imagem
    try:
        img_bytes = await grafico.read()
        mime = grafico.content_type or "image/png"
        data_url = _to_data_url(img_bytes, mime)
    except Exception as e:
        return {"ok": False, "error": "Falha ao ler imagem", "details": str(e)}

    # 3) Prompt
    ativo_txt = ativo.strip() if ativo else ""
    prompt = (
        "Analisa a imagem do gráfico (candlesticks) para opções binárias.\n"
        "Responde APENAS em JSON com esta estrutura:\n"
        "{\n"
        '  "sinal": "COMPRA|VENDA|SEM SINAL",\n'
        '  "confianca": 0-100,\n'
        '  "motivo": "curto"\n'
        "}\n"
        f"Ativo: {ativo_txt}\n"
        f"Duração (segundos): {duracao}\n"
        "Regras:\n"
        "- Se não houver padrão claro, usa SEM SINAL.\n"
        "- Confianca deve ser um número inteiro.\n"
    )

    # 4) OpenAI Responses (AQUI fica o client.responses.create)
    try:
        client = OpenAI(api_key=api_key)

        r = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            max_output_tokens=200,
        )

        text = (r.output_text or "").strip()
        if not text:
            return {"ok": False, "error": "Resposta vazia do modelo."}

        # Se vier JSON puro, ótimo. Se vier texto extra, devolvemos raw.
        return {"ok": True, "raw": text}

    except Exception as e:
        return {"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)}
