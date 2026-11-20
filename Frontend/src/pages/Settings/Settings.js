import React, { useEffect, useState } from "react";
import {
  getSettings,
  updateSettings,
  resetSettings,
  changePassword,
  SESSION_TIMEOUT_OPTIONS,
} from "../../services/settingsService";

import "./Settings.css";

const TIMEZONES = [
  "Asia/Kolkata",
  "UTC",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Australia/Sydney",
];


const EMPTY_PASSWORD = { current: "", next: "", confirm: "" };

function PasswordVisibilityToggle({ visible, onToggle, label }) {
  return (
    <button
      type="button"
      className="settings-password-eye"
      onClick={onToggle}
      aria-label={visible ? `Hide ${label}` : `Show ${label}`}
      title={visible ? "Hide password" : "Show password"}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {visible ? (
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
  );
}


function Settings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadSettings() {
      try {
        setLoading(true);
        setError("");

        const result = await getSettings();

        if (isMounted) {
          setSettings(result);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            requestError?.message ||
              "Unable to load settings."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadSettings();

    return () => {
      isMounted = false;
    };
  }, []);

  const handlePreferenceChange = (key) => {
    setSettings((current) => ({
      ...current,
      preferences: {
        ...current.preferences,
        [key]: !current.preferences[key],
      },
    }));

    setSaved(false);
  };

  const handleTimeoutChange = (event) => {
    const value = Number(event.target.value);
    setSettings((current) => ({
      ...current,
      security: { ...current.security, sessionTimeoutMinutes: value },
    }));
    setSaved(false);
  };

  const handleTimezoneChange = (event) => {
    const value = event.target.value;
    setSettings((current) => ({
      ...current,
      organization: { ...current.organization, timezone: value },
    }));
    setSaved(false);
  };

  const handleReset = async () => {
    if (
      !window.confirm(
        "Reset notification and session settings to their defaults? Your saved preferences will be deleted."
      )
    ) {
      return;
    }
    try {
      setSaving(true);
      setSaved(false);
      setError("");
      setSettings(await resetSettings());
      setSaved(true);
    } catch (requestError) {
      setError(requestError?.message || "Unable to reset settings.");
    } finally {
      setSaving(false);
    }
  };

  const [passwordForm, setPasswordForm] = useState(EMPTY_PASSWORD);
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState({ type: "", text: "" });

  const [passwordVisibility, setPasswordVisibility] = useState({
    current: false,
    next: false,
    confirm: false,
  });

  const passwordChecks = [
    { label: "At least 8 characters", valid: passwordForm.next.length >= 8 },
    { label: "One uppercase letter (A-Z)", valid: /[A-Z]/.test(passwordForm.next) },
    { label: "One lowercase letter (a-z)", valid: /[a-z]/.test(passwordForm.next) },
    { label: "One number (0-9)", valid: /[0-9]/.test(passwordForm.next) },
    { label: "One special character (@#$%! etc.)", valid: /[^A-Za-z0-9\\s]/.test(passwordForm.next) },
  ];

  const passwordStrength = passwordChecks.filter((check) => check.valid).length;
  const strengthLabels = ["", "Weak", "Weak", "Fair", "Good", "Strong"];
  const passwordsMatch =
    passwordForm.confirm.length > 0 &&
    passwordForm.next === passwordForm.confirm;
  const passwordReady =
    passwordChecks.every((check) => check.valid) &&
    passwordsMatch &&
    passwordForm.current.trim().length > 0;


  const handlePasswordSubmit = async (event) => {
    event.preventDefault();
    const { current, next, confirm } = passwordForm;

    const checks = [
      next.length >= 8,
      /[A-Z]/.test(next),
      /[a-z]/.test(next),
      /[0-9]/.test(next),
      /[^A-Za-z0-9\\s]/.test(next),
    ];

    if (!checks.every(Boolean)) {
      setPasswordMessage({ type: "error", text: "Please satisfy all password security requirements." });
      return;
    }
    if (next !== confirm) {
      setPasswordMessage({ type: "error", text: "New password and confirmation do not match." });
      return;
    }

    try {
      setPasswordBusy(true);
      setPasswordMessage({ type: "", text: "" });
      await changePassword(current, next);
      setPasswordForm(EMPTY_PASSWORD);
      setPasswordVisibility({ current: false, next: false, confirm: false });
      setPasswordMessage({ type: "success", text: "Password changed. Use the new password next time you sign in." });
    } catch (requestError) {
      setPasswordMessage({ type: "error", text: requestError?.message || "Unable to change password." });
    } finally {
      setPasswordBusy(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaved(false);
      setError("");

      const result = await updateSettings(settings);

      setSettings(result);
      setSaved(true);
    } catch (requestError) {
      setError(
        requestError?.message ||
          "Unable to save settings."
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <section className="settings-page">
        <div className="settings-state">
          <div className="settings-loader" />
          <p>Loading settings...</p>
        </div>
      </section>
    );
  }

  if (error && !settings) {
    return (
      <section className="settings-page">
        <div className="settings-state settings-error">
          <strong>Unable to load settings</strong>
          <p>{error}</p>
        </div>
      </section>
    );
  }

  return (
    <section className="settings-page">
      <div className="settings-header">
        <div>
          <span className="settings-eyebrow">
            SYSTEM CONFIGURATION
          </span>

          <h1>Settings</h1>

          <p>
            Manage your profile, workspace preferences,
            notifications and security controls.
          </p>
        </div>

        <button
          type="button"
          className="settings-save-button"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>

      {saved && (
        <div className="settings-success">
          <span>✓</span>
          Settings saved successfully.
        </div>
      )}

      {error && (
        <div className="settings-inline-error">
          {error}
        </div>
      )}

      <div className="settings-layout">
        <aside className="settings-navigation">
          <div className="settings-navigation-title">
            SETTINGS
          </div>

          <a href="#profile" className="active">
            <span>◉</span>
            Profile
          </a>

          <a href="#organization">
            <span>▣</span>
            Organization
          </a>

          <a href="#notifications">
            <span>◇</span>
            Notifications
          </a>

          <a href="#security">
            <span>◆</span>
            Security
          </a>
        </aside>

        <div className="settings-content">
          <section
            id="profile"
            className="settings-section"
          >
            <div className="settings-section-header">
              <div>
                <span className="settings-section-label">
                  ACCOUNT
                </span>

                <h2>Profile</h2>

                <p>
                  Basic information associated with your
                  Finance AI account.
                </p>
              </div>
            </div>

            <div className="settings-profile">
              <div className="settings-avatar">
                {(settings.profile.name || "U").charAt(0).toUpperCase()}
              </div>

              <div className="settings-profile-details">
                <strong>{settings.profile.name}</strong>
                <span>{settings.profile.email}</span>

                <div className="settings-role">
                  {settings.profile.role}
                </div>
              </div>
            </div>

            <div className="settings-form-grid">
              <div className="settings-field">
                <label>Full Name</label>
                <input
                  type="text"
                  value={settings.profile.name}
                  readOnly
                />
              </div>

              <div className="settings-field">
                <label>Email Address</label>
                <input
                  type="email"
                  value={settings.profile.email}
                  readOnly
                />
              </div>

              <div className="settings-field">
                <label>Role</label>
                <input
                  type="text"
                  value={settings.profile.role}
                  readOnly
                />
              </div>
            </div>
          </section>

          <section
            id="organization"
            className="settings-section"
          >
            <div className="settings-section-header">
              <div>
                <span className="settings-section-label">
                  WORKSPACE
                </span>

                <h2>Organization</h2>

                <p>
                  Configure workspace-level information and
                  regional preferences.
                </p>
              </div>
            </div>

            <div className="settings-form-grid">
              <div className="settings-field">
                <label>Organization Name</label>
                <input
                  type="text"
                  value={settings.organization.name}
                  readOnly
                />
              </div>

              <div className="settings-field">
                <label>Workspace</label>
                <input
                  type="text"
                  value={settings.organization.workspace}
                  readOnly
                />
              </div>

              <div className="settings-field">
                <label htmlFor="settings-timezone">Timezone</label>
                <select
                  id="settings-timezone"
                  value={settings.organization.timezone}
                  onChange={handleTimezoneChange}
                >
                  {(TIMEZONES.includes(settings.organization.timezone)
                    ? TIMEZONES
                    : [settings.organization.timezone, ...TIMEZONES]
                  ).map((zone) => (
                    <option key={zone} value={zone}>{zone}</option>
                  ))}
                </select>
              </div>

              <div className="settings-field">
                <label>Currency</label>
                <input
                  type="text"
                  value={settings.organization.currency}
                  readOnly
                />
              </div>
            </div>
          </section>

          <section
            id="notifications"
            className="settings-section"
          >
            <div className="settings-section-header">
              <div>
                <span className="settings-section-label">
                  PREFERENCES
                </span>

                <h2>Notifications</h2>

                <p>
                  Choose which platform events should generate
                  notifications. Preferences are saved to your account;
                  email delivery is not connected yet (no mail service
                  is configured).
                </p>
              </div>
            </div>

            <div className="settings-toggle-list">
              <div className="settings-toggle-row">
                <div>
                  <strong>Email Notifications</strong>
                  <span>
                    Receive important platform updates by email.
                  </span>
                </div>

                <button
                  type="button"
                  className={`settings-toggle ${
                    settings.preferences.emailNotifications
                      ? "on"
                      : ""
                  }`}
                  onClick={() =>
                    handlePreferenceChange(
                      "emailNotifications"
                    )
                  }
                  aria-label="Toggle email notifications"
                >
                  <i />
                </button>
              </div>

              <div className="settings-toggle-row">
                <div>
                  <strong>Task Notifications</strong>
                  <span>
                    Get notified when AI employee tasks complete.
                  </span>
                </div>

                <button
                  type="button"
                  className={`settings-toggle ${
                    settings.preferences.taskNotifications
                      ? "on"
                      : ""
                  }`}
                  onClick={() =>
                    handlePreferenceChange(
                      "taskNotifications"
                    )
                  }
                  aria-label="Toggle task notifications"
                >
                  <i />
                </button>
              </div>

              <div className="settings-toggle-row">
                <div>
                  <strong>Security Alerts</strong>
                  <span>
                    Receive alerts for important security events.
                  </span>
                </div>

                <button
                  type="button"
                  className={`settings-toggle ${
                    settings.preferences.securityAlerts
                      ? "on"
                      : ""
                  }`}
                  onClick={() =>
                    handlePreferenceChange(
                      "securityAlerts"
                    )
                  }
                  aria-label="Toggle security alerts"
                >
                  <i />
                </button>
              </div>

              <div className="settings-toggle-row">
                <div>
                  <strong>Weekly Reports</strong>
                  <span>
                    Receive a weekly summary of Finance AI activity.
                  </span>
                </div>

                <button
                  type="button"
                  className={`settings-toggle ${
                    settings.preferences.weeklyReports
                      ? "on"
                      : ""
                  }`}
                  onClick={() =>
                    handlePreferenceChange(
                      "weeklyReports"
                    )
                  }
                  aria-label="Toggle weekly reports"
                >
                  <i />
                </button>
              </div>
            </div>
          </section>

          <section
            id="security"
            className="settings-section"
          >
            <div className="settings-section-header">
              <div>
                <span className="settings-section-label">
                  ACCESS CONTROL
                </span>

                <h2>Security</h2>

                <p>
                  Session length applies the next time you sign in.
                  Change your password below.
                </p>
              </div>
            </div>

            <div className="settings-form-grid">
              <div className="settings-field">
                <label htmlFor="settings-timeout">Session Timeout</label>
                <select
                  id="settings-timeout"
                  value={settings.security.sessionTimeoutMinutes}
                  onChange={handleTimeoutChange}
                >
                  {SESSION_TIMEOUT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            
            <form className="settings-password-form" onSubmit={handlePasswordSubmit}>
              <div className="settings-password-fields">
                <div className="settings-field">
                  <label htmlFor="pw-current">Current Password</label>
                  <div className="settings-password-input">
                    <input
                      id="pw-current"
                      type={passwordVisibility.current ? "text" : "password"}
                      autoComplete="current-password"
                      value={passwordForm.current}
                      onChange={(e) => setPasswordForm((f) => ({ ...f, current: e.target.value }))}
                      required
                    />
                    <PasswordVisibilityToggle
                      visible={passwordVisibility.current}
                      label="current password"
                      onToggle={() => setPasswordVisibility((v) => ({ ...v, current: !v.current }))}
                    />
                  </div>
                </div>

                <div className="settings-field">
                  <label htmlFor="pw-new">New Password</label>
                  <div className="settings-password-input">
                    <input
                      id="pw-new"
                      type={passwordVisibility.next ? "text" : "password"}
                      autoComplete="new-password"
                      value={passwordForm.next}
                      onChange={(e) => {
                        setPasswordForm((f) => ({ ...f, next: e.target.value }));
                        setPasswordMessage({ type: "", text: "" });
                      }}
                      required
                    />
                    <PasswordVisibilityToggle
                      visible={passwordVisibility.next}
                      label="new password"
                      onToggle={() => setPasswordVisibility((v) => ({ ...v, next: !v.next }))}
                    />
                  </div>

                  <div className="settings-password-strength">
                    <div className="settings-strength-heading">
                      <span>Password strength</span>
                      <strong className={`strength-level strength-${passwordStrength}`}>
                        {passwordForm.next ? strengthLabels[passwordStrength] : "Not entered"}
                      </strong>
                    </div>
                    <div
                      className="settings-strength-track"
                      role="progressbar"
                      aria-label="Password strength"
                      aria-valuemin={0}
                      aria-valuemax={5}
                      aria-valuenow={passwordStrength}
                    >
                      {[1, 2, 3, 4, 5].map((level) => (
                        <span
                          key={level}
                          className={level <= passwordStrength ? `filled strength-${passwordStrength}` : ""}
                        />
                      ))}
                    </div>
                  </div>

                  <div className="settings-password-rules">
                    <span className="settings-rules-title">Password requirements</span>
                    {passwordChecks.map((check) => (
                      <div className={`settings-password-rule ${check.valid ? "valid" : ""}`} key={check.label}>
                        <span className="settings-rule-icon">{check.valid ? "✓" : "○"}</span>
                        {check.label}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="settings-field">
                  <label htmlFor="pw-confirm">Confirm New Password</label>
                  <div className="settings-password-input">
                    <input
                      id="pw-confirm"
                      type={passwordVisibility.confirm ? "text" : "password"}
                      autoComplete="new-password"
                      value={passwordForm.confirm}
                      onChange={(e) => setPasswordForm((f) => ({ ...f, confirm: e.target.value }))}
                      required
                    />
                    <PasswordVisibilityToggle
                      visible={passwordVisibility.confirm}
                      label="confirm password"
                      onToggle={() => setPasswordVisibility((v) => ({ ...v, confirm: !v.confirm }))}
                    />
                  </div>
                  {passwordForm.confirm && (
                    <span className={`settings-password-match ${passwordsMatch ? "valid" : "invalid"}`}>
                      {passwordsMatch ? "✓ Passwords match" : "Passwords do not match"}
                    </span>
                  )}
                </div>

                <div className="settings-field settings-password-action">
                  <button
                    type="submit"
                    className="settings-save-button"
                    disabled={passwordBusy || !passwordReady}
                  >
                    {passwordBusy ? "Updating..." : "Change Password"}
                  </button>
                  <span>All security requirements must be met before updating.</span>
                </div>
              </div>
            </form>

            {passwordMessage.text && (
              <div className={passwordMessage.type === "error" ? "settings-inline-error" : "settings-success"}>
                {passwordMessage.text}
              </div>
            )}

            <div className="settings-security-note">
              <strong>Reset preferences</strong>
              <p>
                Delete your saved notification and session preferences and
                return to the defaults. Your account and profile are not
                affected.
              </p>
              <button
                type="button"
                className="settings-save-button"
                onClick={handleReset}
                disabled={saving || !settings.isCustomised}
              >
                Reset to defaults
              </button>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

export default Settings;
