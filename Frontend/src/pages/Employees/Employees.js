import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getEmployees } from "../../services/employeesService";

import "./Employees.css";

function Employees() {
  const navigate = useNavigate();

  const [employees, setEmployees] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadEmployees() {
      try {
        setLoading(true);
        setError("");

        const data = await getEmployees();

        if (isMounted) {
          setEmployees(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load AI employees. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadEmployees();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredEmployees = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return employees.filter((employee) => {
      const matchesSearch =
        normalizedSearch === "" ||
        employee.name.toLowerCase().includes(normalizedSearch) ||
        employee.description.toLowerCase().includes(normalizedSearch) ||
        employee.category.toLowerCase().includes(normalizedSearch);

      const matchesStatus =
        statusFilter === "ALL" ||
        employee.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [employees, searchTerm, statusFilter]);

  if (loading) {
    return (
      <div className="employees-loading">
        <div className="employees-loading-spinner" />
        <span>Loading AI finance workforce...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="employees-error">
        <span>!</span>

        <div>
          <strong>AI Employees unavailable</strong>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="employees-page">
      <section className="employees-page-header">
        <div>
          <span className="employees-eyebrow">
            FINANCE AI WORKFORCE
          </span>

          <h1>AI Employees</h1>

          <p>
            Manage and monitor the specialized AI employees
            supporting your finance operations.
          </p>
        </div>

        <div className="employees-header-count">
          <strong>{employees.length}</strong>
          <span>AI Employees</span>
        </div>
      </section>

      <section className="employees-toolbar">
        <div className="employees-search">
          <span className="employees-search-icon">⌕</span>

          <input
            type="text"
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
            placeholder="Search AI employees..."
            aria-label="Search AI employees"
          />
        </div>

        <select
          className="employees-filter"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value)
          }
          aria-label="Filter employees by status"
        >
          <option value="ALL">All Status</option>
          <option value="READY">Ready</option>
        </select>
      </section>

      <section className="employees-summary">
        <div>
          <span>VISIBLE EMPLOYEES</span>
          <strong>{filteredEmployees.length}</strong>
        </div>

        <div>
          <span>WORKFORCE STATUS</span>
          <strong>
            {employees.length > 0 ? "Operational" : "Unavailable"}
          </strong>
        </div>
      </section>

      {filteredEmployees.length === 0 ? (
        <section className="employees-empty">
          <div className="employees-empty-icon">⌕</div>

          <h2>No employees found</h2>

          <p>
            Try changing your search or status filter.
          </p>

          <button
            type="button"
            onClick={() => {
              setSearchTerm("");
              setStatusFilter("ALL");
            }}
          >
            Clear filters
          </button>
        </section>
      ) : (
        <section className="employees-grid">
          {filteredEmployees.map((employee) => (
            <article
              className="employee-card"
              key={employee.id}
            >
              <div className="employee-card-top">
                <span className="employee-number">
                  {employee.number}
                </span>

                <span className="employee-status">
                  <span className="employee-status-dot" />
                  {employee.status}
                </span>
              </div>

              <div className="employee-card-content">
                <span className="employee-category">
                  {employee.category}
                </span>

                <h2>{employee.name}</h2>

                <p>{employee.description}</p>
              </div>

              <div className="employee-card-output">
                <span>CORE OUTPUT</span>
                <strong>{employee.output}</strong>
              </div>

              <div className="employee-card-footer">
                <span>AI EMPLOYEE {employee.number}</span>

                <button
                  type="button"
                  onClick={() =>
                    navigate(`/employees/${employee.id}`)
                  }
                >
                  Open
                  <span>→</span>
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

export default Employees;
