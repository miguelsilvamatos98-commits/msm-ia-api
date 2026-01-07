import express from "express";
import cors from "cors";
import multer from "multer";

const app = express();
app.use(cors());

const upload = multer({ storage: multer.memoryStorage() });

const PORT = process.env.PORT || 10000;

// URL do serviço Python (Render)
const AI_PYTHON_URL = process.env.AI_PYTHON_URL; // ex: https://trade-speed-ai-python.onrender.com

app.get("/", (req, res) => {
  res.json({ ok: true, service: "msm-ia-api-node" });
});

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!AI_PYTHON_URL) {
      return res.status(500).json({ ok: false, error: "AI_PYTHON_URL não definido no Render (Node)." });
    }

    if (!req.file) {
      return res.status(400).json({ ok: false, error: "Ficheiro 'grafico' em falta." });
    }

    const ativo = (req.body.ativo || "").toString();
    const duracao = (req.body.duracao || "90").toString();

    // Node 18+ tem fetch/FormData/Blob globais
    const form = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype || "image/jpeg" });

    form.append("grafico", blob, req.file.originalname || "grafico.jpg");
    form.append("ativo", ativo);
    form.append("duracao", duracao);

    const url = `${AI_PYTHON_URL.replace(/\/$/, "")}/predict`;

    const resp = await fetch(url, {
      method: "POST",
      body: form,
    });

    const contentType = resp.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const raw = await resp.text();
      return res.status(502).json({
        ok: false,
        error: "Resposta inválida do serviço Python (não é JSON).",
        details: raw.slice(0, 400),
      });
    }

    const data = await resp.json();

    // devolve ao front exatamente o JSON padronizado
    if (!data?.ok) {
      return res.status(502).json(data);
    }

    return res.json(data);
  } catch (e) {
    return res.status(500).json({
      ok: false,
      error: "Erro ao comunicar com a IA",
      details: String(e?.message || e),
    });
  }
});

app.listen(PORT, () => {
  console.log(`✅ Node API a correr na porta ${PORT}`);
});
