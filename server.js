import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 8 * 1024 * 1024 } });

// ====== CONFIG ======
const PORT = process.env.PORT || 10000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";

// Origem permitida (mete o teu domínio da Hostinger aqui como env)
// Ex: https://darkturquoise-stork-767325.hostingersite.com
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || "*")
  .split(",")
  .map(s => s.trim())
  .filter(Boolean);

// ====== CORS ======
app.use(cors({
  origin: (origin, cb) => {
    if (!origin) return cb(null, true); // Postman/cURL
    if (ALLOWED_ORIGINS.includes("*")) return cb(null, true);
    if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
    return cb(new Error("CORS bloqueado: " + origin));
  }
}));

// ====== STATIC SITE ======
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Serve /public como site
app.use(express.static(path.join(__dirname, "public")));

// Home
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

// Health
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// ====== OPENAI CLIENT ======
const client = new OpenAI({ apiKey: OPENAI_API_KEY });

// ====== API: analisar gráfico ======
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!OPENAI_API_KEY) {
      return res.status(500).json({ erro: "OPENAI_API_KEY em falta no servidor." });
    }

    if (!req.file) {
      return res.status(400).json({ erro: "Envie a imagem no form-data: grafico" });
    }

    // imagem em base64
    const base64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${req.file.mimetype};base64,${base64}`;

    // Prompt (1 minuto e 30s, ativos específicos)
    const system = `
Você é um analista técnico de gráficos (opções binárias). 
Você deve responder SOMENTE com "COMPRA" ou "VENDA".
A expiração da operação é de 1 minuto e 30 segundos.
Use apenas o que é visível no gráfico (tendência, suporte/resistência, momentum, volatilidade).
Se a imagem estiver ilegível, escolha a opção mais provável com base no que aparece.
Não escreva explicações, nem "NEUTRO", nem "ERRO".
`;

    const user = `
Analise o print do gráfico e retorne a melhor decisão para expiração de 1 minuto e 30 segundos.
Considere ativos como EUR/USD, GBP/USD, BTC, ETH (se der para identificar no print).
Responda apenas: COMPRA ou VENDA.
`;

    const response = await client.responses.create({
      model: "gpt-4.1-mini",
      input: [
        { role: "system", content: system.trim() },
        {
          role: "user",
          content: [
            { type: "input_text", text: user.trim() },
            { type: "input_image", image_url: dataUrl }
          ]
        }
      ]
    });

    // Extrair texto final
    const out = (response.output_text || "").trim().toUpperCase();

    // Garantir só COMPRA/VENDA
    const sinal = out.includes("VENDA") ? "VENDA" : "COMPRA";

    return res.json({
      ok: true,
      sinal,
      expiracao: "1m30s",
      time: new Date().toISOString()
    });

  } catch (err) {
    console.error("Erro /api/analisar-grafico:", err?.message || err);

    // erro “sem créditos” / quota / 429
    const msg = String(err?.message || "");
    if (msg.includes("429") || msg.toLowerCase().includes("quota") || msg.toLowerCase().includes("insufficient_quota")) {
      return res.status(402).json({ erro: "Sem créditos na OpenAI (quota). Carrega saldo e tenta novamente." });
    }

    return res.status(500).json({ erro: "Erro interno na análise." });
  }
});

// GET neste endpoint devolve “Use POST” (para não aparecer Cannot GET)
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({ erro: "Use POST", exemplo: "POST /api/analisar-grafico (form-data: grafico=image)" });
});

app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});
