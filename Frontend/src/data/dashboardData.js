export const dashboardMockData = {
  overview: {
    aiEmployees: 8,
    documents: 0,
    knowledgeBase: 0,
    conversations: 0,
  },

  systemStatus: {
    status: "operational",
    label: "All systems operational",
  },

  aiEmployees: [
    {
      id: 1,
      number: "01",
      name: "AI Accounts Payable Employee",
      description:
        "Manage supplier invoices, approvals and payable queues.",
      output: "Validated invoices",
      status: "READY",
    },
    {
      id: 2,
      number: "02",
      name: "AI Accounts Receivable Employee",
      description:
        "Monitor receivables and collections.",
      output: "Aging & collection priorities",
      status: "READY",
    },
    {
      id: 3,
      number: "03",
      name: "AI Invoice Processing Employee",
      description:
        "Extract, validate and classify invoice data.",
      output: "Structured invoice data",
      status: "READY",
    },
    {
      id: 4,
      number: "04",
      name: "AI Reconciliation Employee",
      description:
        "Match transactions across ledgers, banks and subledgers.",
      output: "Reconciliation statements",
      status: "READY",
    },
    {
      id: 5,
      number: "05",
      name: "AI Finance Analyst",
      description:
        "Answer finance questions and perform controlled analysis.",
      output: "Variance & forecast analysis",
      status: "READY",
    },
    {
      id: 6,
      number: "06",
      name: "AI Expense Employee",
      description:
        "Process employee and business expenses.",
      output: "Expense validation",
      status: "READY",
    },
    {
      id: 7,
      number: "07",
      name: "AI Financial Reporting Employee",
      description:
        "Prepare recurring management and statutory reporting packs.",
      output: "P&L / BS / CF packs",
      status: "READY",
    },
    {
      id: 8,
      number: "08",
      name: "AI Fraud Detection Employee",
      description:
        "Detect anomalous financial behavior.",
      output: "Risk alerts & scores",
      status: "READY",
    },
  ],
};
