import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getProfile,
  updateProfile,
  deleteProfileField,
} from "../../services/profileService";
import { useAuthContext } from "../../context/AuthContext";
import Settings from "../Settings/Settings";
import "./Profile.css";

const PHONE_PATTERN = /^\+?\(?[0-9][0-9\s()-]{6,24}$/;

const formFrom = (p) => ({
  name: p.personal.name,
  email: p.personal.email,
  phone: p.personal.phone,
  department: p.personal.department,
  jobTitle: p.personal.jobTitle,
  location: p.personal.location,
  bio: p.personal.bio,
});

function validateForm(form) {
  if ((form.name || "").trim().length < 2) return "Full name must be at least 2 characters.";
  if (form.phone && !PHONE_PATTERN.test(form.phone.trim())) return "Enter a valid phone number.";
  if ((form.department || "").length > 100) return "Department must be 100 characters or fewer.";
  if ((form.jobTitle || "").length > 100) return "Job title must be 100 characters or fewer.";
  if ((form.location || "").length > 100) return "Location must be 100 characters or fewer.";
  if ((form.bio || "").length > 500) return "Bio must be 500 characters or fewer.";
  return "";
}

const DELETABLE = [
  ["phone", "Phone Number"],
  ["department", "Department"],
  ["jobTitle", "Job Title"],
  ["location", "Location"],
  ["bio", "Bio"],
];

function Profile() {
  const navigate = useNavigate();
  const { refreshUser } = useAuthContext();

  const [activeTab, setActiveTab] = useState("profile");
  const [profile, setProfile] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      try {
        setLoading(true);
        setError("");

        const result = await getProfile();

        if (isMounted) {
          setProfile(result);
          setEditForm(formFrom(result));
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            requestError?.message || "Unable to load profile information."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  const resetEditForm = () => {
    if (!profile) return;

    setEditForm(formFrom(profile));
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;

    setEditForm((current) => ({
      ...current,
      [name]: value,
    }));

    setSaved(false);
  };

  const handleEdit = () => {
    resetEditForm();
    setError("");
    setSaved(false);
    setEditMode(true);
  };

  const handleCancel = () => {
    resetEditForm();
    setError("");
    setEditMode(false);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaved(false);
      setError("");

      const validationError = validateForm(editForm);
      if (validationError) {
        setError(validationError);
        setSaving(false);
        return;
      }

      const updatedProfile = {
        ...profile,
        personal: {
          ...profile.personal,
          name: editForm.name.trim(),
          phone: (editForm.phone || "").trim(),
          department: (editForm.department || "").trim(),
          jobTitle: (editForm.jobTitle || "").trim(),
          location: (editForm.location || "").trim(),
          bio: (editForm.bio || "").trim(),
        },
      };

      const result = await updateProfile(updatedProfile);

      setProfile(result);
      setEditForm(formFrom(result));
      setEditMode(false);
      setSaved(true);

      // Update the sidebar/topbar user data
      refreshUser();
    } catch (requestError) {
      setError(requestError?.message || "Unable to save profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteField = async (field, label) => {
    if (!window.confirm(`Delete your ${label}? This clears the saved value.`)) {
      return;
    }
    try {
      setSaving(true);
      setSaved(false);
      setError("");
      const result = await deleteProfileField(field);
      setProfile(result);
      setEditForm(formFrom(result));
      setSaved(true);
      refreshUser();
    } catch (requestError) {
      setError(requestError?.message || `Unable to delete ${label}.`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="profile-page">
        <div className="profile-state">
          <div className="profile-loader" />
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="profile-page">
        <div className="profile-state profile-error">
          <strong>Unable to load profile</strong>
          <p>{error}</p>
          <button
            type="button"
            className="profile-save-button"
            onClick={() => window.location.reload()}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <div className="profile-page-header">
        <div>
          <span className="profile-eyebrow">ACCOUNT</span>
          <h1>My Profile</h1>
          <p>Manage your personal information and account settings.</p>
        </div>

        <button
          type="button"
          className="profile-back-button"
          onClick={() => navigate("/employees")}
        >
          ← Back to Finance Employees
        </button>
      </div>

      <div className="profile-page-tabs" role="tablist" aria-label="Profile sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "profile"}
          className={activeTab === "profile" ? "active" : ""}
          onClick={() => setActiveTab("profile")}
        >
          ◉ My Profile
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "settings"}
          className={activeTab === "settings" ? "active" : ""}
          onClick={() => {
            setActiveTab("settings");
            setSaved(false);
            setError("");
          }}
        >
          ⚙ Settings
        </button>
      </div>

      {activeTab === "settings" ? (
        <div className="profile-embedded-settings">
          <Settings />
        </div>
      ) : (
        <>
          {saved && (
            <div className="profile-success">
              <span>✓</span>
              Profile updated successfully.
            </div>
          )}

          {error && (
            <div className="profile-inline-error">{error}</div>
          )}

          <section className="profile-hero-card">
            <div className="profile-avatar-large">
              {(profile.personal.name || "U").charAt(0).toUpperCase()}
            </div>

            <div className="profile-hero-info">
              <div className="profile-name-row">
                <h2>{profile.personal.name}</h2>
                <span className="profile-active-badge">
                  <span />
                  Active
                </span>
              </div>

              <p>{profile.personal.email}</p>

              <div className="profile-role-row">
                <span>{profile.personal.role}</span>
                <span className="profile-dot">•</span>
                <span>{profile.personal.department || "No department"}</span>
              </div>
            </div>

            {!editMode && (
              <button
                type="button"
                className="profile-edit-button"
                onClick={handleEdit}
              >
                Edit Profile
              </button>
            )}
          </section>

          <section className="profile-card profile-personal-card">
            <div className="profile-card-header">
              <div>
                <span className="profile-card-kicker">
                  PERSONAL INFORMATION
                </span>
                <h3>Personal Details</h3>
                <p className="profile-section-description">
                  Basic information associated with your Finance AI account.
                </p>
              </div>
              <span className="profile-card-icon">◉</span>
            </div>

            {editMode ? (
              <div className="profile-edit-form">
                <div className="profile-form-grid">
                  <div className="profile-field">
                    <label htmlFor="profile-name">Full Name</label>
                    <input
                      id="profile-name"
                      name="name"
                      type="text"
                      value={editForm.name || ""}
                      onChange={handleInputChange}
                      autoComplete="name"
                      required
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-email">Email Address</label>
                    <input
                      id="profile-email"
                      name="email"
                      type="email"
                      value={editForm.email || ""}
                      readOnly
                      title="Email is your sign-in identity and cannot be changed here."
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-phone">Phone Number</label>
                    <input
                      id="profile-phone"
                      name="phone"
                      type="text"
                      value={editForm.phone || ""}
                      onChange={handleInputChange}
                      autoComplete="tel"
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-department">Department</label>
                    <input
                      id="profile-department"
                      name="department"
                      type="text"
                      value={editForm.department || ""}
                      onChange={handleInputChange}
                      maxLength={100}
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-jobTitle">Job Title</label>
                    <input
                      id="profile-jobTitle"
                      name="jobTitle"
                      type="text"
                      value={editForm.jobTitle || ""}
                      onChange={handleInputChange}
                      maxLength={100}
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-location">Location</label>
                    <input
                      id="profile-location"
                      name="location"
                      type="text"
                      value={editForm.location || ""}
                      onChange={handleInputChange}
                      maxLength={100}
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-bio">Bio</label>
                    <textarea
                      id="profile-bio"
                      name="bio"
                      rows={3}
                      value={editForm.bio || ""}
                      onChange={handleInputChange}
                      maxLength={500}
                    />
                  </div>

                  <div className="profile-field">
                    <label htmlFor="profile-role">Role</label>
                    <input
                      id="profile-role"
                      type="text"
                      value={profile.personal.role || ""}
                      readOnly
                    />
                  </div>
                </div>

                <div className="profile-form-actions">
                  <button
                    type="button"
                    className="profile-cancel-button"
                    onClick={handleCancel}
                    disabled={saving}
                  >
                    Cancel
                  </button>

                  <button
                    type="button"
                    className="profile-save-button"
                    onClick={handleSave}
                    disabled={saving || !editForm.name?.trim()}
                  >
                    {saving ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="profile-details-grid">
                <div className="profile-detail">
                  <span>Full Name</span>
                  <strong>{profile.personal.name}</strong>
                </div>
                <div className="profile-detail">
                  <span>Email Address</span>
                  <strong>{profile.personal.email}</strong>
                </div>
                <div className="profile-detail">
                  <span>Role</span>
                  <strong>{profile.personal.role}</strong>
                </div>
                {DELETABLE.map(([field, label]) => (
                  <div className="profile-detail" key={field}>
                    <span>{label}</span>
                    <strong>{profile.personal[field] || "Not provided"}</strong>
                    {profile.personal[field] && (
                      <button
                        type="button"
                        className="profile-cancel-button"
                        disabled={saving}
                        onClick={() => handleDeleteField(field, label)}
                        aria-label={`Delete ${label}`}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="profile-grid">
            <section className="profile-card">
              <div className="profile-card-header">
                <div>
                  <span className="profile-card-kicker">ORGANIZATION</span>
                  <h3>Workspace Details</h3>
                </div>
                <span className="profile-card-icon">◇</span>
              </div>

              <div className="profile-details-grid">
                <div className="profile-detail">
                  <span>Company</span>
                  <strong>{profile.organization.company}</strong>
                </div>
                <div className="profile-detail">
                  <span>Workspace</span>
                  <strong>{profile.organization.workspace}</strong>
                </div>
                <div className="profile-detail">
                  <span>Timezone</span>
                  <strong>{profile.organization.timezone}</strong>
                </div>
                <div className="profile-detail">
                  <span>Currency</span>
                  <strong>{profile.organization.currency}</strong>
                </div>
              </div>
            </section>

            <section className="profile-card">
              <div className="profile-card-header">
                <div>
                  <span className="profile-card-kicker">ACCOUNT SECURITY</span>
                  <h3>Account Information</h3>
                </div>
                <span className="profile-card-icon">◈</span>
              </div>

              <div className="profile-account-grid">
                <div className="profile-account-item">
                  <span>Account Status</span>
                  <div className="profile-status-value">
                    <span className="profile-status-dot" />
                    {profile.account.status}
                  </div>
                </div>
                <div className="profile-account-item">
                  <span>Member Since</span>
                  <strong>{profile.account.memberSince}</strong>
                </div>
                <div className="profile-account-item">
                  <span>Last Login</span>
                  <strong>{profile.account.lastLogin}</strong>
                </div>
                <div className="profile-account-item">
                  <span>Authentication</span>
                  <strong>{profile.account.authentication}</strong>
                </div>
              </div>
            </section>
          </div>

          <section className="profile-security-banner">
            <div className="profile-security-icon">!</div>
            <div>
              <h3>Security &amp; Privacy</h3>
              <p>
                Manage notification preferences and account security from the
                Settings tab. Authentication and permissions must be enforced
                by the backend.
              </p>
            </div>
            <button
              type="button"
              className="profile-security-button"
              onClick={() => setActiveTab("settings")}
            >
              Open Settings
            </button>
          </section>
        </>
      )}
    </div>
  );
}

export default Profile;
