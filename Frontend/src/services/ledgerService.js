import apiClient from "./apiClient";

const post = (path, body) => apiClient(path, { method: "POST", body: JSON.stringify(body) });

const query = (params = {}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  return search.toString();
};

export const getLedgerAccounts = () => apiClient("/ledger/accounts");
export const seedLedgerAccounts = () => apiClient("/ledger/accounts/seed-defaults", { method: "POST" });
export const createLedgerAccount = (body) => post("/ledger/accounts", body);
export const getLedgerJournals = (params) => apiClient(`/ledger/journals?${query(params)}`);
export const createLedgerJournal = (body) => post("/ledger/journals", body);
export const reverseLedgerJournal = (voucher) => apiClient(`/ledger/journals/${encodeURIComponent(voucher)}/reverse`, { method: "POST" });
export const getTrialBalance = (asOf) => apiClient(`/ledger/trial-balance?${query({ as_of: asOf })}`);
export const getProfitAndLoss = (start, end) => apiClient(`/ledger/profit-and-loss?${query({ start, end })}`);
export const getBalanceSheet = (asOf) => apiClient(`/ledger/balance-sheet?${query({ as_of: asOf })}`);
export const getCashFlow = (start, end) => apiClient(`/ledger/cash-flow?${query({ start, end })}`);
export const getLedgerPeriodCloses = () => apiClient("/ledger/period-closes");
export const closeLedgerPeriod = (body) => post("/ledger/period-closes", body);

export const getLedgerProfitAndLoss = (start, end) => apiClient(`/ledger/profit-and-loss?${query({ start, end })}`);
export const getLedgerBalanceSheet = (asOf) => apiClient(`/ledger/balance-sheet?${query({ as_of: asOf })}`);
export const getLedgerCashFlow = (start, end) => apiClient(`/ledger/cash-flow?${query({ start, end })}`);
