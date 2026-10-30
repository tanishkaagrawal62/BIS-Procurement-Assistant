import { useEffect, useRef, useState } from 'react';
import {
  BrowserRouter, Link, NavLink, Route, Routes, useLocation, useNavigate, useParams,
} from 'react-router-dom';
import { createWorker } from 'tesseract.js';
import { apiRequest, clearSession, hasSession, saveSession } from './lib/api.js';
import indiaLocations from './data/indiaLocations.json';
import './App.css';

const BIS_URL = 'https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails';
const TODAY_LABEL = new Intl.DateTimeFormat('en-IN', { dateStyle: 'full' }).format(new Date()).toUpperCase();

function toTenderRow(item) {
  return {
    id: item.id,
    title: item.tender_name,
    location: item.location || '',
    buyer: 'Private workspace',
    date: item.created_at ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(item.created_at)) : '—',
    status: item.status === 'complete' ? 'Complete' : item.status,
    matches: item.recommendation_count,
    sample: false,
  };
}

function ThemeToggle({ light, onToggle }) {
  return <button className="icon-button" onClick={onToggle} aria-label={`Switch to ${light ? 'dark' : 'light'} mode`} title="Toggle appearance">{light ? '☾' : '☼'}</button>;
}

function Button({ children, to, variant = 'primary', ...props }) {
  return to ? <Link className={`button ${variant}`} to={to} {...props}>{children}</Link> : <button className={`button ${variant}`} {...props}>{children}</button>;
}

function Card({ children, className = '' }) {
  return <section className={`card ${className}`}>{children}</section>;
}

function Sidebar({ mobileOpen, onNavigate }) {
  const navClass = ({ isActive }) => `nav-item ${isActive ? 'active' : ''}`;
  return <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
    <Link to="/" className="brand" onClick={onNavigate}><span className="brand-mark">B</span><span><b>BIS Assist</b><small>Procurement intelligence</small></span></Link>
    <div className="nav-label">WORKSPACE</div>
    <nav className="main-nav" aria-label="Workspace navigation">
      <NavLink end to="/" className={navClass} onClick={onNavigate}><span>▦</span>Overview</NavLink>
      <NavLink to="/upload" className={navClass} onClick={onNavigate}><span>＋</span>New analysis</NavLink>
      <NavLink to="/history" className={navClass} onClick={onNavigate}><span>◷</span>Tender history</NavLink>
    </nav>
    <div className="nav-label account-label">ACCOUNT</div>
    <nav className="main-nav" aria-label="Account navigation">
      <NavLink to="/account" className={navClass} onClick={onNavigate}><span>⚙</span>Account settings</NavLink>
      <NavLink to="/login" className={navClass} onClick={onNavigate}><span>↪</span>Login</NavLink>
      <NavLink to="/signup" className={navClass} onClick={onNavigate}><span>＋</span>Sign up</NavLink>
    </nav>
    <div className="sidebar-bottom">
      <div className="help-card"><span className="help-icon">✦</span><b>Need a hand?</b><p>Get more from your procurement workspace.</p><a href={BIS_URL} target="_blank" rel="noreferrer">Visit BIS website ↗</a></div>
      <div className="profile"><span className="avatar user-avatar" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c.5-4.1 3.6-6.5 8-6.5s7.5 2.4 8 6.5z"/></svg></span><span><b>My workspace</b><small>{hasSession() ? 'Signed in' : 'Sign in to analyze'}</small></span><button className="dots" title="Sign out" aria-label="Sign out" onClick={async () => { try { await apiRequest('/auth/logout', { method: 'POST' }); } catch { /* Clear the local session even if the API is offline. */ } clearSession(); window.location.assign('/login'); }}>↪</button></div>
    </div>
  </aside>;
}

function Shell({ children, light, setLight }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();
  const titles = { '/': 'Overview', '/upload': 'New analysis', '/progress': 'Analysis progress', '/history': 'Tender history' };
  const crumb = titles[pathname] || (pathname.startsWith('/results/') ? 'Results' : 'Workspace');
  useEffect(() => {
    if (!mobileOpen) return undefined;
    const closeOnEscape = event => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [mobileOpen]);
  return <div className={`app-shell ${light ? 'light-theme' : ''} ${mobileOpen ? 'drawer-open' : ''}`}>
    <Sidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />
    {mobileOpen && <button className="mobile-overlay" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <main className="main-content">
      <header className="topbar"><button className="mobile-menu-button" onClick={() => setMobileOpen(!mobileOpen)} aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileOpen}>{mobileOpen ? '×' : '☰'}</button><span className="breadcrumb">Workspace <i>/</i> <b>{crumb}</b></span><div className="top-actions"><span className="live-indicator"><i /> BIS LIVE SEARCH</span><ThemeToggle light={light} onToggle={() => setLight(!light)} /><span className="avatar small-avatar user-avatar" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c.5-4.1 3.6-6.5 8-6.5s7.5 2.4 8 6.5z"/></svg></span></div></header>
      {children}
      <footer className="page-footer"><span>© 2026 BIS Assist · Procurement workspace</span></footer>
    </main>
  </div>;
}

function PageHeading({ eyebrow, title, text, action }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>{action}</div>;
}

function StatCard({ icon, label, value, note, tone }) {
  return <Card className="stat-card"><div className="stat-top"><span>{label}</span><span className={`stat-icon ${tone}`}>{icon}</span></div><strong className="stat-value">{value}</strong><small>{note}</small></Card>;
}

function TenderTable({ rows }) {
  return <div className="table-wrap"><table><thead><tr><th>TENDER</th><th>DATE ADDED</th><th>STATUS</th><th>STANDARDS</th><th /></tr></thead><tbody>{rows.map(t => <tr key={t.id}>
    <td><b>{t.title}</b><small>{t.location ? `${t.location} · ` : ''}{t.id} · {t.buyer || 'Workspace'}{t.sample ? ' · Sample' : ''}</small></td><td>{t.date}</td>
    <td><span className={`status ${t.status === 'Processing' ? 'processing' : ''}`}><i />{t.status}</span></td><td>{t.matches || '—'}</td>
    <td><Link className="row-link" to={`/results/${encodeURIComponent(t.id)}`} aria-label={`View results for ${t.title}`}>↗</Link></td>
  </tr>)}</tbody></table></div>;
}

function Dashboard() {
  const [analyses, setAnalyses] = useState([]);
  const [loadError, setLoadError] = useState('');
  useEffect(() => {
    if (!hasSession()) return;
    apiRequest('/analyses').then(rows => setAnalyses(rows.map(toTenderRow))).catch(error => setLoadError(error.message));
  }, []);
  const standardsCount = analyses.reduce((total, row) => total + (row.matches || 0), 0);
  return <div className="page-content">
    <PageHeading eyebrow={TODAY_LABEL} title={<>Welcome back <span className="sparkle">✦</span></>} text="Your procurement workspace at a glance." action={<Button to="/upload">＋ Start new analysis</Button>} />
    <div className="stats-grid"><StatCard label="Tenders analyzed" value={analyses.length} note="Saved in your account" icon="▤" tone="blue" /><StatCard label="Standards matched" value={standardsCount} note="From the available catalogue" icon="◇" tone="purple" /><StatCard label="Average match score" value="—" note="No calibrated score available" icon="↗" tone="green" /><StatCard label="In progress" value={analyses.filter(row => row.status === 'Processing').length} note="Current account records" icon="◷" tone="orange" /></div>
    <div className="dashboard-grid">
      <Card className="recent-panel"><div className="section-heading"><div><h2>Recent tenders</h2><p>Your latest procurement analyses</p></div><Link to="/history" className="text-link">View history →</Link></div>{loadError && hasSession() ? <p className="form-error" role="alert">{loadError}</p> : analyses.length ? <TenderTable rows={analyses.slice(0, 4)} /> : <div className="history-empty"><h2>{hasSession() ? 'No analyses yet' : 'Sign in to view your workspace'}</h2><p>{hasSession() ? 'Your submitted analyses will appear here.' : 'Create an account or sign in to save private tender analyses.'}</p><Button to={hasSession() ? '/upload' : '/login'}>{hasSession() ? '＋ Start new analysis' : 'Sign in →'}</Button></div>}</Card>
      <Card className="insight-panel"><div className="insight-icon">✦</div><div className="eyebrow">CATALOGUE STATUS</div><h2>BIS records<br />at a glance</h2><p>Tender keywords are searched against official BIS catalogue metadata when you submit an analysis.</p><a href={BIS_URL} target="_blank" rel="noreferrer" className="text-link">Open official Know Your Standards ↗</a></Card>
    </div>
  </div>;
}

function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [images, setImages] = useState([]);
  const [title, setTitle] = useState('');
  const [stateCode, setStateCode] = useState('');
  const [cityName, setCityName] = useState('');
  const [customCity, setCustomCity] = useState('');
  const [spec, setSpec] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [draggingPdf, setDraggingPdf] = useState(false);
  const [draggingImages, setDraggingImages] = useState(false);
  const [ocrStatus, setOcrStatus] = useState('');
  const [voiceStatus, setVoiceStatus] = useState('');
  const [voiceLanguage, setVoiceLanguage] = useState('en-IN');
  const [listening, setListening] = useState(false);
  const imageUrls = useRef(new Set());
  const recognitionRef = useRef(null);
  const selectedState = indiaLocations.find(state => state.code === stateCode);
  const chosenCity = cityName === '__other__' ? customCity.trim() : cityName;
  const selectedLocation = selectedState && chosenCity ? `${chosenCity}, ${selectedState.name}, India` : '';

  useEffect(() => () => {
    recognitionRef.current?.stop();
    imageUrls.current.forEach(url => URL.revokeObjectURL(url));
  }, []);

  function acceptFile(candidate) {
    if (!candidate) return;
    if (candidate.type !== 'application/pdf' && !candidate.name.toLowerCase().endsWith('.pdf')) {
      setError('Please choose a PDF file.');
      return;
    }
    if (candidate.size > 20 * 1024 * 1024) {
      setError('This PDF is larger than 20 MB. Choose a smaller file.');
      return;
    }
    setError('');
    setFile(candidate);
  }

  function acceptImages(candidates) {
    const selected = Array.from(candidates || []);
    if (!selected.length) return;
    const accepted = [];
    for (const image of selected) {
      if (!['image/jpeg', 'image/png', 'image/webp', 'image/bmp'].includes(image.type)) { setError('Choose a JPG, PNG, WebP, or BMP image.'); continue; }
      if (image.size > 10 * 1024 * 1024) { setError(`${image.name} is larger than 10 MB. Choose a smaller image.`); continue; }
      if (images.length + accepted.length >= 5) { setError('You can add up to 5 images.'); break; }
      const previewUrl = URL.createObjectURL(image);
      imageUrls.current.add(previewUrl);
      accepted.push({ file: image, previewUrl });
    }
    if (accepted.length) { setImages(current => [...current, ...accepted]); setError(''); }
  }

  async function extractImageText() {
    if (!images.length) return '';
    setOcrStatus('Starting image text recognition...');
    let currentImage = 0;
    let worker;
    try {
      worker = await createWorker('eng', 1, {
        logger: message => {
          if (message.status === 'recognizing text') {
            setOcrStatus(`Reading image ${currentImage + 1} of ${images.length}... ${Math.round((message.progress || 0) * 100)}%`);
          }
        },
      });
      const recognized = [];
      for (let index = 0; index < images.length; index += 1) {
        currentImage = index;
        const result = await worker.recognize(images[index].file);
        const extracted = result.data.text.trim();
        if (extracted) recognized.push(`Text from image ${images[index].file.name}:\n${extracted}`);
      }
      return recognized.join('\n\n');
    } finally {
      if (worker) await worker.terminate();
      setOcrStatus('');
    }
  }

  function toggleVoiceInput() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus('Voice typing is unavailable in this browser. Please type the specification instead.');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = voiceLanguage;
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    let receivedResult = false;
    let recognitionError = '';
    recognition.onstart = () => { setListening(true); setVoiceStatus('Listening... speak your tender requirements.'); };
    recognition.onresult = event => {
      const transcript = Array.from(event.results).map(result => result[0]?.transcript || '').join(' ').trim();
      if (transcript) {
        receivedResult = true;
        setSpec(current => `${current}${current.trim() ? '\n' : ''}${transcript}`);
      }
      setVoiceStatus(transcript ? 'Voice text added to tender specifications.' : 'No speech was detected. Try again or type the requirements.');
    };
    recognition.onerror = event => {
      const messages = {
        'not-allowed': 'Microphone access was blocked. Allow it in your browser settings and try again.',
        'service-not-allowed': 'This browser blocked its speech recognition service. Try Chrome or Edge with an internet connection.',
        'audio-capture': 'No working microphone was found. Connect or enable a microphone and try again.',
        'no-speech': 'No speech was detected. Try speaking a little louder and closer to the microphone.',
        network: 'The browser speech service needs an internet connection. Reconnect and try again.',
        'language-not-supported': 'This browser does not support the selected voice language. Choose another language.',
      };
      recognitionError = messages[event.error] || 'Voice input could not be completed. Try again or type the requirements.';
      setVoiceStatus(recognitionError);
      setListening(false);
    };
    recognition.onend = () => {
      setListening(false);
      if (!receivedResult && !recognitionError) setVoiceStatus('No speech was recognized. Try again or type the requirements.');
    };
    recognitionRef.current = recognition;
    setListening(true);
    setVoiceStatus('Requesting microphone access...');
    try {
      recognition.start();
    } catch {
      setListening(false);
      setVoiceStatus('Voice input could not start. Check microphone permission and try again.');
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (!title.trim()) { setError('Enter a tender name to continue.'); return; }
    if ((stateCode || cityName) && !selectedLocation) { setError(cityName === '__other__' ? 'Enter the city or town name to continue.' : 'Select a city after choosing a state, or clear the location selection.'); return; }
    if (!file && !spec.trim() && !images.length) { setError('Choose a PDF or image, or enter tender specifications.'); return; }
    if (!hasSession()) { navigate('/login'); return; }
    setSubmitting(true);
    setError('');
    try {
      let imageText = '';
      try {
        imageText = await extractImageText();
      } catch {
        setOcrStatus('');
        throw new Error('Image text recognition could not start. Check your internet connection for the first OCR setup, then retry or enter the requirements manually.');
      }
      if (!file && !spec.trim() && !imageText.trim()) {
        throw new Error('No readable text was found in the selected image. Try a clearer image or enter the requirements manually.');
      }
      const combinedSpecification = [spec.trim(), imageText].filter(Boolean).join('\n\n');
      let result;
      if (file) {
        const form = new FormData();
        form.set('tender_name', title.trim());
        form.set('location', selectedLocation);
        form.set('specification', combinedSpecification);
        form.set('file', file);
        result = await apiRequest('/analyses/upload', { method: 'POST', body: form });
      } else {
        result = await apiRequest('/analyses/manual', { method: 'POST', body: JSON.stringify({ tender_name: title.trim(), location: selectedLocation || null, specification: combinedSpecification }) });
      }
      navigate(`/progress/${encodeURIComponent(result.id)}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return <div className="page-content narrow"><PageHeading eyebrow="NEW ANALYSIS" title="Add a tender" text="Upload a tender document or enter its key requirements manually." />
    <form onSubmit={submit} noValidate><Card className="form-card"><h2>Tender details</h2><p>Give this analysis a name, then add a PDF or specifications.</p>
      <label className="field-label" htmlFor="tender-title">Tender name</label><input className="text-field" id="tender-title" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Stainless steel fasteners procurement" maxLength={120} />
      <label className="field-label location-field-label" htmlFor="tender-state">Tender location <span>(optional)</span></label>
      <div className="location-selects"><select className="text-field" id="tender-state" value={stateCode} onChange={event => { setStateCode(event.target.value); setCityName(''); setCustomCity(''); }}><option value="">Select a state or union territory</option>{indiaLocations.map(state => <option key={state.code} value={state.code}>{state.name}</option>)}</select><select className="text-field" id="tender-city" value={cityName} onChange={event => { setCityName(event.target.value); setCustomCity(''); }} disabled={!selectedState}><option value="">{selectedState ? 'Select a city' : 'Choose a state first'}</option>{(selectedState?.cities || []).map(city => <option key={city} value={city}>{city}</option>)}<option value="__other__">My city is not listed</option></select></div>
      {cityName === '__other__' && <input className="text-field custom-city-field" aria-label="Enter city or town name" placeholder="Enter city or town name" value={customCity} onChange={event => setCustomCity(event.target.value)} maxLength={150} />}
      <div className="divider"><span>UPLOAD DOCUMENTS OR IMAGES</span></div>
      <div className="upload-options"><label className={`dropzone ${draggingPdf ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDraggingPdf(true); }} onDragLeave={() => setDraggingPdf(false)} onDrop={e => { e.preventDefault(); setDraggingPdf(false); acceptFile(e.dataTransfer.files[0]); }}>
        <input type="file" accept="application/pdf,.pdf" onChange={e => { acceptFile(e.target.files?.[0]); e.target.value = ''; }} />
        <span className="upload-icon">↑</span><b>{file ? file.name : 'Drop your PDF here or browse files'}</b><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · selected locally` : 'PDF only · up to 20 MB'}</small>
      </label><label className={`dropzone image-dropzone ${draggingImages ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDraggingImages(true); }} onDragLeave={() => setDraggingImages(false)} onDrop={e => { e.preventDefault(); setDraggingImages(false); acceptImages(e.dataTransfer.files); }}>
        <input type="file" accept="image/jpeg,image/png,image/webp,image/bmp" multiple onChange={e => { acceptImages(e.target.files); e.target.value = ''; }} />
        <span className="upload-icon">▧</span><b>Drop product or specification images</b><small>JPG, PNG, WebP, or BMP · up to 5 images · 10 MB each</small>
      </label></div>
      {file && <div className="file-actions"><span>Selected file · {file.name}</span><button type="button" className="inline-button" onClick={() => { setFile(null); setError(''); }}>Remove file</button></div>}
      {images.length > 0 && <ul className="selected-images">{images.map((image, index) => <li key={`${image.file.name}-${image.file.lastModified}-${index}`}><span className="selected-image-info"><img src={image.previewUrl} alt={`Preview of ${image.file.name}`} /><span>{image.file.name} <small>({(image.file.size / 1024 / 1024).toFixed(2)} MB)</small></span></span><button type="button" className="inline-button" onClick={() => { imageUrls.current.delete(image.previewUrl); URL.revokeObjectURL(image.previewUrl); setImages(current => current.filter((_, imageIndex) => imageIndex !== index)); }}>Remove</button></li>)}</ul>}
      <div className="divider"><span>OR ENTER MANUALLY</span></div>
      <div className="voice-controls"><span className="field-label">Tender specifications</span><select aria-label="Voice input language" value={voiceLanguage} onChange={e => setVoiceLanguage(e.target.value)} disabled={listening}><option value="en-IN">English</option><option value="hi-IN">Hindi</option></select><button type="button" className={`button secondary voice-button ${listening ? 'listening' : ''}`} onClick={toggleVoiceInput}>{listening ? '■ Stop listening' : '🎙 Speak requirements'}</button></div>
      <div className="form-help">Voice typing needs microphone permission and a supported browser such as Chrome or Edge. English and Hindi are available.</div>
      <textarea id="spec" rows="6" value={spec} onChange={e => setSpec(e.target.value)} placeholder="Example: Supply of M12 carbon steel hex bolts, property class 8.8, with zinc coating…" />
      {voiceStatus && <div className="form-help voice-status" aria-live="polite">{voiceStatus}</div>}
      <div className="form-help">Add product names, materials, dimensions, safety, testing or performance requirements.</div>
      {ocrStatus && <p className="form-help ocr-status" role="status">{ocrStatus}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions"><Button to="/" variant="secondary">Cancel</Button><button className="button primary" type="submit" disabled={submitting}>{submitting ? 'Analysing…' : 'Analyse Tender →'}</button></div>
    </Card></form>
  </div>;
}

function Progress() {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!id) return;
    apiRequest(`/analyses/${encodeURIComponent(id)}`).then(setAnalysis).catch(requestError => setError(requestError.message));
  }, [id]);

  if (!id) return <div className="page-content narrow"><PageHeading eyebrow="ANALYSIS STATUS" title="No analysis selected" text="Start with a PDF or enter specifications to create an analysis." action={<Button to="/upload">＋ New analysis</Button>} /></div>;
  if (!analysis && !error) return <div className="page-content narrow"><PageHeading eyebrow="ANALYSIS" title="Loading analysis" text="Retrieving the saved analysis from your account." /><Card className="progress-card"><div className="spinner">✦</div></Card></div>;
  if (error) return <div className="page-content narrow"><PageHeading eyebrow="ANALYSIS UNAVAILABLE" title="Could not open this analysis" text={error} action={<Button to="/login">Sign in</Button>} /><Button to="/history" variant="secondary">Open tender history</Button></div>;
  return <div className="page-content narrow"><PageHeading eyebrow="ANALYSIS STATUS" title="Analysis complete" text="PDF extraction and requirement search are complete. Recommendations depend on the verified catalogue available to this backend." /><Card className="progress-card"><div className="spinner">✓</div><span className="status"><i />COMPLETE</span><h2>{analysis.tender_name}</h2>{analysis.location && <p className="tender-location-display">⌖ {analysis.location}</p>}<p>{analysis.recommendations.length} supported catalogue matches · {analysis.created_at ? new Date(analysis.created_at).toLocaleString() : ''}</p>{analysis.warning && <div className="notice"><span>ⓘ</span> {analysis.warning}</div>}<Button to={`/results/${encodeURIComponent(id)}`}>View analysis results →</Button></Card></div>;
}

function ExtractedParameters({ requirements = {} }) {
  const labels = [
    ['product', 'Product'], ['quantity', 'Quantity'], ['materials', 'Materials'],
    ['dimensions', 'Dimensions / values'], ['grades', 'Grades / classes'],
    ['referenced_standards', 'Referenced standards'], ['testing', 'Testing'],
    ['safety', 'Safety'], ['performance', 'Performance'], ['application', 'Application'],
  ];
  const groups = labels.map(([key, label]) => {
    const raw = requirements[key];
    const values = key === 'product' ? [raw?.value] : (Array.isArray(raw) ? raw.map(item => item?.value) : []);
    return { label, values: [...new Set(values.filter(Boolean))] };
  }).filter(group => group.values.length);

  return <div className="parameter-grid" aria-label="Key parameters extracted from your input">
    {groups.length ? groups.map(group => <div className="parameter-item" key={group.label}>
      <span>{group.label}</span><strong>{group.values.join(', ')}</strong>
    </div>) : <p className="parameter-empty">No key parameters were detected. Try adding a product name, quantity, material, or technical requirement.</p>}
  </div>;
}

function sourceLabel(state) {
  if (state === 'live_search') return 'Live BIS data';
  if (state === 'cached') return 'Cached BIS data';
  return 'Unverified source';
}

function Results() {
  const { id } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    apiRequest(`/analyses/${encodeURIComponent(id)}`).then(setAnalysis).catch(requestError => setError(requestError.message));
  }, [id]);

  async function downloadReport() {
    try {
      const blob = await apiRequest(`/analyses/${encodeURIComponent(id)}/report.pdf`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `bis-analysis-${id}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  if (!analysis) return <div className="page-content"><PageHeading eyebrow="ANALYSIS RESULTS" title={error ? 'Results unavailable' : 'Loading results'} text={error || 'Loading your saved analysis and recommendations.'} action={<Button to={error ? '/login' : '/history'}>{error ? 'Sign in' : 'Tender history'}</Button>} /></div>;
  const recommendations = analysis.recommendations || [];
  return <div className="page-content">
    <PageHeading eyebrow="ANALYSIS RESULTS" title="BIS recommendations" text={`Evidence-backed catalogue matches for “${analysis.tender_name}”.`} action={<Button to="/upload" variant="secondary">＋ New analysis</Button>} />
    <div className="results-summary"><Card className="summary-card"><div className="eyebrow">TENDER SUMMARY · ACCOUNT DATA</div><h2>{analysis.tender_name}</h2>{analysis.location && <p className="tender-location-display">⌖ {analysis.location}</p>}<p>{analysis.filename ? `Key parameters extracted from ${analysis.filename}.` : 'Key parameters extracted from your specification.'}</p><div className="eyebrow requirements-label">PARAMETERS EXTRACTED FROM YOUR INPUT</div><ExtractedParameters requirements={analysis.requirements} /></Card></div>
    {recommendations.length ? <div className="result-list">{recommendations.map(item => {
      const standard = item.standard;
      const score = Math.round(item.combined_score * 100);
      const evidence = item.evidence || [];
      return <Card className="result-card" key={standard.id}><div className="rank">0{item.rank}</div><div className="result-main"><div className="result-top"><span className="standard-code">{standard.is_number}</span><span className="revision">{standard.revision_year ? `Edition year: ${standard.revision_year}` : 'Edition year unavailable'} · {sourceLabel(standard.verification_state)}</span></div><p className="recommendation-reason"><strong>Why recommended:</strong> This BIS record matched tender terms: {evidence.length ? evidence.join(', ') : 'related product and specification keywords'}.</p><h2 className="standard-title">{standard.title}</h2><p>{standard.scope || 'No sourced scope description is available.'}</p><div className="evidence-label">MATCHING EVIDENCE <span>· FROM SUPPLIED PARAMETERS</span></div><ul>{evidence.map((term, index) => <li key={`${index}-${term}`}>{term}</li>)}</ul><a className="evidence-source-link" href={standard.source_url || BIS_URL} target="_blank" rel="noreferrer">Search {standard.is_number} on official BIS ↗</a><div className="result-bottom"><span className="confidence">Evidence indicator: <b>{score}% ranking score</b></span></div><small className="result-status-note">Status: {standard.status || 'Unable to verify current status'} · {standard.source_checked_at ? `Source checked ${new Date(standard.source_checked_at).toLocaleDateString()}` : 'No verification timestamp'}</small></div><div className="score"><strong>{score}%</strong><small>relevance rank</small><div className="progress-track"><i style={{ width: `${score}%` }} /></div></div></Card>;
    })}</div> : <Card className="history-empty"><span>ⓘ</span><h2>No strong BIS matches found</h2><p>The live BIS search did not find a standard with enough matching evidence for these requirements. Add a clearer product name, material, or technical detail and submit a new analysis.</p><a className="text-link" href={BIS_URL} target="_blank" rel="noreferrer">Search the official BIS catalogue ↗</a></Card>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="result-actions"><Button to="/" variant="secondary">← Return to Dashboard</Button><button className="button primary" onClick={downloadReport}>Download PDF report</button></div>
  </div>;
}

function History() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [analyses, setAnalyses] = useState([]);
  const [loadError, setLoadError] = useState('');
  useEffect(() => {
    if (!hasSession()) return;
    apiRequest('/analyses').then(items => setAnalyses(items.map(toTenderRow))).catch(error => setLoadError(error.message));
  }, []);
  const rows = analyses.filter(t => `${t.id} ${t.title}`.toLowerCase().includes(query.toLowerCase())).filter(t => status === 'All statuses' || t.status === status);
  return <div className="page-content"><PageHeading eyebrow="WORKSPACE" title="Tender history" text="Browse analyses saved to your account." action={<Button to="/upload">＋ New analysis</Button>} />
    <Card className="history-panel"><div className="section-heading"><div><h2>All tenders <span className="count-pill">{rows.length}</span></h2><p>Analyses stored in your account.</p></div><div className="history-filters"><input className="search" aria-label="Search tenders" placeholder="⌕  Search tenders" value={query} onChange={e => setQuery(e.target.value)} /><select className="search status-filter" aria-label="Filter by analysis status" value={status} onChange={e => setStatus(e.target.value)}><option>All statuses</option><option>Complete</option><option>Processing</option></select></div></div>
      {loadError && hasSession() && <p className="form-error" role="alert">{loadError}</p>}{rows.length ? <TenderTable rows={rows} /> : <div className="history-empty"><span>◷</span><h2>{!hasSession() ? 'Sign in to view history' : 'No tenders found'}</h2><p>{query || status !== 'All statuses' ? 'Try another search or status filter.' : 'Your private account analyses will appear here.'}</p><Button to={hasSession() ? '/upload' : '/login'}>{hasSession() ? '＋ Start new analysis' : 'Sign in →'}</Button></div>}
    </Card><div className="notice"><span>ⓘ</span> Tender history is loaded from your account. Only tenders saved to your account are shown.</div>
  </div>;
}

function Auth({ signup = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState(location.state?.notice || '');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault(); setError(''); setMessage('');
    const form = new FormData(event.currentTarget);
    const password = String(form.get('password') || '');
    if (signup && password !== form.get('confirmPassword')) { setError('Those passwords do not match. Check them and try again.'); return; }
    setSubmitting(true);
    try {
      const payload = { email: email.trim(), password };
      if (signup) payload.name = String(form.get('name') || '').trim();
      else payload.remember = Boolean(form.get('remember'));
      const session = await apiRequest(`/auth/${signup ? 'signup' : 'login'}`, { method: 'POST', body: JSON.stringify(payload) });
      saveSession(session.access_token, Boolean(payload.remember));
      navigate('/');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return <div className="auth-page"><section className="auth-art"><Link className="brand" to="/"><span className="brand-mark">B</span><span><b>BIS Assist</b><small>Procurement intelligence</small></span></Link><div className="auth-message"><span className="eyebrow">CONFIDENT PROCUREMENT STARTS HERE</span><h1>Find the right standards for every tender.</h1><p>Review tender requirements and explore relevant BIS standards in one focused workspace.</p></div><small>© 2025 BIS Assist</small></section>
    <section className="auth-form-wrap"><form className="auth-form" onSubmit={submit}>
      <span className="eyebrow">{signup ? 'GET STARTED' : 'WELCOME BACK'}</span><h2>{signup ? 'Create your workspace' : 'Sign in to your workspace'}</h2><p>{signup ? 'Create your workspace profile.' : 'Enter your details to continue.'}</p>
      {signup && <><label htmlFor="name">Full name</label><input id="name" name="name" autoComplete="name" placeholder="Arjun Sharma" required minLength={2} /></>}
      <label htmlFor="email">Work email</label><input id="email" name="email" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={e => setEmail(e.target.value)} required />
      <label htmlFor="password">Password</label><div className="auth-password"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} placeholder="At least 8 characters" minLength={8} required /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button></div>
      {!signup && <div className="auth-options"><label className="remember-check"><input type="checkbox" name="remember" /> Remember me</label><button className="forgot-link" type="button" onClick={() => setMessage(email ? `Password reset is not connected. Ask your workspace administrator for help with ${email}.` : 'Enter your work email first. Password reset is not connected yet.')}>Forgot password?</button></div>}
      {signup && <><label htmlFor="confirm-password">Confirm password</label><div className="auth-password"><input id="confirm-password" name="confirmPassword" type={showConfirm ? 'text' : 'password'} autoComplete="new-password" placeholder="Re-enter your password" minLength={8} required /><button type="button" onClick={() => setShowConfirm(!showConfirm)} aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}>{showConfirm ? 'Hide' : 'Show'}</button></div><label className="terms-check"><input name="terms" type="checkbox" required /> I agree to the terms and privacy notice.</label></>}
      {error && <p className="form-error" role="alert">{error}</p>}{message && <p className="form-message" role="status">{message}</p>}
      <button className="button primary auth-submit" type="submit" disabled={submitting}>{submitting ? 'Please wait…' : `${signup ? 'Create account' : 'Sign in'} →`}</button>
      <p className="auth-switch">{signup ? 'Already have an account?' : 'New to BIS Assist?'} <button type="button" onClick={() => navigate(signup ? '/login' : '/signup')}>{signup ? 'Sign in' : 'Create an account'}</button></p><div className="auth-warning">Accounts are stored locally by the development backend. Passwords are hashed; password reset is not configured.</div>
    </form></section></div>;
}

function AccountSettings() {
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setDeleting(true);
    try {
      await apiRequest('/auth/account', {
        method: 'DELETE',
        body: JSON.stringify({ password, confirmation }),
      });
      clearSession();
      navigate('/login', { replace: true, state: { notice: 'Your account and saved tender history have been deleted.' } });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setDeleting(false);
    }
  }

  if (!hasSession()) return <div className="page-content narrow"><PageHeading eyebrow="ACCOUNT" title="Sign in required" text="Sign in to manage or delete your account." action={<Button to="/login">Sign in →</Button>} /></div>;
  return <div className="page-content narrow"><PageHeading eyebrow="ACCOUNT SETTINGS" title="Manage your account" text="Review account access and data options." />
    <Card className="form-card"><h2>Delete account</h2><p>This permanently removes your account, active sessions and all tender analyses saved under it.</p>
      <div className="notice"><span>ⓘ</span> This cannot be undone. Your uploaded PDF files are not retained by this app; saved extracted text and analysis history will be deleted.</div>
      <form onSubmit={submit} noValidate>
        <label className="field-label" htmlFor="delete-account-password">Current password</label>
        <input className="text-field" id="delete-account-password" type="password" autoComplete="current-password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} />
        <label className="field-label" htmlFor="delete-account-confirmation">Type DELETE to confirm</label>
        <input className="text-field" id="delete-account-confirmation" autoComplete="off" required value={confirmation} onChange={event => setConfirmation(event.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="form-actions"><Button to="/" variant="secondary">Cancel</Button><button className="button danger-button" type="submit" disabled={deleting || confirmation !== 'DELETE' || password.length < 8}>{deleting ? 'Deleting…' : 'Delete my account'}</button></div>
      </form>
    </Card>
  </div>;
}

function AppRoutes({ light, setLight }) {
  const { pathname } = useLocation();
  if (pathname === '/login' || pathname === '/signup') return <Routes><Route path="/login" element={<Auth />} /><Route path="/signup" element={<Auth signup />} /></Routes>;
  return <Shell light={light} setLight={setLight}><Routes>
    <Route path="/" element={<Dashboard />} /><Route path="/upload" element={<Upload />} />
    <Route path="/progress" element={<Progress />} /><Route path="/progress/:id" element={<Progress />} />
    <Route path="/results/:id" element={<Results />} /><Route path="/history" element={<History />} />
    <Route path="/account" element={<AccountSettings />} />
    <Route path="*" element={<div className="page-content"><PageHeading eyebrow="NOT FOUND" title="That page isn’t here" text="Use the navigation to return to your workspace." action={<Button to="/">Return to Dashboard</Button>} /></div>} />
  </Routes></Shell>;
}

export default function App() {
  const [light, setLight] = useState(false);
  return <BrowserRouter><AppRoutes light={light} setLight={setLight} /></BrowserRouter>;
}
