import os
import re
import json
import base64
from typing import Optional, Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI


app = FastAPI(title="AI Python", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # podes restringir depois
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Tenta apanhar JSON mesmo que o modelo devolva texto com lixo à volta.
    """
    text = (text or "").strip()
    if not text:
        return {}

    # caso venha com ```json ... ```
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()

    # tenta direto
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # tenta encontrar primeiro bloco {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}

    return {}


@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}


@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form(""),
    duracao: int = Form(90),
):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY em falta no servico Python."}

    # ler imagem
    try:
        img_bytes = await grafico.read()
        mime = grafico.content_type or "image/png"
        data_url = _to_data_url(img_bytes, mime)
    except Exception as e:
        return {"ok": False, "error": "Falha ao ler imagem", "details": str(e)}

    ativo_txt = (ativo or "").strip()

    prompt = (
        "Analisa a imagem do gráfico (candlesticks) para opções binárias.\n"
        "Responde APENAS em JSON (sem texto extra) com esta estrutura:\n"
        '{ "sinal":"COMPRA|VENDA|SEM SINAL", "confianca":0-100, "motivo":"curto" }\n'
        f"Ativo: {ativo_txt}\n"
        f"Duração (segundos): {duracao}\n"
        "Regras:\n"
        "- Se não houver padrão claro, usa SEM SINAL.\n"
        "- confianca tem de ser número inteiro (0-100).\n"
    )

    try:
        client = OpenAI(api_key=api_key)

        # ✅ IMPORTANTE:
        # - Nada de image_base64
        # - Nada de response_format
        # - Usa input_image com image_url "data:..."
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
            max_output_tokens=220,
        )

        text = (getattr(r, "output_text", "") or "").strip()
        if not text:
            return {"ok": False, "error": "Resposta vazia do modelo."}

        obj = _extract_json(text)

        sinal = str(obj.get("sinal", "")).strip().upper()
        conf = obj.get("confianca", None)
        motivo = str(obj.get("motivo", "")).strip()

        # validação final
        try:
            conf_int = int(conf)
        except Exception:
            conf_int = None

        if sinal not in ["COMPRA", "VENDA", "SEM SINAL"] or conf_int is None:
            # devolve raw para debug (mas ainda assim 200 OK)
            return {
                "ok": False,
                "error": "Resposta inválida do modelo (não veio JSON válido).",
                "raw": text,
            }

        # ✅ resposta final “bonita” para o Node/HTML
        return {
            "ok": True,
            "sinal": sinal,
            "confianca": conf_int,
            "motivo": motivo,
            "ativo": ativo_txt,
            "duracao_segundos": int(duracao),
        }

    except Exception as e:
        return {"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)}
