import express from "express";
import cors from "cors";
import multer from "multer";
import fetch from "node-fetch";
import FormData from "form-data";

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

app.use(cors());

// URL do serviço Python (vem do Render ENV)
const AI_PYTHON_URL = process.env.AI_PYTHON_URL;

if (!AI_PYTHON_URL) {
  console.warn("⚠️ AI_PYTHON_URL não definida nas variáveis de ambiente");
}

app.get("/", (req, res) => {
  res.json({ ok: true, service: "trade-speed-node" });
});

// 🔥 ENDPOINT PRINCIPAL
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ ok: false, erro: "Ficheiro 'grafico' não enviado." });
    }

    const ativo = req.body.ativo || "EURUSD";
    const duracao = req.body.duracao || "90";

    // preparar form para o Python
    const form = new FormData();
    form.append("grafico", req.file.buffer, {
      filename: req.file.originalname || "grafico.png",
      contentType: req.file.mimetype || "image/png",
    });
    form.append("ativo", ativo);
    form.append("duracao", duracao);

    // chamar serviço Python
    const resp = await fetch(AI_PYTHON_URL, {
      method: "POST",
      body: form,
      headers: form.getHeaders(),
    });

    let data;
    try {
      data = await resp.json();
    } catch {
      throw new Error("Resposta inválida do serviço de IA");
    }

    if (!resp.ok) {
      return res.status(resp.status).json({
        ok: false,
        erro: data?.erro || "Erro no serviço de IA",
      });
    }

    // devolver direto ao frontend
    return res.json(data);

  } catch (err) {
    console.error(err);
    return res.status(500).json({
      ok: false,
      erro: err.message || "Erro interno",
    });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("✅ Node API a correr na porta", PORT);
});
