import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getDocuments,
  uploadDocument,
} from "../../services/documentsService";

import { documentCategories } from "../../data/documentsData";

import "./Documents.css";

function Documents() {
  const fileInputRef = useRef(null);

  const [documents, setDocuments] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] =
    useState("All Categories");

  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadDocuments() {
      try {
        setLoading(true);
        setError("");

        const data = await getDocuments();

        if (isMounted) {
          setDocuments(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load documents. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadDocuments();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredDocuments = useMemo(() => {
    const normalizedSearch = searchTerm
      .trim()
      .toLowerCase();

    return documents.filter((document) => {
      const matchesSearch =
        normalizedSearch === "" ||
        document.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        document.category
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesStatus =
        statusFilter === "ALL" ||
        document.status === statusFilter;

      const matchesCategory =
        categoryFilter === "All Categories" ||
        document.category === categoryFilter;

      return (
        matchesSearch &&
        matchesStatus &&
        matchesCategory
      );
    });
  }, [
    documents,
    searchTerm,
    statusFilter,
    categoryFilter,
  ]);

  const processedCount = documents.filter(
    (document) => document.status === "PROCESSED"
  ).length;

  const processingCount = documents.filter(
    (document) => document.status === "PROCESSING"
  ).length;

  const pendingCount = documents.filter(
    (document) => document.status === "PENDING"
  ).length;

  const handleUploadClick = () => {
    setUploadMessage("");
    setError("");
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setUploading(true);
    setUploadMessage("");
    setError("");

    try {
      const newDocument = await uploadDocument(file);

      setDocuments((currentDocuments) => [
        newDocument,
        ...currentDocuments,
      ]);

      setUploadMessage(
        `"${file.name}" added and queued for processing.`
      );
    } catch (uploadError) {
      setError(
        "Unable to upload the document. Please try again."
      );
    } finally {
      setUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleClearFilters = () => {
    setSearchTerm("");
    setStatusFilter("ALL");
    setCategoryFilter("All Categories");
  };

  const getStatusClass = (status) => {
    switch (status) {
      case "PROCESSED":
        return "document-status-processed";

      case "PROCESSING":
        return "document-status-processing";

      case "PENDING":
        return "document-status-pending";

      default:
        return "";
    }
  };

  if (loading) {
    return (
      <div className="documents-loading">
        <div className="documents-loading-spinner" />
        <span>Loading document workspace...</span>
      </div>
    );
  }

  if (error && documents.length === 0) {
    return (
      <div className="documents-error">
        <span>!</span>

        <div>
          <strong>Documents unavailable</strong>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="documents-page">
      <section className="documents-page-header">
        <div>
          <span className="documents-eyebrow">
            DOCUMENT INTELLIGENCE
          </span>

          <h1>Documents</h1>

          <p>
            Upload, manage and monitor the financial documents
            available to your AI workforce.
          </p>
        </div>

        <div className="documents-header-actions">
          <input
            ref={fileInputRef}
            type="file"
            className="documents-hidden-input"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt"
          />

          <button
            type="button"
            className="documents-upload-button"
            onClick={handleUploadClick}
            disabled={uploading}
          >
            <span>+</span>
            {uploading
              ? "Uploading..."
              : "Upload Document"}
          </button>
        </div>
      </section>

      {uploadMessage && (
        <div className="documents-success-message">
          <span>✓</span>
          {uploadMessage}
        </div>
      )}

      {error && documents.length > 0 && (
        <div className="documents-error-message">
          <span>!</span>
          {error}
        </div>
      )}

      <section className="documents-overview">
        <div className="documents-overview-card">
          <span>TOTAL DOCUMENTS</span>
          <strong>{documents.length}</strong>
          <small>Documents in workspace</small>
        </div>

        <div className="documents-overview-card">
          <span>PROCESSED</span>
          <strong>{processedCount}</strong>
          <small>Ready for AI retrieval</small>
        </div>

        <div className="documents-overview-card">
          <span>PROCESSING</span>
          <strong>{processingCount}</strong>
          <small>Currently being processed</small>
        </div>

        <div className="documents-overview-card">
          <span>PENDING</span>
          <strong>{pendingCount}</strong>
          <small>Waiting for processing</small>
        </div>
      </section>

      <section className="documents-toolbar">
        <div className="documents-search">
          <span>⌕</span>

          <input
            type="text"
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
            placeholder="Search documents..."
            aria-label="Search documents"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value)
          }
          className="documents-filter"
          aria-label="Filter by document status"
        >
          <option value="ALL">All Status</option>
          <option value="PROCESSED">Processed</option>
          <option value="PROCESSING">Processing</option>
          <option value="PENDING">Pending</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(event) =>
            setCategoryFilter(event.target.value)
          }
          className="documents-filter documents-category-filter"
          aria-label="Filter by document category"
        >
          {documentCategories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      </section>

      <section className="documents-table-container">
        <div className="documents-table-header">
          <div>
            <span className="documents-section-eyebrow">
              DOCUMENT LIBRARY
            </span>

            <h2>Financial Documents</h2>
          </div>

          <span className="documents-visible-count">
            {filteredDocuments.length} visible
          </span>
        </div>

        {filteredDocuments.length === 0 ? (
          <div className="documents-empty">
            <div className="documents-empty-icon">
              ▤
            </div>

            <h2>No documents found</h2>

            <p>
              No documents match your current search or
              filters.
            </p>

            <button
              type="button"
              onClick={handleClearFilters}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="documents-table-wrapper">
            <table className="documents-table">
              <thead>
                <tr>
                  <th>DOCUMENT</th>
                  <th>TYPE</th>
                  <th>CATEGORY</th>
                  <th>SIZE</th>
                  <th>UPLOADED</th>
                  <th>STATUS</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {filteredDocuments.map((document) => (
                  <tr key={document.id}>
                    <td>
                      <div className="document-name-cell">
                        <div className="document-file-icon">
                          {document.type === "PDF"
                            ? "P"
                            : "X"}
                        </div>

                        <div>
                          <strong>
                            {document.name}
                          </strong>
                          <span>
                            Document ID #{document.id}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="document-type">
                        {document.type}
                      </span>
                    </td>

                    <td>
                      <span className="document-category">
                        {document.category}
                      </span>
                    </td>

                    <td>
                      <span className="document-muted">
                        {document.size}
                      </span>
                    </td>

                    <td>
                      <span className="document-muted">
                        {document.uploadedAt}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`document-status ${getStatusClass(
                          document.status
                        )}`}
                      >
                        <i />
                        {document.status}
                      </span>
                    </td>

                    <td>
                      <button
                        type="button"
                        className="document-more-button"
                        aria-label={`Actions for ${document.name}`}
                      >
                        ⋮
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="documents-upload-info">
        <div className="documents-upload-info-icon">
          ↑
        </div>

        <div>
          <strong>Upload financial documents</strong>

          <p>
            Supported formats: PDF, DOC, DOCX, XLS, XLSX,
            CSV and TXT. Document validation, secure storage,
            parsing and RAG indexing will be handled by the
            backend.
          </p>
        </div>

        <button
          type="button"
          onClick={handleUploadClick}
          disabled={uploading}
        >
          Upload
        </button>
      </section>
    </div>
  );
}

export default Documents;
