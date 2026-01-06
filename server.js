import express from "express";
import cors from "cors";
import multer from "multer";
import OpenAI from "openai";

const app = express();

// =========================
// CORS (ALLOWED ORIGINS)
// =========================
// Podes também definir no Render: ALLOWED_ORIGINS="https://tradespeedpro.click,https://www.tradespeedpro.click"
const allowedOrigins = (process.env.ALLOWED_ORIGINS ||
  "https://tradespeedpro.click,https://www.tradespeedpro.click"
)
  .split(",")
  .map(s => s.trim())
  .filter(Boolean);

app.use(cors({
  origin: function (origin, cb) {
    // origin pode vir undefined em alguns testes (curl/postman/server-to-server)
    if (!origin) return cb(null, true);

    if (allowedOrigins.includes(origin)) return cb(null, true);

    // Bloqueia e mostra no log qual origin tentou
    console.log("CORS bloqueado:", origin);
    return cb(new Error("CORS bloqueado: " + origin), false);
  },
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type", "Authorization"],
  credentials: false
}));

app.options("*", cors());

// =========================
// Upload
// =========================
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 8 * 1024 * 1024 } // 8MB
});

// =========================
// OpenAI
// =========================
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const client = new OpenAI({ apiKey: OPENAI_API_KEY });

// =========================
// Routes
// =========================
app.get("/health", (req, res) => {
  res.json({ ok: true, service: "MSM-IA-API", time: new Date().toISOString() });
});

// Protege contra GET no endpoint de análise
app.get("/api/analisar-grafico", (req, res) => {
  res.status(405).json({
    erro: "Use POST",
    exemplo: "POST /api/analisar-grafico (form-data: grafico=image)"
  });
});

app.post("/api/analisar-grafico", upload.single("grafico"), async (req, res) => {
  try {
    // 1) validações
    if (!OPENAI_API_KEY) {
      return res.status(500).json({ erro: "OPENAI_API_KEY não configurada no servidor." });
    }
    if (!req.file) {
      return res.status(400).json({ erro: "Envie a imagem em form-data com o campo: grafico" });
    }

    const ativo = (req.body.ativo || "EURUSD").toString();
    const duracao = (req.body.duracao || "90").toString(); // 90 = 1m30

    // 2) transforma imagem em base64 data url
    const mime = req.file.mimetype || "image/png";
    const base64 = req.file.buffer.toString("base64");
    const dataUrl = `data:${mime};base64,${base64}`;

    // 3) prompt (resposta só COMPRA ou VENDA)
    const prompt = `
Analisa a imagem do gráfico (candlesticks) para opções binárias.
Ativo: ${ativo}
Duração da operação: ${duracao} segundos (1m30)

Regras:
- Responde APENAS com "COMPRA" ou "VENDA".
- Não escrevas "NEUTRO", não escrevas explicações.
- Se a imagem não permitir análise, escolhe a opção mais provável entre COMPRA/VENDA (mesmo assim, só uma palavra).
`;

    // 4) chamada OpenAI (visão)
    const response = await client.responses.create({
      model: "gpt-4.1-mini",
      input: [
        {
          role: "user",
          content: [
            { type: "input_text", text: prompt.trim() },
            { type: "input_image", image_url: dataUrl }
          ]
        }
      ]
    });

    const text = (response.output_text || "").trim().toUpperCase();
    const sinal = text.includes("VENDA") ? "VENDA" : "COMPRA"; // garante 1 palavra

    // (Opcional) confiança simples (podes melhorar depois)
    const confianca = 60;

    return res.json({
      ok: true,
      sinal,
      confianca,
      ativo,
      duracao_segundos: Number(duracao)
    });

  } catch (err) {
    // Se der quota/429, não “rebenta” o servidor
    const msg = err?.message || "Erro interno";
    console.log("Erro /api/analisar-grafico:", msg);

    // Mantém resposta clara
    return res.status(500).json({
      ok: false,
      erro: "Falha na análise",
      detalhe: msg
    });
  }
});

// =========================
// Start
// =========================
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("MSM-IA-API a correr na porta", PORT);
  console.log("ALLOWED_ORIGINS:", allowedOrigins.join(" | "));
});
