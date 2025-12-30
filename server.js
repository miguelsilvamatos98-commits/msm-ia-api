// server.js
const express = require("express");
const cors = require("cors");
const multer = require("multer");
const OpenAI = require("openai");

const app = express();

// ✅ CORS: permite o teu site da Hostinger chamar a API
app.use(cors({
  origin: "*",
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type", "Authorization"],
}));

app.use(express.json({ limit: "2mb" }));

// Upload em memória (sem criar pasta uploads/)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 }, // 8MB
});

// Health check
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// Se alguém abrir no browser (GET), responde “Use POST”
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)",
  });
});

function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }

// POST real
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ ok:false, erro: "Falta o ficheiro. Envie form-data com chave: grafico" });
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return res.status(500).json({
        ok:false,
        erro: "OPENAI_API_KEY ausente no Render. Vai a: Service → Environment → Add Environment Variable.",
      });
    }

    const client = new OpenAI({ apiKey });

    const base64 = req.file.buffer.toString("base64");
    const mime = req.file.mimetype || "image/png";

    // Prompt “seguro” (não garante acertos — devolve leitura/estimativa)
    const system = `
És um assistente de leitura visual de gráficos (educacional).
Não garantas lucro nem certezas. Não dês instruções de “aposta”.
Devolve apenas um JSON válido com:
- sinal: "COMPRA" | "VENDA" | "NEUTRO"
- confianca: número inteiro 0-100
- resumo: frase curta (1 linha) a explicar o que foi visto.
Se a imagem não for um gráfico, devolve sinal "NEUTRO" e confianca baixa.
`.trim();

    const user = `
Analisa o screenshot do gráfico (candlesticks) e dá uma leitura educacional.
Foca: tendência curta, possível continuação/reversão, volatilidade, suporte/resistência visíveis.
Responde APENAS com JSON.
`.trim();

    // ✅ OpenAI Responses API (visão)
    const result = await client.responses.create({
      model: "gpt-4.1-mini", // bom custo/benefício para visão
      input: [
        { role: "system", content: system },
        {
          role: "user",
          content: [
            { type: "input_text", text: user },
            { type: "input_image", image_url: `data:${mime};base64,${base64}` },
          ],
        },
      ],
      temperature: 0.2,
    });

    const outText =
      (result.output_text && String(result.output_text)) ||
      "";

    // Tenta extrair JSON
    let data;
    try {
      data = JSON.parse(outText);
    } catch (e) {
      // fallback: tenta encontrar um bloco JSON dentro do texto
      const m = outText.match(/\{[\s\S]*\}/);
      if (m) data = JSON.parse(m[0]);
    }

    if (!data || typeof data !== "object") {
      return res.status(200).json({
        ok: true,
        sinal: "NEUTRO",
        confianca: 30,
        resumo: "Não foi possível extrair um JSON válido da análise.",
        raw: outText.slice(0, 600),
      });
    }

    const sinal = String(data.sinal || "NEUTRO").toUpperCase();
    const confianca = clamp(parseInt(data.confianca ?? 30, 10) || 30, 0, 100);
    const resumo = String(data.resumo || "").slice(0, 220);

    const sinalFinal = ["COMPRA","VENDA","NEUTRO"].includes(sinal) ? sinal : "NEUTRO";

    return res.json({
      ok: true,
      sinal: sinalFinal,
      confianca,
      resumo,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({
      ok:false,
      erro: "Erro interno na análise",
      detalhe: String(err?.message || err),
    });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log("MSM-IA-API a ouvir na porta", PORT));
