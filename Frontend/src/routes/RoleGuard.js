import React from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";
import { canAccessAgent, AGENT_ACCESS } from "../config/roleAccess";

export function RoleGuard({ agentPath, children }) {
  const { currentUser } = useAuthContext();
  if (!canAccessAgent(currentUser, agentPath)) {
    const firstAllowed = Object.keys(AGENT_ACCESS).find((path) => canAccessAgent(currentUser, path));
    return <Navigate to={firstAllowed ? `/employees/${firstAllowed}` : "/login"} replace />;
  }
  return children;
}

export function RoleLanding() {
  const { currentUser } = useAuthContext();
  const firstAllowed = Object.keys(AGENT_ACCESS).find((path) => canAccessAgent(currentUser, path));
  return <Navigate to={firstAllowed ? `/employees/${firstAllowed}` : "/login"} replace />;
}


export function AdminGuard({ children }) {
  const { currentUser } = useAuthContext();
  if ((currentUser?.role_name || currentUser?.role?.name) !== "Administrator") {
    return <RoleLanding />;
  }
  return children;
}
