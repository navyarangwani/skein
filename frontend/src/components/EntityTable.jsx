export default function EntityTable({ entities, onSelect }) {
  return (
    <table>
      <thead>
        <tr>
          <th>entity_id</th>
          <th>name</th>
          <th>type</th>
          <th>risk score</th>
          <th>flags</th>
        </tr>
      </thead>
      <tbody>
        {entities.map((e) => (
          <tr key={e.entity_id} onClick={() => onSelect(e.entity_id)}>
            <td>{e.entity_id}</td>
            <td>{e.name}</td>
            <td>{e.entity_type}</td>
            <td>
              <div className="score-bar-track">
                <div
                  className="score-bar-fill"
                  style={{ width: `${e.anomaly_score}%` }}
                />
              </div>
            </td>
            <td>
              {e.in_cycle && <span className="cycle-flag">in cycle</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}