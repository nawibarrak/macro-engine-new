import cors from 'cors';
import express from 'express';
import rateLimit from 'express-rate-limit';
import { GoogleGenAI } from '@google/genai';

const app = express();
const port = Number(process.env.PORT) || 3000;
const apiKey = process.env.GEMINI_API_KEY;
const model = process.env.GEMINI_MODEL || 'gemini-3.8-flash';
const allowedOrigins = (process.env.ALLOWED_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

const ai = apiKey ? new GoogleGenAI({ apiKey }) : null;

app.disable('x-powered-by');

app.use(cors({
  origin(origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) return callback(null, true);
    return callback(new Error('Origin is not allowed'));
  },
}));

app.use(express.json({ limit: '8kb' }));

app.use('/api/', rateLimit({
  windowMs: 60_000,
  limit: 10,
  standardHeaders: 'draft-8',
  legacyHeaders: false,
  message: { error: 'Terlalu banyak permintaan. Coba lagi sebentar.' },
}));

app.get('/healthz', (_req, res) => res.json({ ok: true }));

app.post('/api/macro-search', async (req, res) => {
  const query = req.body?.query;
  if (typeof query !== 'string' || !query.trim()) {
    res.status(400).json({ error: 'Query wajib berupa teks.' });
    return;
  }

  if (query.length > 1000) {
    res.status(413).json({ error: 'Query terlalu panjang (maksimum 1000 karakter).' });
    return;
  }

  if (!ai) {
    res.status(503).json({ error: 'Layanan pencarian belum dikonfigurasi.' });
    return;
  }

  try {
    const cleanQuery = query.trim();
    const response = await ai.models.generateContent({
      model,
      contents: `You are a macroeconomic research analyst. Analyze the latest updates using Google Search data for: "${cleanQuery}". Structure the response with (1) latest official data and dates, (2) central-bank stance and market consensus, (3) cross-asset implications, and (4) a concise quantitative takeaway. Distinguish verified facts from interpretation and avoid presenting this as investment advice.`,
      config: { tools: [{ googleSearch: {} }] },
    });

    const candidate = response.candidates?.[0];
    const grounding = candidate?.groundingMetadata;

    res.json({
      query: cleanQuery,
      analysis: response.text || 'Tidak ada analisis yang dihasilkan.',
      searchQueries: grounding?.webSearchQueries || [],
      sources: (grounding?.groundingChunks || [])
        .map((chunk) => ({ title: chunk.web?.title || 'Web Source', uri: chunk.web?.uri || '' }))
        .filter((source) => source.uri),
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Gemini macro-search failed:', error);
    res.status(502).json({ error: 'Pencarian makro gagal sementara. Coba lagi nanti.' });
  }
});

app.listen(port, '0.0.0.0', () => {
  console.log(`Macro search API listening on port ${port}`);
});
