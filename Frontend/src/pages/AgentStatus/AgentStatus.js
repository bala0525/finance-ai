import React, { useEffect, useMemo, useState } from "react";
import { getAgentStatusData } from "../../services/agentStatusService";
import "./AgentStatus.css";

function AgentStatus() {
  const [data, setData] = useState({
    overview: null,
    agents: [],
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    let isMounted = true;

    async function loadAgentStatus() {
      try {
        setLoading(true);
        setError("");

        const result = await getAgentStatusData();

        if (isMounted) {
          setData(result);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            requestError?.message ||
              "Unable to load agent status."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadAgentStatus();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredAgents = useMemo(() => {
    return data.agents.filter((agent) => {
      const matchesSearch =
        agent.name
          .toLowerCase()
          .includes(searchTerm.toLowerCase()) ||
        agent.type
          .toLowerCase()
          .includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === "ALL" ||
        agent.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [data.agents, searchTerm, statusFilter]);

  const overview = data.overview || {
    totalAgents: 0,
    activeAgents: 0,
    idleAgents: 0,
    failedAgents: 0,
  };

  return (
    <section className="agent-status-page">
      <div className="agent-status-header">
        <div>
          <span className="agent-status-eyebrow">
            SYSTEM MONITORING
          </span>

          <h1>Agent Status</h1>

          <p>
            Monitor the health, activity and execution state of
            your AI finance employees.
          </p>
        </div>

        <div className="agent-status-live">
          <span className="agent-status-live-dot" />
          <span>LIVE MONITORING</span>
        </div>
      </div>

      <div className="agent-status-overview">
        <div className="agent-status-overview-card">
          <div className="agent-status-card-icon">◈</div>

          <div>
            <span>Total Agents</span>
            <strong>{overview.totalAgents}</strong>
          </div>
        </div>

        <div className="agent-status-overview-card">
          <div className="agent-status-card-icon">●</div>

          <div>
            <span>Active</span>
            <strong>{overview.activeAgents}</strong>
          </div>
        </div>

        <div className="agent-status-overview-card">
          <div className="agent-status-card-icon">◌</div>

          <div>
            <span>Idle</span>
            <strong>{overview.idleAgents}</strong>
          </div>
        </div>

        <div className="agent-status-overview-card">
          <div className="agent-status-card-icon">!</div>

          <div>
            <span>Failed</span>
            <strong>{overview.failedAgents}</strong>
          </div>
        </div>
      </div>

      <div className="agent-status-toolbar">
        <div className="agent-status-search">
          <span>⌕</span>

          <input
            type="text"
            placeholder="Search AI employees..."
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
          />
        </div>

        <div className="agent-status-filter">
          <label htmlFor="agent-status-filter">
            Status
          </label>

          <select
            id="agent-status-filter"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value)
            }
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="IDLE">Idle</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {loading && (
        <div className="agent-status-state">
          <div className="agent-status-loader" />
          <p>Loading agent status...</p>
        </div>
      )}

      {!loading && error && (
        <div className="agent-status-state agent-status-error">
          <strong>Unable to load agent status</strong>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && filteredAgents.length === 0 && (
        <div className="agent-status-state">
          <div className="agent-status-empty-icon">⌕</div>
          <strong>No agents found</strong>
          <p>
            Try changing your search term or status filter.
          </p>
        </div>
      )}

      {!loading && !error && filteredAgents.length > 0 && (
        <div className="agent-status-table-wrapper">
          <div className="agent-status-table-header">
            <div>
              <span className="agent-status-section-label">
                AI EMPLOYEES
              </span>

              <h2>Agent Runtime Status</h2>
            </div>

            <span className="agent-status-count">
              {filteredAgents.length} agents
            </span>
          </div>

          <div className="agent-status-table-scroll">
            <table className="agent-status-table">
              <thead>
                <tr>
                  <th>AI Employee</th>
                  <th>Status</th>
                  <th>Health</th>
                  <th>Tasks Today</th>
                  <th>Success Rate</th>
                  <th>Last Activity</th>
                </tr>
              </thead>

              <tbody>
                {filteredAgents.map((agent) => (
                  <tr key={agent.id}>
                    <td>
                      <div className="agent-status-agent">
                        <div className="agent-status-agent-icon">
                          ◈
                        </div>

                        <div>
                          <strong>{agent.name}</strong>
                          <span>{agent.type}</span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span
                        className={`agent-status-badge ${agent.status.toLowerCase()}`}
                      >
                        <i />
                        {agent.status}
                      </span>
                    </td>

                    <td>
                      <span className="agent-status-health">
                        <i />
                        {agent.health}
                      </span>
                    </td>

                    <td>
                      <span className="agent-status-number">
                        {agent.tasksToday}
                      </span>
                    </td>

                    <td>
                      <span className="agent-status-success">
                        {agent.successRate}
                      </span>
                    </td>

                    <td>
                      <span className="agent-status-last-activity">
                        {agent.lastActivity}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !error && filteredAgents.length > 0 && (
        <div className="agent-status-bottom-grid">
          <div className="agent-status-info-card">
            <div className="agent-status-info-header">
              <div>
                <span className="agent-status-section-label">
                  SYSTEM HEALTH
                </span>
                <h2>Runtime Environment</h2>
              </div>

              <span className="agent-status-healthy-badge">
                OPERATIONAL
              </span>
            </div>

            <div className="agent-status-health-list">
              <div>
                <span>AI Runtime</span>
                <strong>Operational</strong>
              </div>

              <div>
                <span>Knowledge Retrieval</span>
                <strong>Operational</strong>
              </div>

              <div>
                <span>Document Processing</span>
                <strong>Operational</strong>
              </div>

              <div>
                <span>Task Queue</span>
                <strong>Operational</strong>
              </div>
            </div>
          </div>

          <div className="agent-status-info-card">
            <div className="agent-status-info-header">
              <div>
                <span className="agent-status-section-label">
                  EXECUTION POLICY
                </span>
                <h2>Controlled Operations</h2>
              </div>

              <span className="agent-status-policy-icon">
                ✓
              </span>
            </div>

            <p className="agent-status-policy-text">
              AI employees operate within configured permissions,
              document access rules and controlled finance workflows.
            </p>

            <div className="agent-status-policy-items">
              <span>✓ Role-based access</span>
              <span>✓ Document isolation</span>
              <span>✓ Audit logging</span>
              <span>✓ Controlled actions</span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default AgentStatus;
