import os
import json
import base64
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI

app = FastAPI(title="AI Python", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # podes restringir depois ao teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def safe_int(n: Any, default: int = 0) -> int:
    try:
        return int(float(n))
    except Exception:
        return default


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}


@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form(""),
    duracao: int = Form(90),
):
    # 1) API key
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY em falta no servico Python."}

    # 2) Ler imagem
    try:
        img_bytes = await grafico.read()
        mime = grafico.content_type or "image/png"
        data_url = to_data_url(img_bytes, mime)
    except Exception as e:
        return {"ok": False, "error": "Falha ao ler imagem", "details": str(e)}

    ativo_txt = (ativo or "").strip()
    dur = safe_int(duracao, 90)

    # 3) Prompt + JSON Schema (para o modelo devolver JSON limpo)
    prompt = (
        "Analisa a imagem do gráfico (candlesticks) para opções binárias.\n"
        "Tens de devolver um JSON válido (sem texto extra) com:\n"
        "- sinal: COMPRA, VENDA ou SEM SINAL\n"
        "- confianca: inteiro 0 a 100\n"
        "- motivo: frase curta\n"
        f"Ativo: {ativo_txt}\n"
        f"Duração (segundos): {dur}\n"
        "Regras:\n"
        "- Se não houver padrão claro, devolve SEM SINAL.\n"
        "- Confiança é um inteiro.\n"
    )

    # 4) OpenAI Responses API (AQUI fica o client.responses.create)
    try:
        client = OpenAI(api_key=api_key)

        r = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        # ✅ IMPORTANTE: usa "image_url" com data URL (NÃO image_base64)
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "trade_signal",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "sinal": {
                                "type": "string",
                                "enum": ["COMPRA", "VENDA", "SEM SINAL"],
                            },
                            "confianca": {"type": "integer", "minimum": 0, "maximum": 100},
                            "motivo": {"type": "string"},
                        },
                        "required": ["sinal", "confianca", "motivo"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            max_output_tokens=220,
        )

        text = (r.output_text or "").strip()
        if not text:
            return {"ok": False, "error": "Resposta vazia do modelo."}

        # 5) Parse do JSON garantido
        obj: Dict[str, Any] = json.loads(text)

        sinal = str(obj.get("sinal", "SEM SINAL")).upper().strip()
        confianca = clamp(safe_int(obj.get("confianca", 0), 0), 0, 100)
        motivo = str(obj.get("motivo", "")).strip()

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca,
            "motivo": motivo,
            "ativo": ativo_txt,
            "duracao_segundos": dur,
        }

    except Exception as e:
        return {"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)}
