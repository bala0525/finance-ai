import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthContext } from "../../context/AuthContext";
import LogoutConfirmModal from "../common/LogoutConfirmModal";
import { canAccessAgent, getRoleName } from "../../config/roleAccess";
import "./DashboardLayout.css";
import NotificationBell from "./NotificationBell";

const financeAgents = [
  { path: "accounts-payable", label: "Accounts Payable", icon: "▤" },
  { path: "accounts-receivable", label: "Accounts Receivable", icon: "◉" },
  { path: "invoice-processing", label: "Invoice Processing", icon: "▧" },
  { path: "reconciliation", label: "Reconciliation", icon: "⇄" },
  { path: "finance-analyst", label: "Finance Analyst", icon: "⌁" },
  { path: "expense-employee", label: "Expense Employee", icon: "▣" },
  { path: "financial-reporting", label: "Financial Reporting", icon: "▥" },
  { path: "fraud-detection", label: "Fraud Detection", icon: "⬡" },
];

function DashboardLayout() {
  const navigate = useNavigate();
  const { currentUser, logout } = useAuthContext();
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  const userName = currentUser?.full_name || "Finance User";
  const userInitial = userName.trim().charAt(0).toUpperCase() || "F";

  const userRole = getRoleName(currentUser);
  const visibleFinanceAgents = financeAgents.filter((agent) => canAccessAgent(currentUser, agent.path));
  const workflowResponsibilities = {
    "Employee / Requester": "Submit invoices and expenses; track approval status and corrections.",
    "Finance User": "Verify requests, process approved supplier payments and record transfer proof.",
    "Finance Manager": "Review and approve invoices and expense requests before final authorization.",
    "Chief Accountant": "Finalise AP approvals, authorise payment batches and monitor ledger controls.",
    Administrator: "Manage users, complete final AR/expense approvals and oversee finance operations.",
  };

  function handleLogoutClick() {
    setShowLogoutModal(true);
  }

  function handleLogoutCancel() {
    setShowLogoutModal(false);
  }

  function handleLogoutConfirm() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar-header">
          <div className="dashboard-brand-mark">A</div>
          <div className="dashboard-brand-text">
            <strong>Azentmart AI</strong>
            <span>FINANCE INTELLIGENCE</span>
          </div>
        </div>

        <nav className="dashboard-navigation" aria-label="Main navigation">
          {userRole === "Administrator" && (
            <div className="dashboard-navigation-section">
              <span className="dashboard-navigation-title">ADMINISTRATION</span>
              <NavLink to="/admin/users" className={({ isActive }) => `dashboard-agent-nav ${isActive ? "active" : ""}`}>
                <span className="dashboard-agent-icon" aria-hidden="true">♙</span>
                <span className="dashboard-agent-name">User Management</span>
                <span className="dashboard-agent-indicator" aria-hidden="true" />
              </NavLink>
            </div>
          )}
          <div className="dashboard-navigation-section">
            <span className="dashboard-navigation-title">FINANCE AI EMPLOYEES</span>

            <div className="dashboard-agent-list">
              {visibleFinanceAgents.map((agent) => (
                <NavLink
                  key={agent.path}
                  to={`/employees/${agent.path}`}
                  className={({ isActive }) =>
                    `dashboard-agent-nav ${isActive ? "active" : ""}`
                  }
                  title={agent.label}
                >
                  <span className="dashboard-agent-icon" aria-hidden="true">
                    {agent.icon}
                  </span>
                  <span className="dashboard-agent-name">{agent.label}</span>
                  <span className="dashboard-agent-indicator" aria-hidden="true" />
                </NavLink>
              ))}
            </div>
          </div>
        </nav>

        <div style={{ margin: "12px 14px", padding: "12px", border: "1px solid rgba(34, 211, 238, 0.18)", borderRadius: "10px", background: "rgba(8, 145, 178, 0.07)" }}>
          <div style={{ color: "#67e8f9", fontSize: "10px", fontWeight: 700, letterSpacing: "0.12em", marginBottom: "6px" }}>YOUR WORKFLOW ROLE</div>
          <div style={{ color: "#e2e8f0", fontSize: "11px", lineHeight: 1.5 }}>{workflowResponsibilities[userRole] || "Access finance workspaces assigned to your role."}</div>
        </div>

        <div className="dashboard-sidebar-footer">
          <button
            type="button"
            className="dashboard-user-card"
            onClick={() => navigate("/profile")}
          >
            <span className="dashboard-user-avatar">{userInitial}</span>
            <span className="dashboard-user-info">
              <strong>{userName}</strong>
              <span>{userRole}</span>
            </span>
          </button>

          <button type="button" className="dashboard-logout-button" onClick={handleLogoutClick}>
            <span aria-hidden="true">↪</span>
            <span>Log Out</span>
          </button>
        </div>
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <span className="dashboard-topbar-label">FINANCE INTELLIGENCE PLATFORM</span>
          <div style={{display:"flex",alignItems:"center",gap:"12px"}}>
          <NotificationBell />
          <button
            type="button"
            className="dashboard-topbar-user"
            onClick={() => navigate("/profile")}
            aria-label="Open profile"
          >
            <span className="dashboard-topbar-avatar">{userInitial}</span>
            <span className="dashboard-topbar-user-info">
              <strong>{userName}</strong>
              <span>{userRole}</span>
            </span>
          </button>
          </div>
        </header>

        <main className="dashboard-content">
          <Outlet />
        </main>
      </div>

      <LogoutConfirmModal
        open={showLogoutModal}
        onCancel={handleLogoutCancel}
        onLogout={handleLogoutConfirm}
      />
    </div>
  );
}

export default DashboardLayout;
