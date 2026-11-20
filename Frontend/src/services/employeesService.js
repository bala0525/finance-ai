import { employeesMockData } from "../data/employeesData";
import { getAgents } from "./agentsService";

/*
 * Employee catalogue = static presentation metadata (names, descriptions,
 * intended outputs from employeesData.js) + live summary counts from
 * GET /agents. Employee ids 1-8 line up with the backend agent ids.
 *
 * If the backend is unreachable this throws, so the Employees page shows its
 * error state instead of pretending the workforce is operational.
 */

export async function getEmployees() {
  const { agents } = await getAgents();

  const summaryById = new Map(
    (Array.isArray(agents) ? agents : []).map((agent) => [
      agent.id,
      agent.summary || {},
    ])
  );

  return employeesMockData.map((employee) => ({
    ...employee,
    summary: summaryById.get(employee.id) || null,
  }));
}
