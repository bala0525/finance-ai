import { API_BASE_URL } from "../config";

const ACCESS_TOKEN_KEY = "azentmart_access_token";


export async function loginUser(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",

    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },

    body: JSON.stringify({
      email,
      password,
    }),
  });


  let data = {};

  try {
    data = await response.json();
  } catch {
    data = {};
  }


  if (!response.ok) {
    throw new Error(
      data.detail || "Unable to sign in. Please try again."
    );
  }


  return data;
}


export function saveAccessToken(token, rememberMe = false) {
  // Remove any older token before saving the newly issued token.
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);

  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem(ACCESS_TOKEN_KEY, token);
}


export function getAccessToken() {
  return (
    localStorage.getItem(ACCESS_TOKEN_KEY) ||
    sessionStorage.getItem(ACCESS_TOKEN_KEY)
  );
}


export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}
export async function signupUser(email, password, fullName) {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",

    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },

    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
    }),
  });

  let data = {};

  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(
      data.detail || "Unable to create your account. Please try again."
    );
  }

  return data;
}




async function authPost(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) throw new Error(data.detail || "Authentication request failed.");
  return data;
}

export const requestPasswordReset = (email) => authPost("/auth/forgot-password", { email });
export const resetPassword = (token, newPassword) => authPost("/auth/reset-password", { token, new_password: newPassword });

export const verifyEmail = (token) => authPost("/auth/verify-email", { token });
export const resendVerification = (email) => authPost("/auth/resend-verification", { email });
