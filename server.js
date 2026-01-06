import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();

/* ===============================
   CONFIG UPLOAD (IMAGEM)
================================ */
const upload = multer({
  limits: { fileSize: 5 * 1024 * 1024 } // 5MB
});

/* ===============================
   CORS – DOMÍNIOS AUTORIZADOS
================================ */
const allowedOrigins = [
  "https://darkturquoise-stork-767325.hostingersite.com",
  "https://tradespeedpro.click",
  "http://localhost:5500",
  "http://localhost:3000"
];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error("CORS bloqueado: " + origin));
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
   HEALTH CHECK
================================ */
app.get("/health", (req, res) => {
  res.json({
    ok: true,
    service: "MSM-IA-API",
    time: new Date().toISOString()
  });
});

/* ===============================
   ANALISAR GRÁFICO (POST)
   RESPONDE APENAS:
   - COMPRA
   - VENDA
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
És uma IA profissional de análise técnica para OPÇÕES BINÁRIAS.
Objetivo: decidir operação de 1 MINUTO.

Regras OBRIGATÓRIAS:
- Responder APENAS "COMPRA" ou "VENDA"
- Nunca responder NEUTRO, ERRO ou texto extra
- Basear-se apenas no gráfico visível
- Analisar micro-tendência, força, rejeições e candles recentes
`
        },
        {
          role: "user",
          content: [
            { type: "text", text: "Analisa este gráfico e decide a operação." },
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

  } catch (error) {
    console.error("Erro IA:", error);
    res.status(500).json({
      erro: "Erro interno na análise"
    });
  }
});

/* ===============================
   START SERVER
================================ */
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});
