import {
  agentStatusOverview,
  agentStatusMockData,
} from "../data/agentStatusData";

export async function getAgentStatusData() {
  return {
    overview: agentStatusOverview,
    agents: agentStatusMockData,
  };
}
