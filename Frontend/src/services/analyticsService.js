import {
  analyticsOverview,
  analyticsTrendData,
  employeeAnalytics,
  recentAnalyticsActivity,
} from "../data/analyticsData";

/*
 * Temporary Analytics service.
 *
 * Later this service will communicate with the FastAPI backend.
 *
 * Planned endpoints:
 * - GET /api/analytics/overview
 * - GET /api/analytics/trends
 * - GET /api/analytics/employees
 * - GET /api/analytics/activity
 */

export async function getAnalyticsData() {
  return {
    overview: analyticsOverview,
    trend: analyticsTrendData,
    employees: employeeAnalytics,
    recentActivity: recentAnalyticsActivity,
  };
}
