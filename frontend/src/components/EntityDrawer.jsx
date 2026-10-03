import { useEffect, useState } from "react";
import { getEntity, getEntityTransactions } from "../api";

export default function EntityDrawer({ entityId, onClose }) {
  const [entity, setEntity] = useState(null);
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    getEntity(entityId).then(setEntity);
    getEntityTransactions(entityId, 15).then(setTransactions);
  }, [entityId]);

  if (!entity) return null;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer">
        <button className="drawer-close" onClick={onClose}>close ×</button>
        <div className="drawer-name">{entity.name}</div>
        <div className="drawer-id">{entity.entity_id} · {entity.entity_type}</div>

        <div className="drawer-section">
          <div className="drawer-section-label">risk score: {entity.anomaly_score.toFixed(1)}</div>
          <div className="score-bar-track" style={{ width: "100%" }}>
            <div className="score-bar-fill" style={{ width: `${entity.anomaly_score}%` }} />
          </div>
        </div>

        <div className="drawer-section">
          <div className="drawer-section-label">recent thread ({transactions.length} shown)</div>
          {transactions.map((t) => (
            <div className="thread-item" key={t.transaction_id}>
              <div className="thread-row">
                <span>{t.source_entity_id} → {t.destination_entity_id}</span>
                <span>₹{t.amount.toLocaleString("en-IN")}</span>
              </div>
              <div className="thread-meta">{t.timestamp} · {t.transaction_type}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}