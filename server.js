import express from "express";
import multer from "multer";
import cors from "cors";
import fetch from "node-fetch";
import FormData from "form-data";

const app = express();
const upload = multer();

app.use(cors());

const AI_URL = process.env.AI_PYTHON_URL; // ex: https://trade-speed-ai-python.onrender.com/predict

app.get("/", (req, res) => res.json({ ok: true, service: "msm-ia-api" }));
app.get("/health", (req, res) => res.json({ ok: true }));

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!AI_URL) {
      return res.status(500).json({
        error: "AI_PYTHON_URL não está definido no Environment do Render (Node).",
      });
    }

    if (!req.file) {
      return res.status(400).json({ error: "Imagem não enviada (campo: grafico)" });
    }

    const ativo = req.body.ativo || "EURUSD";
    const duracao = req.body.duracao || "90";

    // Cria multipart para enviar ao Python
    const formData = new FormData();
    formData.append("grafico", req.file.buffer, {
      filename: req.file.originalname || "grafico.png",
      contentType: req.file.mimetype || "image/png",
    });
    formData.append("ativo", ativo);
    formData.append("duracao", duracao);

    const resp = await fetch(AI_URL, {
      method: "POST",
      body: formData,
      headers: formData.getHeaders(),
    });

    // Lê texto e tenta JSON (para nunca dar "Unexpected token <")
    const text = await resp.text();

    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return res.status(502).json({
        error: "Python não devolveu JSON (provavelmente devolveu HTML/erro).",
        status: resp.status,
        details: text.slice(0, 300),
      });
    }

    // Se Python devolveu erro mas em JSON
    if (!resp.ok) {
      return res.status(resp.status).json(data);
    }

    return res.json(data);
  } catch (err) {
    console.error("❌ Erro no Node:", err);
    return res.status(500).json({ error: "Erro no Node", details: err.message });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log("✅ msm-ia-api a correr na porta", PORT));
