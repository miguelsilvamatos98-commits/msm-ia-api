import os
import io
import hashlib
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from PIL import Image


APP_NAME = "trade-speed-ai-python"

app = FastAPI(title="Trade Speed AI (Python)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # se quiseres, depois restringimos ao teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"ok": True, "service": APP_NAME}


@app.get("/health")
def health():
    return {"ok": True}


def _safe_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


def _compute_image_fingerprint(img_bytes: bytes) -> str:
    """Fingerprint simples para debug (não é para segurança)."""
    return hashlib.sha256(img_bytes).hexdigest()[:16]


def _basic_quality_checks(img: Image.Image) -> dict:
    """
    Checks básicos para prints Pocket Option:
    - resolução mínima
    - formato
    - modo (RGB)
    """
    w, h = img.size
    issues = []
    if w < 900 or h < 450:
        issues.append("Imagem pequena. Usa print em ecrã cheio (ideal >= 1280x720).")
    if img.mode not in ("RGB", "RGBA"):
        issues.append(f"Modo de cor incomum: {img.mode}")
    return {"width": w, "height": h, "issues": issues}


def _placeholder_predict(img: Image.Image, ativo: str, duracao: int) -> dict:
    """
    Placeholder (base) — aqui é onde vais evoluir a IA.
    Por agora devolve SEM SINAL / 60.
    """
    # Podes futuramente:
    # - cortar a área do gráfico
    # - detetar velas (vermelho/verde)
    # - detetar direção e força
    # - alimentar modelo
    return {
        "ok": True,
        "sinal": "SEM SINAL",
        "confianca": 60,
        "ativo": ativo,
        "duracao_segundos": duracao
    }


@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: str = Form("90"),
):
    """
    Recebe:
      - grafico: UploadFile (imagem)
      - ativo: string
      - duracao: segundos (string -> int)
    Retorna JSON:
      { ok, sinal, confianca, ativo, duracao_segundos }
    """
    try:
        # Lê bytes do ficheiro
        img_bytes = await grafico.read()
        if not img_bytes:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Ficheiro vazio"})

        # debug fingerprint
        fp = _compute_image_fingerprint(img_bytes)

        # abre imagem
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img.load()
        except Exception:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Ficheiro não é uma imagem válida"})

        dur = _safe_int(duracao, 90)

        # checks básicos
        quality = _basic_quality_checks(img)

        # placeholder de previsão
        result = _placeholder_predict(img, ativo, dur)

        # adiciona metadados úteis (podes remover depois)
        result["meta"] = {
            "filename": grafico.filename,
            "content_type": grafico.content_type,
            "fingerprint": fp,
            "width": quality["width"],
            "height": quality["height"],
            "issues": quality["issues"],
        }

        return result

    except Exception as e:
        # SEMPRE JSON, nunca HTML
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Erro interno no predict", "details": str(e)},
        )
