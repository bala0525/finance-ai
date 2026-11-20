import apiClient from "./apiClient";

/*
 * Settings service - persisted per user in the database.
 *   GET    /users/me/settings   read (defaults when nothing saved)
 *   PATCH  /users/me/settings   create / update
 *   DELETE /users/me/settings   reset to defaults
 *   POST   /users/me/password   change password
 * Account/profile details come from /users/me/profile.
 */

export const SESSION_TIMEOUT_OPTIONS = [
  { value: 15, label: "15 minutes" },
  { value: 30, label: "30 minutes" },
  { value: 60, label: "1 hour" },
  { value: 120, label: "2 hours" },
  { value: 480, label: "8 hours" },
];

function toSettingsShape(profile, prefs) {
  return {
    profile: {
      name: profile.fullName || "",
      email: profile.email || "",
      role: profile.roleName || "Finance User",
    },
    organization: {
      name: "Azentmart",
      workspace: "Finance Intelligence Platform",
      timezone: profile.timezone || "Asia/Kolkata",
      currency: "INR (₹)",
    },
    preferences: {
      emailNotifications: prefs.emailNotifications,
      taskNotifications: prefs.taskNotifications,
      securityAlerts: prefs.securityAlerts,
      weeklyReports: prefs.weeklyReports,
    },
    security: { sessionTimeoutMinutes: prefs.sessionTimeoutMinutes },
    isCustomised: prefs.isCustomised,
  };
}

export async function getSettings() {
  const [profile, prefs] = await Promise.all([
    apiClient("/users/me/profile"),
    apiClient("/users/me/settings"),
  ]);
  return toSettingsShape(profile, prefs);
}

export async function updateSettings(settings) {
  const body = {
    email_notifications: settings.preferences.emailNotifications,
    task_notifications: settings.preferences.taskNotifications,
    security_alerts: settings.preferences.securityAlerts,
    weekly_reports: settings.preferences.weeklyReports,
    session_timeout_minutes: Number(settings.security.sessionTimeoutMinutes),
  };
  const [profile, prefs] = await Promise.all([
    apiClient("/users/me/profile", {
      method: "PUT",
      body: JSON.stringify({ timezone: settings.organization.timezone }),
    }),
    apiClient("/users/me/settings", { method: "PATCH", body: JSON.stringify(body) }),
  ]);
  return toSettingsShape(profile, prefs);
}

export async function resetSettings() {
  await apiClient("/users/me/settings", { method: "DELETE" });
  return getSettings();
}

export async function changePassword(currentPassword, newPassword) {
  await apiClient("/users/me/password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
