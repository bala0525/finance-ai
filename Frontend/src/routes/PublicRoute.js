import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthContext } from "../context/AuthContext";

function PublicRoute() {
  const { isAuthenticated, loading } = useAuthContext();

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#07111f",
          color: "#8ea4bd",
          fontSize: "14px",
        }}
      >
        Loading...
      </div>
    );
  }

  // Authenticated users should go to a route that actually exists.
  if (isAuthenticated) {
    return (
      <Navigate
        to="/employees/accounts-payable"
        replace
      />
    );
  }

  return <Outlet />;
}

export default PublicRoute;
