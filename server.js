// server.js (CommonJS) - MSM-IA-API
const express = require("express");
const multer = require("multer");
const cors = require("cors");
const OpenAI = require("openai");

const app = express();

// ✅ CORS (podes deixar "*" para teste; em produção mete o teu domínio)
app.use(cors({ origin: "*" }));

// ✅ Upload em memória (não grava em disco)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
});

// ✅ Health check
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// ✅ GET no endpoint de análise: explica que é POST
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)",
  });
});

// ✅ POST: recebe imagem e envia para OpenAI (vision)
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    // 1) validações
    if (!req.file) {
      return res.status(400).json({ erro: "Falta o ficheiro", campo: "grafico" });
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return res.status(500).json({
        erro: "OPENAI_API_KEY ausente no Render (Environment Variables).",
      });
    }

    // 2) prepara imagem
    const mime = req.file.mimetype || "image/png";
    const base64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${base64}`;

    // 3) cliente OpenAI
    const client = new OpenAI({ apiKey });

    // 4) prompt (ajusta ao teu gosto)
    const prompt = `
Analisa o screenshot de um gráfico (candlesticks) de opções binárias.
Responde APENAS em JSON com:
{
  "sinal": "COMPRA" | "VENDA" | "NEUTRO",
  "confianca": number, 
  "motivo": string
}
- confianca de 0 a 100
- se a imagem estiver confusa, usa NEUTRO com baixa confiança.
`;

    // 5) chamada vision
    const response = await client.chat.completions.create({
      model: "gpt-4.1-mini",
      temperature: 0.2,
      messages: [
        { role: "system", content: "Responde sempre em JSON válido, sem texto extra." },
        {
          role: "user",
          content: [
            { type: "text", text: prompt.trim() },
            { type: "image_url", image_url: { url: dataUrl } },
          ],
        },
      ],
      response_format: { type: "json_object" },
    });

    // 6) parse seguro
    const content = response?.choices?.[0]?.message?.content || "{}";
    let json;
    try {
      json = JSON.parse(content);
    } catch {
      json = { sinal: "NEUTRO", confianca: 10, motivo: "Resposta inválida do modelo." };
    }

    // 7) normaliza
    const sinal = (json.sinal || "NEUTRO").toString().toUpperCase();
    const confianca = Number.isFinite(Number(json.confianca)) ? Number(json.confianca) : 0;
    const motivo = (json.motivo || "").toString();

    return res.json({
      sinal: ["COMPRA", "VENDA", "NEUTRO"].includes(sinal) ? sinal : "NEUTRO",
      confianca: Math.max(0, Math.min(100, confianca)),
      motivo,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({
      erro: "Erro interno na análise",
      detalhe: err?.message || String(err),
    });
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log("MSM-IA-API a correr na porta", port));
