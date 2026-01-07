import express from "express";
import cors from "cors";
import multer from "multer";

const app = express();
app.use(cors({ origin: "*" }));

// multer em memória (buffer)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 } // 8MB
});

const PORT = process.env.PORT || 10000;
const AI_PYTHON_URL = (process.env.AI_PYTHON_URL || "").replace(/\/+$/, ""); // sem "/" no fim

app.get("/", (req, res) => {
  res.json({ ok: true, service: "msm-ia-api" });
});

app.get("/health", async (req, res) => {
  try {
    if (!AI_PYTHON_URL) return res.status(200).json({ ok: true, node: "ok", python: "missing AI_PYTHON_URL" });

    const r = await fetch(`${AI_PYTHON_URL}/`, { method: "GET" });
    const t = await r.text();
    res.status(200).json({ ok: true, node: "ok", python_status: r.status, python_body: t.slice(0, 200) });
  } catch (e) {
    res.status(200).json({ ok: true, node: "ok", python_error: String(e).slice(0, 200) });
  }
});

// recebe o print do teu site e envia para o Python
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!AI_PYTHON_URL) {
      return res.status(500).json({ ok: false, error: "AI_PYTHON_URL não configurado no Node (Render)." });
    }

    if (!req.file || !req.file.buffer) {
      return res.status(400).json({ ok: false, error: "Ficheiro 'grafico' em falta." });
    }

    const ativo = (req.body.ativo || "EURUSD").toString();
    const duracao = (req.body.duracao || "90").toString();

    // Node 22 tem FormData/Blob/File nativos
    const fd = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype || "image/png" });
    const filename = req.file.originalname || "grafico.png";

    fd.append("grafico", blob, filename);
    fd.append("ativo", ativo);
    fd.append("duracao", duracao);

    const r = await fetch(`${AI_PYTHON_URL}/predict`, {
      method: "POST",
      body: fd
    });

    const text = await r.text();

    // tenta JSON
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return res.status(502).json({
        ok: false,
        error: "Resposta não-JSON do serviço Python",
        details: text.slice(0, 250)
      });
    }

    // devolve exatamente o que veio do Python
    return res.status(200).json(data);

  } catch (e) {
    return res.status(500).json({ ok: false, error: "Erro no Node ao encaminhar para Python.", details: String(e).slice(0, 250) });
  }
});

app.listen(PORT, () => {
  console.log(`✅ Node API a correr na porta ${PORT}`);
  console.log(`➡️ AI_PYTHON_URL=${AI_PYTHON_URL || "(vazio)"}`);
});
