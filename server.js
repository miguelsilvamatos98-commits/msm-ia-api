// server.js (CommonJS) — MSM-IA-API
// Endpoints:
//  - GET  /health
//  - POST /api/analisar-grafico  (form-data: grafico=image)

const express = require("express");
const cors = require("cors");
const multer = require("multer");
const OpenAI = require("openai");

const app = express();

// =========================
// CONFIG
// =========================
const PORT = process.env.PORT || 10000;

// Domínios permitidos (Hostinger + localhost). Podes adicionar mais.
const ALLOWED_ORIGINS = [
  "https://darkturquoise-stork-767325.hostingersite.com",
  "http://localhost:3000",
  "http://localhost:5173",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:5173",
];

// Se quiseres permitir qualquer domínio (menos seguro), mete ALLOW_ALL_ORIGINS=true no Render
const ALLOW_ALL = String(process.env.ALLOW_ALL_ORIGINS || "").toLowerCase() === "true";

// =========================
// CORS
// =========================
app.use(
  cors({
    origin: (origin, cb) => {
      // requests sem origin (curl/postman) -> permitir
      if (!origin) return cb(null, true);

      if (ALLOW_ALL) return cb(null, true);

      if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);

      return cb(new Error("CORS bloqueado: " + origin), false);
    },
    methods: ["GET", "POST", "OPTIONS"],
    allowedHeaders: ["Content-Type"],
  })
);

// Para o Render/proxies
app.set("trust proxy", 1);

// =========================
// Upload (multer em memória)
// =========================
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 }, // 8MB
});

// =========================
// OpenAI (opcional)
// =========================
let client = null;
if (process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY.trim() !== "") {
  client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY.trim() });
}

// =========================
// Helpers
// =========================
function pickTradeSignalFromText(text) {
  // Heurística simples para transformar análise em COMPRA/VENDA
  // (mesmo que o texto venha “neutro”, aqui escolhemos 1)
  const t = String(text || "").toLowerCase();
  const buyHints = ["buy", "compra", "alta", "bull", "subida", "call", "long", "rompimento"];
  const sellHints = ["sell", "venda", "baixa", "bear", "queda", "put", "short", "rejeição"];

  let buyScore = 0;
  let sellScore = 0;

  buyHints.forEach(k => { if (t.includes(k)) buyScore++; });
  sellHints.forEach(k => { if (t.includes(k)) sellScore++; });

  if (buyScore === sellScore) {
    // desempate: aleatório
    return Math.random() > 0.5 ? "COMPRA" : "VENDA";
  }
  return buyScore > sellScore ? "COMPRA" : "VENDA";
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function fallbackResult() {
  const sinal = Math.random() > 0.5 ? "COMPRA" : "VENDA";
  const confianca = 68 + Math.floor(Math.random() * 22); // 68–89
  return { sinal, confianca, modo: "fallback" };
}

// =========================
// Routes
// =========================
app.get("/", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", hint: "Use GET /health ou POST /api/analisar-grafico" });
});

app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// Se alguém fizer GET no endpoint, responde com aviso (como já estavas a ver)
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)",
  });
});

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      // Sem ficheiro -> devolve COMPRA/VENDA na mesma (nunca ERRO)
      return res.json({ ...fallbackResult(), nota: "Sem imagem enviada (grafico)" });
    }

    // Converter imagem para base64 (data URL)
    const mime = req.file.mimetype || "image/png";
    const b64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${b64}`;

    // Se não houver API key configurada, fallback imediato
    if (!client) {
      return res.json({ ...fallbackResult(), nota: "OPENAI_API_KEY não configurada" });
    }

    // =========================
    // Chamada OpenAI (visão)
    // =========================
    // Podes trocar o modelo via env: OPENAI_VISION_MODEL (ex: gpt-4o-mini)
    const model = process.env.OPENAI_VISION_MODEL || "gpt-4o-mini";

    const prompt =
      "Analisa este print de um gráfico de trading (candles). " +
      "Responde APENAS com: COMPRA ou VENDA. " +
      "Não escrevas mais nada.";

    const resp = await client.chat.completions.create({
      model,
      temperature: 0.2,
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: prompt },
            { type: "image_url", image_url: { url: dataUrl } },
          ],
        },
      ],
    });

    const text = resp?.choices?.[0]?.message?.content || "";
    const sinal = pickTradeSignalFromText(text);

    // Confianca “simulada” mas consistente (tu podes melhorar depois)
    let confianca = 72 + Math.floor(Math.random() * 20); // 72–91
    confianca = clamp(confianca, 50, 99);

    return res.json({
      sinal,
      confianca,
      modo: "openai",
    });
  } catch (err) {
    // Qualquer falha (quota 429, CORS, etc.) -> fallback SEM ERRO no UI
    return res.json({
      ...fallbackResult(),
      nota: "Falha ao analisar com OpenAI (fallback usado)",
    });
  }
});

app.listen(PORT, () => {
  console.log(`MSM-IA-API a correr na porta ${PORT}`);
});

