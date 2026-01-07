import os
import base64
from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io

from openai import OpenAI

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY não definida")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# ROOT (health)
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}

# ─────────────────────────────────────────────
# PREDICT
# ─────────────────────────────────────────────
@app.post("/predict")
async def predict(
    grafico: UploadFile,
    ativo: str = Form(...),
    duracao: int = Form(...)
):
    try:
        # ── ler imagem
        image_bytes = await grafico.read()

        # validar imagem
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()

        # converter para base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # ─────────────────────────────────────────
        # OPENAI — API NOVA (Responses)
        # ─────────────────────────────────────────
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analisa o gráfico de candlesticks para opções binárias.\n"
                                "Responde APENAS em JSON com este formato:\n\n"
                                "{\n"
                                '  "sinal": "COMPRA | VENDA | SEM SINAL",\n'
                                '  "confianca": numero de 0 a 100\n'
                                "}\n\n"
                                f"Ativo: {ativo}\n"
                                f"Duração: {duracao} segundos\n"
                            )
                        },
                        {
                            "type": "input_image",
                            "image_base64": image_b64
                        }
                    ]
                }
            ]
        )

        # ── extrair texto final
        output_text = response.output_text.strip()

        # tentar converter JSON
        import json
        data = json.loads(output_text)

        sinal = data.get("sinal", "SEM SINAL")
        confianca = int(data.get("confianca", 50))

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca,
            "ativo": ativo,
            "duracao_segundos": duracao
        }

    except Exception as e:
        return {
            "ok": False,
            "error": "Erro ao comunicar com a IA.",
            "details": str(e)
        }
