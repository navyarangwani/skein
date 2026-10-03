const BASE_URL = "http://localhost:8000";

async function request(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`Request failed: ${path} (${res.status})`);
  return res.json();
}

export const getStats = () => request("/stats");

export const getEntities = ({ limit = 100, sortBy = "anomaly_score", anomaliesOnly = false } = {}) =>
  request(`/entities?limit=${limit}&sort_by=${sortBy}&anomalies_only=${anomaliesOnly}`);

export const getEntity = (entityId) => request(`/entities/${entityId}`);

export const getEntityTransactions = (entityId, limit = 50) =>
  request(`/entities/${entityId}/transactions?limit=${limit}`);