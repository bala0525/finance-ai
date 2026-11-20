import React, {
  useEffect,
  useMemo,
  useState,
} from "react";

import { getAnalyticsData } from "../../services/analyticsService";

import "./Analytics.css";

function Analytics() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadAnalytics() {
      try {
        setLoading(true);
        setError("");

        const data = await getAnalyticsData();

        if (isMounted) {
          setAnalytics(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load analytics. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadAnalytics();

    return () => {
      isMounted = false;
    };
  }, []);

  const maxQueryValue = useMemo(() => {
    if (!analytics?.trend?.length) {
      return 1;
    }

    return Math.max(
      ...analytics.trend.map((item) => item.queries)
    );
  }, [analytics]);

  if (loading) {
    return (
      <div className="analytics-loading">
        <div className="analytics-loading-spinner" />
        <span>Loading analytics...</span>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="analytics-error">
        <div className="analytics-error-icon">!</div>

        <div>
          <strong>Analytics unavailable</strong>
          <p>
            {error ||
              "Analytics data could not be loaded."}
          </p>
        </div>
      </div>
    );
  }

  const {
    overview,
    trend,
    employees,
    recentActivity,
  } = analytics;

  return (
    <div className="analytics-page">
      <section className="analytics-page-header">
        <div>
          <span className="analytics-eyebrow">
            PLATFORM INTELLIGENCE
          </span>

          <h1>Analytics</h1>

          <p>
            Monitor AI workforce activity, processing volume,
            task performance and operational trends.
          </p>
        </div>

        <div className="analytics-period">
          <span className="analytics-live-dot" />
          LAST 7 DAYS
        </div>
      </section>

      <section className="analytics-overview">
        <div className="analytics-overview-card">
          <div className="analytics-card-top">
            <span>AI QUERIES</span>
            <div className="analytics-card-icon">✦</div>
          </div>

          <strong>{overview.totalQueries.toLocaleString()}</strong>

          <div className="analytics-card-bottom">
            <span className="analytics-positive">
              {overview.queriesChange}
            </span>
            <span>vs previous period</span>
          </div>
        </div>

        <div className="analytics-overview-card">
          <div className="analytics-card-top">
            <span>DOCUMENTS PROCESSED</span>
            <div className="analytics-card-icon">▤</div>
          </div>

          <strong>{overview.documentsProcessed}</strong>

          <div className="analytics-card-bottom">
            <span className="analytics-positive">
              {overview.documentsChange}
            </span>
            <span>vs previous period</span>
          </div>
        </div>

        <div className="analytics-overview-card">
          <div className="analytics-card-top">
            <span>SUCCESS RATE</span>
            <div className="analytics-card-icon">✓</div>
          </div>

          <strong>{overview.successRate}</strong>

          <div className="analytics-card-bottom">
            <span className="analytics-positive">
              {overview.successfulTasks}
            </span>
            <span>successful tasks</span>
          </div>
        </div>

        <div className="analytics-overview-card">
          <div className="analytics-card-top">
            <span>ACTIVE EMPLOYEES</span>
            <div className="analytics-card-icon">◈</div>
          </div>

          <strong>{overview.activeEmployees}</strong>

          <div className="analytics-card-bottom">
            <span className="analytics-active">
              OPERATIONAL
            </span>
            <span>AI employees</span>
          </div>
        </div>
      </section>

      <section className="analytics-main-grid">
        <div className="analytics-panel analytics-trend-panel">
          <div className="analytics-panel-header">
            <div>
              <span className="analytics-panel-eyebrow">
                ACTIVITY TREND
              </span>
              <h2>AI Workforce Activity</h2>
            </div>

            <div className="analytics-legend">
              <span>
                <i className="analytics-legend-query" />
                Queries
              </span>

              <span>
                <i className="analytics-legend-task" />
                Tasks
              </span>
            </div>
          </div>

          <div className="analytics-chart">
            <div className="analytics-chart-y">
              <span>{maxQueryValue}</span>
              <span>
                {Math.round(maxQueryValue * 0.75)}
              </span>
              <span>
                {Math.round(maxQueryValue * 0.5)}
              </span>
              <span>
                {Math.round(maxQueryValue * 0.25)}
              </span>
              <span>0</span>
            </div>

            <div className="analytics-chart-area">
              <div className="analytics-chart-grid">
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>

              <div className="analytics-bars">
                {trend.map((item) => {
                  const queryHeight =
                    (item.queries / maxQueryValue) *
                    100;

                  const taskHeight =
                    (item.tasks / maxQueryValue) *
                    100;

                  return (
                    <div
                      className="analytics-bar-group"
                      key={item.day}
                    >
                      <div className="analytics-bar-values">
                        <div
                          className="analytics-bar query-bar"
                          style={{
                            height: `${queryHeight}%`,
                          }}
                          title={`Queries: ${item.queries}`}
                        />

                        <div
                          className="analytics-bar task-bar"
                          style={{
                            height: `${taskHeight}%`,
                          }}
                          title={`Tasks: ${item.tasks}`}
                        />
                      </div>

                      <span>{item.day}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="analytics-panel analytics-status-panel">
          <div className="analytics-panel-header">
            <div>
              <span className="analytics-panel-eyebrow">
                SYSTEM HEALTH
              </span>
              <h2>Operational Status</h2>
            </div>
          </div>

          <div className="analytics-health">
            <div className="analytics-health-ring">
              <strong>98%</strong>
              <span>HEALTH</span>
            </div>

            <div className="analytics-health-details">
              <div>
                <span>AI Employees</span>
                <strong>8 / 8</strong>
              </div>

              <div>
                <span>Knowledge Retrieval</span>
                <strong>Operational</strong>
              </div>

              <div>
                <span>Processing Queue</span>
                <strong>Normal</strong>
              </div>
            </div>
          </div>

          <div className="analytics-health-footer">
            <span className="analytics-live-dot" />
            All core systems operational
          </div>
        </div>
      </section>

      <section className="analytics-bottom-grid">
        <div className="analytics-panel analytics-employees-panel">
          <div className="analytics-panel-header">
            <div>
              <span className="analytics-panel-eyebrow">
                AI WORKFORCE
              </span>
              <h2>Employee Performance</h2>
            </div>

            <span className="analytics-panel-count">
              {employees.length} employees
            </span>
          </div>

          <div className="analytics-employee-list">
            {employees.map((employee) => (
              <div
                className="analytics-employee-row"
                key={employee.id}
              >
                <div className="analytics-employee-info">
                  <div className="analytics-employee-avatar">
                    {employee.shortName.charAt(0)}
                  </div>

                  <div>
                    <strong>{employee.shortName}</strong>
                    <span>{employee.tasks} tasks</span>
                  </div>
                </div>

                <div className="analytics-employee-progress">
                  <div className="analytics-progress-track">
                    <div
                      className="analytics-progress-value"
                      style={{
                        width: employee.successRate,
                      }}
                    />
                  </div>

                  <span>{employee.successRate}</span>
                </div>

                <span className="analytics-employee-status">
                  {employee.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="analytics-panel analytics-activity-panel">
          <div className="analytics-panel-header">
            <div>
              <span className="analytics-panel-eyebrow">
                LIVE OPERATIONS
              </span>
              <h2>Recent Activity</h2>
            </div>

            <span className="analytics-live-label">
              LIVE
            </span>
          </div>

          <div className="analytics-activity-list">
            {recentActivity.map((activity) => (
              <div
                className="analytics-activity-row"
                key={activity.id}
              >
                <div className="analytics-activity-dot" />

                <div className="analytics-activity-content">
                  <strong>{activity.action}</strong>
                  <span>{activity.employee}</span>
                </div>

                <div className="analytics-activity-meta">
                  <span>{activity.time}</span>
                  <small>{activity.status}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export default Analytics;
