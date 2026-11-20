import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import "./ForgotPassword.css";
import { resetPassword } from "../../../services/authService";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!token) return setError("This reset link is missing its token. Request a new link.");
    if (password !== confirm) return setError("Passwords do not match.");
    setLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err.message || "Unable to reset password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="forgot-password-page">
      <div className="forgot-password-container">
        <div className="forgot-password-brand-section">
          <div className="forgot-password-brand"><div className="forgot-password-logo-mark">A</div><div><h1>Azentmart</h1><span>Finance AI</span></div></div>
          <div className="forgot-password-brand-content"><h2>Secure access to your<br />financial intelligence.</h2><p>Choose a new password for your Azentmart Finance AI account.</p></div>
          <div className="forgot-password-security"><span className="security-dot" /> Secure authentication</div>
        </div>
        <div className="forgot-password-form-section">
          <div className="forgot-password-card">
            {done ? <div className="reset-success"><div className="reset-success-icon">✓</div><h2>Password updated</h2><p>Your password has been changed. You can now sign in.</p><button type="button" className="forgot-password-button" onClick={() => navigate("/login")}>Back to login</button></div> : <>
              <div className="forgot-password-header"><h2>Set a new password</h2><p>Use at least 8 characters. This reset link can only be used once.</p></div>
              <form onSubmit={submit}>
                {error ? <p role="alert" className="auth-error">{error}</p> : null}
                <div className="form-group"><label htmlFor="new-password">New password</label><input id="new-password" type="password" minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
                <div className="form-group"><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type="password" minLength={8} maxLength={128} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required /></div>
                <button type="submit" className="forgot-password-button" disabled={loading || !token}>{loading ? "Updating..." : "Update password"}</button>
              </form>
              <div className="forgot-password-back"><Link to="/login">← Back to login</Link></div>
            </>}
          </div>
        </div>
      </div>
    </div>
  );
}
