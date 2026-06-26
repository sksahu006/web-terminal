import { useCallback, useEffect, useMemo, useState } from 'react';

const TOKEN_KEY = 'workspace_token';
const REFRESH_TOKEN_KEY = 'workspace_refresh_token';
const API_BASE = import.meta.env.VITE_API_BASE || '';

function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) return false;

  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    return false;
  }

  const data = await response.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
  return true;
}

async function apiRequest(path, options = {}, retry = true) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  });

  if (response.status === 401 && retry && path !== '/auth/login' && path !== '/auth/register') {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiRequest(path, options, false);
  }

  const data = await response.json().catch(() => ({}));

  if (response.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    throw new Error('Session expired. Please log in again.');
  }

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed');
  }

  return data;
}

function Badge({ children, tone = 'default' }) {
  const tones = {
    default: 'border-slate-700 bg-slate-900 text-slate-300',
    easy: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
    running: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
    solved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  };

  return <span className={`inline-flex items-center rounded border px-2 py-1 text-xs font-medium ${tones[tone] || tones.default}`}>{children}</span>;
}

function EmptyState({ title, body }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-8 text-center">
      <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
      <p className="mt-2 text-sm text-slate-400">{body}</p>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [selectedSlug, setSelectedSlug] = useState(null);
  const [room, setRoom] = useState(null);
  const [progress, setProgress] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ email: '', username: '', password: '' });

  const selectedRoom = useMemo(() => rooms.find((item) => item.slug === selectedSlug), [rooms, selectedSlug]);

  const showMessage = useCallback((text, type = 'info') => {
    setMessage({ text, type });
    window.setTimeout(() => setMessage(null), 4500);
  }, []);

  const loadActiveSession = useCallback(async () => {
    try {
      const data = await apiRequest('/labs/sessions/active');
      setActiveSession(data.has_active_session ? data.session : null);
    } catch (error) {
      showMessage(error.message, 'error');
    }
  }, [showMessage]);

  const loadRoomProgress = useCallback(async (slug) => {
    if (!slug) return;
    try {
      const data = await apiRequest(`/labs/rooms/${slug}/progress`);
      setProgress(data);
    } catch (error) {
      setProgress(null);
    }
  }, []);

  const loadRoom = useCallback(async (slug) => {
    if (!slug) return;
    setBusy(true);
    try {
      const [roomData] = await Promise.all([apiRequest(`/labs/rooms/${slug}`), loadRoomProgress(slug)]);
      setRoom(roomData);
    } catch (error) {
      showMessage(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }, [loadRoomProgress, showMessage]);

  const loadApp = useCallback(async () => {
    setLoading(true);
    try {
      const me = await apiRequest('/auth/me');
      const roomList = await apiRequest('/labs/rooms');
      setUser(me);
      setRooms(roomList);
      const firstSlug = selectedSlug || roomList[0]?.slug || null;
      setSelectedSlug(firstSlug);
      await Promise.all([loadActiveSession(), firstSlug ? loadRoom(firstSlug) : Promise.resolve()]);
    } catch (error) {
      setUser(null);
      setRooms([]);
      setActiveSession(null);
      setRoom(null);
    } finally {
      setLoading(false);
    }
  }, [loadActiveSession, loadRoom, selectedSlug]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    loadApp();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedSlug) loadRoom(selectedSlug);
  }, [selectedSlug]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = authMode === 'register'
        ? { email: authForm.email, username: authForm.username, password: authForm.password }
        : { email: authForm.email, password: authForm.password };
      const data = await apiRequest(`/auth/${authMode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
      setUser(data.user);
      showMessage(authMode === 'register' ? 'Account created.' : 'Logged in.', 'success');
      await loadApp();
    } catch (error) {
      showMessage(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setUser(null);
    setActiveSession(null);
    setRoom(null);
    setProgress(null);
  }

  async function startLab() {
    if (!room) return;
    setBusy(true);
    try {
      const session = await apiRequest(`/labs/rooms/${room.slug}/start`, { method: 'POST' });
      setActiveSession(session);
      showMessage('Lab started. Terminal is ready.', 'success');
    } catch (error) {
      showMessage(error.message, 'error');
      await loadActiveSession();
    } finally {
      setBusy(false);
    }
  }

  async function stopLab() {
    if (!activeSession) return;
    setBusy(true);
    try {
      await apiRequest(`/labs/sessions/${activeSession.id}/stop`, { method: 'POST' });
      setActiveSession(null);
      showMessage('Lab stopped.', 'success');
    } catch (error) {
      showMessage(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function submitFlag(challengeId) {
    const flag = answers[challengeId]?.trim();
    if (!flag) {
      showMessage('Enter a flag before submitting.', 'error');
      return;
    }

    setBusy(true);
    try {
      const result = await apiRequest(`/labs/challenges/${challengeId}/submit`, {
        method: 'POST',
        body: JSON.stringify({ flag }),
      });
      showMessage(result.message, result.correct ? 'success' : 'error');
      if (room?.slug) await loadRoomProgress(room.slug);
    } catch (error) {
      showMessage(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }

  if (!user && !loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        {message && (
          <div className={`fixed right-5 top-5 z-20 rounded-md border px-4 py-3 text-sm shadow-lg ${message.type === 'error' ? 'border-red-500/40 bg-red-950 text-red-100' : 'border-emerald-500/40 bg-emerald-950 text-emerald-100'}`}>{message.text}</div>
        )}
        <section className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-6 py-12 lg:grid-cols-[1fr_420px]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">Cyber Lab Platform</p>
            <h1 className="mt-4 text-4xl font-bold tracking-tight text-white sm:text-6xl">Practice security labs in disposable browser terminals.</h1>
            <p className="mt-5 text-lg text-slate-300">Create a local account, start a room, find flags, submit answers, and track progress without GitHub OAuth.</p>
          </div>

          <form onSubmit={submitAuth} className="rounded-lg border border-slate-800 bg-slate-900/70 p-5 shadow-xl">
            <div className="grid grid-cols-2 rounded-md bg-slate-950 p-1">
              <button type="button" onClick={() => setAuthMode('login')} className={`rounded px-3 py-2 text-sm font-semibold ${authMode === 'login' ? 'bg-cyan-400 text-slate-950' : 'text-slate-300'}`}>Login</button>
              <button type="button" onClick={() => setAuthMode('register')} className={`rounded px-3 py-2 text-sm font-semibold ${authMode === 'register' ? 'bg-cyan-400 text-slate-950' : 'text-slate-300'}`}>Register</button>
            </div>

            <label className="mt-5 block text-sm font-medium text-slate-200">Email</label>
            <input value={authForm.email} onChange={(event) => setAuthForm((current) => ({ ...current, email: event.target.value }))} type="email" required className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />

            {authMode === 'register' && (
              <>
                <label className="mt-4 block text-sm font-medium text-slate-200">Username</label>
                <input value={authForm.username} onChange={(event) => setAuthForm((current) => ({ ...current, username: event.target.value }))} required minLength={2} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />
              </>
            )}

            <label className="mt-4 block text-sm font-medium text-slate-200">Password</label>
            <input value={authForm.password} onChange={(event) => setAuthForm((current) => ({ ...current, password: event.target.value }))} type="password" required minLength={6} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-400" />

            <button disabled={busy} className="mt-6 w-full rounded-md bg-cyan-400 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-300 disabled:opacity-50">
              {busy ? 'Please wait...' : authMode === 'register' ? 'Create Account' : 'Login'}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Cyber Lab</p>
            <h1 className="text-xl font-semibold text-white">Room Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            {user && <span className="text-sm text-slate-300">{user.username || user.github_username || user.email}</span>}
            <button onClick={loadApp} className="rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-900">Refresh</button>
            <button onClick={logout} className="rounded-md bg-slate-800 px-3 py-2 text-sm text-slate-100 hover:bg-slate-700">Logout</button>
          </div>
        </div>
      </header>

      {message && (
        <div className={`fixed right-5 top-5 z-20 rounded-md border px-4 py-3 text-sm shadow-lg ${message.type === 'error' ? 'border-red-500/40 bg-red-950 text-red-100' : 'border-emerald-500/40 bg-emerald-950 text-emerald-100'}`}>{message.text}</div>
      )}

      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
          <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-white">Rooms</h2>
              <Badge>{rooms.length}</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {rooms.map((item) => (
                <button key={item.id} onClick={() => setSelectedSlug(item.slug)} className={`w-full rounded-md border p-4 text-left transition ${item.slug === selectedSlug ? 'border-cyan-400 bg-cyan-400/10' : 'border-slate-800 bg-slate-950 hover:border-slate-600'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium text-white">{item.title}</h3>
                      <p className="mt-1 line-clamp-2 text-sm text-slate-400">{item.description}</p>
                    </div>
                    <Badge tone={item.difficulty}>{item.difficulty}</Badge>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">{item.challenge_count} challenges / {item.access_mode}</p>
                </button>
              ))}
              {!rooms.length && <EmptyState title="No rooms" body="No published rooms were returned by the backend." />}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h2 className="font-semibold text-white">Active Lab</h2>
            {activeSession ? (
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <Badge tone="running">{activeSession.status}</Badge>
                <p className="break-all">{activeSession.access_url || 'No terminal URL yet'}</p>
                <div className="flex gap-2">
                  {activeSession.access_url && <a href={activeSession.access_url} target="_blank" rel="noreferrer" className="rounded-md bg-cyan-400 px-3 py-2 font-semibold text-slate-950 hover:bg-cyan-300">Open</a>}
                  <button disabled={busy} onClick={stopLab} className="rounded-md bg-red-500 px-3 py-2 font-semibold text-white hover:bg-red-400 disabled:opacity-50">Stop</button>
                </div>
              </div>
            ) : <p className="mt-3 text-sm text-slate-400">No active lab session.</p>}
          </section>
        </aside>

        <section className="space-y-6">
          {loading && <EmptyState title="Loading" body="Fetching your rooms and lab status." />}
          {!loading && room && (
            <>
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="flex flex-wrap gap-2"><Badge tone={room.difficulty}>{room.difficulty}</Badge><Badge>{room.template.access_mode}</Badge></div>
                    <h2 className="mt-3 text-2xl font-bold text-white">{room.title}</h2>
                    <p className="mt-2 max-w-3xl text-slate-300">{room.description}</p>
                  </div>
                  <button disabled={busy || !!activeSession} onClick={startLab} className="rounded-md bg-cyan-400 px-4 py-2 font-semibold text-slate-950 hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50">{activeSession ? 'Lab Running' : 'Start Lab'}</button>
                </div>

                {progress && (
                  <div className="mt-5 grid gap-3 sm:grid-cols-4">
                    <div className="rounded-md bg-slate-950 p-3"><p className="text-xs text-slate-500">Solved</p><p className="text-xl font-semibold">{progress.solved_challenges}/{progress.total_challenges}</p></div>
                    <div className="rounded-md bg-slate-950 p-3"><p className="text-xs text-slate-500">Points</p><p className="text-xl font-semibold">{progress.earned_points}/{progress.total_points}</p></div>
                    <div className="rounded-md bg-slate-950 p-3"><p className="text-xs text-slate-500">Room</p><p className="text-xl font-semibold">{selectedRoom?.slug}</p></div>
                    <div className="rounded-md bg-slate-950 p-3"><p className="text-xs text-slate-500">Status</p><p className="text-xl font-semibold">{activeSession ? 'Running' : 'Stopped'}</p></div>
                  </div>
                )}
              </div>

              {activeSession?.access_url && (
                <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/60">
                  <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3"><h3 className="font-semibold text-white">Terminal</h3><a href={activeSession.access_url} target="_blank" rel="noreferrer" className="text-sm text-cyan-300 hover:text-cyan-200">Open in new tab</a></div>
                  <iframe title="Lab terminal" src={activeSession.access_url} className="h-[520px] w-full bg-black" />
                </div>
              )}

              <div className="space-y-3">
                {room.challenges.map((challenge) => {
                  const challengeProgress = progress?.challenges?.find((item) => item.challenge_id === challenge.id);
                  return (
                    <div key={challenge.id} className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="flex flex-wrap gap-2"><Badge>{challenge.points} pts</Badge>{challengeProgress?.solved && <Badge tone="solved">solved</Badge>}</div>
                          <h3 className="mt-3 font-semibold text-white">{challenge.title}</h3>
                          <p className="mt-1 text-sm text-slate-300">{challenge.prompt}</p>
                        </div>
                        <div className="flex w-full gap-2 md:w-[420px]">
                          <input value={answers[challenge.id] || ''} onChange={(event) => setAnswers((current) => ({ ...current, [challenge.id]: event.target.value }))} placeholder="flag{...}" className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400" />
                          <button disabled={busy} onClick={() => submitFlag(challenge.id)} className="rounded-md bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-white disabled:opacity-50">Submit</button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default App;
