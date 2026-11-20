import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./Login.css";

import { useAuthContext } from "../../../context/AuthContext";


function Login() {
  const navigate = useNavigate();

  const { login } = useAuthContext();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");


  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      await login(
        email,
        password,
        rememberMe
      );

      // RoleLanding selects the first workspace this role is authorised to use.
      // Do not send every role to AP (Employee / Requester has no AP access).
      navigate("/employees", { replace: true });

    } catch (error) {
      setError(
        error.message || "Unable to sign in. Please try again."
      );

    } finally {
      setLoading(false);
    }
  };


  return (
    <main className="login-page">

      {/* LEFT SIDE */}

      <section className="login-brand-section">

        <div className="login-brand-content">

          <div className="login-logo">

            <div className="login-logo-mark">
              A
            </div>

            <div className="login-logo-text">
              <strong>azentmart</strong>
              <span>AI</span>
            </div>

          </div>


          <div className="login-hero-text">

            <span className="login-eyebrow">
              FINANCE INTELLIGENCE PLATFORM
            </span>

            <h1>
              Intelligent finance.
              <br />
              <span>Powered by AI.</span>
            </h1>

            <p>
              Securely access your financial knowledge,
              documents and AI-powered insights from one
              intelligent workspace.
            </p>

          </div>


          <div className="login-features">

            <div className="login-feature">

              <div className="login-feature-icon">
                AI
              </div>

              <div>
                <strong>AI Financial Assistant</strong>

                <span>
                  Ask questions and get intelligent answers.
                </span>
              </div>

            </div>


            <div className="login-feature">

              <div className="login-feature-icon">
                RAG
              </div>

              <div>
                <strong>Knowledge Retrieval</strong>

                <span>
                  Find relevant information from your documents.
                </span>
              </div>

            </div>


            <div className="login-feature">

              <div className="login-feature-icon">
                SEC
              </div>

              <div>
                <strong>Secure Workspace</strong>

                <span>
                  Your financial data stays protected.
                </span>
              </div>

            </div>

          </div>

        </div>


        <div className="login-brand-footer">
          © {new Date().getFullYear()} Azentmart Finance AI
        </div>

      </section>


      {/* RIGHT SIDE */}

      <section className="login-form-section">

        <div className="login-form-container">

          <div className="login-mobile-logo">

            <div className="login-logo-mark">
              A
            </div>

            <div className="login-logo-text">
              <strong>azentmart</strong>
              <span>AI</span>
            </div>

          </div>


          <div className="login-heading">

            <span>
              WELCOME BACK
            </span>

            <h2>
              Sign in to your account
            </h2>

            <p>
              Enter your credentials to access your workspace.
            </p>

          </div>


          <form
            className="login-form"
            onSubmit={handleSubmit}
          >

            <div className="login-input-group">

              <label htmlFor="email">
                Email address
              </label>

              <input
                id="email"
                name="email"
                type="email"
                placeholder="you@company.com"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />

            </div>


            <div className="login-input-group">

              <div className="login-password-label">

                <label htmlFor="password">
                  Password
                </label>

                <Link to="/forgot-password">
                  Forgot password?
                </Link>

              </div>


              <div className="login-password-input">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    {showPassword ? (
                      <>
                        <path d="M3 3l18 18" />
                        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                        <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.2 0 8.7 4.8 9.5 7-.3.8-1.1 2-2.3 3.2" />
                        <path d="M6.2 6.2C3.9 7.7 2.8 10 2.5 12c.8 2.2 4.3 7 9.5 7 1.2 0 2.3-.3 3.3-.8" />
                      </>
                    ) : (
                      <>
                        <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
                        <circle cx="12" cy="12" r="3" />
                      </>
                    )}
                  </svg>
                </button>
              </div>

            </div>


            <label className="login-remember">

              <input
                type="checkbox"
                name="remember"
                checked={rememberMe}
                onChange={(event) =>
                  setRememberMe(event.target.checked)
                }
              />

              <span>
                Keep me signed in
              </span>

            </label>


            {error && (
              <div
                role="alert"
                style={{
                  marginBottom: "16px",
                  padding: "10px 12px",
                  border: "1px solid rgba(255, 82, 82, 0.25)",
                  borderRadius: "8px",
                  background: "rgba(255, 82, 82, 0.06)",
                  color: "#ff7b7b",
                  fontSize: "11px",
                  lineHeight: "1.5",
                }}
              >
                {error}
              </div>
            )}


            <button
              type="submit"
              className="login-submit-button"
              disabled={loading}
            >
              {loading ? "Signing In..." : "Sign In"}

              {!loading && (
                <span>→</span>
              )}
            </button>

          </form>


          <div className="login-divider">
            <span>OR</span>
          </div>


          <div className="login-security-note">

            <span>●</span>

            Secure enterprise authentication

          </div>

        </div>

      </section>

    </main>
  );
}


export default Login;