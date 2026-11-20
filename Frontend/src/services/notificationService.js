import apiClient from "./apiClient";
export const getNotifications = (unreadOnly = false) => apiClient(`/notifications?limit=50${unreadOnly ? "&unread_only=true" : ""}`);
export const markNotificationRead = (id) => apiClient(`/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () => apiClient("/notifications/read-all", { method: "POST" });
