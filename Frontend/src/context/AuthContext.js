import { createContext, useContext, useEffect, useState } from "react";

import {
  loginUser,
  saveAccessToken,
  getAccessToken,
  clearAccessToken,
} from "../services/authService";

import { getCurrentUser } from "../services/userService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      setLoading(false);
      return;
    }

    const loadCurrentUser = async () => {
      try {
        const user = await getCurrentUser();

        setCurrentUser(user);
      } catch (error) {
        if (error.status === 401) {
          clearAccessToken();
        }

        setCurrentUser(null);
      } finally {
        setLoading(false);
      }
    };

    loadCurrentUser();
  }, []);

  const login = async (email, password, rememberMe = false) => {
    const data = await loginUser(email, password);

    saveAccessToken(data.access_token, rememberMe);

    const user = await getCurrentUser();

    setCurrentUser(user);

    return user;
  };

  const logout = () => {
    clearAccessToken();
    setCurrentUser(null);
  };

  const refreshUser = async () => {
    try {
      const user = await getCurrentUser();
      setCurrentUser(user);
      return user;
    } catch {
      // Silently fail — the user stays as-is
      return currentUser;
    }
  };

  const value = {
    currentUser,
    loading,
    isAuthenticated: Boolean(currentUser),
    login,
    logout,
    refreshUser,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuthContext must be used inside AuthProvider."
    );
  }

  return context;
}