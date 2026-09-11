import express from "express";
import QRCode from "qrcode";
import { state } from "./state.js";

const PORT = process.env.WEB_PORT || 3000;

const app = express();

app.get("/api/status", async (req, res) => {
  let qrImage = null;
  if (state.qr) {
    qrImage = await QRCode.toDataURL(state.qr, { width: 320, margin: 2 });
  }
  res.json({
    status: state.status,
    qrImage,
    pairingCode: state.pairingCode,
    recentMessages: state.recentMessages,
  });
});

app.get("/", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(HTML_PAGE);
});

export function startWebServer() {
  app.listen(PORT, () => {
    console.log(`🌐 Interface disponible sur http://localhost:${PORT}`);
  });
}

const HTML_PAGE = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>Assistant WhatsApp</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {
    --ink: #0f172a; --muted: #64748b; --accent: #16a34a; --border: #e2e8f0; --surface: #f8fafc;
  }
  @media (prefers-color-scheme: dark) {
    :root { --ink: #f1f5f9; --muted: #94a3b8; --accent: #4ade80; --border: rgba(255,255,255,0.14); --surface: rgba(255,255,255,0.04); }
    body { background: #0e1117; }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", Inter, sans-serif;
    color: var(--ink);
    max-width: 480px;
    margin: 0 auto;
    padding: 2rem 1.2rem;
  }
  h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
  .subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 1.6rem; }
  .card {
    border: 1px solid var(--border); border-radius: 12px; padding: 1.4rem;
    text-align: center; margin-bottom: 1.4rem; background: var(--surface);
  }
  .status-badge {
    display: inline-block; font-size: 0.75rem; font-weight: 600; padding: 0.3rem 0.8rem;
    border-radius: 999px; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.04em;
  }
  .status-badge.connected { background: rgba(22,163,74,0.15); color: var(--accent); }
  .status-badge.waiting { background: rgba(217,119,6,0.15); color: #d97706; }
  img.qr { max-width: 100%; border-radius: 8px; }
  .pairing-code { font-size: 1.8rem; font-weight: 700; letter-spacing: 0.15em; color: var(--accent); margin: 0.6rem 0; }
  .hint { color: var(--muted); font-size: 0.82rem; line-height: 1.4; }
  .messages { display: flex; flex-direction: column; gap: 0.7rem; }
  .msg { border: 1px solid var(--border); border-radius: 8px; padding: 0.7rem 0.9rem; font-size: 0.85rem; text-align: left; }
  .msg .from { font-weight: 600; color: var(--muted); font-size: 0.72rem; margin-bottom: 0.3rem; }
  .msg .text { margin-bottom: 0.4rem; }
  .msg .reply { color: var(--accent); }
  .empty { color: var(--muted); font-size: 0.85rem; text-align: center; padding: 1rem; }
</style>
</head>
<body>
  <h1>🤖 Assistant WhatsApp</h1>
  <div class="subtitle">Statut de connexion et derniers échanges</div>

  <div class="card" id="connection-card">
    <div class="hint">Chargement...</div>
  </div>

  <h2 style="font-size:1rem;">Derniers messages</h2>
  <div class="messages" id="messages"></div>

  <script>
    async function refresh() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        renderConnection(data);
        renderMessages(data.recentMessages);
      } catch (e) {
        console.error(e);
      }
    }

    function renderConnection(data) {
      const card = document.getElementById('connection-card');
      if (data.status === 'connected') {
        card.innerHTML = '<span class="status-badge connected">Connecté</span><div class="hint">L\\'assistant répond automatiquement aux messages entrants.</div>';
      } else if (data.pairingCode) {
        card.innerHTML = '<span class="status-badge waiting">En attente</span>' +
          '<div class="pairing-code">' + data.pairingCode + '</div>' +
          '<div class="hint">WhatsApp → Appareils liés → Lier un appareil → Lier avec un numéro de téléphone → entre ce code.</div>';
      } else if (data.qrImage) {
        card.innerHTML = '<span class="status-badge waiting">En attente</span>' +
          '<img class="qr" src="' + data.qrImage + '" alt="QR code WhatsApp" />' +
          '<div class="hint">WhatsApp → Appareils liés → Lier un appareil → scanne ce QR code.</div>';
      } else {
        card.innerHTML = '<span class="status-badge waiting">Démarrage</span><div class="hint">Connexion à WhatsApp en cours...</div>';
      }
    }

    function renderMessages(messages) {
      const el = document.getElementById('messages');
      if (!messages || messages.length === 0) {
        el.innerHTML = '<div class="empty">Aucun message pour l\\'instant.</div>';
        return;
      }
      el.innerHTML = messages.map(m =>
        '<div class="msg"><div class="from">' + m.from + ' · ' + m.at + '</div>' +
        '<div class="text">' + escapeHtml(m.text) + '</div>' +
        '<div class="reply">→ ' + escapeHtml(m.reply) + '</div></div>'
      ).join('');
    }

    function escapeHtml(str) {
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    }

    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>`;
