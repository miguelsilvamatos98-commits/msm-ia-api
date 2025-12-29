import express from "express";
import cors from "cors";
import multer from "multer";
import dotenv from "dotenv";
import OpenAI from "openai";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ storage: multer.memoryStorage() });

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

async function analisar(base64) {
  const resp = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: "Responde apenas em JSON: {\"sinal\":\"COMPRA|VENDA\",\"confianca\":0-100}"
      },
      {
        role: "user",
        content: [
          { type: "text", text: "Analisa o gráfico." },
          {
            type: "image_url",
            image_url: "data:image/png;base64," + base64
          }
        ]
      }
    ],
    max_tokens: 200
  });

  return JSON.parse(resp.choices[0].message.content);
}

app.get("/", (req, res) => {
  res.send("MSM IA API ONLINE ✅");
});

app.post("/analisar", upload.single("grafico"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ erro: "Sem imagem" });
    const base64 = req.file.buffer.toString("base64");
    const data = await analisar(base64);
    res.json(data);
  } catch (e) {
    res.status(500).json({ erro: "Falha na análise" });
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("API a correr na porta " + PORT);
});
