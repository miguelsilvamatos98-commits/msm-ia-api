from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import torch
import torch.nn.functional as F
import timm
from torchvision import transforms

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LABELS = ["COMPRA", "VENDA", "SEM_SINAL"]
MODEL_PATH = "pocket_model_best.pt"

device = "cuda" if torch.cuda.is_available() else "cpu"

model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=3)

# ⚠️ por agora NÃO carrega modelo (para não dar erro)
# model.load_state_dict(torch.load(MODEL_PATH, map_location=device))

model.eval().to(device)

tf = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.ToTensor(),
    transforms.Normalize(mean=(0.485,0.456,0.406), std=(0.229,0.224,0.225)),
])

def crop_chart(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.crop((0, int(0.12*h), int(0.78*w), int(0.95*h)))

@app.get("/")
def health():
    return {"ok": True, "service": "ai-python"}

@app.post("/predict")
async def predict(
    grafico: UploadFile = File(...),
    ativo: str = Form("EURUSD"),
    duracao: int = Form(90),
):
    # ⚠️ TEMPORÁRIO: confiança simulada variável
    import random

    fake_conf = random.randint(45, 85)
    sinal = "COMPRA" if fake_conf >= 60 else "SEM_SINAL"

    return {
        "ok": True,
        "sinal": sinal,
        "confianca": fake_conf,
        "ativo": ativo,
        "duracao_segundos": duracao
    }
