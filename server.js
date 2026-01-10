import express from "express";

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// health check (Render precisa disto)
app.get("/", (req, res) => {
  res.json({
    ok: true,
    service: "msm-ia-api",
    status: "running"
  });
});

// exemplo de rota (se quiseres usar depois)
app.get("/status", (req, res) => {
  res.json({ online: true });
});

app.listen(PORT, () => {
  console.log(`MSM IA API running on port ${PORT}`);
});
