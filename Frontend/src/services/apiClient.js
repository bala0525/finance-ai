import { API_BASE_URL } from "../config";
import { getAccessToken } from "./authService";


/*
 * FastAPI returns `detail` as a string for most errors, but as an array of
 * objects for 422 validation errors. Normalise both to a readable message.
 */
function extractErrorMessage(data) {
  const detail = data?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => item?.msg || (typeof item === "string" ? item : ""))
      .filter(Boolean)
      .join(" ");
  }

  return "Something went wrong. Please try again.";
}

async function apiClient(endpoint, options = {}) {
  const token = getAccessToken();

  // FormData (file uploads) must NOT get a JSON content-type: the browser
  // has to set multipart/form-data with the correct boundary itself.
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  const headers = {
    Accept: "application/json",
    ...(options.body && !isFormData
      ? { "Content-Type": "application/json" }
      : {}),
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch {
    const networkError = new Error(
      "Cannot reach the server. Check that the backend is running."
    );
    networkError.status = 0;
    throw networkError;
  }

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(extractErrorMessage(data));

    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}

/*
 * Authenticated binary fetch (preview / download). Returns { blob, filename }.
 * Plain <a href> links cannot send the Bearer token, so files are fetched
 * here and exposed to the browser via object URLs.
 */
export async function apiBlob(endpoint) {
  const token = getAccessToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    const networkError = new Error(
      "Cannot reach the server. Check that the backend is running."
    );
    networkError.status = 0;
    throw networkError;
  }

  if (!response.ok) {
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const error = new Error(extractErrorMessage(data));
    error.status = response.status;
    throw error;
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
  const filename = match ? decodeURIComponent(match[1] || match[2]) : null;

  return { blob: await response.blob(), filename };
}

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default apiClient;
