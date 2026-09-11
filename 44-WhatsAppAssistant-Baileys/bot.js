import "dotenv/config";
import makeWASocket, { DisconnectReason, useMultiFileAuthState } from "baileys";
import { Boom } from "@hapi/boom";
import qrcode from "qrcode-terminal";
import pino from "pino";
import { getResponse } from "./agent.js";
import { state as appState, pushMessage } from "./state.js";

// Le scan du QR code dans un terminal échoue souvent (police du terminal qui
// déforme les caractères ▄▀█, fenêtre trop étroite...). Si PAIRING_NUMBER est
// renseigné dans .env (ton numéro, chiffres uniquement, avec indicatif pays,
// ex: 33612345678), on utilise à la place le CODE D'APPAIRAGE : plus fiable,
// pas de QR à photographier. Les deux sont aussi affichés sur l'interface web
// (voir web.js) — plus fiable qu'un QR en ASCII dans le terminal.
const PAIRING_NUMBER = process.env.PAIRING_NUMBER?.replace(/[^0-9]/g, "") || null;

// Ignore les messages envoyés avant le démarrage du bot (historique synchronisé
// à la connexion) : sans ce filtre, le bot répondrait à tous les vieux messages
// non lus au premier lancement.
const startedAt = Math.floor(Date.now() / 1000);

export async function connectToWhatsApp() {
  const { state: authState, saveCreds } = await useMultiFileAuthState("auth_info");

  const sock = makeWASocket({
    auth: authState,
    logger: pino({ level: "silent" }),
  });

  // Demande le code d'appairage une seule fois, dès que le socket est prêt et
  // que le compte n'est pas encore enregistré (sinon Baileys régénère un code
  // à chaque tentative de connexion, y compris lors des reconnexions normales).
  if (PAIRING_NUMBER && !sock.authState.creds.registered) {
    setTimeout(async () => {
      try {
        const code = await sock.requestPairingCode(PAIRING_NUMBER);
        appState.pairingCode = code;
        console.log(`\n🔑 Code d'appairage : ${code}\n`);
        console.log("Sur ton téléphone : WhatsApp → Appareils liés → Lier un appareil → Lier avec un numéro de téléphone → entre ce code.\n");
      } catch (err) {
        console.error("Impossible de générer le code d'appairage :", err.message);
      }
    }, 3000);
  }

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      appState.qr = qr;
      appState.status = "waiting_qr";
      if (!PAIRING_NUMBER) {
        console.log("\nScanne ce QR code avec WhatsApp (Appareils liés) :\n");
        console.log("Si le scan échoue depuis le terminal, ouvre plutôt http://localhost:3000\n");
        qrcode.generate(qr, { small: false });
      }
    }

    if (connection === "close") {
      appState.status = "disconnected";
      const statusCode = lastDisconnect?.error instanceof Boom ? lastDisconnect.error.output?.statusCode : undefined;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log("Connexion fermée.", lastDisconnect?.error?.message || "", "Reconnexion :", shouldReconnect);
      if (shouldReconnect) {
        connectToWhatsApp();
      } else {
        console.log("Session déconnectée (logout). Supprime le dossier 'auth_info' et relance pour scanner un nouveau QR code.");
      }
    } else if (connection === "open") {
      appState.status = "connected";
      appState.qr = null;
      appState.pairingCode = null;
      console.log("✅ Connecté à WhatsApp. En attente de messages...");
    }
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("messages.upsert", async (event) => {
    for (const message of event.messages) {
      try {
        await handleIncomingMessage(sock, message);
      } catch (err) {
        console.error("Erreur lors du traitement d'un message :", err);
      }
    }
  });
}

async function handleIncomingMessage(sock, message) {
  const chatId = message.key.remoteJid;

  // On ignore : nos propres messages envoyés, les messages de groupe (pour un
  // usage personnel simple), les messages sans texte (images, audio...), et
  // tout ce qui date d'avant le démarrage du bot.
  if (message.key.fromMe) return;
  if (chatId?.endsWith("@g.us")) return;
  if ((message.messageTimestamp ?? 0) < startedAt) return;

  const text = message.message?.conversation || message.message?.extendedTextMessage?.text;
  if (!text) return;

  console.log(`📩 Message de ${chatId} : ${text}`);

  await sock.sendPresenceUpdate("composing", chatId);
  const reply = await getResponse(text, chatId);
  await sock.sendMessage(chatId, { text: reply });

  pushMessage({
    from: chatId,
    text,
    reply,
    at: new Date().toLocaleTimeString("fr-FR"),
  });

  console.log(`📤 Réponse envoyée à ${chatId}`);
}
