import React, { useEffect, useState } from 'react';
import {
  ShieldCheck, Mic, Send, Wallet, History, Headphones, LogOut,
  CheckCircle2, AlertTriangle, Users, RefreshCw, ArrowRight,
  LockKeyhole, MessageCircle, Sliders, UserCheck, ShieldAlert, XCircle, Save
} from 'lucide-react';
import { request, setAuthToken, getAuthToken } from './api';
import { speechProvider } from './speechAdapter';

const speak = (text) => {
  if ('speechSynthesis' in window && text) {
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'en-IN';
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    } catch (e) {
      // Speech synthesis fallback
    }
  }
};

export default function App() {
  // Saved session persistence
  const savedUser = (() => {
    try {
      const raw = localStorage.getItem('saathi_user');
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  })();

  // Auth state
  const [demoUsers, setDemoUsers] = useState([]);
  const [user, setUser] = useState(savedUser);
  const [username, setUsername] = useState('customer1');
  const [pin, setPin] = useState('1234');
  const [voiceConsent, setVoiceConsent] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);

  // Navigation
  const [tab, setTab] = useState(savedUser?.role === 'agent' ? 'agent' : 'send');
  const [caseFilter, setCaseFilter] = useState('ALL');

  // Customer banking state
  const [transcript, setTranscript] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [alternate, setAlternate] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [spoken, setSpoken] = useState('');
  const [pinInput, setPinInput] = useState('');
  const [listening, setListening] = useState(false);
  const [livenessListening, setLivenessListening] = useState(false);

  // Dynamic data from SQL database
  const [account, setAccount] = useState(null);
  const [payees, setPayees] = useState([]);
  const [payments, setPayments] = useState([]);
  const [customerCases, setCustomerCases] = useState([]);

  // Agent dashboard state
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [agentNote, setAgentNote] = useState('Verified case details and checked safety context.');
  const [auditLogs, setAuditLogs] = useState([]);
  const [systemConfigs, setSystemConfigs] = useState([]);
  const [auditSearch, setAuditSearch] = useState('');
  const [editLimits, setEditLimits] = useState({});

  // UI feedback
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Handle unauthorized events dispatched from api.js
  useEffect(() => {
    function handleUnauthorized(e) {
      setUser(null);
      setAuthToken(null);
      localStorage.removeItem('saathi_user');
      setError('Session expired or unauthorized. Please sign in.');
    }
    window.addEventListener('saathi_unauthorized', handleUnauthorized);
    return () => window.removeEventListener('saathi_unauthorized', handleUnauthorized);
  }, []);

  // Load demo users from SQL backend on mount
  useEffect(() => {
    async function loadDemoAccounts() {
      try {
        const users = await request('/api/demo-users');
        setDemoUsers(users);
        if (users.length && !user) {
          const defaultUser = users.find(u => u.username === 'customer1') || users[0];
          setUsername(defaultUser.username);
          setPin(defaultUser.username === 'customer2' ? '2468' : defaultUser.username === 'agent1' ? 'agentpass' : '1234');
        }
      } catch (err) {
        // Backend offline or starting up
      }
    }
    loadDemoAccounts();
  }, []);

  async function login(e) {
    if (e) e.preventDefault();
    if (!voiceConsent) {
      setError('Please accept the voice processing consent to proceed.');
      return;
    }
    setError('');
    setLoginLoading(true);
    try {
      const u = await request('/api/login', { username, pin });
      setAuthToken(u.token);
      setUser(u);
      localStorage.setItem('saathi_user', JSON.stringify(u));
      setTab(u.role === 'agent' ? 'agent' : 'send');
      setSuccessMsg(`Signed in as ${u.display_name}`);
      speak(`Welcome back, ${u.display_name.split(' ')[0]}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    setUser(null);
    setAuthToken(null);
    localStorage.removeItem('saathi_user');
    setResult(null);
    setTranscript('');
    setError('');
    setSuccessMsg('');
    speak('Signed out.');
  }

  // Refresh dynamic data based on role
  async function refresh() {
    if (!user) return;
    setError('');
    try {
      if (user.role === 'customer') {
        const [acctData, payeeData, paymentData, casesData] = await Promise.all([
          request(`/api/account/${user.user_id}`),
          request(`/api/payees/${user.user_id}`),
          request(`/api/payments/${user.user_id}`),
          request(`/api/cases/${user.user_id}`)
        ]);
        setAccount(acctData);
        setPayees(payeeData);
        setPayments(paymentData);
        setCustomerCases(casesData);
      } else {
        const [casesData, auditData, configsData] = await Promise.all([
          request('/api/agent/cases'),
          request('/api/audit'),
          request('/api/system/config')
        ]);
        setCases(casesData);
        setAuditLogs(auditData);
        setSystemConfigs(configsData);
        const map = {};
        configsData.forEach(c => { map[c.key] = c.value; });
        setEditLimits(map);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (user && getAuthToken()) {
      refresh();
    }
  }, [user, tab]);

  // Speech Recognition Provider
  function toggleListen() {
    if (listening) {
      speechProvider.stop();
      setListening(false);
      return;
    }
    if (!speechProvider.isAvailable()) {
      setError('Speech recognition is not supported in this browser. Please use the typed input fallback below.');
      return;
    }
    setError('');
    setListening(true);
    speechProvider.start(
      (data) => {
        setTranscript(data.transcript);
      },
      (err) => {
        setListening(false);
        setError(err);
      },
      (finalText) => {
        setListening(false);
        if (finalText) setTranscript(finalText);
      }
    );
  }

  // Voice input for liveness challenge phrase
  function toggleLivenessListen() {
    if (livenessListening) {
      speechProvider.stop();
      setLivenessListening(false);
      return;
    }
    if (!speechProvider.isAvailable()) {
      setError('Speech recognition is not available. Please type the digits in the input box.');
      return;
    }
    setLivenessListening(true);
    speechProvider.start(
      (data) => {
        setSpoken(data.transcript);
      },
      (err) => {
        setLivenessListening(false);
        setError(err);
      },
      (finalText) => {
        setLivenessListening(false);
        if (finalText) setSpoken(finalText);
      }
    );
  }

  // Step 1: Submit Turn (Understand)
  async function submitTurn(e) {
    if (e) e.preventDefault();
    if (!transcript.trim()) return;
    setBusy(true);
    setError('');
    try {
      const r = await request('/api/turn', {
        user_id: user.user_id,
        transcript,
        confidence,
        alternate_transcript: alternate || null
      });
      setResult(r);
      if (r.action === 'readback') {
        speak(`Please confirm ${r.amount_words} to ${r.payee}`);
      } else if (r.action === 'clarify' || r.action === 'handoff') {
        speak(r.message);
      }
    } catch (err) {
      setError(err.message);
      speak('An error occurred. ' + err.message);
    } finally {
      setBusy(false);
    }
  }

  // Step 2: Confirm Transaction (Readback -> Confirm / Cancel)
  async function confirmTransaction(confirmed) {
    if (!result?.session_id) return;
    setBusy(true);
    setError('');
    try {
      const r = await request('/api/confirm', {
        user_id: user.user_id,
        session_id: result.session_id,
        confirmed
      });
      setResult(r);
      if (r.action === 'liveness') {
        speak(`Please repeat the digits: ${r.phrase}`);
      } else if (r.action === 'cancelled') {
        speak('Payment cancelled. No money moved.');
        setSuccessMsg('Payment cancelled safely.');
      }
    } catch (err) {
      setError(err.message);
      speak(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Step 3: Verify Liveness Challenge
  async function verifyLiveness() {
    if (!result?.session_id || !result?.token) return;
    setBusy(true);
    setError('');
    try {
      const r = await request('/api/liveness', {
        user_id: user.user_id,
        session_id: result.session_id,
        token: result.token,
        spoken_phrase: spoken
      });
      setResult(r);
      setSpoken('');
      if (r.action === 'pin') {
        speak('Liveness verified. Please enter your demo PIN.');
      } else if (r.action === 'receipt') {
        speak(`Payment of ${r.amount_rupees} rupees to ${r.payee} completed successfully.`);
        refresh();
      } else if (r.action === 'handoff') {
        speak(r.message);
      }
    } catch (err) {
      setError(err.message);
      speak(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Step 4: Verify PIN Step-Up
  async function verifyStepUpPin() {
    if (!result?.session_id || !pinInput) return;
    setBusy(true);
    setError('');
    try {
      const r = await request('/api/pin', {
        user_id: user.user_id,
        session_id: result.session_id,
        pin: pinInput
      });
      setResult(r);
      setPinInput('');
      if (r.action === 'receipt') {
        speak(`Payment of ${r.amount_rupees} rupees to ${r.payee} completed successfully.`);
        refresh();
      } else if (r.action === 'handoff') {
        speak(r.message);
      }
    } catch (err) {
      setError(err.message);
      speak(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Agent Case Actions (Approve, Reject, Repeat)
  async function actOnCase(action) {
    if (!selectedCase) return;
    setBusy(true);
    setError('');
    try {
      const res = await request(`/api/agent/cases/${selectedCase.id}`, {
        action,
        note: agentNote
      });
      setSuccessMsg(res.message);
      setSelectedCase(null);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Agent Unlocks Locked User
  async function unlockUserAccount(targetUserId) {
    setBusy(true);
    try {
      const res = await request(`/api/agent/unlock-user/${targetUserId}`);
      setSuccessMsg(res.message);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Agent Updates System Limit Threshold
  async function saveSystemConfig(key, value) {
    setBusy(true);
    try {
      await request('/api/system/config', { key, value: String(value) });
      setSuccessMsg(`Updated ${key} to ${value}`);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Reset Demo Database
  async function handleResetDemo() {
    if (!window.confirm('Reset all demo accounts, balances, and history to fresh seeded state?')) return;
    setBusy(true);
    try {
      await request('/api/reset-demo');
      setSuccessMsg('Demo environment reset successfully.');
      setResult(null);
      setTranscript('');
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // --------------------------------------------------------------------------
  // SCREEN 1: LOGIN & VOICE CONSENT NOTICE
  // --------------------------------------------------------------------------
  if (!user) {
    return (
      <div className="login-shell">
        <div className="login-art">
          <div className="brand">
            <span className="brand-mark"><ShieldCheck /></span> saathi<span className="brand-dot">.</span>
          </div>
          <div className="hero-copy">
            <span className="eyebrow">VOICE-FIRST BANKING</span>
            <h1>Your money.<br /><em>Your voice.</em><br />Your control.</h1>
            <p>
              An intelligent, safety-first banking interface designed for English and Hinglish voice payments.
              Every spoken detail is deterministically parsed and verified before any funds move.
            </p>
            <div className="trust-row">
              <ShieldCheck />
              <span>Deterministic Double-Entry Ledger</span>
              <span className="dot-sep">•</span>
              <span>Single-Use Liveness Safety</span>
            </div>
          </div>
          <div className="orb orb-one" />
          <div className="orb orb-two" />
        </div>

        <div className="login-panel">
          <div className="mobile-brand brand">
            <span className="brand-mark"><ShieldCheck /></span> saathi<span className="brand-dot">.</span>
          </div>
          <div className="login-card">
            <span className="eyebrow">AUTHENTICATION</span>
            <h2>Sign in to continue</h2>
            <p className="muted">Accounts loaded directly from SQL database as single source of truth.</p>

            <form onSubmit={login}>
              <label>Select Demo Account</label>
              <select
                value={username}
                onChange={(e) => {
                  const uname = e.target.value;
                  setUsername(uname);
                  setPin(uname === 'customer2' ? '2468' : uname === 'agent1' ? 'agentpass' : '1234');
                }}
              >
                {demoUsers.length > 0 ? (
                  demoUsers.map((u) => (
                    <option key={u.id} value={u.username}>
                      {u.display_name} · {u.role === 'agent' ? 'Agent Desk' : 'Customer'} ({u.username})
                      {u.is_locked ? ' [LOCKED]' : ''}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="customer1">Aarav Sharma · Customer (customer1)</option>
                    <option value="customer2">Meera Iyer · Customer (customer2)</option>
                    <option value="agent1">Demo Human Agent · Agent (agent1)</option>
                  </>
                )}
              </select>

              <label>{username === 'agent1' ? 'Agent Password' : 'Demo PIN'}</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="Enter PIN or password"
                required
              />

              {/* Consent Notice for Voice Processing */}
              <div style={{ marginTop: '16px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="consentCheckbox"
                  checked={voiceConsent}
                  onChange={(e) => setVoiceConsent(e.target.checked)}
                  style={{ width: '18px', height: '18px', marginTop: '2px' }}
                />
                <label htmlFor="consentCheckbox" style={{ margin: 0, fontSize: '11px', color: '#66768b', lineHeight: 1.5 }}>
                  <strong>Voice Processing Consent:</strong> I agree to spoken payment commands being processed in the browser. Audio is never stored permanently.
                </label>
              </div>

              <button className="primary full" type="submit" disabled={loginLoading || !voiceConsent}>
                {loginLoading ? (
                  <span className="loading-inline"><span className="spinner" /> Authenticating…</span>
                ) : (
                  <>Secure sign in <ArrowRight size={17} /></>
                )}
              </button>
            </form>

            {error && (
              <div className="error banner">
                <span>{error}</span>
                <button onClick={() => setError('')}>×</button>
              </div>
            )}

            <div className="demo-hint">
              <LockKeyhole size={16} />
              <span>Demo accounts: customer1 (1234) · customer2 (2468) · agent1 (agentpass)</span>
            </div>
          </div>

          <div className="login-footer">
            Designed around clarity, consent, and confidence. Synthetic demo only.
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // AUTHENTICATED WORKSPACE
  // --------------------------------------------------------------------------
  const isAgent = user.role === 'agent';
  const openCasesCount = cases.filter(c => c.status === 'OPEN').length;

  return (
    <div className="app-shell">
      {/* SIDEBAR NAVIGATION */}
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><ShieldCheck /></span> saathi<span className="brand-dot">.</span>
        </div>

        <div className="profile">
          <div className="avatar">
            {user.display_name.split(' ').map(x => x[0]).join('').slice(0, 2)}
          </div>
          <div>
            <strong>{user.display_name}</strong>
            <small>{isAgent ? 'Authorized Agent' : 'Verified Customer'}</small>
          </div>
        </div>

        <span className="nav-label">WORKSPACE</span>

        {isAgent ? (
          <>
            <button
              className={`nav-item ${tab === 'agent' ? 'active' : ''}`}
              onClick={() => setTab('agent')}
            >
              <Users size={18} />
              Agent Queue
              {openCasesCount > 0 && <span className="nav-count">{openCasesCount}</span>}
            </button>
            <button
              className={`nav-item ${tab === 'audit' ? 'active' : ''}`}
              onClick={() => setTab('audit')}
            >
              <History size={18} />
              Audit Trail
            </button>
            <button
              className={`nav-item ${tab === 'system' ? 'active' : ''}`}
              onClick={() => setTab('system')}
            >
              <Sliders size={18} />
              System Limits
            </button>
          </>
        ) : (
          <>
            <button
              className={`nav-item ${tab === 'send' ? 'active' : ''}`}
              onClick={() => setTab('send')}
            >
              <Send size={18} />
              Send Money
            </button>
            <button
              className={`nav-item ${tab === 'payees' ? 'active' : ''}`}
              onClick={() => setTab('payees')}
            >
              <Users size={18} />
              Saved Contacts
            </button>
            <button
              className={`nav-item ${tab === 'activity' ? 'active' : ''}`}
              onClick={() => setTab('activity')}
            >
              <History size={18} />
              Activity & Ledger
            </button>
            <button
              className={`nav-item ${tab === 'account' ? 'active' : ''}`}
              onClick={() => setTab('account')}
            >
              <Wallet size={18} />
              My Account
            </button>
            <button
              className={`nav-item ${tab === 'support' ? 'active' : ''}`}
              onClick={() => setTab('support')}
            >
              <Headphones size={18} />
              My Requests
              {customerCases.some(c => c.status === 'OPEN') && (
                <span className="nav-count">{customerCases.filter(c => c.status === 'OPEN').length}</span>
              )}
            </button>
          </>
        )}

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><Headphones /></div>
            <strong>Human Support</strong>
            <p>Uncertain requests pause automatically for agent review.</p>
            <button onClick={() => {
              if (!isAgent) {
                setTranscript('Please have an agent review my payment');
                submitTurn();
              } else {
                setTab('agent');
              }
            }}>
              {isAgent ? 'Open Queue' : 'Request Help'} <ArrowRight size={14} />
            </button>
          </div>

          <button className="nav-item logout" onClick={handleLogout}>
            <LogOut size={18} /> Sign out
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace /</span>{' '}
            <strong>
              {tab === 'send' ? 'Send Money' :
               tab === 'payees' ? 'Saved Contacts' :
               tab === 'activity' ? 'Activity & Ledger' :
               tab === 'account' ? 'My Account' :
               tab === 'support' ? 'Support Requests' :
               tab === 'agent' ? 'Agent Review Queue' :
               tab === 'audit' ? 'Audit Trail' : 'System Limits'}
            </strong>
          </div>

          <div className="top-right">
            <span className="secure-pill"><span /> SQL Database Source of Truth</span>
            <button className="icon-button" title="Refresh data" onClick={refresh} disabled={busy}>
              <RefreshCw size={17} className={busy ? 'spinner' : ''} />
            </button>
            <button className="icon-button" title="Reset Demo Data" onClick={handleResetDemo} disabled={busy}>
              <Sliders size={17} />
            </button>
            <div className="mini-avatar">{user.display_name[0]}</div>
          </div>
        </header>

        <div className="content">
          {/* FEEDBACK BANNERS */}
          {error && (
            <div className="error banner">
              <span>{error}</span>
              <button onClick={() => setError('')}>×</button>
            </div>
          )}
          {successMsg && (
            <div className="success-banner">
              <span>{successMsg}</span>
              <button onClick={() => setSuccessMsg('')}>×</button>
            </div>
          )}

          {/* ---------------- CUSTOMER: SEND MONEY ---------------- */}
          {!isAgent && tab === 'send' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">VOICE-ENABLED PAYMENTS</span>
                  <h1>How can I help you today?</h1>
                  <p>Speak naturally in English or Hinglish. We deterministically verify every detail before any money moves.</p>
                </div>
                <div className="balance-mini">
                  <span>Available Balance</span>
                  <strong>₹{(account?.balance_rupees || 0).toLocaleString('en-IN')}</strong>
                  <small><ShieldCheck size={13} /> Protected by double-entry ledger</small>
                </div>
              </div>

              <div className="send-grid">
                {/* Voice & Input Panel */}
                <section className="panel voice-panel">
                  <div className="panel-head">
                    <div>
                      <span className="step-label">STEP 01</span>
                      <h2>Tell me what to do</h2>
                    </div>
                    <span className="optional-pill">English + Hinglish</span>
                  </div>

                  <div className={`voice-orb ${listening ? 'listening' : ''}`}>
                    <div className="voice-orb-inner"><Mic size={30} /></div>
                    <span className="wave wave-a" />
                    <span className="wave wave-b" />
                  </div>

                  <p className="voice-caption">
                    {listening ? 'Listening… speak clearly into your mic' : 'Tap below to speak your payment request'}
                  </p>

                  <button
                    className={`record-button ${listening ? 'recording' : ''}`}
                    onClick={toggleListen}
                    type="button"
                  >
                    <Mic size={18} />
                    {listening ? 'Stop listening' : 'Push to talk'}
                  </button>

                  <div className="or-divider"><span />OR TYPE YOUR REQUEST<span /></div>

                  <form onSubmit={submitTurn}>
                    <textarea
                      value={transcript}
                      onChange={(e) => setTranscript(e.target.value)}
                      placeholder="e.g. Ramesh ko paanch sau rupaye bhej do"
                      rows="3"
                      required
                    />

                    {/* Quick Payee Chips */}
                    {payees.length > 0 && (
                      <div className="quick-send-hint">
                        <span>Quick contacts:</span>
                        <div className="quick-chips">
                          {payees.map(p => (
                            <button
                              key={p.id}
                              type="button"
                              className="chip-btn"
                              onClick={() => setTranscript(`${p.name} ko paanch sau rupaye bhej do`)}
                            >
                              {p.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="form-row" style={{ marginTop: '16px' }}>
                      <div className="field">
                        <label>Speech Confidence (Safety cross-check)</label>
                        <select
                          value={confidence ?? ''}
                          onChange={(e) => setConfidence(e.target.value === '' ? null : Number(e.target.value))}
                        >
                          <option value="">Not available</option>
                          <option value="0.95">High · 95%</option>
                          <option value="0.65">Medium · 65% (triggers review)</option>
                          <option value="0.35">Low · 35% (triggers review)</option>
                        </select>
                      </div>

                      <div className="field">
                        <label>Alternate Transcript (Cross-check)</label>
                        <input
                          value={alternate}
                          onChange={(e) => setAlternate(e.target.value)}
                          placeholder="Optional secondary transcript"
                        />
                      </div>
                    </div>

                    <button className="primary full" disabled={busy || !transcript.trim()}>
                      {busy ? (
                        <span className="loading-inline"><span className="spinner" /> Validating safely…</span>
                      ) : (
                        <>Understand request <ArrowRight size={17} /></>
                      )}
                    </button>
                  </form>

                  <p className="privacy-note">
                    <ShieldCheck size={15} />
                    Audio is never stored permanently. Deterministic NLP ensures amounts like <em>paanch sau</em>, <em>dedh hazaar</em>, and <em>dhai sau</em> are safely resolved.
                  </p>
                </section>

                {/* Safety Process Panel */}
                <section className="panel process-panel">
                  <div className="panel-head">
                    <div>
                      <span className="step-label">BUILT-IN SAFEGUARDS</span>
                      <h2>Safety before sending</h2>
                    </div>
                    <ShieldCheck className="green-icon" />
                  </div>

                  <div className="safety-steps">
                    {[
                      ['01', 'Deterministic Parsing', 'Understands amounts in digits, English, and Hinglish without guessing.'],
                      ['02', 'Cross-Check & Ambiguity', 'Disagreements or low confidence stop immediately for clarification or agent handoff.'],
                      ['03', 'Explicit Readback', 'You see and hear the exact amount and recipient before anything happens.'],
                      ['04', 'Single-Use Challenge', 'Server-generated 3-digit challenge expires in 90 seconds and prevents replays.'],
                      ['05', 'Atomic Double-Entry Ledger', 'Funds move safely between distinct accounts with full rollback on error.']
                    ].map(x => (
                      <div className="safety-step" key={x[0]}>
                        <span>{x[0]}</span>
                        <div>
                          <strong>{x[1]}</strong>
                          <p>{x[2]}</p>
                        </div>
                        <CheckCircle2 size={17} />
                      </div>
                    ))}
                  </div>

                  <div className="warning-card">
                    <AlertTriangle size={18} />
                    <div>
                      <strong>Never guess an amount or payee</strong>
                      <p>If anything is ambiguous, the payment pauses. You stay in full control.</p>
                    </div>
                  </div>
                </section>
              </div>

              {/* Step 2-5: Dynamic Flow Results */}
              {result && (
                <section className="panel result-panel">
                  <div className="panel-head">
                    <div>
                      <span className="step-label">SECURE CHECKOUT</span>
                      <h2>
                        {result.action === 'readback' ? 'Review before you confirm' :
                         result.action === 'liveness' ? 'Single-use liveness check' :
                         result.action === 'pin' ? 'Additional PIN verification' :
                         result.action === 'receipt' ? 'Payment complete' :
                         result.action === 'handoff' ? 'Human review requested' :
                         result.action === 'cancelled' ? 'Payment cancelled' : 'Please clarify'}
                      </h2>
                    </div>
                    <span className={`status-pill ${result.action === 'receipt' ? 'good' : result.action === 'handoff' ? 'warn' : ''}`}>
                      {result.action.replace('_', ' ')}
                    </span>
                  </div>

                  <p className="result-message">{result.message}</p>

                  {/* READBACK STATE: Large Confirm and Cancel Buttons */}
                  {result.action === 'readback' && (
                    <>
                      <div className="readback-card">
                        <div>
                          <span>YOU'RE SENDING</span>
                          <strong>₹{Number(result.amount_rupees).toLocaleString('en-IN')}</strong>
                          <small>{result.amount_words}</small>
                        </div>
                        <div className="recipient">
                          <span>TO RECIPIENT</span>
                          <strong>{result.payee}</strong>
                          <small>{result.pin_required ? 'PIN step-up required' : 'Saved contact'}</small>
                        </div>
                      </div>

                      <div className="consent-line">
                        <ShieldCheck size={17} />
                        I have verified the recipient and amount shown above.
                      </div>

                      <div className="action-row" style={{ marginTop: '20px', gap: '14px' }}>
                        <button
                          className="secondary"
                          style={{ minHeight: '48px', padding: '14px 24px', fontSize: '14px', flex: 1 }}
                          onClick={() => confirmTransaction(false)}
                          disabled={busy}
                        >
                          <XCircle size={18} /> Cancel payment
                        </button>
                        <button
                          className="primary"
                          style={{ minHeight: '48px', padding: '14px 28px', fontSize: '14px', flex: 1.2 }}
                          onClick={() => confirmTransaction(true)}
                          disabled={busy}
                        >
                          {busy ? <span className="spinner" /> : <>Confirm details <ArrowRight size={18} /></>}
                        </button>
                      </div>
                    </>
                  )}

                  {/* LIVENESS CHALLENGE STATE: Please say: X Y Z */}
                  {result.action === 'liveness' && (
                    <div className="challenge-card">
                      <span>YOUR SINGLE-USE CHALLENGE</span>
                      <strong style={{ fontSize: '32px', letterSpacing: '8px' }}>
                        Please say: {result.phrase}
                      </strong>
                      <p>
                        Say the three digits aloud or type them below. This single-use challenge expires in 90 seconds.
                      </p>

                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px' }}>
                        <button
                          type="button"
                          className={`record-button ${livenessListening ? 'recording' : ''}`}
                          style={{ padding: '10px 16px', fontSize: '11px' }}
                          onClick={toggleLivenessListen}
                        >
                          <Mic size={15} />
                          {livenessListening ? 'Listening…' : 'Speak challenge'}
                        </button>
                        <span style={{ fontSize: '11px', color: '#8898aa' }}>or type digits below:</span>
                      </div>

                      <input
                        value={spoken}
                        onChange={(e) => setSpoken(e.target.value)}
                        placeholder="e.g. 4 7 2 or four seven two"
                      />
                      <button className="primary full" onClick={verifyLiveness} disabled={busy || !spoken.trim()}>
                        {busy ? <span className="spinner" /> : 'Verify challenge'}
                      </button>
                    </div>
                  )}

                  {/* PIN STEP-UP STATE */}
                  {result.action === 'pin' && (
                    <div className="pin-card">
                      <LockKeyhole />
                      <div>
                        <strong>Enter your demo PIN</strong>
                        <p>{result.spoof_explanation || 'Customer 1: 1234 · Customer 2: 2468'}</p>
                      </div>
                      <input
                        type="password"
                        value={pinInput}
                        onChange={(e) => setPinInput(e.target.value)}
                        placeholder="4-digit PIN"
                        maxLength="8"
                      />
                      <button className="primary" onClick={verifyStepUpPin} disabled={busy || !pinInput}>
                        {busy ? <span className="spinner" /> : 'Verify PIN'}
                      </button>
                    </div>
                  )}

                  {/* SUCCESS RECEIPT STATE */}
                  {result.action === 'receipt' && (
                    <div className="receipt">
                      <CheckCircle2 size={32} />
                      <div>
                        <strong>₹{Number(result.amount_rupees).toLocaleString('en-IN')} sent to {result.payee}</strong>
                        <p>Reference: {result.reference}</p>
                        <small>Simulated transaction · Double-entry ledger verified · No real money moved</small>
                      </div>
                      <button
                        className="secondary"
                        onClick={() => {
                          setResult(null);
                          setTranscript('');
                          refresh();
                        }}
                      >
                        Done
                      </button>
                    </div>
                  )}

                  {/* HANDOFF / FAILURE STATE */}
                  {result.action === 'handoff' && (
                    <div className="warning-card">
                      <Headphones />
                      <div>
                        <strong>Escalated to Human Review (Case #{result.case_id || 'Pending'})</strong>
                        <p>{result.reason || 'Your payment was paused safely for agent review. No money moved.'}</p>
                      </div>
                      <button
                        className="secondary small"
                        style={{ marginLeft: 'auto', alignSelf: 'center' }}
                        onClick={() => {
                          setTab('support');
                        }}
                      >
                        View My Requests
                      </button>
                    </div>
                  )}
                </section>
              )}
            </>
          )}

          {/* ---------------- CUSTOMER: SAVED PAYEES ---------------- */}
          {!isAgent && tab === 'payees' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">BENEFICIARIES</span>
                  <h1>Saved contacts</h1>
                  <p>All payees loaded dynamically from your account record in the database.</p>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>Contacts ({payees.length})</h2>
                  <button className="secondary small" onClick={refresh}>Refresh</button>
                </div>

                <div className="payees-grid">
                  {payees.map(p => (
                    <div
                      key={p.id}
                      className="payee-card"
                      onClick={() => {
                        setTranscript(`${p.name} ko paanch sau rupaye bhej do`);
                        setTab('send');
                      }}
                      title="Click to initiate payment"
                    >
                      <div className="payee-avatar">{p.name[0]}</div>
                      <div className="payee-info">
                        <strong>{p.name}</strong>
                        <small>Acc: {p.account_number}</small>
                        <div style={{ marginTop: '6px' }}>
                          <span className={p.trusted ? 'badge-trusted' : 'badge-untrusted'}>
                            {p.trusted ? 'Trusted Contact' : 'New (PIN Required)'}
                          </span>
                        </div>
                      </div>
                      <ArrowRight size={15} color="#9aa7b8" />
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ---------------- CUSTOMER: ACTIVITY & LEDGER ---------------- */}
          {!isAgent && tab === 'activity' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">YOUR HISTORY</span>
                  <h1>Recent activity & ledger</h1>
                  <p>Every simulated transaction with balanced double-entry ledger verification.</p>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>Transactions ({payments.length})</h2>
                  <button className="secondary small" onClick={refresh}>Refresh</button>
                </div>

                {payments.length ? (
                  payments.map(p => (
                    <div className="payment-row" key={p.id} style={{ display: 'block' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '13px' }}>
                        <div className="payment-icon"><Send /></div>
                        <div className="payment-info">
                          <strong>{p.payee}</strong>
                          <small>
                            Ref: {p.reference} · {p.created_at ? new Date(p.created_at).toLocaleString() : ''}
                          </small>
                        </div>
                        <div className="payment-amount">
                          −₹{p.amount_rupees.toLocaleString('en-IN')}
                          <small>{p.status}</small>
                        </div>
                      </div>

                      {/* Double-Entry Ledger Breakdown */}
                      {p.ledger_entries && p.ledger_entries.length > 0 && (
                        <div className="ledger-box">
                          {p.ledger_entries.map(le => (
                            <span
                              key={le.id}
                              className={`ledger-tag ${le.entry_type === 'DEBIT' ? 'debit' : 'credit'}`}
                            >
                              {le.entry_type === 'DEBIT' ? '↓ DEBIT' : '↑ CREDIT'}: Account #{le.account_id} (₹{le.amount_paise / 100})
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="empty">
                    <History />
                    <strong>No transactions yet</strong>
                    <p>Your completed demo payments will appear here with full ledger breakdown.</p>
                  </div>
                )}
              </div>
            </>
          )}

          {/* ---------------- CUSTOMER: MY ACCOUNT & LIMITS ---------------- */}
          {!isAgent && tab === 'account' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">ACCOUNT OVERVIEW</span>
                  <h1>Your demo account</h1>
                  <p>All balances and transactions are synthetic and isolated from real banking systems.</p>
                </div>
              </div>

              <div className="account-card">
                <Wallet />
                <span>AVAILABLE DEMO BALANCE</span>
                <strong>₹{(account?.balance_rupees || 0).toLocaleString('en-IN')}</strong>
                <small>Account Number: {account?.account_number}</small>
              </div>

              <div className="panel limits-panel">
                <div className="panel-head">
                  <h2>Database-backed Safety Limits</h2>
                  <ShieldCheck className="green-icon" />
                </div>
                <div className="limit-row">
                  <span>Per-payment cap</span>
                  <strong>₹{(account?.limits?.per_payment_limit_rupees || 10000).toLocaleString('en-IN')}</strong>
                </div>
                <div className="limit-row">
                  <span>Daily payment cap</span>
                  <strong>₹{(account?.limits?.daily_limit_rupees || 20000).toLocaleString('en-IN')}</strong>
                </div>
                <div className="limit-row">
                  <span>Daily spent today</span>
                  <strong>₹{(account?.daily_spent_rupees || 0).toLocaleString('en-IN')}</strong>
                </div>
                <div className="limit-row">
                  <span>Extra PIN verification threshold</span>
                  <strong>Above ₹{(account?.limits?.payment_threshold_rupees || 5000).toLocaleString('en-IN')} or untrusted payee</strong>
                </div>
              </div>
            </>
          )}

          {/* ---------------- CUSTOMER: SUPPORT & HANDOFF REQUESTS ---------------- */}
          {!isAgent && tab === 'support' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">SUPPORT STATUS</span>
                  <h1>My escalated requests</h1>
                  <p>Track the real-time status of payment requests routed for human review.</p>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>Requests ({customerCases.length})</h2>
                  <button className="secondary small" onClick={refresh}>Refresh</button>
                </div>

                {customerCases.length > 0 ? (
                  <table className="cases-table">
                    <thead>
                      <tr>
                        <th>CASE ID</th>
                        <th>TRANSCRIPT</th>
                        <th>AMOUNT</th>
                        <th>REASON</th>
                        <th>STATUS</th>
                        <th>AGENT NOTE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {customerCases.map(c => (
                        <tr key={c.id}>
                          <td><strong>#{c.id}</strong></td>
                          <td><em>{c.transcript}</em></td>
                          <td>{c.amount_rupees ? `₹${c.amount_rupees}` : 'Uncertain'}</td>
                          <td>{c.reason}</td>
                          <td>
                            <span className={`case-status ${c.status.toLowerCase()}`}>{c.status}</span>
                          </td>
                          <td>{c.agent_note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="empty">
                    <CheckCircle2 />
                    <strong>No escalated requests</strong>
                    <p>When a payment requires review, you can track it here.</p>
                  </div>
                )}
              </div>
            </>
          )}

          {/* ---------------- AGENT: REVIEW QUEUE (Desktop Web, One Page) ---------------- */}
          {isAgent && tab === 'agent' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">HUMAN-IN-THE-LOOP</span>
                  <h1>Agent review queue</h1>
                  <p>Review uncertain requests with full context. Agent decisions never execute money movement.</p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {['ALL', 'OPEN', 'REVIEWED', 'REJECTED'].map(f => (
                    <button
                      key={f}
                      className={`secondary small ${caseFilter === f ? 'active' : ''}`}
                      onClick={() => setCaseFilter(f)}
                    >
                      {f}
                    </button>
                  ))}
                  <button className="secondary small" onClick={refresh}>
                    <RefreshCw size={14} /> Refresh
                  </button>
                </div>
              </div>

              <div className="agent-layout">
                {/* Case List */}
                <div className="panel queue-panel">
                  <div className="panel-head">
                    <h2>
                      Cases <span className="count-badge">{openCasesCount} open</span>
                    </h2>
                  </div>

                  {cases.filter(c => caseFilter === 'ALL' || c.status === caseFilter).length > 0 ? (
                    cases
                      .filter(c => caseFilter === 'ALL' || c.status === caseFilter)
                      .map(c => (
                        <button
                          key={c.id}
                          className={`case-row ${selectedCase?.id === c.id ? 'selected' : ''}`}
                          onClick={() => {
                            setSelectedCase(c);
                            setAgentNote(c.agent_note || 'Verified case details and checked safety context.');
                          }}
                        >
                          <span className="case-alert"><AlertTriangle /></span>
                          <span className="case-copy">
                            <strong>Case #{c.id} · Customer #{c.user_id}</strong>
                            <small>{c.reason}</small>
                          </span>
                          <span className={`case-status ${c.status.toLowerCase()}`}>{c.status}</span>
                        </button>
                      ))
                  ) : (
                    <div className="empty">
                      <CheckCircle2 />
                      <strong>Queue is clear</strong>
                      <p>No escalated requests match this filter.</p>
                    </div>
                  )}
                </div>

                {/* Case Detail Pane: Transcript, Extracted Fields, Uncertain Field Highlighted, Escalation Reason */}
                <div className="panel case-detail">
                  <h2>{selectedCase ? `Case #${selectedCase.id}` : 'Select a case'}</h2>

                  {selectedCase ? (
                    <>
                      <div className="detail-block">
                        <label>Original Spoken/Typed Transcript</label>
                        <p className="transcript-box">{selectedCase.transcript}</p>
                      </div>

                      <div className="detail-block">
                        <label>Extracted Fields & Uncertain Field</label>
                        <p>
                          Amount:{' '}
                          <strong className={selectedCase.uncertain_field === 'amount' ? 'highlight' : ''}>
                            {selectedCase.amount_paise == null
                              ? 'Uncertain'
                              : `₹${(selectedCase.amount_paise / 100).toLocaleString('en-IN')}`}
                          </strong>
                        </p>
                        <p>
                          Payee:{' '}
                          <strong className={selectedCase.uncertain_field === 'payee' ? 'highlight' : ''}>
                            {selectedCase.payee || 'Uncertain'}
                          </strong>
                        </p>
                        <p>
                          Uncertain Field Highlighted:{' '}
                          <span className="highlight">{selectedCase.uncertain_field}</span>
                        </p>
                      </div>

                      <div className="detail-block">
                        <label>Escalation Reason</label>
                        <p>{selectedCase.reason}</p>
                      </div>

                      <div className="detail-block">
                        <label>Customer Account Management</label>
                        <button
                          className="secondary small"
                          type="button"
                          onClick={() => unlockUserAccount(selectedCase.user_id)}
                          disabled={busy}
                        >
                          <UserCheck size={14} /> Unlock Customer #{selectedCase.user_id} Account
                        </button>
                      </div>

                      <label>Required Agent Decision Note</label>
                      <textarea
                        rows="3"
                        value={agentNote}
                        onChange={(e) => setAgentNote(e.target.value)}
                        placeholder="Provide mandatory rationale for review outcome"
                        required
                      />

                      {/* Actions: Approve, Reject, Repeat with required note */}
                      <div className="action-row wrap" style={{ marginTop: '16px' }}>
                        <button
                          className="secondary"
                          onClick={() => actOnCase('repeat')}
                          disabled={busy || !agentNote.trim()}
                        >
                          Ask to Repeat
                        </button>
                        <button
                          className="danger"
                          onClick={() => actOnCase('reject')}
                          disabled={busy || !agentNote.trim()}
                        >
                          Reject
                        </button>
                        <button
                          className="primary"
                          onClick={() => actOnCase('approve')}
                          disabled={busy || !agentNote.trim()}
                        >
                          Mark Reviewed (Approve)
                        </button>
                      </div>

                      <p className="privacy-note">
                        <ShieldAlert size={15} />
                        Decisions are recorded in the immutable audit trail. Agent approval never moves money directly.
                      </p>
                    </>
                  ) : (
                    <div className="empty">
                      <MessageCircle />
                      <p>Select a case from the queue to inspect details and record a decision.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* ---------------- AGENT: AUDIT TRAIL ---------------- */}
          {isAgent && tab === 'audit' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">TRACEABILITY & COMPLIANCE</span>
                  <h1>Audit trail</h1>
                  <p>Immutable audit records persisted in database. Raw audio and PIN values are never stored.</p>
                </div>
                <button className="secondary small" onClick={refresh}>Refresh</button>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>Recent Events ({auditLogs.length})</h2>
                  <input
                    type="text"
                    value={auditSearch}
                    onChange={(e) => setAuditSearch(e.target.value)}
                    placeholder="Filter audit events…"
                    style={{ maxWidth: '250px', padding: '8px 12px' }}
                  />
                </div>

                <table className="cases-table">
                  <thead>
                    <tr>
                      <th>EVENT ID</th>
                      <th>TIMESTAMP</th>
                      <th>USER</th>
                      <th>EVENT TYPE</th>
                      <th>DETAILS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs
                      .filter(a =>
                        !auditSearch ||
                        a.event_type.toLowerCase().includes(auditSearch.toLowerCase()) ||
                        a.details.toLowerCase().includes(auditSearch.toLowerCase())
                      )
                      .map(a => (
                        <tr key={a.id}>
                          <td>#{a.id}</td>
                          <td><small>{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</small></td>
                          <td>{a.user_id ? `User #${a.user_id}` : 'System'}</td>
                          <td><strong>{a.event_type}</strong></td>
                          <td><code>{a.details}</code></td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* ---------------- AGENT: SYSTEM CONFIGS (Editable Thresholds with Audit Logging) ---------------- */}
          {isAgent && tab === 'system' && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">DATABASE-BACKED CONFIGURATION</span>
                  <h1>System limits & thresholds</h1>
                  <p>Thresholds held as editable values in the SQL database, with all updates logged in the audit trail.</p>
                </div>
                <button className="secondary small" onClick={refresh}>Refresh</button>
              </div>

              <div className="panel" style={{ maxWidth: '750px' }}>
                <div className="panel-head">
                  <h2>Configured Thresholds</h2>
                  <Sliders className="green-icon" />
                </div>

                {systemConfigs.map(c => (
                  <div key={c.key} style={{ padding: '16px 0', borderBottom: '1px solid #edf1f6' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>{c.key}</strong>
                        <small style={{ display: 'block', color: '#8898aa', marginTop: '3px' }}>
                          {c.description}
                        </small>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <input
                          type="text"
                          value={editLimits[c.key] ?? c.value}
                          onChange={(e) => setEditLimits({ ...editLimits, [c.key]: e.target.value })}
                          style={{ width: '130px', padding: '8px 12px', textAlign: 'right' }}
                        />
                        <button
                          className="secondary small"
                          onClick={() => saveSystemConfig(c.key, editLimits[c.key])}
                          disabled={busy || editLimits[c.key] === c.value}
                          title="Save this threshold to database"
                        >
                          <Save size={14} /> Save
                        </button>
                      </div>
                    </div>
                  </div>
                ))}

                <div style={{ marginTop: '24px', paddingTop: '18px', borderTop: '1px solid #edf1f6' }}>
                  <button className="danger" onClick={handleResetDemo} disabled={busy}>
                    Reset Demo Environment
                  </button>
                </div>
              </div>
            </>
          )}

          {/* FOOTER */}
          <footer className="footer">
            <span>
              saathi<span className="brand-dot">.</span> <span className="muted">Voice Banking Safety Architecture</span>
            </span>
            <span><ShieldCheck size={14} /> Synthetic Data · Double-Entry Mock Ledger</span>
          </footer>
        </div>
      </main>

      {/* FLOATING ACTION: TALK TO A PERSON (Visible at all times) */}
      <button
        className="floating-help"
        onClick={() => {
          if (!isAgent) {
            setTranscript('I would like to talk to a human agent');
            setTab('send');
            setResult({
              action: 'handoff',
              message: 'Your request has been routed to human review. An agent will review the full context.'
            });
            speak('Your request has been routed to human review.');
          } else {
            setTab('agent');
          }
        }}
        title="Escalate to human review"
      >
        <Headphones size={18} />
        <span>Talk to a person</span>
      </button>
    </div>
  );
}