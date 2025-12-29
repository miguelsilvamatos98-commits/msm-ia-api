import express from "express";
import multer from "multer";
import cors from "cors";
import OpenAI from "openai";

const app = express();
const upload = multer({ limits: { fileSize: 5 * 1024 * 1024 } }); // 5MB

app.use(cors());
app.use(express.json());

// 🔑 OpenAI (seguro)
const apiKey = process.env.OPENAI_API_KEY;
let openai = null;

if (apiKey) {
  openai = new OpenAI({ apiKey });
  console.log("✅ OpenAI API KEY carregada");
} else {
  console.warn("⚠️ OPENAI_API_KEY não definida");
}

// ===============================
// ROOT – Página informativa
// ===============================
app.get("/", (req, res) => {
  res.send(`
    <h2>MSM-IA-API</h2>
    <p>API online e funcional.</p>
    <ul>
      <li><b>GET</b> /health</li>
      <li><b>POST</b> /api/analisar-grafico (form-data: grafico)</li>
    </ul>
  `);
});

// ===============================
// HEALTH CHECK
// ===============================
app.get("/health", (req, res) => {
  res.json({
    ok: true,
    service: "MSM-IA-API",
    time: new Date().toISOString()
  });
});

// ===============================
// GET amigável (evita Cannot GET)
// ===============================
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)"
  });
});

// ===============================
// POST REAL – ANÁLISE
// ===============================
app.post(
  "/api/analisar-grafico",
  upload.single("grafico"),
  async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ erro: "Imagem não enviada" });
      }

      if (!openai) {
        return res.status(500).json({
          erro: "OPENAI_API_KEY não configurada no servidor"
        });
      }

      const base64Image = req.file.buffer.toString("base64");

      const response = await openai.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [
          {
            role: "system",
            content:
              "És um analista técnico de opções binárias. Responde APENAS com JSON."
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text:
                  "Analisa o gráfico e responde apenas com JSON: {sinal: COMPRA|VENDA, confianca: numero, motivo: texto curto}"
              },
              {
                type: "image_url",
                image_url: {
                  url: `data:image/png;base64,${base64Image}`
                }
              }
            ]
          }
        ],
        max_tokens: 200
      });

      const content = response.choices[0].message.content;

      // tenta parsear JSON
      let data;
      try {
        data = JSON.parse(content);
      } catch {
        data = {
          sinal: "INDEFINIDO",
          confianca: 0,
          motivo: "Resposta inválida do modelo"
        };
      }

      res.json(data);
    } catch (err) {
      console.error(err);
      res.status(500).json({
        erro: "Erro interno na análise",
        detalhe: err.message
      });
    }
  }
);

// ===============================
// START SERVER (Render)
// ===============================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () =>
  console.log("🚀 MSM-IA-API ativa na porta", PORT)
);
