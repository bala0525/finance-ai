import React, {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  generateReport,
  getReportsData,
} from "../../services/reportsService";

import {
  reportCategories,
  reportStatuses,
} from "../../data/reportsData";

import "./Reports.css";

function Reports() {
  const [reports, setReports] = useState([]);
  const [overview, setOverview] = useState(null);

  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] =
    useState("All Categories");
  const [statusFilter, setStatusFilter] =
    useState("All Statuses");

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadReports() {
      try {
        setLoading(true);
        setError("");

        const data = await getReportsData();

        if (isMounted) {
          setReports(data.reports);
          setOverview(data.overview);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load reports. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadReports();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredReports = useMemo(() => {
    const normalizedSearch =
      searchTerm.trim().toLowerCase();

    return reports.filter((report) => {
      const matchesSearch =
        normalizedSearch === "" ||
        report.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        report.category
          .toLowerCase()
          .includes(normalizedSearch) ||
        report.generatedBy
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesCategory =
        categoryFilter === "All Categories" ||
        report.category === categoryFilter;

      const matchesStatus =
        statusFilter === "All Statuses" ||
        report.status === statusFilter;

      return (
        matchesSearch &&
        matchesCategory &&
        matchesStatus
      );
    });
  }, [
    reports,
    searchTerm,
    categoryFilter,
    statusFilter,
  ]);

  const handleGenerateReport = async () => {
    if (generating) {
      return;
    }

    setGenerating(true);
    setError("");

    try {
      const generatedReport =
        await generateReport({
          name: "New Financial Report",
        });

      setReports((currentReports) => [
        generatedReport,
        ...currentReports,
      ]);

      setGenerating(false);
    } catch (requestError) {
      setError(
        "Unable to generate the report."
      );
      setGenerating(false);
    }
  };

  const handleClearFilters = () => {
    setSearchTerm("");
    setCategoryFilter("All Categories");
    setStatusFilter("All Statuses");
  };

  const getStatusClass = (status) => {
    switch (status) {
      case "READY":
        return "reports-status-ready";

      case "GENERATING":
        return "reports-status-generating";

      case "SCHEDULED":
        return "reports-status-scheduled";

      case "PENDING":
        return "reports-status-pending";

      default:
        return "";
    }
  };

  if (loading) {
    return (
      <div className="reports-loading">
        <div className="reports-loading-spinner" />
        <span>Loading reports...</span>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="reports-error">
        <div className="reports-error-icon">!</div>

        <div>
          <strong>Reports unavailable</strong>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="reports-page">
      <section className="reports-page-header">
        <div>
          <span className="reports-eyebrow">
            FINANCIAL INTELLIGENCE
          </span>

          <h1>Reports</h1>

          <p>
            Generate, manage and review financial reports
            produced by the AI workforce.
          </p>
        </div>

        <button
          type="button"
          className="reports-generate-button"
          onClick={handleGenerateReport}
          disabled={generating}
        >
          <span>{generating ? "◌" : "+"}</span>
          {generating
            ? "Generating..."
            : "Generate Report"}
        </button>
      </section>

      {error && overview && (
        <div className="reports-error-message">
          <span>!</span>
          {error}
        </div>
      )}

      <section className="reports-overview">
        <div className="reports-overview-card">
          <span>TOTAL REPORTS</span>
          <strong>{overview.totalReports}</strong>
          <small>Available reports</small>
        </div>

        <div className="reports-overview-card">
          <span>GENERATED THIS MONTH</span>
          <strong>
            {overview.generatedThisMonth}
          </strong>
          <small>Reports completed</small>
        </div>

        <div className="reports-overview-card">
          <span>SCHEDULED</span>
          <strong>{overview.scheduledReports}</strong>
          <small>Automated reports</small>
        </div>

        <div className="reports-overview-card">
          <span>PENDING</span>
          <strong>{overview.pendingReports}</strong>
          <small>Awaiting generation</small>
        </div>
      </section>

      <section className="reports-toolbar">
        <div className="reports-search">
          <span>⌕</span>

          <input
            type="text"
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
            placeholder="Search reports..."
            aria-label="Search reports"
          />
        </div>

        <select
          className="reports-filter"
          value={categoryFilter}
          onChange={(event) =>
            setCategoryFilter(event.target.value)
          }
          aria-label="Filter reports by category"
        >
          {reportCategories.map((category) => (
            <option
              key={category}
              value={category}
            >
              {category}
            </option>
          ))}
        </select>

        <select
          className="reports-filter reports-status-filter"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value)
          }
          aria-label="Filter reports by status"
        >
          {reportStatuses.map((status) => (
            <option
              key={status}
              value={status}
            >
              {status}
            </option>
          ))}
        </select>
      </section>

      <section className="reports-table-container">
        <div className="reports-table-header">
          <div>
            <span className="reports-section-eyebrow">
              REPORT LIBRARY
            </span>

            <h2>Financial Reports</h2>
          </div>

          <span className="reports-visible-count">
            {filteredReports.length} visible
          </span>
        </div>

        {filteredReports.length === 0 ? (
          <div className="reports-empty">
            <div className="reports-empty-icon">
              ▦
            </div>

            <h2>No reports found</h2>

            <p>
              No reports match your current search or
              filter selection.
            </p>

            <button
              type="button"
              onClick={handleClearFilters}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="reports-table-wrapper">
            <table className="reports-table">
              <thead>
                <tr>
                  <th>REPORT</th>
                  <th>CATEGORY</th>
                  <th>PERIOD</th>
                  <th>GENERATED BY</th>
                  <th>STATUS</th>
                  <th>FORMAT</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {filteredReports.map((report) => (
                  <tr key={report.id}>
                    <td>
                      <div className="reports-name-cell">
                        <div className="reports-file-icon">
                          {report.format === "XLSX"
                            ? "X"
                            : "P"}
                        </div>

                        <div>
                          <strong>
                            {report.name}
                          </strong>

                          <span>
                            {report.frequency} ·{" "}
                            {report.generatedAt}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="reports-category">
                        {report.category}
                      </span>
                    </td>

                    <td>
                      <span className="reports-period">
                        {report.period}
                      </span>
                    </td>

                    <td>
                      <span className="reports-generated-by">
                        {report.generatedBy}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`reports-status ${getStatusClass(
                          report.status
                        )}`}
                      >
                        <i />
                        {report.status}
                      </span>
                    </td>

                    <td>
                      <span className="reports-format">
                        {report.format}
                      </span>
                    </td>

                    <td>
                      {report.status === "READY" ? (
                        <button
                          type="button"
                          className="reports-action-button"
                        >
                          View
                        </button>
                      ) : (
                        <span className="reports-action-disabled">
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="reports-automation-panel">
        <div className="reports-automation-icon">
          ◈
        </div>

        <div className="reports-automation-content">
          <span>AI REPORTING AUTOMATION</span>

          <strong>
            Automated financial reporting is ready for
            backend integration
          </strong>

          <p>
            Scheduled reports will be generated by authorized
            AI employees and stored through the secure backend
            reporting pipeline.
          </p>
        </div>

        <div className="reports-automation-status">
          <span />
          SYSTEM READY
        </div>
      </section>
    </div>
  );
}

export default Reports;
