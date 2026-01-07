const AI_URL = process.env.AI_PYTHON_URL;

const resp = await fetch(AI_URL, {
  method: "POST",
  body: formData
});

const data = await resp.json();

if (!data || !data.sinal) {
  throw new Error("Resposta inválida do serviço de IA");
}
