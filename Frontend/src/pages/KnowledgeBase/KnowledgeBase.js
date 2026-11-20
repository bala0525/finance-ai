import React, {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getKnowledgeSources,
  reindexKnowledgeSource,
} from "../../services/knowledgeBaseService";

import {
  knowledgeCategories,
} from "../../data/knowledgeBaseData";

import "./KnowledgeBase.css";

function KnowledgeBase() {
  const [sources, setSources] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] =
    useState("All Categories");

  const [loading, setLoading] = useState(true);
  const [reindexingId, setReindexingId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadKnowledgeSources() {
      try {
        setLoading(true);
        setError("");

        const data = await getKnowledgeSources();

        if (isMounted) {
          setSources(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load the knowledge base. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadKnowledgeSources();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredSources = useMemo(() => {
    const normalizedSearch = searchTerm
      .trim()
      .toLowerCase();

    return sources.filter((source) => {
      const matchesSearch =
        normalizedSearch === "" ||
        source.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        source.category
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesCategory =
        categoryFilter === "All Categories" ||
        source.category === categoryFilter;

      return matchesSearch && matchesCategory;
    });
  }, [sources, searchTerm, categoryFilter]);

  const indexedCount = sources.filter(
  (source) => source.status === "INDEXED"
).length;

const indexingCount = sources.filter(
  (source) => source.status === "INDEXING"
).length;

const totalChunks = sources.reduce(
  (total, source) => total + source.chunks,
  0
);

  const handleReindex = async (sourceId) => {
    if (reindexingId) {
      return;
    }

    setReindexingId(sourceId);
    setError("");

    try {
      await reindexKnowledgeSource(sourceId);

      setSources((currentSources) =>
        currentSources.map((source) =>
          source.id === sourceId
            ? {
                ...source,
                status: "INDEXING",
                indexedAt: "Indexing...",
              }
            : source
        )
      );

      setTimeout(() => {
        setSources((currentSources) =>
          currentSources.map((source) =>
            source.id === sourceId
              ? {
                  ...source,
                  status: "INDEXED",
                  indexedAt: "Just now",
                  chunks:
                    source.chunks > 0
                      ? source.chunks
                      : 64,
                }
              : source
          )
        );

        setReindexingId(null);
      }, 1200);
    } catch (requestError) {
      setError(
        "Unable to reindex the selected source."
      );
      setReindexingId(null);
    }
  };

  const handleClearFilters = () => {
    setSearchTerm("");
    setCategoryFilter("All Categories");
  };

  const getStatusClass = (status) => {
    switch (status) {
      case "INDEXED":
        return "knowledge-status-indexed";

      case "INDEXING":
        return "knowledge-status-indexing";

      case "PENDING":
        return "knowledge-status-pending";

      default:
        return "";
    }
  };

  if (loading) {
    return (
      <div className="knowledge-loading">
        <div className="knowledge-loading-spinner" />
        <span>
          Loading knowledge base...
        </span>
      </div>
    );
  }

  if (error && sources.length === 0) {
    return (
      <div className="knowledge-error">
        <span>!</span>

        <div>
          <strong>
            Knowledge Base unavailable
          </strong>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="knowledge-page">
      <section className="knowledge-page-header">
        <div>
          <span className="knowledge-eyebrow">
            RAG KNOWLEDGE LAYER
          </span>

          <h1>Knowledge Base</h1>

          <p>
            Manage the financial knowledge sources available
            to the AI workforce for grounded retrieval and
            analysis.
          </p>
        </div>

        <div className="knowledge-header-status">
          <span className="knowledge-status-dot" />
          KNOWLEDGE SYSTEM READY
        </div>
      </section>

      {error && sources.length > 0 && (
        <div className="knowledge-error-message">
          <span>!</span>
          {error}
        </div>
      )}

      <section className="knowledge-overview">
        <div className="knowledge-overview-card">
          <span>KNOWLEDGE SOURCES</span>
          <strong>{sources.length}</strong>
          <small>Connected sources</small>
        </div>

        <div className="knowledge-overview-card">
          <span>INDEXED SOURCES</span>
          <strong>{indexedCount}</strong>
          <small>Available for retrieval</small>
        </div>

        <div className="knowledge-overview-card">
          <span>INDEXING</span>
          <strong>{indexingCount}</strong>
          <small>Currently being indexed</small>
        </div>

        <div className="knowledge-overview-card">
          <span>KNOWLEDGE CHUNKS</span>
          <strong>{totalChunks}</strong>
          <small>Total indexed chunks</small>
        </div>
      </section>

      <section className="knowledge-system-panel">
        <div className="knowledge-system-icon">
          ◈
        </div>

        <div className="knowledge-system-content">
          <span>RAG KNOWLEDGE PIPELINE</span>
          <strong>
            Documents → Parsing → Chunking → Embeddings → Retrieval
          </strong>
          <p>
            Financial documents will be transformed into
            searchable knowledge for authorized AI employees.
          </p>
        </div>

        <div className="knowledge-system-state">
          <span />
          OPERATIONAL
        </div>
      </section>

      <section className="knowledge-toolbar">
        <div className="knowledge-search">
          <span>⌕</span>

          <input
            type="text"
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
            placeholder="Search knowledge sources..."
            aria-label="Search knowledge sources"
          />
        </div>

        <select
          className="knowledge-filter"
          value={categoryFilter}
          onChange={(event) =>
            setCategoryFilter(event.target.value)
          }
          aria-label="Filter knowledge sources by category"
        >
          {knowledgeCategories.map((category) => (
            <option
              key={category}
              value={category}
            >
              {category}
            </option>
          ))}
        </select>
      </section>

      <section className="knowledge-table-container">
        <div className="knowledge-table-header">
          <div>
            <span className="knowledge-section-eyebrow">
              INDEXED KNOWLEDGE
            </span>

            <h2>Knowledge Sources</h2>
          </div>

          <span className="knowledge-visible-count">
            {filteredSources.length} visible
          </span>
        </div>

        {filteredSources.length === 0 ? (
          <div className="knowledge-empty">
            <div className="knowledge-empty-icon">
              ◇
            </div>

            <h2>No knowledge sources found</h2>

            <p>
              No sources match your current search or filter.
            </p>

            <button
              type="button"
              onClick={handleClearFilters}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="knowledge-table-wrapper">
            <table className="knowledge-table">
              <thead>
                <tr>
                  <th>SOURCE</th>
                  <th>CATEGORY</th>
                  <th>CHUNKS</th>
                  <th>LAST INDEXED</th>
                  <th>STATUS</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {filteredSources.map((source) => (
                  <tr key={source.id}>
                    <td>
                      <div className="knowledge-source-cell">
                        <div className="knowledge-source-icon">
                          {source.sourceType === "DOCUMENT"
                            ? "D"
                            : "K"}
                        </div>

                        <div>
                          <strong>{source.name}</strong>
                          <span>
                            Source ID #{source.id}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="knowledge-category">
                        {source.category}
                      </span>
                    </td>

                    <td>
                      <span className="knowledge-chunks">
                        {source.chunks || "—"}
                      </span>
                    </td>

                    <td>
                      <span className="knowledge-indexed-date">
                        {source.indexedAt}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`knowledge-status ${getStatusClass(
                          source.status
                        )}`}
                      >
                        <i />
                        {source.status}
                      </span>
                    </td>

                    <td>
                      <button
                        type="button"
                        className="knowledge-reindex-button"
                        disabled={
                          reindexingId === source.id
                        }
                        onClick={() =>
                          handleReindex(source.id)
                        }
                      >
                        {reindexingId === source.id
                          ? "Indexing..."
                          : "Reindex"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="knowledge-security-note">
        <div className="knowledge-security-icon">
          ✓
        </div>

        <div>
          <strong>
            Retrieval access is backend-controlled
          </strong>

          <p>
            In production, document ownership, tenant
            isolation and employee permissions will be
            enforced by the backend before any knowledge is
            retrieved.
          </p>
        </div>
      </section>
    </div>
  );
}

export default KnowledgeBase;
