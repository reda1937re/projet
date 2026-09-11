// État partagé entre bot.js (connexion WhatsApp) et web.js (interface) : les
// deux tournent dans le même process Node, donc un simple objet en mémoire
// suffit (pas besoin de base de données pour ce cas d'usage personnel).
export const state = {
  status: "starting", // "starting" | "waiting_qr" | "connected" | "disconnected"
  qr: null, // chaîne QR brute à convertir en image côté web.js
  pairingCode: null,
  recentMessages: [], // { from, text, reply, at } les plus récents en tête
};

const MAX_RECENT_MESSAGES = 20;

export function pushMessage(entry) {
  state.recentMessages.unshift(entry);
  if (state.recentMessages.length > MAX_RECENT_MESSAGES) {
    state.recentMessages.length = MAX_RECENT_MESSAGES;
  }
}
