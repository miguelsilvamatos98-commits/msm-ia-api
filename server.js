import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();

// CORS aberto (para o Hostinger poder chamar)
app.use(cors());
app.use(express.json());

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 } // 8MB
});

const PORT = process.env.PORT || 3000;

// Health
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// GET explicativo (para não dar confusão)
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)"
  });
});

// POST real
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!process.env.OPENAI_API_KEY) {
      return res.status(500).json({ erro: "OPENAI_API_KEY não definida no Render (Environment)." });
    }

    if (!req.file) {
      return res.status(400).json({
        erro: "Ficheiro não enviado. Envie form-data com a chave 'grafico'.",
        exemplo: "POST /api/analisar-grafico (form-data: grafico=image)"
      });
    }

    // OpenAI client
    const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

    // Converter imagem para base64 data url
    const mime = req.file.mimetype || "image/png";
    const base64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${base64}`;

    // Prompt (ajusta como quiseres)
    const system = `És um analista técnico. Responde SEMPRE em JSON puro.
Campos: sinal (COMPRA|VENDA|NEUTRO), confianca (0-100), resumo (string curta).`;

    const user = `Analisa o print do gráfico (candlesticks) e devolve sinal para a próxima entrada.
Não inventes dados. Se não der para ler, devolve NEUTRO com baixa confiança.`;

    // Chamada multimodal (imagem + texto)
    const r = await client.chat.completions.create({
      model: "gpt-4.1-mini",
      messages: [
        { role: "system", content: system },
        {
          role: "user",
          content: [
            { type: "text", text: user },
            { type: "image_url", image_url: { url: dataUrl } }
          ]
        }
      ],
      temperature: 0.2
    });

    const raw = r?.choices?.[0]?.message?.content?.trim() || "";

    // tentar parse JSON
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      // fallback se vier texto
      parsed = { sinal: "NEUTRO", confianca: 35, resumo: raw.slice(0, 200) || "Sem leitura." };
    }

    // normalizar
    const sinal = String(parsed.sinal || "NEUTRO").toUpperCase();
    const confianca = Math.max(0, Math.min(100, Number(parsed.confianca ?? 50)));
    const resumo = String(parsed.resumo || "").slice(0, 500);

    return res.json({ ok: true, sinal, confianca, resumo });

  } catch (err) {
    console.error("ERRO /api/analisar-grafico:", err);
    return res.status(500).json({ erro: "Erro interno na análise" });
  }
});

app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});
