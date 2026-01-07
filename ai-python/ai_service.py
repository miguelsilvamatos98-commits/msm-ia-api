from fastapi import FastAPI, UploadFile, File, Form

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "service": "ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: int = Form(90),
):
    return {
        "ok": True,
        "sinal": "SEM_SINAL",
        "confianca": 55,
        "ativo": ativo,
        "duracao_segundos": duracao
    }
