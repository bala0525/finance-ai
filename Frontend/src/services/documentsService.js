import apiClient, { apiBlob, saveBlob } from "./apiClient";

/*
 * Document service - talks to the FastAPI document endpoints.
 *
 *   GET  /documents          list the signed-in user's documents
 *   POST /documents/upload   multipart upload (classified + extracted server-side)
 *
 * The backend classifies the file (Gemini) and, for invoices, extracts and
 * validates the invoice fields, so the category is NOT sent by the client.
 */

export async function getDocuments() {
  return apiClient("/documents");
}

export async function uploadDocument(file, options = {}) {
  const formData = new FormData();
  formData.append("file", file);

  if (options.workspace) {
    formData.append("workspace", options.workspace);
  }
  if (options.replacesDocumentId) {
    formData.append("replaces_document_id", String(options.replacesDocumentId));
  }
  if (options.assignedFinanceUserId) {
    formData.append("assigned_finance_user_id", String(options.assignedFinanceUserId));
  }

  return apiClient("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function getDocumentPreview(documentId) {
  return apiClient(`/documents/${documentId}/preview`);
}

export async function getDocumentFileBlob(documentId) {
  return apiBlob(`/documents/${documentId}/file`);
}

export async function downloadDocument(document) {
  const { blob, filename } = await apiBlob(
    `/documents/${document.id}/file?download=true`
  );
  saveBlob(blob, filename || document.name);
}

export async function deleteDocument(documentId) {
  return apiClient(`/documents/${documentId}`, { method: "DELETE" });
}

// NEW: Final AP payment is recorded against the invoice and posted to the GL.
export async function payInvoice(documentId, payload) {
  return apiClient(`/documents/${documentId}/pay`, {
    method: "POST",
    body: JSON.stringify({
      amount: payload.amount,
      transfer_reference: payload.transferReference,
      bank_name: payload.bankName || null,
      payment_date: payload.paymentDate,
    }),
  });
}
