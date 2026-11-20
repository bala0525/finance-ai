import React from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import Login from "../pages/auth/Login/Login";
import Signup from "../pages/auth/Signup/Signup";
import ForgotPassword from "../pages/auth/ForgotPassword/ForgotPassword";
import ResetPassword from "../pages/auth/ForgotPassword/ResetPassword";
import VerifyEmail from "../pages/auth/VerifyEmail/VerifyEmail";

import DashboardLayout from "../components/layout/DashboardLayout";
import ProtectedRoute from "./ProtectedRoute";
import PublicRoute from "./PublicRoute";
import Profile from "../pages/Profile/Profile";
import EmployeeWorkspace from "../pages/Employees/EmployeeWorkspace";
import { AdminGuard, RoleGuard, RoleLanding } from "./RoleGuard";
import UserManagement from "../pages/UserManagement/UserManagement";

const employeeRoutes = [
  { path: "accounts-payable", id: 1 },
  { path: "accounts-receivable", id: 2 },
  { path: "invoice-processing", id: 3 },
  { path: "reconciliation", id: 4 },
  { path: "finance-analyst", id: 5 },
  { path: "expense-employee", id: 6 },
  { path: "financial-reporting", id: 7 },
  { path: "fraud-detection", id: 8 },
];

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicRoute />}>
          <Route
            path="/"
            element={<Navigate to="/login" replace />}
          />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/forgot-password"
            element={<ForgotPassword />}
          />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            {employeeRoutes.map((employee) => (
              <Route
                key={employee.id}
                path={`/employees/${employee.path}`}
                element={
                  <RoleGuard agentPath={employee.path}>
                    <EmployeeWorkspace employeeId={employee.id} />
                  </RoleGuard>
                }
              />
            ))}

            <Route
              path="/employees"
              element={<RoleLanding />}
            />

            <Route path="/profile" element={<Profile />} />
            <Route path="/admin/users" element={<AdminGuard><UserManagement /></AdminGuard>} />

            <Route
              path="/settings"
              element={<Navigate to="/profile" replace />}
            />

            <Route
              index
              element={<RoleLanding />}
            />
          </Route>
        </Route>

        {/* Send unknown URLs to a valid entry route. */}
        <Route
          path="*"
          element={
            <RoleLanding />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
