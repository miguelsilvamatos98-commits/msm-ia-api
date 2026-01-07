import os
import base64
import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

app = FastAPI(title="AI Python", version="1.0.0")

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
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "erro": "OPENAI_API_KEY em falta no serviço Python."}

    # ler imagem
    try:
        img_bytes = await grafico.read()
        mime = grafico.content_type or "image/png"
        data_url = _to_data_url(img_bytes, mime)
    except Exception as e:
        return {"ok": False, "erro": "Falha ao ler imagem", "details": str(e)}

    ativo_txt = (ativo or "").strip()

    # prompt (força JSON)
    prompt = (
        "Analisa a imagem do gráfico (candlesticks) para opções binárias.\n"
        "Responde APENAS com um JSON válido (sem texto extra) exatamente neste formato:\n"
        "{\n"
        '  "sinal": "COMPRA|VENDA|SEM SINAL",\n'
        '  "confianca": 0-100,\n'
        '  "motivo": "curto"\n'
        "}\n"
        f"Ativo: {ativo_txt}\n"
        f"Duração (segundos): {duracao}\n"
        "Regras:\n"
        "- Se não houver padrão claro, usa SEM SINAL.\n"
        "- 'confianca' tem de ser inteiro.\n"
    )

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
            max_output_tokens=220,
        )

        text = (getattr(r, "output_text", "") or "").strip()
        if not text:
            return {"ok": False, "erro": "Resposta vazia do modelo."}

        # tenta interpretar JSON (mesmo se vier com lixo)
        parsed = None
        try:
            parsed = json.loads(text)
        except:
            # fallback: tenta extrair o primeiro bloco JSON dentro do texto
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(text[start:end+1])
                except:
                    parsed = None

        if not isinstance(parsed, dict):
            return {"ok": False, "erro": "Modelo não devolveu JSON válido.", "raw": text}

        sinal = str(parsed.get("sinal", "")).upper().strip()
        conf = parsed.get("confianca", None)
        motivo = str(parsed.get("motivo", "")).strip()

        try:
            conf_int = int(round(float(conf)))
        except:
            return {"ok": False, "erro": "JSON inválido: confiança ausente/ inválida.", "raw": text}

        if sinal not in ["COMPRA", "VENDA", "SEM SINAL"]:
            # normaliza se vier algo estranho
            sinal = "SEM SINAL"

        conf_int = max(0, min(100, conf_int))

        return {
            "ok": True,
            "sinal": sinal,
            "confianca": conf_int,
            "motivo": motivo[:220],
            "ativo": ativo_txt,
            "duracao_segundos": int(duracao),
        }

    except Exception as e:
        return {"ok": False, "erro": "Erro ao comunicar com a IA.", "details": str(e)}
