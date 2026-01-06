import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();
const upload = multer({ limits: { fileSize: 5 * 1024 * 1024 } });

// 👉 LISTA DE DOMÍNIOS AUTORIZADOS
const allowedOrigins = [
  "https://darkturquoise-stork-767325.hostingersite.com",
  "https://tradespeedpro.click",
  "http://localhost:5500"
];

// 👉 CORS (UMA ÚNICA VEZ)
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

// 👉 OpenAI
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// 👉 Health check
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date() });
});

// 👉 Endpoint principal
app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ erro: "Imagem não enviada" });
    }

    const base64Image = req.file.buffer.toString("base64");

    const response = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "És uma IA de análise técnica para opções binárias. Responde APENAS com COMPRA ou VENDA para 1 minuto."
        },
        {
          role: "user",
          content: [
            { type: "text", text: "Analisa este gráfico e decide." },
            {
              type: "image_url",
              image_url: {
                url: `data:image/png;base64,${base64Image}`
              }
            }
          ]
        }
      ],
      max_tokens: 10
    });

    const decisao = response.choices[0].message.content.trim();

    res.json({
      sinal: decisao === "COMPRA" ? "COMPRA" : "VENDA",
      duracao: "1 minuto"
    });

  } catch (err) {
    console.error(err);
    res.status(500).json({ erro: "Erro interno na análise" });
  }
});

// 👉 Porta Render
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
});
