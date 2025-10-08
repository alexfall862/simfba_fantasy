import express from 'express';
import { runSync } from './src/processor.js';
import { getManifestJSON } from './src/manifest.js';

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const RUN_TOKEN = process.env.RUN_TOKEN || ''; // set a long random token

app.get('/health', (_req, res) => res.json({ ok: true }));

app.post('/run', async (req, res) => {
  const hdr = req.headers.authorization || '';
  const provided = hdr.startsWith('Bearer ') ? hdr.slice(7) : '';
  if (!RUN_TOKEN || provided !== RUN_TOKEN) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  try {
    const result = await runSync();
    res.json(result);
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  }
});

app.get('/manifest', async (req, res) => {
  try {
    const json = await getManifestJSON();
    res.json(json);
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  }
});

app.listen(PORT, () => {
  console.log(`simfba worker listening on :${PORT}`);
});
