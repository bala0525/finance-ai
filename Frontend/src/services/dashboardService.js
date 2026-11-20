import { dashboardMockData } from "../data/dashboardData";

/*
 * Temporary dashboard data source.
 *
 * Later, when FastAPI backend is ready, this file will become
 * the single place where dashboard API requests are handled.
 */

export async function getDashboardData() {
  return dashboardMockData;
}
