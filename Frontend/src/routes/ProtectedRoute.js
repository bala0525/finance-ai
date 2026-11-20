import React from "react";
import { Navigate, Outlet } from "react-router-dom";

import { useAuthContext } from "../context/AuthContext";
import Loader from "../components/common/Loader";

function ProtectedRoute() {
  const {
    isAuthenticated,
    loading,
  } = useAuthContext();

  if (loading) {
    return <Loader label="Loading your secure workspace..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
