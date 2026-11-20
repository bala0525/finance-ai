
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDashboardData } from "../../services/dashboardService";
import { SkeletonLoader } from "../../components/common/Loader";

import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      try {
        setLoading(true);
        setError("");

        const data = await getDashboardData();

        if (!data?.overview || !data?.systemStatus || !Array.isArray(data?.aiEmployees)) {
          throw new Error("The dashboard API returned an unexpected response.");
        }

        if (active) {
          setDashboardData(data);
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError.message ||
              "Unable to load dashboard data. Please try again."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="dashboard-page">
        <SkeletonLoader variant="cards" />
        <SkeletonLoader variant="workspace" rows={4} />
      </div>
    );
  }

  if (error || !dashboardData) {
    return (
      <div className="dashboard-error" role="alert">
        <span>!</span>
        <div>
          <strong>Dashboard unavailable</strong>
          <p>{error || "Dashboard data is not available."}</p>
          <button
            type="button"
            className="dashboard-secondary-button"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { overview, systemStatus, aiEmployees } = dashboardData;

  return (
    <div className="dashboard-page">
      <section className="dashboard-page-header">
        <div>
          <span className="dashboard-eyebrow">FINANCE INTELLIGENCE</span>
          <h1>Dashboard</h1>
          <p>
            Monitor your AI finance workforce, financial intelligence
            and knowledge operations from one workspace.
          </p>
        </div>

        <div className="dashboard-header-status">
          <span className="dashboard-status-dot" />
          {systemStatus.label}
        </div>
      </section>

      <section className="dashboard-overview-grid">
        <div className="dashboard-overview-card">
          <span className="dashboard-card-label">AI EMPLOYEES</span>
          <strong>{overview.aiEmployees}</strong>
          <small>Configured finance AI employees</small>
        </div>

        <div className="dashboard-overview-card">
          <span className="dashboard-card-label">DOCUMENTS</span>
          <strong>{overview.documents}</strong>
          <small>Documents recorded in the workspace</small>
        </div>

        <div className="dashboard-overview-card">
          <span className="dashboard-card-label">KNOWLEDGE BASE</span>
          <strong>{overview.knowledgeBase}</strong>
          <small>Indexed knowledge sources</small>
        </div>

        <div className="dashboard-overview-card">
          <span className="dashboard-card-label">AI CONVERSATIONS</span>
          <strong>{overview.conversations}</strong>
          <small>Recorded finance conversations</small>
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-header">
          <div>
            <span className="dashboard-section-eyebrow">
              FINANCE AI WORKFORCE
            </span>
            <h2>AI Employees</h2>
            <p>
              Specialized AI employees for finance operations and
              controlled financial intelligence.
            </p>
          </div>

          <button
            type="button"
            className="dashboard-secondary-button"
            onClick={() => navigate("/employees")}
          >
            View all <span>→</span>
          </button>
        </div>

        <div className="dashboard-employees-grid">
          {aiEmployees.map((employee) => (
            <div className="dashboard-employee-card" key={employee.id}>
              <div className="dashboard-employee-top">
                <span className="dashboard-employee-number">
                  {employee.number}
                </span>
                <span className="dashboard-employee-status">
                  {employee.status}
                </span>
              </div>

              <h3>{employee.name}</h3>
              <p>{employee.description}</p>

              <div className="dashboard-employee-output">
                <span>CORE OUTPUT</span>
                <strong>{employee.output}</strong>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="dashboard-action-panel">
          <div className="dashboard-panel-heading">
            <span className="dashboard-section-eyebrow">AI ASSISTANT</span>
            <h2>Finance AI Assistant</h2>
            <p>
              Ask questions about financial documents, reports and
              your organization's knowledge base.
            </p>
          </div>

          <button
            type="button"
            className="dashboard-primary-button"
            onClick={() => navigate("/assistant")}
          >
            Open Assistant <span>→</span>
          </button>
        </div>

        <div className="dashboard-action-panel">
          <div className="dashboard-panel-heading">
            <span className="dashboard-section-eyebrow">KNOWLEDGE</span>
            <h2>Knowledge Base</h2>
            <p>
              Manage financial documents and their availability to
              authorized AI workflows.
            </p>
          </div>

          <button
            type="button"
            className="dashboard-primary-button"
            onClick={() => navigate("/documents")}
          >
            Manage Documents <span>→</span>
          </button>
        </div>
      </section>
    </div>
  );
}

export default Dashboard;