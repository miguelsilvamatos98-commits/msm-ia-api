import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();

/* ===============================
   UPLOAD CONFIG
================================ */
const upload = multer({
  limits: { fileSize: 5 * 1024 * 1024 } // 5MB
});

/* ===============================
   CORS CONFIG (APENAS UMA VEZ)
================================ */
const allowedOrigins = [
  "https://darkturquoise-stork-767325.hostingersite.com",
  "https://tradespeedpro.click",
  "http://localhost:3000",
  "http://localhost:5500"
];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error("CORS bloqueado"));
    }
  }
}));

app.use(express.json());

/* ===============================
   OPENAI
================================ */
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

/* ===============================
   HEALTH
================================ */
app.get("/health", (req, res) => {
  res.json({
    ok: true,
    service: "MSM-IA-API",
    time: new Date().toISOString()
  });
});

/* ===============================
   ANALISAR GRÁFICO
   - SÓ COMPRA ou VENDA
   - 1 MINUTO
================================ */
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ erro: "Imagem não enviada" });
    }

    const imageBase64 = req.file.buffer.toString("base64");

    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content: `
És um analista profissional de opções binárias.
Decide operação de 1 minuto.

REGRAS:
- Responde APENAS "COMPRA" ou "VENDA"
- Nunca escrevas texto extra
- Baseia-te apenas no gráfico
`
        },
        {
          role: "user",
          content: [
            { type: "text", text: "Analisa o gráfico." },
            {
              type: "image_url",
              image_url: {
                url: `data:image/png;base64,${imageBase64}`
              }
            }
          ]
        }
      ],
      max_tokens: 5
    });

    const resposta = completion.choices[0].message.content
      .toUpperCase()
      .includes("COMPRA")
      ? "COMPRA"
      : "VENDA";

    res.json({
      sinal: resposta,
      duracao: "1 minuto"
    });

  } catch (err) {
    console.error(err);
    res.status(500).json({ erro: "Erro interno" });
  }
});

/* ===============================
   START SERVER
================================ */
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});
