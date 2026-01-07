import express from "express";
import multer from "multer";
import fetch from "node-fetch";
import FormData from "form-data";
import cors from "cors";

const app = express();
const upload = multer();

app.use(cors());

const AI_URL = process.env.AI_PYTHON_URL;

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "Imagem não enviada" });
    }

    const formData = new FormData();
    formData.append("grafico", req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });
    formData.append("ativo", req.body.ativo || "EURUSD");
    formData.append("duracao", req.body.duracao || "90");

    const resp = await fetch(AI_URL, {
      method: "POST",
      body: formData,
      headers: formData.getHeaders(),
    });

    const data = await resp.json();

    return res.json(data);
  } catch (err) {
    console.error(err);
    return res.status(500).json({
      error: "Erro ao comunicar com a IA",
      details: err.message,
    });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("✅ Node API a correr na porta", PORT);
});

