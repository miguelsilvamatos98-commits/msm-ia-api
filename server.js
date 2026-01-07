// server.js
import express from "express";
import cors from "cors";
import multer from "multer";

const app = express();

// CORS (podes apertar depois para só o teu domínio)
app.use(cors({ origin: "*", methods: ["GET", "POST", "OPTIONS"] }));

// Upload em memória
const upload = multer({ storage: multer.memoryStorage() });

// URL do serviço Python
const AI_PYTHON_URL =
  (process.env.AI_PYTHON_URL || "https://trade-speed-ai-python.onrender.com").replace(/\/$/, "");

const PY_ENDPOINT = `${AI_PYTHON_URL}/predict`;

// Health check
app.get("/", (req, res) => {
  res.json({ ok: true, service: "msm-ia-api", python: AI_PYTHON_URL });
});

// Endpoint do teu front
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ ok: false, erro: "Falta o ficheiro 'grafico'." });
    }

    const ativo = (req.body?.ativo || "EURUSD").toString();
    const duracao = (req.body?.duracao || "90").toString();

    // FormData multipart para enviar ao Python
    const form = new FormData();

    // Buffer -> Blob (compatível com fetch/FormData nativos)
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype || "image/png" });

    // nome do campo tem de ser "grafico" (igual ao FastAPI)
    form.append("grafico", blob, req.file.originalname || "grafico.png");
    form.append("ativo", ativo);
    form.append("duracao", duracao);

    // Timeout (evita ficar preso)
    const controller = new AbortController();
    const timeoutMs = Number(process.env.PY_TIMEOUT_MS || 60000);
    const t = setTimeout(() => controller.abort(), timeoutMs);

    const resp = await fetch(PY_ENDPOINT, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });

    clearTimeout(t);

    // tenta sempre JSON
    let data = null;
    try {
      data = await resp.json();
    } catch {
      const text = await resp.text().catch(() => "");
      return res.status(502).json({
        ok: false,
        erro: "Resposta inválida do serviço Python (não é JSON).",
        details: text?.slice(0, 500) || `HTTP ${resp.status}`,
      });
    }

    // Se Python devolveu ok=false, manda na mesma para o front
    if (!resp.ok) {
      return res.status(502).json({
        ok: false,
        erro: "Erro do serviço Python.",
        details: data,
      });
    }

    // Normaliza campos para o teu HTML
    // Esperado do Python: { ok:true, sinal, confianca, ativo, duracao_segundos }
    if (!data || data.ok !== true) {
      return res.status(200).json({
        ok: false,
        erro: data?.error || "Erro ao comunicar com a IA.",
        details: data?.details || data,
      });
    }

    return res.status(200).json({
      ok: true,
      sinal: data.sinal,
      confianca: data.confianca,
      ativo: data.ativo || ativo,
      duracao_segundos: data.duracao_segundos || Number(duracao),
      meta: data.meta || null,
    });
  } catch (e) {
    const msg =
      e?.name === "AbortError"
        ? "Timeout ao comunicar com o serviço Python."
        : (e?.message || "Erro desconhecido");

    return res.status(500).json({ ok: false, erro: "Erro no servidor Node.", details: msg });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ msm-ia-api a correr em http://0.0.0.0:${PORT}`);
  console.log(`➡️ Python: ${PY_ENDPOINT}`);
});
