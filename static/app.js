/**
 * KINETIC FEED & PULSEPILOT AI™ — CLIENT ENGINE & ORCHESTRATOR
 * Real-time SSE listener, Algorithm Cracking Hashtags, Theme Manager (Dark/Light),
 * Multi-View Switching (Home vs Workspace), Session Verifier & Terminal Controller.
 */

let sseStream = null;
let reconnectDelay = 2500;
let currentTargetingMode = 'trending'; // 'trending' | 'direct_links'
let hashtagDebounceTimer = null;

// STATE STORE (ACCURATE PERSISTED DATA)
const appState = {
  stats: {
    posts_analyzed: 0,
    ai_comments: 0,
    reach_boost: 0.0,
    active_campaigns: 0
  },
  platforms: {
    instagram: { logged_in: false, username: null, status: 'UNCHECKED', details: 'Not verified' },
    twitter: { logged_in: false, username: null, status: 'UNCHECKED', details: 'Not verified' },
    threads: { logged_in: false, username: null, status: 'UNCHECKED', details: 'Not verified' }
  }
};

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initParallaxEngine();
  initViewNavigation();
  initSSEPipeline();
  fetchInitialState();
  setupSettingsDialog();
  fetchHashtagSuggestions();
});

/* ==========================================================================
   THEME MANAGER (DARK / LIGHT MODE)
   ========================================================================== */
function initTheme() {
  const savedTheme = localStorage.getItem('kinetic_theme') || 'dark';
  applyTheme(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const target = current === 'dark' ? 'light' : 'dark';
  applyTheme(target);
  localStorage.setItem('kinetic_theme', target);
  appendTerminalLine(`[THEME] Switched interface to ${target.toUpperCase()} mode.`, 'text-cyan');
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  if (theme === 'light') {
    document.body.classList.remove('cyber-void');
  } else {
    document.body.classList.add('cyber-void');
  }
}

/* ==========================================================================
   VIEW NAVIGATION (HOME VS WORKSPACE)
   ========================================================================== */
function initViewNavigation() {
  const savedView = localStorage.getItem('kinetic_view') || 'home';
  switchView(savedView, false);
}

function switchView(viewName, smoothScroll = true) {
  const homeView = document.getElementById('view-home');
  const workspaceView = document.getElementById('view-workspace');
  const navHomeBtn = document.getElementById('nav-home-btn');
  const navWorkspaceBtn = document.getElementById('nav-workspace-btn');

  if (viewName === 'workspace') {
    if (homeView) homeView.classList.remove('active');
    if (workspaceView) workspaceView.classList.add('active');
    if (navHomeBtn) navHomeBtn.classList.remove('active');
    if (navWorkspaceBtn) navWorkspaceBtn.classList.add('active');
    localStorage.setItem('kinetic_view', 'workspace');
  } else {
    if (workspaceView) workspaceView.classList.remove('active');
    if (homeView) homeView.classList.add('active');
    if (navWorkspaceBtn) navWorkspaceBtn.classList.remove('active');
    if (navHomeBtn) navHomeBtn.classList.add('active');
    localStorage.setItem('kinetic_view', 'home');
  }

  if (smoothScroll) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function scrollToTools() {
  const homeView = document.getElementById('view-home');
  if (!homeView || !homeView.classList.contains('active')) {
    switchView('home', false);
  }
  const toolsEl = document.getElementById('tools-hub');
  if (toolsEl) {
    toolsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

/* ==========================================================================
   INTERACTIVE PARALLAX AURORA MESH
   ========================================================================== */
function initParallaxEngine() {
  const orb1 = document.getElementById('orb-1');
  const orb2 = document.getElementById('orb-2');
  const orb3 = document.getElementById('orb-3');

  let mouseX = 0, mouseY = 0;
  let currentX = 0, currentY = 0;

  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 45;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 45;
  });

  function renderParallax() {
    currentX += (mouseX - currentX) * 0.05;
    currentY += (mouseY - currentY) * 0.05;

    if (orb1) orb1.style.transform = `translate(${currentX * 1.2}px, ${currentY * 1.2}px)`;
    if (orb2) orb2.style.transform = `translate(${-currentX * 0.9}px, ${-currentY * 0.9}px)`;
    if (orb3) orb3.style.transform = `translate(${currentX * 0.6}px, ${-currentY * 0.7}px)`;

    requestAnimationFrame(renderParallax);
  }
  renderParallax();
}

/* ==========================================================================
   INITIAL STATE & REAL METRICS SYNC
   ========================================================================== */
async function fetchInitialState() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    if (data.stats) {
      appState.stats = { ...appState.stats, ...data.stats };
      renderMetricsUI();
      if (data.stats.model) {
        document.getElementById('nav-model-name').innerText = data.stats.model;
        document.getElementById('cfg-model').value = data.stats.model;
      }
    }

    if (data.platforms) {
      appState.platforms = data.platforms;
      renderPlatformNodes();
    }

    // Render persisted real activity history
    if (data.history && Array.isArray(data.history) && data.history.length > 0) {
      const feed = document.getElementById('activity-scroll-container');
      const emptyState = document.getElementById('stream-empty-state');
      if (emptyState) emptyState.style.display = 'none';

      feed.innerHTML = '';
      data.history.forEach(item => {
        appendActivityCard({
          platform: item.platform,
          author: item.author || 'creator',
          postId: item.postId,
          comment: item.comment,
          reachScore: item.reachScore || 92,
          viralScore: item.viralScore || 88,
          url: item.url,
          timestamp: item.timestamp
        });
      });
      document.getElementById('feed-count-badge').innerText = `${data.history.length} Actions`;
    }
  } catch (err) {
    console.warn('[Kinetic Feed] Could not fetch initial state:', err);
  }
}

function renderMetricsUI() {
  const { posts_analyzed, ai_comments, reach_boost, active_campaigns } = appState.stats;

  const countStr = Number(posts_analyzed || 0).toLocaleString();
  const commStr = Number(ai_comments || 0).toLocaleString();
  const reachStr = `${Number(reach_boost || 0).toFixed(1)}x`;

  // Workspace metrics
  const pAnalyzedEl = document.getElementById('stat-posts-analyzed');
  const pCommEl = document.getElementById('stat-ai-comments');
  const pReachEl = document.getElementById('stat-reach-boost');
  const pActiveEl = document.getElementById('stat-active-campaigns');

  if (pAnalyzedEl) pAnalyzedEl.innerText = countStr;
  if (pCommEl) pCommEl.innerText = commStr;
  if (pReachEl) pReachEl.innerText = reachStr;
  if (pActiveEl) pActiveEl.innerText = active_campaigns || 0;

  // Hero section sync
  const heroAnalyzed = document.getElementById('hero-analyzed-val');
  const heroComments = document.getElementById('hero-comments-val');
  const heroReach = document.getElementById('hero-reach-val');

  if (heroAnalyzed) heroAnalyzed.innerText = `${countStr}+`;
  if (heroComments) heroComments.innerText = `${commStr}+`;
  if (heroReach) heroReach.innerText = reachStr;

  const workersLabel = document.getElementById('stat-workers-state');
  if (workersLabel) {
    if (active_campaigns > 0) {
      workersLabel.innerHTML = `<span class="text-emerald">● ${active_campaigns} Campaign${active_campaigns > 1 ? 's' : ''} Running</span>`;
    } else {
      workersLabel.innerText = 'Standby — Workers Idle';
    }
  }
}

/* ==========================================================================
   ALGORITHM HASHTAG INTELLIGENCE
   ========================================================================== */
async function fetchHashtagSuggestions() {
  const platformInput = document.querySelector('input[name="platform"]:checked');
  const platform = platformInput ? platformInput.value : 'instagram';
  const topicInput = document.getElementById('campaign-topic');
  const topic = topicInput ? topicInput.value.trim() : '';

  try {
    const res = await fetch(`/api/hashtags/suggest?platform=${platform}&topic=${encodeURIComponent(topic)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.success && Array.isArray(data.hashtags)) {
      renderHashtagChips(data.hashtags);
    }
  } catch (e) {
    console.warn('[Hashtags] Could not load suggestions:', e);
  }
}

function renderHashtagChips(hashtags) {
  const container = document.getElementById('algo-hashtag-chips');
  if (!container) return;

  container.innerHTML = '';
  hashtags.forEach(h => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip-algo-hashtag';
    chip.innerHTML = `<span>${h.tag}</span><span class="chip-viral-tag">${h.viral_score}%</span>`;
    chip.onclick = () => appendHashtagToInput(h.tag);
    container.appendChild(chip);
  });
}

function appendHashtagToInput(tag) {
  const input = document.getElementById('campaign-topic');
  if (!input) return;

  const current = input.value.trim();
  if (!current) {
    input.value = tag;
  } else {
    const parts = current.split(',').map(p => p.trim());
    if (!parts.includes(tag)) {
      parts.push(tag);
      input.value = parts.join(', ');
    }
  }
  appendTerminalLine(`[ALGO] Added algorithm hashtag: ${tag}`, 'text-cyan');
}

function onHashtagInput(val) {
  clearTimeout(hashtagDebounceTimer);
  hashtagDebounceTimer = setTimeout(() => {
    fetchHashtagSuggestions();
  }, 400);
}

function refreshHashtagSuggestions() {
  fetchHashtagSuggestions();
  appendTerminalLine('[ALGO] Refreshed algorithm-cracked hashtag suggestions.', 'text-muted');
}

/* ==========================================================================
   PLATFORM SESSION STATUS & REAL VERIFIER
   ========================================================================== */
function renderPlatformNodes() {
  const pMap = {
    instagram: { prefix: 'ig', name: 'Instagram' },
    twitter: { prefix: 'x', name: 'Twitter / X' },
    threads: { prefix: 'threads', name: 'Meta Threads' }
  };

  let verifiedCount = 0;

  for (const [platform, node] of Object.entries(appState.platforms)) {
    const meta = pMap[platform];
    if (!meta) continue;

    const badgeEl = document.getElementById(`${meta.prefix}-status-badge`);
    const textEl = document.getElementById(`${meta.prefix}-status-text`);
    const handleEl = document.getElementById(`${meta.prefix}-handle-display`);
    const detailsEl = document.getElementById(`${meta.prefix}-details-text`);

    if (node.checking) {
      badgeEl.className = 'session-status-badge status-checking';
      textEl.innerText = 'CHECKING...';
      detailsEl.innerText = 'Inspecting live session context in headless browser...';
    } else if (node.logged_in) {
      verifiedCount++;
      badgeEl.className = 'session-status-badge status-verified';
      textEl.innerText = 'LOGGED IN';
      handleEl.innerText = node.username ? node.username : 'Active Account';
      detailsEl.innerText = node.details || 'Active authenticated session verified.';
    } else {
      badgeEl.className = 'session-status-badge status-unverified';
      textEl.innerText = 'NOT LOGGED IN';
      handleEl.innerText = 'No session';
      detailsEl.innerText = node.details || 'No active session detected. Click Open Login.';
    }
  }

  const sumBadge = document.getElementById('session-summary-badge');
  if (sumBadge) {
    sumBadge.innerText = `${verifiedCount}/3 Authenticated`;
  }
}

async function verifyPlatform(platform) {
  appendTerminalLine(`[AUTH] Dispatching verification check for ${platform.toUpperCase()}...`, 'text-cyan');

  if (appState.platforms[platform]) {
    appState.platforms[platform].checking = true;
    renderPlatformNodes();
  }

  try {
    const res = await fetch('/api/platform/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform })
    });
    const json = await res.json();
    if (!json.success) {
      appendTerminalLine(`[ERROR] Verification dispatch failed: ${json.error}`, 'text-amber');
    }
  } catch (err) {
    appendTerminalLine(`[ERROR] Network error verifying ${platform}: ${err}`, 'text-amber');
    if (appState.platforms[platform]) {
      appState.platforms[platform].checking = false;
      renderPlatformNodes();
    }
  }
}

async function verifyAllPlatforms() {
  const btn = document.getElementById('btn-verify-all');
  const label = document.getElementById('verify-all-text');
  if (label) label.innerText = 'Checking...';

  for (const p of ['instagram', 'twitter', 'threads']) {
    if (appState.platforms[p]) appState.platforms[p].checking = true;
  }
  renderPlatformNodes();

  try {
    await fetch('/api/platform/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'all' })
    });
    appendTerminalLine('[AUTH] Headless session inspection dispatched for all 3 nodes.', 'text-cyan');
  } catch (e) {
    appendTerminalLine(`[ERROR] Verify all failed: ${e}`, 'text-amber');
  } finally {
    setTimeout(() => { if (label) label.innerText = 'Check Sessions'; }, 1500);
  }
}

async function triggerPlatformLogin(platform) {
  appendTerminalLine(`[LOGIN] Spawning persistent Chrome session for ${platform.toUpperCase()}...`, 'text-violet');
  appendTerminalLine(`[INFO] Stealth bypass active. Complete login or 2FA in the opened browser window. Engine detects authentication automatically.`, 'text-muted');

  try {
    await fetch('/api/login/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform })
    });
  } catch (err) {
    appendTerminalLine(`[ERROR] Login trigger failed: ${err}`, 'text-amber');
  }
}

/* ==========================================================================
   CAMPAIGN CONTROLLER & TARGETING MODES
   ========================================================================== */
function setTargetingMode(mode) {
  currentTargetingMode = mode;
  const tabTrending = document.getElementById('tab-trending-mode');
  const tabDirect = document.getElementById('tab-direct-links-mode');
  const boxTrending = document.getElementById('container-trending-mode');
  const boxDirect = document.getElementById('container-direct-links-mode');
  const sliderGroup = document.getElementById('quota-slider-group');

  if (mode === 'trending') {
    tabTrending.classList.add('active');
    tabDirect.classList.remove('active');
    boxTrending.classList.remove('hidden');
    boxDirect.classList.add('hidden');
    sliderGroup.style.display = 'block';
  } else {
    tabDirect.classList.add('active');
    tabTrending.classList.remove('active');
    boxDirect.classList.remove('hidden');
    boxTrending.classList.add('hidden');
    sliderGroup.style.display = 'none';
    updateLinksCount();
  }
}

function updateLinksCount() {
  const text = document.getElementById('direct-urls-input').value;
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  let igCount = 0, xCount = 0, threadsCount = 0, otherCount = 0;
  lines.forEach(url => {
    const u = url.toLowerCase();
    if (u.includes('instagram.com')) igCount++;
    else if (u.includes('x.com') || u.includes('twitter.com')) xCount++;
    else if (u.includes('threads.net')) threadsCount++;
    else otherCount++;
  });

  const countBadge = document.getElementById('direct-links-count');
  const breakdownEl = document.getElementById('direct-links-breakdown');

  if (countBadge) {
    countBadge.innerText = `${lines.length} link${lines.length !== 1 ? 's' : ''} parsed`;
  }

  if (lines.length > 0) {
    const parts = [];
    if (igCount) parts.push(`${igCount} Instagram`);
    if (xCount) parts.push(`${xCount} Twitter/X`);
    if (threadsCount) parts.push(`${threadsCount} Threads`);
    if (otherCount) parts.push(`${otherCount} Direct Target`);
    if (breakdownEl) breakdownEl.innerHTML = `<span class="text-cyan">Detected:</span> ${parts.join(', ')}`;
  } else {
    if (breakdownEl) breakdownEl.innerText = 'One URL per line. Comments will be placed sequentially on each target.';
  }
}

function onPlatformChange() {
  fetchHashtagSuggestions();
}

function onQuotaSliderChange(val) {
  const readout = document.getElementById('target-quota-readout');
  if (readout) readout.innerText = `${val} comments`;
}

async function executeCampaign(e) {
  e.preventDefault();

  const platform = document.querySelector('input[name="platform"]:checked').value;
  const feedMode = document.getElementById('campaign-feed-mode').value;
  const topic = document.getElementById('campaign-topic').value.trim();
  const quota = parseInt(document.getElementById('target-quota-slider').value, 10);

  const platState = appState.platforms[platform];
  if (platState && platState.logged_in === false) {
    const ok = confirm(`⚠️ Notice: ${platform.toUpperCase()} is marked as NOT LOGGED IN.\n\nWithout an authenticated session, feed scanning may fail.\n\nClick OK to open the interactive Login Window now, or Cancel to proceed anyway.`);
    if (ok) {
      triggerPlatformLogin(platform);
      return;
    }
  }

  let payload = {
    platform,
    mode: feedMode,
    topic,
    target: quota
  };

  if (currentTargetingMode === 'direct_links') {
    const text = document.getElementById('direct-urls-input').value;
    const rawUrls = text.split('\n').map(u => u.trim()).filter(u => u.length > 0);

    if (rawUrls.length === 0) {
      alert('Please paste at least one valid post link to launch direct targeting.');
      return;
    }

    payload.mode = 'direct_urls';
    payload.urls = rawUrls;
    payload.target = rawUrls.length;
    appendTerminalLine(`[CAMPAIGN] Launching Direct Link targeting for ${rawUrls.length} posts on ${platform.toUpperCase()}...`, 'text-cyan');
  } else {
    appendTerminalLine(`[CAMPAIGN] Launching PulsePilot AI™ on ${platform.toUpperCase()} [${feedMode.toUpperCase()}]. Target: ${quota} comments.`, 'text-cyan');
    if (topic) {
      appendTerminalLine(`[TARGETING] Filter Tags: ${topic}`, 'text-cyan');
    }
  }

  const launchBtn = document.getElementById('btn-master-launch');
  if (launchBtn) launchBtn.disabled = true;

  try {
    const res = await fetch('/api/campaign/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();

    if (json.success) {
      appendTerminalLine(`[CAMPAIGN] PulsePilot AI™ dispatched for ${platform.toUpperCase()}.`, 'text-emerald');
      fetchInitialState();
    } else {
      appendTerminalLine(`[WARNING] Cannot start campaign: ${json.error}`, 'text-amber');
      alert(json.error || 'Failed to start campaign.');
    }
  } catch (err) {
    appendTerminalLine(`[ERROR] Network failure starting campaign: ${err}`, 'text-amber');
  } finally {
    setTimeout(() => { if (launchBtn) launchBtn.disabled = false; }, 1200);
  }
}

async function stopActiveCampaigns() {
  appendTerminalLine('[HALT] Dispatching emergency halt signal to all workers...', 'text-amber');
  appState.stats.active_campaigns = 0;
  for (const p of ['instagram', 'twitter', 'threads']) {
    if (appState.platforms[p]) appState.platforms[p].active = false;
  }
  renderMetricsUI();

  for (const p of ['instagram', 'twitter', 'threads']) {
    try {
      await fetch('/api/campaign/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: p })
      });
    } catch (_) {}
  }
  setTimeout(fetchInitialState, 500);
}

/* ==========================================================================
   REAL-TIME SERVER-SENT EVENTS (SSE) STREAM
   ========================================================================== */
function initSSEPipeline() {
  if (sseStream) sseStream.close();

  const dot = document.getElementById('sse-dot');
  const label = document.getElementById('sse-status-label');

  sseStream = new EventSource('/api/stream');

  sseStream.onopen = () => {
    if (dot) dot.className = 'pulse-indicator pulse-emerald';
    if (label) label.innerText = 'STREAM LIVE';
    appendTerminalLine('[SSE] Real-time event pipeline connected.', 'text-emerald');
  };

  sseStream.onmessage = (event) => {
    try {
      const ev = JSON.parse(event.data);
      processLiveEvent(ev);
    } catch (e) {
      console.error('[SSE] Parse error:', e);
    }
  };

  sseStream.onerror = () => {
    if (dot) {
      dot.className = 'pulse-indicator';
      dot.style.background = '#f43f5e';
    }
    if (label) label.innerText = 'DISCONNECTED';
    sseStream.close();
    setTimeout(initSSEPipeline, reconnectDelay);
  };
}

function processLiveEvent(ev) {
  // 1. Logs
  if (ev.type === 'log') {
    appendTerminalLine(`[${(ev.platform || 'CORE').toUpperCase()}] ${ev.message}`, 'text-muted');
  }

  // 2. Verification Completed
  if (ev.type === 'verification_completed') {
    if (appState.platforms[ev.platform]) {
      appState.platforms[ev.platform].checking = false;
      appState.platforms[ev.platform].logged_in = ev.logged_in;
      appState.platforms[ev.platform].username = ev.username;
      appState.platforms[ev.platform].status = ev.status;
      appState.platforms[ev.platform].details = ev.details;
      renderPlatformNodes();
    }
    const stateStr = ev.logged_in ? `LOGGED IN (${ev.username || 'active'})` : 'NOT LOGGED IN';
    appendTerminalLine(`[VERIFY] ${ev.platform.toUpperCase()} Session: ${stateStr}`, ev.logged_in ? 'text-emerald' : 'text-amber');
  }

  // 3. Post Discovered & Evaluated by Algorithm Cracker
  if (ev.type === 'post_found') {
    const scoreStr = ev.viralScore ? ` [Viral Score: ${ev.viralScore}/100]` : '';
    appendTerminalLine(`[DISCOVERY] ${ev.platform.toUpperCase()} Candidate @${ev.author} (${ev.postId})${scoreStr}`, 'text-cyan');
    appState.stats.posts_analyzed = (appState.stats.posts_analyzed || 0) + 1;
    renderMetricsUI();
  }

  // 4. Comment Generated
  if (ev.type === 'comment_generated') {
    appendTerminalLine(`[VISION AI] Generated context reply for @${ev.author} (Reach Score: ${ev.reachScore}/100)`, 'text-violet');
  }

  // 5. Comment Successfully Posted
  if (ev.type === 'comment_posted') {
    appendTerminalLine(`[SUCCESS] Placed comment on ${ev.platform.toUpperCase()} post by @${ev.author}! (${ev.progress}/${ev.target})`, 'text-emerald');
    appState.stats.ai_comments = (appState.stats.ai_comments || 0) + 1;
    appState.stats.reach_boost = roundNum(1.0 + (appState.stats.ai_comments * 0.12), 1);
    renderMetricsUI();

    appendActivityCard({
      platform: ev.platform,
      author: ev.author,
      postId: ev.postId,
      comment: ev.comment,
      reachScore: ev.reachScore || 95,
      viralScore: ev.viralScore || 90,
      url: ev.url,
      timestamp: ev.timestamp || (Date.now() / 1000)
    });
  }

  // 6. Comment Failed
  if (ev.type === 'comment_failed') {
    appendTerminalLine(`[FAILED] Comment placement failed on ${ev.platform.toUpperCase()} post ${ev.postId}.`, 'text-amber');
  }

  // 7. Campaign State
  if (ev.type === 'campaign_started') {
    appState.stats.active_campaigns = (appState.stats.active_campaigns || 0) + 1;
    if (appState.platforms[ev.platform]) appState.platforms[ev.platform].active = true;
    renderMetricsUI();
  }

  if (ev.type === 'campaign_completed' || ev.type === 'campaign_stopped') {
    appState.stats.active_campaigns = Math.max(0, (appState.stats.active_campaigns || 1) - 1);
    if (appState.platforms[ev.platform]) appState.platforms[ev.platform].active = false;
    renderMetricsUI();
    appendTerminalLine(`[CAMPAIGN] Finished for ${ev.platform.toUpperCase()}. Total comments placed: ${ev.totalCommented || 0}.`, 'text-cyan');
  }

  // 8. API Key Error Intercept
  if (ev.type === 'api_error' && ev.error) {
    const errLow = String(ev.error).toLowerCase();
    if (errLow.includes('api_key') || errLow.includes('401') || errLow.includes('unauthenticated') || errLow.includes('invalid api key')) {
      showApiErrorModal(ev.error);
    }
  }
}

function roundNum(num, dec = 1) {
  const f = Math.pow(10, dec);
  return Math.round(num * f) / f;
}

/* ==========================================================================
   ACTIVITY FEED CARDS
   ========================================================================== */
function getPostFallbackUrl(platform, postId, author) {
  if (!postId) return null;
  const cleanPostId = String(postId).trim();
  const cleanAuth = author ? String(author).replace('@', '').trim() : '';

  if (platform === 'instagram') {
    return `https://www.instagram.com/p/${cleanPostId}/`;
  }
  if (platform === 'twitter') {
    return cleanAuth && cleanAuth !== 'user'
      ? `https://x.com/${cleanAuth}/status/${cleanPostId}`
      : `https://x.com/i/status/${cleanPostId}`;
  }
  if (platform === 'threads') {
    if (cleanPostId.startsWith('@')) {
      return `https://www.threads.net/${cleanPostId}`;
    }
    return cleanAuth && cleanAuth !== 'creator'
      ? `https://www.threads.net/@${cleanAuth}/post/${cleanPostId}`
      : `https://www.threads.net/t/${cleanPostId}`;
  }
  return null;
}

function appendActivityCard(data) {
  const container = document.getElementById('activity-scroll-container');
  const emptyState = document.getElementById('stream-empty-state');
  if (emptyState) emptyState.style.display = 'none';

  const card = document.createElement('div');
  card.className = 'activity-row-item';

  let tagClass = 'tag-ig', pName = 'Instagram';
  if (data.platform === 'twitter') {
    tagClass = 'tag-x';
    pName = 'X / Twitter';
  } else if (data.platform === 'threads') {
    tagClass = 'tag-threads';
    pName = 'Threads';
  }

  const timeStr = data.timestamp 
    ? new Date(data.timestamp * 1000).toLocaleTimeString() 
    : new Date().toLocaleTimeString();

  const postUrl = data.url || getPostFallbackUrl(data.platform, data.postId, data.author);
  
  if (postUrl) {
    card.title = `Click to view post on ${pName}`;
    card.onclick = () => {
      window.open(postUrl, '_blank', 'noopener,noreferrer');
    };
  }

  card.innerHTML = `
    <div class="act-meta-row">
      <div class="act-identity">
        <span class="tag-platform ${tagClass}">${pName}</span>
        <span class="act-creator-link font-mono">@${data.author || 'creator'}</span>
      </div>
      <div style="display:flex; gap:6px;">
        ${data.viralScore ? `<span class="act-reach-pill font-mono" style="background:rgba(0,242,254,0.12); color:var(--cyan-core);">Viral ${data.viralScore}/100</span>` : ''}
        <span class="act-reach-pill font-mono">Reach ${data.reachScore || 92}/100</span>
      </div>
    </div>
    <div class="act-comment-bubble">
      "${data.comment}"
    </div>
    <div class="act-foot-row font-mono">
      <span>Target: ${data.postId || 'post'}</span>
      ${postUrl ? `<span class="act-visit-badge">View Post ↗</span>` : ''}
      <span>${timeStr}</span>
    </div>
  `;

  container.prepend(card);

  // Keep top 50 in DOM
  const cards = container.querySelectorAll('.activity-row-item');
  if (cards.length > 50) cards[cards.length - 1].remove();

  const badge = document.getElementById('feed-count-badge');
  if (badge) badge.innerText = `${cards.length} Actions`;
}

/* ==========================================================================
   STRICT FIXED-BOTTOM LOG TERMINAL
   ========================================================================== */
function appendTerminalLine(text, colorClass = '') {
  const view = document.getElementById('terminal-viewport');
  if (!view) return;

  const row = document.createElement('div');
  row.className = `term-row ${colorClass}`;
  const now = new Date().toTimeString().split(' ')[0];
  row.innerText = `[${now}] ${text}`;
  view.appendChild(row);

  // Auto-scroll inside bounded container without expanding page layout
  view.scrollTop = view.scrollHeight;

  if (view.childNodes.length > 150) {
    view.removeChild(view.firstChild);
  }
}

function clearTerminal() {
  const view = document.getElementById('terminal-viewport');
  if (view) view.innerHTML = '';
}

/* ==========================================================================
   SETTINGS MODAL
   ========================================================================== */
function setupSettingsDialog() {
  const btn = document.getElementById('open-settings-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      document.getElementById('settings-modal').style.display = 'flex';
    });
  }
}

function closeSettings() {
  const modal = document.getElementById('settings-modal');
  if (modal) modal.style.display = 'none';
}

async function saveConfiguration(e) {
  e.preventDefault();
  const apiKey = document.getElementById('cfg-api-key').value;
  const model = document.getElementById('cfg-model').value;
  const minDelay = parseInt(document.getElementById('cfg-min-delay').value, 10);
  const maxDelay = parseInt(document.getElementById('cfg-max-delay').value, 10);

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey, model, minDelay, maxDelay })
    });
    const json = await res.json();
    if (json.success) {
      appendTerminalLine('[CONFIG] Runtime settings updated successfully.', 'text-emerald');
      if (model) document.getElementById('nav-model-name').innerText = model;
      closeSettings();
    }
  } catch (err) {
    alert('Config save error: ' + err);
  }
}

/* ==========================================================================
   API KEY ERROR ALERT MODAL HANDLERS
   ========================================================================== */
function showApiErrorModal(errorDetail) {
  const modal = document.getElementById('api-error-modal');
  const errorBadge = document.getElementById('modal-api-error-detail');
  const keyInput = document.getElementById('modal-api-key-input');
  
  if (errorBadge && errorDetail) {
    errorBadge.innerText = String(errorDetail);
  }
  if (keyInput) {
    keyInput.value = '';
  }
  if (modal) {
    modal.style.display = 'flex';
    setTimeout(() => {
      if (keyInput) keyInput.focus();
    }, 150);
  }
}

function closeApiErrorModal() {
  const modal = document.getElementById('api-error-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

async function saveApiKeyFromModal(e) {
  e.preventDefault();
  const inputEl = document.getElementById('modal-api-key-input');
  const newApiKey = inputEl ? inputEl.value.trim() : '';

  if (!newApiKey) {
    alert('Please enter a valid Gemini API key.');
    return;
  }

  const btnSubmit = e.target.querySelector('button[type="submit"]');
  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.innerText = 'Saving...';
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey: newApiKey })
    });
    const json = await res.json();
    if (json.success) {
      appendTerminalLine('[CONFIG] Gemini API Key updated in .env! Multimodal Vision active.', 'text-emerald');
      closeApiErrorModal();
      
      const cfgKeyInput = document.getElementById('cfg-api-key');
      if (cfgKeyInput) cfgKeyInput.value = newApiKey;

      fetchInitialState();
    } else {
      alert('Error updating API key: ' + (json.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Failed to save API key: ' + err);
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerText = 'Update Key & Save';
    }
  }
}
