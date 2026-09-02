export function ApiUnavailable() {
  return (
    <div className="alert error" role="alert">
      <strong>Local API unavailable</strong>
      <span>Start the API with <code>npm run dev</code>, then refresh this page.</span>
    </div>
  );
}

