import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./ForgotPassword.css";
import { requestPasswordReset } from "../../../services/authService";

function ForgotPassword() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await requestPasswordReset(email);
      setSubmitted(true);
    } catch (requestError) {
      setError(requestError.message || "Unable to request a password reset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-password-page">
      <div className="forgot-password-container">

        {/* Left Branding Section */}
        <div className="forgot-password-brand-section">
          <div className="forgot-password-brand">
            <div className="forgot-password-logo-mark">
              A
            </div>

            <div>
              <h1>Azentmart</h1>
              <span>Finance AI</span>
            </div>
          </div>

          <div className="forgot-password-brand-content">
            <h2>Secure access to your<br />financial intelligence.</h2>

            <p>
              Reset your password securely and continue using
              Azentmart Finance AI.
            </p>
          </div>

          <div className="forgot-password-security">
            <span className="security-dot"></span>
            Secure authentication
          </div>
        </div>

        {/* Right Form Section */}
        <div className="forgot-password-form-section">
          <div className="forgot-password-card">

            {!submitted ? (
              <>
                <div className="forgot-password-header">
                  <h2>Forgot password?</h2>

                  <p>
                    Enter your work email address and we'll send you
                    instructions to reset your password.
                  </p>
                </div>

                <form onSubmit={handleSubmit}>
                  {error ? <p role="alert" className="auth-error">{error}</p> : null}

                  <div className="form-group">
                    <label htmlFor="email">
                      Work email
                    </label>

                    <input
                      id="email"
                      type="email"
                      placeholder="you@company.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoComplete="email"
                    />
                  </div>

                  <button
                    type="submit"
                    className="forgot-password-button"
                    disabled={loading}
                  >
                    {loading ? "Sending..." : "Send reset instructions"}
                  </button>

                </form>

                <div className="forgot-password-back">
                  <Link to="/login">
                    ← Back to login
                  </Link>
                </div>
              </>
            ) : (
              <div className="reset-success">

                <div className="reset-success-icon">
                  ✓
                </div>

                <h2>Check your email</h2>

                <p>
                  If an account exists for{" "}
                  <strong>{email}</strong>, you will receive
                  password reset instructions shortly.
                </p>

                <button
                  type="button"
                  className="forgot-password-button"
                  onClick={() => navigate("/login")}
                >
                  Back to login
                </button>

                <button
                  type="button"
                  className="resend-button"
                  onClick={() => setSubmitted(false)}
                >
                  Try another email
                </button>

              </div>
            )}

          </div>
        </div>

      </div>
    </div>
  );
}

export default ForgotPassword;