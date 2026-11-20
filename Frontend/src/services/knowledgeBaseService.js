import {
  knowledgeBaseMockData,
} from "../data/knowledgeBaseData";

/*
 * Temporary Knowledge Base service.
 *
 * Later this service will communicate with the FastAPI backend.
 *
 * Planned operations:
 * - GET  /api/knowledge-base
 * - POST /api/knowledge-base/{id}/index
 * - DELETE /api/knowledge-base/{id}
 * - GET  /api/knowledge-base/search
 */

export async function getKnowledgeSources() {
  return knowledgeBaseMockData;
}

export async function reindexKnowledgeSource(sourceId) {
  /*
   * Temporary frontend simulation.
   *
   * Real indexing will be performed by the backend RAG pipeline.
   */
  return {
    id: sourceId,
    status: "INDEXING",
  };
}
