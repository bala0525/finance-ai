import { useState } from "react";
import { Link } from "react-router-dom";

import { signupUser } from "../../../services/authService";

import "./Signup.css";

function Signup() {

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }

    setLoading(true);

    try {
      const result = await signupUser(email, password, fullName);
      setSuccess(result.message || "Account created successfully. You can sign in now.");
    } catch (requestError) {
      setError(
        requestError.message ||
          "Unable to create your account. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="signup-page">

      {/* LEFT SIDE */}

      <section className="signup-brand-section">

        <div className="signup-brand-content">

          <div className="signup-logo">
            <div className="signup-logo-mark">
              A
            </div>

            <div className="signup-logo-text">
              <strong>azentmart</strong>
              <span>AI</span>
            </div>
          </div>

          <div className="signup-hero-text">

            <span className="signup-eyebrow">
              FINANCE INTELLIGENCE PLATFORM
            </span>

            <h1>
              Build a smarter
              <br />
              <span>financial workspace.</span>
            </h1>

            <p>
              Bring your financial documents, business knowledge
              and AI-powered workflows together in one secure
              enterprise workspace.
            </p>

          </div>

          <div className="signup-benefits">

            <div className="signup-benefit">
              <div className="signup-benefit-icon">
                AI
              </div>

              <div>
                <strong>AI-powered insights</strong>
                <span>
                  Understand financial information faster.
                </span>
              </div>
            </div>

            <div className="signup-benefit">
              <div className="signup-benefit-icon">
                DOC
              </div>

              <div>
                <strong>Centralized documents</strong>
                <span>
                  Keep your financial knowledge organized.
                </span>
              </div>
            </div>

            <div className="signup-benefit">
              <div className="signup-benefit-icon">
                SEC
              </div>

              <div>
                <strong>Security-first architecture</strong>
                <span>
                  Access is controlled by backend authorization.
                </span>
              </div>
            </div>

          </div>

        </div>

        <div className="signup-brand-footer">
          © {new Date().getFullYear()} Azentmart Finance AI
        </div>

      </section>


      {/* RIGHT SIDE */}

      <section className="signup-form-section">

        <div className="signup-form-container">

          <div className="signup-mobile-logo">

            <div className="signup-logo-mark">
              A
            </div>

            <div className="signup-logo-text">
              <strong>azentmart</strong>
              <span>AI</span>
            </div>

          </div>


          <div className="signup-heading">

            <span>
              GET STARTED
            </span>

            <h2>
              Create your account
            </h2>

            <p>
              Set up your secure finance AI workspace. New public accounts are created with the Employee / Requester role.
            </p>

          </div>


          {error && (
            <div
              role="alert"
              style={{
                marginBottom: "16px",
                padding: "12px 14px",
                borderRadius: "8px",
                background: "rgba(239, 68, 68, 0.10)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                color: "#f87171",
                fontSize: "13px",
              }}
            >
              {error}
            </div>
          )}


          {success && (
            <div
              role="status"
              style={{
                marginBottom: "16px",
                padding: "12px 14px",
                borderRadius: "8px",
                background: "rgba(34, 197, 94, 0.10)",
                border: "1px solid rgba(34, 197, 94, 0.25)",
                color: "#4ade80",
                fontSize: "13px",
              }}
            >
              {success}
            </div>
          )}


          <form
            className="signup-form"
            onSubmit={handleSubmit}
          >

            <div className="signup-input-group">

              <label htmlFor="fullName">
                Full name
              </label>

              <input
                id="fullName"
                name="fullName"
                type="text"
                placeholder="Your full name"
                autoComplete="name"
                value={fullName}
                onChange={(event) =>
                  setFullName(event.target.value)
                }
                required
              />

            </div>


            <div className="signup-input-group">

              <label htmlFor="email">
                Work email
              </label>

              <input
                id="email"
                name="email"
                type="email"
                placeholder="you@company.com"
                autoComplete="email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                required
              />

            </div>


            <div className="signup-input-group">

              <label htmlFor="company">
                Company name
              </label>

              <input
                id="company"
                name="company"
                type="text"
                placeholder="Your company"
                autoComplete="organization"
                value={company}
                onChange={(event) =>
                  setCompany(event.target.value)
                }
                required
              />

            </div>


            <div className="signup-input-row">

              <div className="signup-input-group">

                <label htmlFor="password">
                  Password
                </label>

                <input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="Create password"
                  autoComplete="new-password"
                  minLength="8"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  required
                />

              </div>


              <div className="signup-input-group">

                <label htmlFor="confirmPassword">
                  Confirm password
                </label>

                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  placeholder="Confirm password"
                  autoComplete="new-password"
                  minLength="8"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  required
                />

              </div>

            </div>


            <label className="signup-terms">

              <input
                type="checkbox"
                name="terms"
                required
              />

              <span>
                I agree to the
                <a href="#terms"> Terms of Service </a>
                and
                <a href="#privacy"> Privacy Policy</a>.
              </span>

            </label>


            <button
              type="submit"
              className="signup-submit-button"
              disabled={loading}
            >
              {loading ? "Creating Account..." : "Create Account"}
              {!loading && <span>→</span>}
            </button>

          </form>


          <div className="signup-login">

            <span>
              Already have an account?
            </span>

            <Link to="/login">
              Sign in
            </Link>

          </div>


          <div className="signup-security-note">

            <span>●</span>

            Your account will be protected by secure authentication.

          </div>

        </div>

      </section>

    </main>
  );
}

export default Signup;
