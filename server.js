import express from "express";
import cors from "cors";
import multer from "multer";
import dotenv from "dotenv";
import OpenAI from "openai";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: "2mb" }));

// Upload em memória (não precisa pasta uploads/)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 12 * 1024 * 1024 }, // 12MB
});

// Se a env não existir, o Render cai com o mesmo erro que tens agora
if (!process.env.OPENAI_API_KEY) {
  console.error("❌ OPENAI_API_KEY em falta. Define-a nas Environment Variables do Render.");
}

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Health check
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// Endpoint principal
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ erro: "Envie uma imagem no campo 'grafico' (form-data)." });
    }

    if (!process.env.OPENAI_API_KEY) {
      return res.status(500).json({ erro: "OPENAI_API_KEY não configurada no servidor." });
    }

    const mime = req.file.mimetype || "image/png";
    const base64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${base64}`;

    // Prompt: devolve SEMPRE JSON puro
    const prompt = `
Analisa o print de um gráfico (candlesticks) de opções binárias.
Devolve APENAS JSON puro (sem markdown) no formato:

{
  "sinal": "COMPRA" | "VENDA" | "AGUARDAR",
  "confianca": número de 0 a 100,
  "resumo": string curta (1-2 frases)
}

Regras:
- Se a imagem estiver desfocada, cortada, ou sem informação suficiente, usa "AGUARDAR" com confianca <= 55.
- Evita inventar indicadores que não estejam visíveis.
- "confianca" deve refletir a clareza do padrão/continuação/reversão visível.
`.trim();

    const response = await client.responses.create({
      model: "gpt-5.2",
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

    const text = response.output_text?.trim() || "";
    let json;

    try {
      json = JSON.parse(text);
    } catch {
      // fallback: tenta extrair o primeiro bloco JSON
      const m = text.match(/\{[\s\S]*\}/);
      if (!m) {
        return res.status(502).json({
          erro: "A IA não devolveu JSON válido.",
          raw: text.slice(0, 4000),
        });
      }
      json = JSON.parse(m[0]);
    }

    // Normalização/validação rápida
    const sinal = String(json.sinal || "").toUpperCase();
    const allowed = new Set(["COMPRA", "VENDA", "AGUARDAR"]);
    const confiancaNum = Number(json.confianca);

    const out = {
      sinal: allowed.has(sinal) ? sinal : "AGUARDAR",
      confianca: Number.isFinite(confiancaNum)
        ? Math.max(0, Math.min(100, Math.round(confiancaNum)))
        : 50,
      resumo: typeof json.resumo === "string" ? json.resumo.slice(0, 240) : "",
    };

    return res.json(out);
  } catch (err) {
    console.error("❌ ERRO /api/analisar-grafico:", err?.message || err);
    return res.status(500).json({
      erro: "Falha no servidor ao analisar o gráfico.",
      detalhe: err?.message || "erro desconhecido",
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ MSM-IA-API a correr na porta ${PORT}`);
});

