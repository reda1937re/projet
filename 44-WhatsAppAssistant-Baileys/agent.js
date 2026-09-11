import "dotenv/config";
import Groq from "groq-sdk";

const GROQ_API_KEY = process.env.GROQ_API_KEY;
const MODEL_ID = "openai/gpt-oss-120b";

// Historique de conversation par expéditeur (numéro WhatsApp / JID) : sans ça,
// chaque message serait traité isolément, sans mémoire de ce qui précède.
// En mémoire uniquement (perdu si le bot redémarre) — suffisant pour un usage
// personnel ; passer par un fichier/DB si la persistance entre redémarrages
// devient nécessaire.
const MAX_HISTORY_MESSAGES = 20;
const conversations = new Map();

const groq = new Groq({ apiKey: GROQ_API_KEY });

const SYSTEM_PROMPT = `Tu es un assistant personnel qui répond aux messages WhatsApp à la place de l'utilisateur.

Règles :
- Réponds de façon naturelle, concise et directe (style message, pas un pavé).
- Si on te pose une question dont tu ne connais pas la réponse avec certitude, dis-le clairement plutôt que d'inventer.
- Adapte-toi à la langue utilisée par la personne qui écrit.
- Tu peux utiliser des emojis avec modération, sans en abuser.`;

function getHistory(chatId) {
  if (!conversations.has(chatId)) {
    conversations.set(chatId, []);
  }
  return conversations.get(chatId);
}

function pushToHistory(chatId, role, content) {
  const history = getHistory(chatId);
  history.push({ role, content });
  // Ne garde que les N derniers messages pour rester sous la limite de tokens
  // du modèle sur les conversations longues.
  if (history.length > MAX_HISTORY_MESSAGES) {
    history.splice(0, history.length - MAX_HISTORY_MESSAGES);
  }
}

/**
 * Génère la réponse de l'agent pour `message`, dans le contexte de la
 * conversation `chatId` (le JID WhatsApp de l'expéditeur).
 */
export async function getResponse(message, chatId) {
  pushToHistory(chatId, "user", message);

  const completion = await groq.chat.completions.create({
    model: MODEL_ID,
    messages: [{ role: "system", content: SYSTEM_PROMPT }, ...getHistory(chatId)],
  });

  const reply = completion.choices[0].message.content;
  pushToHistory(chatId, "assistant", reply);
  return reply;
}
