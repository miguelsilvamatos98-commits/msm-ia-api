import os
import json
import base64
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openai import OpenAI


# ---------- Config ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

app = FastAPI(title="trade-speed-ai-python", version="1.0.0")

# CORS (ajusta se quiseres restringir ao teu domínio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _data_url_from_bytes(image_bytes: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _safe_json_parse(text: str) -> Optional[dict]:
    """
    Tenta extrair JSON mesmo que venha com texto extra.
    """
    text = (text or "").strip()
    if not text:
        return None

    # Caso venha JSON puro
    try:
        return json.loads(text)
    except Exception:
        pass

    # Caso venha com lixo antes/depois
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except Exception:
            return None

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
    # 1) validações básicas
    if not OPENAI_API_KEY:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": "OPENAI_API_KEY em falta no serviço Python."},
        )

    try:
        image_bytes = await grafico.read()
        if not image_bytes:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "error": "Ficheiro de imagem vazio."},
            )

        # tenta manter content-type do upload (fallback png)
        mime = grafico.content_type or "image/png"
        if not mime.startswith("image/"):
            mime = "image/png"

        image_data_url = _data_url_from_bytes(image_bytes, mime=mime)

        # 2) prompt (força JSON estrito)
        prompt = f"""
Analisa o print do gráfico (candlesticks) e devolve UM JSON válido (sem texto extra) no formato:

{{
  "sinal": "COMPRA" | "VENDA" | "SEM SINAL",
  "confianca": número de 0 a 100,
  "motivo": "curto (1 frase)"
}}

Contexto:
- Ativo: {ativo or "desconhecido"}
- Duração: {duracao} segundos
Regras:
- Se a confiança for < 75, usa "SEM SINAL".
- NÃO devolvas markdown. Apenas JSON.
""".strip()

        # 3) chamada OpenAI (Responses API com input_image + image_url base64)
        client = OpenAI(api_key=OPENAI_API_KEY)

        resp = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
            # opcional: limita custo/saída
            max_output_tokens=200,
        )

        out_text = (resp.output_text or "").strip()

        data = _safe_json_parse(out_text)
        if not data:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "error": "Resposta inválida do serviço de IA (JSON não encontrado).",
                    "raw": out_text[:500],
                },
            )

        sinal = (data.get("sinal") or "").strip().upper()
        confianca = data.get("confianca")

        # normalizações
        if sinal not in {"COMPRA", "VENDA", "SEM SINAL"}:
            sinal = "SEM SINAL"

        try:
            confianca = int(float(confianca))
        except Exception:
            confianca = None

        if confianca is None:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "error": "Resposta inválida: confiança ausente.", "raw": data},
            )

        # aplica regra final
        if confianca < 75:
            sinal = "SEM SINAL"

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": confianca,
            "ativo": (ativo or "").upper(),
            "duracao_segundos": int(duracao),
            "motivo": (data.get("motivo") or "").strip(),
            "meta": {
                "filename": grafico.filename,
                "mime": mime,
                "model": MODEL,
            },
        }

    except Exception as e:
        # NUNCA devolver HTML — sempre JSON
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)},
        )
