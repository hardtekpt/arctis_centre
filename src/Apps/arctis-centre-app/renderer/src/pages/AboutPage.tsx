interface AboutPageProps {
  logs: string[];
  lastStatus: string;
  lastError: string | null;
}

export default function AboutPage({ logs, lastStatus, lastError }: AboutPageProps) {
  return (
    <section className="card about-page">
      <h3>About</h3>
      <p>Arctis Centre</p>
      <p>Electron + React flyout dashboard for Arctis Nova + Sonar control.</p>
      <p>Backend bridge status: {lastError ? `Error (${lastError})` : lastStatus}</p>
      <div className="logs-panel">
        <div className="logs-header">Logs</div>
        <div className="logs-list">
          {logs.length === 0 && <div className="log-line">No logs yet.</div>}
          {logs.map((line, idx) => (
            <div className="log-line" key={`${idx}-${line.slice(0, 12)}`}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
