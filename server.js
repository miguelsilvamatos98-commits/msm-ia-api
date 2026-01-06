// server.js (ESM) - MSM-IA-API
import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();
const PORT = process.env.PORT || 10000;

import cors from "cors";

const allowedOrigins = [
  "https://darkturquoise-stork-767325.hostingersite.com",
  "https://tradespeedpro.click",
  "http://localhost:5500"
];

app.use(cors({
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error("CORS bloqueado"));
    }
  }
}));
;

app.set("trust proxy", 1);

// ========= Upload =========
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 }, // 8MB
});

// ========= OpenAI =========
const apiKey = (process.env.OPENAI_API_KEY || "").trim();
const client = apiKey ? new OpenAI({ apiKey }) : null;

// Modelo (podes trocar no Render com env OPENAI_VISION_MODEL)
const VISION_MODEL = process.env.OPENAI_VISION_MODEL || "gpt-4o-mini";

// ========= Rotas =========
app.get("/", (req, res) => {
  res.json({
    ok: true,
    service: "MSM-IA-API",
    endpoints: ["GET /health", "POST /api/analisar-grafico (form-data: grafico)"],
  });
});

app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// Se abrirem no browser:
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)",
  });
});

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    // Obrigatório: imagem
    if (!req.file) {
      return res.status(400).json({
        erro: "Envie a imagem em form-data com o campo 'grafico'",
        exemplo: "POST /api/analisar-grafico (form-data: grafico=image)",
      });
    }

    // Obrigatório: API key (IA real)
    if (!client) {
      return res.status(500).json({
        erro: "OPENAI_API_KEY não configurada no servidor (Render)",
      });
    }

    // Base64 data URL
    const mime = req.file.mimetype || "image/png";
    const b64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${b64}`;

    // Prompt ajustado por ativo + duração fixa 90s
    const prompt = `
Você é um analista técnico especializado em opções binárias com expiração fixa de 1 minuto e 30 segundos (90s).

Tarefa:
1) Identifique o tipo de ativo visível no print: "FOREX" ou "CRIPTO".
  - FOREX (EUR/USD, GBP/USD, etc.): priorize reversões em suporte/resistência e rejeições (pavios).
  - CRIPTO (BTC, ETH, etc.): considere maior volatilidade; reduza confiança em spikes e valorize momentum/continuação.

2) Analise APENAS o que está visível no gráfico (candlesticks, de preferência M1):
  - micro-tendência (últimos 10-20 candles)
  - suporte/resistência visíveis
  - rejeição (pavios), força do corpo, possível exaustão
  - volatilidade/spikes

3) Objetivo: escolher a direção MAIS PROVÁVEL para os PRÓXIMOS 90 segundos.

Regras obrigatórias:
- Nunca use "NEUTRO"
- Sempre escolha "COMPRA" ou "VENDA"
- Se estiver incerto, escolha o lado mais provável e reduza a confiança
- Responda SOMENTE com JSON válido (sem texto extra)

Formato exato:
{
  "ativo_tipo": "FOREX" ou "CRIPTO",
  "sinal": "COMPRA" ou "VENDA",
  "duracao_segundos": 90,
  "confianca": 0-100
}
`.trim();

    // Chamada OpenAI (visão)
    const response = await client.responses.create({
      model: VISION_MODEL,
      input: [
        {
          role: "user",
          content: [
            { type: "input_text", text: prompt },
            { type: "input_image", image_url: dataUrl },
          ],
        },
      ],
    });

    const out = String(response.output_text || "").trim();

    // Extrair JSON
    let parsed;
    try {
      parsed = JSON.parse(out);
    } catch {
      const m = out.match(/\{[\s\S]*\}/);
      if (!m) throw new Error("A IA não devolveu JSON válido.");
      parsed = JSON.parse(m[0]);
    }

    // Normalizar
    const sinal = String(parsed.sinal || "").trim().toUpperCase();
    const ativo_tipo = String(parsed.ativo_tipo || "").trim().toUpperCase();
    let confianca = Number(parsed.confianca);

    // Regras: só COMPRA/VENDA
    if (sinal !== "COMPRA" && sinal !== "VENDA") {
      throw new Error("Sinal inválido retornado pela IA.");
    }
    if (ativo_tipo !== "FOREX" && ativo_tipo !== "CRIPTO") {
      // se não veio, define pelo menos algo
      // (mas não inventa sinal; só classifica)
      // aqui deixamos "FOREX" por padrão
    }
    if (!Number.isFinite(confianca)) confianca = 70;
    confianca = Math.max(0, Math.min(100, Math.round(confianca)));

    return res.json({
      ativo_tipo: (ativo_tipo === "FOREX" || ativo_tipo === "CRIPTO") ? ativo_tipo : "FOREX",
      sinal,
      duracao_segundos: 90,
      confianca,
    });
  } catch (err) {
    const msg = String(err?.message || err);

    // Quota / billing
    if (msg.includes("429") || msg.toLowerCase().includes("insufficient_quota")) {
      return res.status(429).json({
        erro: "Sem quota/créditos na OpenAI API (billing).",
        detalhe: "Ativa billing/uso na tua organização da OpenAI API e tenta novamente.",
      });
    }

    console.error("ERRO /api/analisar-grafico:", err);
    return res.status(500).json({ erro: "Falha na análise.", detalhe: msg });
  }
});

app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});

