import { assistantInitialMessages } from "../data/assistantData";
import { askFinanceAnalyst } from "./agentsService";

/*
 * Assistant service - backed by the Finance Analyst agent (RAG).
 *
 * POST /agents/finance-analyst/ask retrieves the most relevant passages from
 * the user's own documents and answers only from them. `sources` are the
 * retrieved passages ([S1], [S2]... as cited inside the answer).
 */

export async function getAssistantConversation() {
  return assistantInitialMessages;
}

export async function sendAssistantMessage(message) {
  const result = await askFinanceAnalyst(message);

  return {
    id: `assistant-${Date.now()}`,
    role: "assistant",
    content: result?.answer || "No answer was returned.",
    sources: Array.isArray(result?.sources) ? result.sources : [],
    retrieval: result?.retrieval || null,
  };
}
