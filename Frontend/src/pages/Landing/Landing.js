import { Link } from "react-router-dom";
import "./Landing.css";

function Landing() {
  return (
    <main className="landing-page">

      {/* ================= NAVBAR ================= */}

      <header className="landing-navbar">
        <div className="landing-navbar-inner">

          <Link to="/" className="landing-brand">
            <div className="landing-brand-mark">
              A
            </div>

            <div className="landing-brand-text">
              <strong>Azentmart</strong>
              <span>AI</span>
            </div>
          </Link>

          <nav className="landing-nav-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#security">Security</a>
          </nav>

          <div className="landing-nav-actions">

            <Link
              to="/login"
              className="landing-signin"
            >
              Sign In
            </Link>

            <Link
              to="/signup"
              className="landing-get-started"
            >
              Get Started
            </Link>

          </div>

        </div>
      </header>

      {/* ================= HERO ================= */}

      <section className="landing-hero">

        <div className="landing-glow landing-glow-one" />
        <div className="landing-glow landing-glow-two" />

        <div className="landing-hero-content">

          <div className="landing-badge">
            <span />
            AI-powered financial intelligence
          </div>

          <div className="landing-logo-placeholder">
            <div className="landing-logo-symbol">
              A
            </div>

            <div className="landing-logo-name">
              <strong>azentmart</strong>
              <span>AI</span>
            </div>
          </div>

          <h1>
            Intelligent AI for
            <span> financial knowledge.</span>
          </h1>

          <p className="landing-hero-description">
            Transform financial documents and business knowledge
            into intelligent, secure and actionable insights with
            Azentmart Finance AI.
          </p>

          <div className="landing-hero-actions">

            <Link
              to="/signup"
              className="landing-primary-button"
            >
              Get Started
              <span>→</span>
            </Link>

            <Link
              to="/login"
              className="landing-secondary-button"
            >
              Sign In
            </Link>

          </div>

          <div className="landing-trust">
            <span>●</span>
            Built for secure enterprise finance workflows
          </div>

        </div>

      </section>

      {/* ================= STATS ================= */}

      <section className="landing-stats">

        <div>
          <strong>AI</strong>
          <span>Financial Intelligence</span>
        </div>

        <div>
          <strong>RAG</strong>
          <span>Knowledge Retrieval</span>
        </div>

        <div>
          <strong>24/7</strong>
          <span>AI Availability</span>
        </div>

        <div>
          <strong>Secure</strong>
          <span>Enterprise Architecture</span>
        </div>

      </section>

      {/* ================= FEATURES ================= */}

      <section
        id="features"
        className="landing-section"
      >

        <div className="landing-section-heading">

          <span>CAPABILITIES</span>

          <h2>
            Everything you need for
            <strong> smarter financial decisions.</strong>
          </h2>

          <p>
            A centralized AI workspace designed to help teams
            understand documents, retrieve knowledge and work
            with financial information more efficiently.
          </p>

        </div>

        <div className="landing-feature-grid">

          <article className="landing-feature-card">

            <div className="feature-icon">
              AI
            </div>

            <h3>
              AI Financial Assistant
            </h3>

            <p>
              Ask questions in natural language and receive
              intelligent answers based on your authorized
              financial knowledge.
            </p>

          </article>

          <article className="landing-feature-card">

            <div className="feature-icon">
              RAG
            </div>

            <h3>
              RAG Knowledge Retrieval
            </h3>

            <p>
              Retrieve relevant information from approved
              documents before generating AI responses.
            </p>

          </article>

          <article className="landing-feature-card">

            <div className="feature-icon">
              DOC
            </div>

            <h3>
              Document Intelligence
            </h3>

            <p>
              Upload and manage financial documents that become
              part of your organization's AI knowledge.
            </p>

          </article>

          <article className="landing-feature-card">

            <div className="feature-icon">
              KB
            </div>

            <h3>
              Knowledge Base
            </h3>

            <p>
              Organize company financial knowledge into a
              searchable AI-ready knowledge base.
            </p>

          </article>

          <article className="landing-feature-card">

            <div className="feature-icon">
              AN
            </div>

            <h3>
              Analytics
            </h3>

            <p>
              Understand platform activity and usage through
              centralized analytics and insights.
            </p>

          </article>

          <article className="landing-feature-card">

            <div className="feature-icon">
              RP
            </div>

            <h3>
              Reports
            </h3>

            <p>
              Convert financial information into structured
              reports that teams can easily review.
            </p>

          </article>

        </div>

      </section>

      {/* ================= HOW IT WORKS ================= */}

      <section
        id="how-it-works"
        className="landing-section landing-workflow"
      >

        <div className="landing-section-heading">

          <span>HOW IT WORKS</span>

          <h2>
            From financial data to
            <strong> intelligent answers.</strong>
          </h2>

          <p>
            A simple workflow for turning organizational
            financial knowledge into AI-powered intelligence.
          </p>

        </div>

        <div className="landing-steps">

          <div className="landing-step">

            <div className="step-number">
              01
            </div>

            <h3>
              Upload
            </h3>

            <p>
              Add approved financial documents and business
              knowledge to your workspace.
            </p>

          </div>

          <div className="landing-step">

            <div className="step-number">
              02
            </div>

            <h3>
              Process
            </h3>

            <p>
              Documents are processed and prepared for
              intelligent retrieval.
            </p>

          </div>

          <div className="landing-step">

            <div className="step-number">
              03
            </div>

            <h3>
              Ask
            </h3>

            <p>
              Ask natural-language questions using the AI
              assistant.
            </p>

          </div>

          <div className="landing-step">

            <div className="step-number">
              04
            </div>

            <h3>
              Understand
            </h3>

            <p>
              Receive context-aware answers from authorized
              financial knowledge.
            </p>

          </div>

        </div>

      </section>

      {/* ================= SECURITY ================= */}

      <section
        id="security"
        className="landing-section"
      >

        <div className="landing-security">

          <div className="landing-security-content">

            <span>
              SECURITY FIRST
            </span>

            <h2>
              Security built into
              <strong> every layer.</strong>
            </h2>

            <p>
              Finance AI is designed around controlled access,
              protected data and secure AI workflows.
              Authentication, authorization and document access
              will be enforced by the backend.
            </p>

            <div className="security-list">

              <div>
                <b>✓</b>
                Role-based access control
              </div>

              <div>
                <b>✓</b>
                Protected financial documents
              </div>

              <div>
                <b>✓</b>
                Authorized knowledge retrieval
              </div>

              <div>
                <b>✓</b>
                Secure AI interaction layer
              </div>

            </div>

          </div>

          <div className="security-visual">

            <div className="security-circle">

              <div className="security-core">
                AI
              </div>

            </div>

            <span className="security-chip auth">
              AUTH
            </span>

            <span className="security-chip rbac">
              RBAC
            </span>

            <span className="security-chip rag">
              RAG
            </span>

          </div>

        </div>

      </section>

      {/* ================= CTA ================= */}

      <section className="landing-cta">

        <span>
          GET STARTED
        </span>

        <h2>
          Turn financial knowledge into
          <strong> intelligence.</strong>
        </h2>

        <p>
          Build a smarter, more connected financial workspace
          with Azentmart Finance AI.
        </p>

        <Link
          to="/signup"
          className="landing-primary-button"
        >
          Create Your Workspace
          <span>→</span>
        </Link>

      </section>

      {/* ================= FOOTER ================= */}

      <footer className="landing-footer">

        <div className="landing-footer-inner">

          <div className="landing-footer-brand">

            <div className="landing-footer-logo">
              <div>A</div>

              <span>
                <strong>azentmart</strong>
                <small>AI</small>
              </span>
            </div>

            <p>
              Intelligent financial knowledge,
              powered by AI.
            </p>

          </div>

          <div className="landing-footer-links">

            <Link to="/login">
              Sign In
            </Link>

            <Link to="/signup">
              Get Started
            </Link>

          </div>

        </div>

        <div className="landing-footer-bottom">
          © {new Date().getFullYear()} Azentmart Finance AI
        </div>

      </footer>

    </main>
  );
}

export default Landing;
