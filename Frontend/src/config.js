const rawApiUrl = process.env.REACT_APP_API_BASE_URL;

if (!rawApiUrl) {
  throw new Error(
    "REACT_APP_API_BASE_URL is not set. Add it to .env.local (development) or the Amplify environment variables, then restart."
  );
}

export const API_BASE_URL = rawApiUrl.replace(/\/+$/, "");