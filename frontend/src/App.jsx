import { useEffect, useState } from "react";
import { getStats, getEntities } from "./api";
import EntityTable from "./components/EntityTable";
import EntityDrawer from "./components/EntityDrawer";

export default function App() {
  const [stats, setStats] = useState(null);
  const [entities, setEntities] = useState([]);
  const [sortBy, setSortBy] = useState("anomaly_score");
  const [anomaliesOnly, setAnomaliesOnly] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    getStats().then(setStats);
  }, []);

  useEffect(() => {
    getEntities({ limit: 100, sortBy, anomaliesOnly }).then(setEntities);
  }, [sortBy, anomaliesOnly]);

  return (
    <div className="app">
      <aside className="rail">
        <div>
          <div className="wordmark">Skein</div>
          <div className="wordmark-sub">Financial crime network detector</div>
        </div>
        {stats && (
          <div className="rail-stats">
            <div className="stat-block">
              <div className="stat-value">{stats.total_entities.toLocaleString()}</div>
              <div className="stat-label">entities tracked</div>
            </div>
            <div className="stat-block">
              <div className="stat-value">{stats.total_anomalies}</div>
              <div className="stat-label">flagged anomalies</div>
            </div>
            <div className="stat-block">
              <div className="stat-value">{stats.total_in_cycle}</div>
              <div className="stat-label">entities in cycles</div>
            </div>
            <div className="stat-block">
              <div className="stat-value">{stats.community_count}</div>
              <div className="stat-label">communities (Louvain)</div>
            </div>
          </div>
        )}
      </aside>

      <main className="main">
        <div className="ledger-controls">
          <span>sort by</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="anomaly_score">risk score</option>
            <option value="pagerank">pagerank</option>
            <option value="betweenness">betweenness</option>
          </select>
          <label>
            <input
              type="checkbox"
              checked={anomaliesOnly}
              onChange={(e) => setAnomaliesOnly(e.target.checked)}
            />
            anomalies only
          </label>
        </div>

        <EntityTable entities={entities} onSelect={setSelectedId} />
      </main>

      {selectedId && (
        <EntityDrawer entityId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}