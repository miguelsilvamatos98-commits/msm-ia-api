import express from "express";
import cors from "cors";
import multer from "multer";

const app = express();
app.use(cors({ origin: "*"}));

const upload = multer({ storage: multer.memoryStorage() });

const AI_PYTHON_URL = process.env.AI_PYTHON_URL; // ex: https://trade-speed-ai-python.onrender.com
if (!AI_PYTHON_URL) {
  console.error("FALTA AI_PYTHON_URL no ambiente do Node.");
}

app.get("/", (req, res) => res.json({ ok: true, service: "msm-ia-api" }));

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!AI_PYTHON_URL) {
      return res.status(500).json({ ok: false, error: "AI_PYTHON_URL não definido no Node." });
    }
    if (!req.file) {
      return res.status(400).json({ ok: false, error: "Ficheiro 'grafico' em falta." });
    }

    const ativo = (req.body?.ativo || "").toString();
    const duracao = parseInt(req.body?.duracao || "90", 10);

    // FormData global (Node 18+ / 20+ / 22+)
    const form = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype || "image/png" });
    form.append("grafico", blob, req.file.originalname || "grafico.png");
    form.append("ativo", ativo);
    form.append("duracao", String(Number.isFinite(duracao) ? duracao : 90));

    const url = `${AI_PYTHON_URL.replace(/\/$/, "")}/predict`;

    const r = await fetch(url, { method: "POST", body: form });
    const data = await r.json().catch(() => null);

    if (!r.ok || !data) {
      return res.status(502).json({
        ok: false,
        error: "Falha ao chamar serviço Python",
        status: r.status,
        details: data || "Resposta não-JSON do Python",
      });
    }

    // O Python devolve {ok:true, raw:"{...json...}"}
    if (!data.ok) {
      return res.status(500).json(data);
    }

    // Tentar extrair JSON do raw
    let parsed = null;
    try {
      parsed = JSON.parse(data.raw);
    } catch {
      // se vier algo não-JSON, devolve como raw
      return res.json({ ok: true, raw: data.raw });
    }

    // Normalizar saída final que o teu frontend espera
    const sinal = (parsed.sinal || "SEM SINAL").toString().toUpperCase();
    const confianca = Number(parsed.confianca ?? 0);

    return res.json({
      ok: true,
      sinal,
      confianca: Number.isFinite(confianca) ? confianca : 0,
      motivo: parsed.motivo || "",
      ativo,
      duracao_segundos: Number.isFinite(duracao) ? duracao : 90,
    });

  } catch (e) {
    return res.status(500).json({ ok: false, error: "Erro interno no Node", details: String(e) });
  }
});

const port = process.env.PORT || 10000;
app.listen(port, () => console.log("Node API a correr na porta", port));
