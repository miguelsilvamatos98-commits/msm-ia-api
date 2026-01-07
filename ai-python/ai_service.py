import os
import json
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from PIL import Image
import io

from openai import OpenAI

app = FastAPI(title="trade-speed-ai-python", version="0.1.0")

# CORS (podes restringir depois ao teu domínio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _safe_int(v, default: int):
    try:
        return int(v)
    except Exception:
        return default

def _clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def _normalize_signal(s: str) -> str:
    s = (s or "").strip().upper()
    if "COMPRA" in s:
        return "COMPRA"
    if "VENDA" in s:
        return "VENDA"
    if "SEM" in s:
        return "SEM SINAL"
    return "SEM SINAL"

def _extract_json(text: str) -> Optional[dict]:
    """
    Tenta extrair JSON mesmo que o modelo escreva texto extra.
    """
    if not text:
        return None
    text = text.strip()

    # caso já seja JSON puro
    try:
        return json.loads(text)
    except Exception:
        pass

    # tenta localizar o primeiro {...} completo
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None

    return None

@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: str = Form("90"),
):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": "OPENAI_API_KEY em falta no serviço Python."},
        )

    # ler imagem
    try:
        raw = await grafico.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": "Não foi possível ler o ficheiro de imagem."},
        )

    # opcional: reduzir tamanho (mais rápido/barato)
    try:
        max_w = 1280
        if img.width > max_w:
            ratio = max_w / float(img.width)
            new_h = int(img.height * ratio)
            img = img.resize((max_w, new_h))
    except Exception:
        pass

    # re-encode PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    dur_s = _clamp(_safe_int(duracao, 90), 30, 300)
    ativo_norm = (ativo or "EURUSD").strip().upper()

    client = OpenAI(api_key=api_key)

    # IMPORTANTE:
    # - Não dá para garantir “dizer exatamente o que vai acontecer”.
    # - Aqui a IA só faz leitura do print e devolve sinal com confiança.
    # - Para não ficar sempre 60%, pedimos escala + justificativa curta e forçamos JSON.
    prompt = f"""
Vais analisar um PRINT do Pocket Option (gráfico de candles).
Objetivo: devolver um JSON ESTRITO (sem texto fora do JSON) com:
- ok: true
- sinal: "COMPRA" ou "VENDA" ou "SEM SINAL"
- confianca: inteiro 0-100 (não uses sempre 60; usa a escala completa)
- ativo: "{ativo_norm}"
- duracao_segundos: {dur_s}
- motivo_curto: string curta (máx 120 caracteres) explicando o porquê

Regras:
- Se o print estiver desfocado, cortado, ou sem contexto suficiente -> sinal = "SEM SINAL" e confiança <= 55.
- Só dá "COMPRA" ou "VENDA" se houver um padrão razoável (tendência + pullback / suporte-resistência / rejeição).
- A resposta TEM de ser JSON válido. Nada de markdown.
"""

    try:
        # Responses API com imagem (vision)
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_data": png_bytes,  # SDK aceita bytes
                        },
                    ],
                }
            ],
        )

        # texto de saída
        out_text = ""
        try:
            out_text = resp.output_text
        except Exception:
            # fallback
            out_text = str(resp)

        data = _extract_json(out_text)
        if not isinstance(data, dict):
            return JSONResponse(
                status_code=200,
                content={"ok": False, "error": "Resposta inválida do modelo (não veio JSON).", "raw": out_text[:400]},
            )

        sinal = _normalize_signal(str(data.get("sinal", "")))
        conf = _clamp(_safe_int(data.get("confianca", 50), 50), 0, 100)
        motivo = str(data.get("motivo_curto", "")).strip()[:120]

        # regra extra: se SEM SINAL, baixa teto de confiança
        if sinal == "SEM SINAL":
            conf = min(conf, 55)

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": conf,
            "ativo": ativo_norm,
            "duracao_segundos": dur_s,
            "motivo_curto": motivo,
        }

    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": "Erro ao comunicar com a IA.", "details": str(e)[:300]},
        )
