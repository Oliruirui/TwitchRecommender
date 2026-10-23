import { useRef, useState, type FormEvent } from 'react';
import { fetchRecommendations, type RecommendationResponse } from './api';
import './App.css';

export default function App() {
  const [userId, setUserId] = useState('');
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submittedId, setSubmittedId] = useState('');
  const pending = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const id = userId.trim();
    setResult(null); setError('');
    if (Array.from(id).length < 1 || Array.from(id).length > 128) {
      setError('Enter a user ID between 1 and 128 characters.'); return;
    }
    pending.current = true; setLoading(true); setSubmittedId(id);
    try { setResult(await fetchRecommendations(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Something went wrong. Please try again.'); }
    finally { pending.current = false; setLoading(false); }
  }

  return <div className="shell">
    <header className="header">
      <a className="brand" href="/" aria-label="Channel Atlas home"><span className="brand-mark" aria-hidden="true">a</span>channel<span className="brand-light">atlas</span></a>
      <span className="project-label">TWITCH RECOMMENDER <span> / </span> LOCAL EXPLORER</span>
      <span className="build-label">V.01 <span className="dot" /> LOCAL</span>
    </header>
    <main>
      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow"><span className="tiny-line" /> YOUR NEXT CHANNEL STARTS HERE</p>
        <h1 id="page-title">Less searching.<br />More <span>your thing.</span></h1>
        <p className="intro-copy">Explore channels picked for a user, powered by a<br className="desktop-break" /> two-tower recommendation model.</p>
      </section>
      <section className="workspace" aria-label="Recommendation explorer">
        <aside className="controls">
          <div className="section-heading"><span className="step">01</span><h2>Find your channels</h2></div>
          <form onSubmit={submit} noValidate>
            <label htmlFor="user-id">Dataset user ID</label>
            <p id="user-id-help" className="help">Use a user from the training dataset.</p>
            <div className="input-wrap"><span aria-hidden="true">#</span><input id="user-id" name="user-id" value={userId} onChange={event => setUserId(event.target.value)} placeholder="e.g. 1" autoComplete="off" spellCheck={false} aria-describedby="user-id-help" disabled={loading} /></div>
            <button type="submit" disabled={loading}>{loading ? 'Finding channels…' : 'Get recommendations'}<span aria-hidden="true">↗</span></button>
          </form>
          <div className="settings"><span>RESULTS PER REQUEST</span><strong>10 channels</strong></div>
          <div className="dataset-note"><span className="note-icon" aria-hidden="true">i</span><p>This is a historical dataset.<br />New user IDs receive popular channels. Results don’t indicate live status.</p></div>
          <div className="architecture"><span>THE REQUEST JOURNEY</span><p>React <span>→</span> Java <span>→</span> Python</p></div>
        </aside>
        <section className="results" aria-labelledby="results-title" aria-busy={loading}>
          <div className="results-header"><div className="section-heading"><span className="step">02</span><h2 id="results-title">Your discovery list</h2></div><span className="count">{result ? `${String(result.items.length).padStart(2, '0')} CHANNELS` : 'TOP 10'}</span></div>
          <div role="status" aria-live="polite" className="status-message">
            {loading && <p>Finding channels for user {submittedId}…</p>}
            {result && <><div className="result-meta"><span className={`badge ${result.method === 'popular' ? 'popular' : ''}`}>{result.method === 'two_tower' ? 'Personalized' : 'Popular channels'}</span><span className="user-caption">For user {submittedId}</span></div>
              {result.fallback_reason === 'unknown_user' && <p className="fallback">This user is not in the trained model. Here are popular channels to explore.</p>}
              {result.fallback_reason === 'retrieval_error' && <p className="fallback">Personalized retrieval is temporarily unavailable. Here are popular channels instead.</p>}
              {result.items.length === 0 && <p className="fallback">No channels were returned. Try another user ID.</p>}</>}
          </div>
          {error && <div role="alert" className="error"><strong>Couldn’t load recommendations</strong><p>{error}</p></div>}
          {!result && !error && <div className={`empty-state ${loading ? 'is-loading' : ''}`}>
            <div className="orbit" aria-hidden="true"><span className="orbit-dot" /><span className="orbit-core">↗</span><span className="orbit-dot second" /></div>
            <h3>{loading ? 'Connecting the dots' : 'A little discovery awaits.'}</h3>
            <p>{loading ? 'Your model is finding the closest channel matches.' : 'Enter a dataset user ID to explore their channel picks.'}</p>
            {!loading && <span className="empty-hint">START WITH USER ID 1 <span aria-hidden="true">↖</span></span>}
          </div>}
          {result && result.items.length > 0 && <ol className="channel-list">{result.items.map((channel, index) => <li key={channel.channel_id} className="channel-card">
            <span className="rank">{String(index + 1).padStart(2, '0')}</span><span className={`avatar tone-${index % 4}`} aria-hidden="true">{Array.from(channel.channel_name)[0]?.toUpperCase()}</span>
            <div className="channel-info"><h3>{channel.channel_name}</h3><span>Channel ID {channel.channel_id}</span></div>
            {channel.retrieval_score !== null && <details className="score"><summary>Match details</summary><span>Retrieval score: {channel.retrieval_score.toFixed(3)}</span></details>}
          </li>)}</ol>}
          {result && <p className="model-version">MODEL <code>{result.model_version}</code></p>}
        </section>
      </section>
    </main>
    <footer><span>BUILT FOR CURIOUS VIEWERS.</span><span>Offline learning. Online discovery.</span></footer>
  </div>;
}
