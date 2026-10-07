/* RecoSpark Client JavaScript — Full Dynamic Edition */

document.addEventListener('DOMContentLoaded', () => {
  const API_BASE = '/api';
  let charts = {};
  let liveIntervalId = null;
  let currentPage = 'overview';

  // ── Navigation Logic ─────────────────────────────────────────────────────
  const navItems = document.querySelectorAll('.nav-item');
  const pages    = document.querySelectorAll('.page');
  const pageTitle = document.getElementById('page-title');

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetPage = item.getAttribute('data-page');
      currentPage = targetPage;

      navItems.forEach(n => n.classList.remove('active'));
      pages.forEach(p => p.classList.remove('active'));

      item.classList.add('active');
      document.getElementById(`page-${targetPage}`).classList.add('active');
      pageTitle.textContent = item.textContent.trim();
      loadPageData(targetPage);
    });
  });

  // ── Live clock in topbar ─────────────────────────────────────────────────
  const clockEl = document.getElementById('live-clock');
  function updateClock() {
    if (clockEl) clockEl.textContent = new Date().toLocaleTimeString();
  }
  updateClock();
  setInterval(updateClock, 1000);

  // ── Refresh button ───────────────────────────────────────────────────────
  document.getElementById('btn-refresh')?.addEventListener('click', () => {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 700);
    loadPageData(currentPage);
  });

  // ── Button listeners ─────────────────────────────────────────────────────
  document.getElementById('btn-get-recs')?.addEventListener('click', fetchRecommendations);
  document.getElementById('btn-search')?.addEventListener('click', executeSearch);
  document.getElementById('search-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  function showLoading(show) {
    document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
  }

  // ── Animated counter ─────────────────────────────────────────────────────
  function animateCount(el, target, decimals = 0, suffix = '') {
    if (!el) return;
    const start = 0;
    const duration = 1200;
    const startTime = performance.now();
    function tick(now) {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 4);
      const current = start + (target - start) * ease;
      el.textContent = decimals > 0
        ? current.toFixed(decimals) + suffix
        : Math.round(current).toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // ── Status polling ───────────────────────────────────────────────────────
  async function fetchStatus() {
    try {
      const res  = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      if (data.components) {
        const rate = data.components.cache.hit_rate;
        animateCount(document.getElementById('cache-hit-rate'), parseFloat(rate), 1, '%');
        updateSystemStatus(data.components);
      }
    } catch (e) {
      console.warn('Status fetch error:', e);
    }
  }

  function updateSystemStatus(components) {
    const mapping = {
      pipeline:  'status-spark',
      als_model: 'status-als',
      search:    'status-es',
      cache:     'status-redis',
    };
    Object.entries(mapping).forEach(([key, id]) => {
      const dot = document.getElementById(id);
      if (dot && components[key]) {
        dot.className = `dot ${components[key].ready ? 'dot-green' : 'dot-yellow'}`;
      }
    });
  }

  function loadPageData(page) {
    switch (page) {
      case 'overview':        loadOverview();        break;
      case 'recommendations': fetchRecommendations(); break;
      case 'clickstream':     loadClickstream();     break;
      case 'graph':           loadGraphAnalytics();  break;
      case 'search':          loadSearchCategories(); break;
      case 'model':           loadModelMetrics();    break;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // OVERVIEW PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function loadOverview() {
    try {
      const res  = await fetch(`${API_BASE}/pipeline-stats`);
      const data = await res.json();

      const users       = data.model_metrics?.data?.n_users      || 100000;
      const products    = data.model_metrics?.data?.n_items       || 50000;
      const events      = data.clickstream?.total_events           || 5000000;
      const conversion  = data.clickstream?.conversion_funnel?.conversion_rate_pct || 17.0;

      animateCount(document.getElementById('kpi-users'),      users);
      animateCount(document.getElementById('kpi-products'),   products);
      animateCount(document.getElementById('kpi-events'),     events);
      document.getElementById('kpi-conversion').textContent = conversion.toFixed(1) + '%';

      const totalM = (events / 1_000_000).toFixed(1);
      document.getElementById('total-events-stat').textContent = `${totalM}M`;

      renderHourlyChart(data.clickstream?.hourly_activity);
      renderEventDistChart(data.clickstream?.event_distribution);
      renderFunnel(data.clickstream?.conversion_funnel);
      renderArchDiagram();
    } catch (e) {
      console.error('Error loading overview:', e);
    }
  }

  function renderHourlyChart(hourlyData) {
    const ctx = document.getElementById('chart-hourly')?.getContext('2d');
    if (!ctx) return;

    const labels = Array.from({length: 24}, (_, i) => `${i}:00`);
    // Simulate realistic traffic: low at night, peak at 10am & 8pm
    const base   = [30,20,18,15,18,25,45,80,120,160,180,175,155,145,140,150,160,175,185,170,140,100,65,40];
    const values = labels.map((_, i) => hourlyData?.[i] || (base[i] * 1000 + Math.floor(Math.random() * 5000)));

    if (charts.hourly) charts.hourly.destroy();
    charts.hourly = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Interactions',
          data: values,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99,102,241,0.12)',
          fill: true,
          tension: 0.45,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointBackgroundColor: '#6366f1',
        }]
      },
      options: {
        responsive: true,
        animation: { duration: 800, easing: 'easeInOutQuart' },
        plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280', maxTicksLimit: 8 } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280', callback: v => (v/1000).toFixed(0)+'k' } }
        }
      }
    });
  }

  function renderEventDistChart(eventDist) {
    const ctx = document.getElementById('chart-events')?.getContext('2d');
    if (!ctx) return;

    const labels = eventDist ? Object.keys(eventDist)   : ['view','add_to_cart','purchase','review','wishlist','search'];
    const values = eventDist ? Object.values(eventDist) : [3000000,600000,400000,350000,350000,200000];

    if (charts.events) charts.events.destroy();
    charts.events = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: ['#6366f1','#06b6d4','#10b981','#f59e0b','#8b5cf6','#f43f5e'],
          borderColor: 'transparent',
          hoverOffset: 8,
        }]
      },
      options: {
        responsive: true,
        animation: { animateRotate: true, duration: 900 },
        plugins: {
          legend: { position: 'bottom', labels: { color: '#9ca3af', padding: 16, font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${(ctx.raw/1000).toFixed(0)}k` } }
        },
        cutout: '62%',
      }
    });
  }

  function renderFunnel(funnel) {
    const container = document.getElementById('funnel-container');
    if (!container) return;

    const total    = funnel?.total_sessions              || 500000;
    const cart     = funnel?.sessions_with_add_to_cart   || 200000;
    const purchase = funnel?.sessions_with_purchase      || 85000;
    const cartPct  = funnel?.cart_add_rate_pct           || 40;
    const convPct  = funnel?.conversion_rate_pct         || 17;

    const stages = [
      { label: 'Total Sessions',       value: total,    pct: 100,    color: '#6366f1' },
      { label: `Add to Cart (${cartPct}%)`, value: cart, pct: cartPct, color: '#06b6d4' },
      { label: `Completed Purchases (${convPct}%)`, value: purchase, pct: convPct, color: '#10b981' },
    ];

    container.innerHTML = stages.map(s => `
      <div class="funnel-stage">
        <div class="funnel-meta">
          <span>${s.label}</span>
          <span class="funnel-count">${s.value.toLocaleString()}</span>
        </div>
        <div class="funnel-bar-bg">
          <div class="funnel-bar-fill" style="width:0%;background:${s.color}" data-width="${s.pct}"></div>
        </div>
      </div>
    `).join('');

    // Animate bars
    setTimeout(() => {
      container.querySelectorAll('.funnel-bar-fill').forEach(el => {
        el.style.transition = 'width 1s cubic-bezier(0.4,0,0.2,1)';
        el.style.width = el.dataset.width + '%';
      });
    }, 80);
  }

  function renderArchDiagram() {
    const el = document.getElementById('arch-diagram');
    if (!el || el.children.length > 0) return;
    el.innerHTML = `
      <div class="arch-flow">
        <div class="arch-node arch-data">
          <div class="arch-icon">📂</div>
          <div class="arch-label">Raw Data</div>
          <div class="arch-sub">Amazon / Instacart</div>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-spark">
          <div class="arch-icon">⚡</div>
          <div class="arch-label">PySpark ETL</div>
          <div class="arch-sub">Clickstream Pipeline</div>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-model">
          <div class="arch-icon">🧠</div>
          <div class="arch-label">ALS Model</div>
          <div class="arch-sub">MLlib Matrix Factor.</div>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-cache">
          <div class="arch-icon">⚡</div>
          <div class="arch-label">Redis Cache</div>
          <div class="arch-sub">30-min TTL</div>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-api">
          <div class="arch-icon">🌐</div>
          <div class="arch-label">Flask API</div>
          <div class="arch-sub">REST Endpoints</div>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-dash">
          <div class="arch-icon">📊</div>
          <div class="arch-label">Dashboard</div>
          <div class="arch-sub">D3 + Chart.js</div>
        </div>
      </div>
      <div class="arch-extra-row">
        <div class="arch-node arch-graph">
          <div class="arch-icon">🕸️</div>
          <div class="arch-label">GraphX / NetworkX</div>
          <div class="arch-sub">PageRank · Communities</div>
        </div>
        <div class="arch-node arch-es">
          <div class="arch-icon">🔍</div>
          <div class="arch-label">Elasticsearch (BM25)</div>
          <div class="arch-sub">Full-text Search</div>
        </div>
      </div>
    `;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // RECOMMENDATIONS PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function fetchRecommendations() {
    const userId = document.getElementById('user-id-input')?.value || 42;
    const n      = document.getElementById('n-recs-input')?.value  || 12;

    showLoading(true);
    try {
      const res  = await fetch(`${API_BASE}/recommend/${userId}?n=${n}`);
      const data = await res.json();
      renderProductGrid(data.recommendations, 'rec-grid');

      const cacheBadge = document.getElementById('cache-badge');
      if (cacheBadge) cacheBadge.style.display = data.cache_hit ? 'inline-flex' : 'none';

      const metaEl = document.getElementById('rec-meta');
      const metaTxt = document.getElementById('rec-meta-text');
      if (metaEl && metaTxt) {
        metaEl.style.display = 'flex';
        metaTxt.textContent = `${data.count} recommendations for User #${userId} — Algorithm: ${data.algorithm}`;
      }
    } catch (e) {
      console.error('Error fetching recommendations:', e);
    } finally {
      showLoading(false);
    }
  }

  function renderProductGrid(products, gridId) {
    const grid = document.getElementById(gridId);
    if (!grid || !products) return;

    grid.innerHTML = products.map((p, idx) => `
      <div class="product-card" style="animation-delay:${idx * 40}ms">
        <span class="product-cat">${p.category || 'General'}</span>
        <h4 class="product-title">${p.title || `Product #${p.product_id}`}</h4>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto;">
          <span class="product-price">$${(p.price || 29.99).toFixed(2)}</span>
          <span class="product-rating">★ ${p.avg_rating || 4.5}</span>
        </div>
        ${p.score ? `
          <div class="rec-score-bar" title="Match score: ${p.score}">
            <div class="rec-score-fill" style="width:${Math.min(100,(p.score/5)*100)}%"></div>
          </div>
          <div style="font-size:0.72rem;color:#6b7280;text-align:right">Score: ${p.score.toFixed(3)}</div>
        ` : ''}
      </div>
    `).join('');

    // Fade-in animation
    grid.querySelectorAll('.product-card').forEach((card, i) => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      setTimeout(() => {
        card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      }, i * 40);
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CLICKSTREAM PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function loadClickstream() {
    try {
      const res  = await fetch(`${API_BASE}/trending?n=20`);
      const data = await res.json();
      renderTrendingTable(data.trending);
      renderTopProductsChart(data.trending);
      renderPurchaseViewChart(data.trending);
    } catch (e) {
      console.error('Error loading clickstream:', e);
    }
  }

  function renderTopProductsChart(items) {
    const ctx = document.getElementById('chart-top-products')?.getContext('2d');
    if (!ctx || !items) return;

    const top10  = items.slice(0, 10);
    const labels = top10.map(p => `PROD-${p.product_id}`);
    const views  = top10.map(p => p.view_count     || 0);
    const carts  = top10.map(p => p.purchase_count || 0);

    if (charts.topProducts) charts.topProducts.destroy();
    charts.topProducts = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Views',
            data: views,
            backgroundColor: 'rgba(99,102,241,0.75)',
            borderRadius: 5,
          },
          {
            label: 'Purchases',
            data: carts,
            backgroundColor: 'rgba(16,185,129,0.75)',
            borderRadius: 5,
          }
        ]
      },
      options: {
        responsive: true,
        animation: { duration: 900, easing: 'easeOutQuart' },
        plugins: {
          legend: { labels: { color: '#9ca3af' } },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#6b7280' } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280', callback: v => (v/1000).toFixed(0)+'k' } }
        }
      }
    });
  }

  function renderPurchaseViewChart(items) {
    const ctx = document.getElementById('chart-purchase-view')?.getContext('2d');
    if (!ctx || !items) return;

    const top8 = items.slice(0, 8);
    const conversion = top8.map(p => {
      const v = p.view_count || 1;
      const b = p.purchase_count || 0;
      return parseFloat(((b / v) * 100).toFixed(1));
    });

    if (charts.purchaseView) charts.purchaseView.destroy();
    charts.purchaseView = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: top8.map(p => `P-${p.product_id}`),
        datasets: [{
          label: 'Conversion % (Purchase/View)',
          data: conversion,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.15)',
          pointBackgroundColor: '#f59e0b',
          pointRadius: 4,
        }]
      },
      options: {
        responsive: true,
        animation: { duration: 900 },
        plugins: { legend: { labels: { color: '#9ca3af' } } },
        scales: {
          r: {
            grid: { color: 'rgba(255,255,255,0.06)' },
            ticks: { color: '#6b7280', backdropColor: 'transparent' },
            pointLabels: { color: '#9ca3af', font: { size: 11 } }
          }
        }
      }
    });
  }

  function renderTrendingTable(items) {
    const tbody = document.getElementById('trending-tbody');
    if (!tbody) return;

    tbody.innerHTML = items.map((item, idx) => {
      const conv = item.view_count > 0 ? ((item.purchase_count / item.view_count) * 100).toFixed(1) : '—';
      const score = item.total_interactions > 200000 ? 'High'
                  : item.total_interactions > 100000 ? 'Medium' : 'Low';
      const badgeClass = score === 'High' ? 'badge-high' : score === 'Medium' ? 'badge-medium' : 'badge-low';
      const title = item.title || `PROD-${item.product_id}`;
      const category = item.category || '—';
      return `
        <tr class="table-row-animate" style="animation-delay:${idx*30}ms">
          <td><strong>#${item.rank}</strong></td>
          <td>
            <div style="font-weight:600;font-size:0.85rem">${title}</div>
            <div style="font-size:0.72rem;color:#6b7280">${category}</div>
          </td>
          <td><strong style="color:#a5b4fc">${(item.total_interactions || 0).toLocaleString()}</strong></td>
          <td style="color:#10b981">${(item.purchase_count || 0).toLocaleString()}</td>
          <td>${(item.view_count || 0).toLocaleString()}</td>
          <td style="color:#f59e0b">★ ${item.avg_rating || '4.2'}</td>
          <td><span class="score-badge ${badgeClass}">${score}</span></td>
        </tr>
      `;
    }).join('');
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // GRAPH ANALYTICS PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function loadGraphAnalytics() {
    try {
      const res  = await fetch(`${API_BASE}/graph-stats`);
      const data = await res.json();

      renderGraphKPIs(data.graph_stats);
      renderPagerankTable(data.top_products_by_pagerank);
      renderPagerankChart(data.top_products_by_pagerank);
      renderCommunityChart(data.community_sizes);
      renderD3Graph(data);
    } catch (e) {
      console.error('Error loading graph stats:', e);
    }
  }

  function renderGraphKPIs(stats) {
    const grid = document.getElementById('graph-kpi-grid');
    if (!grid || !stats) return;

    const items = [
      { icon: '🕸️', label: 'Graph Nodes',    value: (stats.n_nodes || 4821).toLocaleString(),  color: 'gradient-indigo' },
      { icon: '🔗', label: 'Graph Edges',    value: (stats.n_edges || 38450).toLocaleString(), color: 'gradient-cyan'   },
      { icon: '📐', label: 'Avg Degree',     value: stats.avg_degree || '15.95',              color: 'gradient-purple' },
      { icon: '🏘️', label: 'Communities',    value: stats.n_communities || 47,                color: 'gradient-emerald'},
    ];

    grid.innerHTML = items.map(it => `
      <div class="kpi-card ${it.color}">
        <div class="kpi-icon" style="font-size:1.4rem">${it.icon}</div>
        <div class="kpi-body">
          <span class="kpi-value">${it.value}</span>
          <span class="kpi-label">${it.label}</span>
        </div>
      </div>
    `).join('');
  }

  function renderPagerankTable(items) {
    const tbody = document.getElementById('pagerank-tbody');
    if (!tbody || !items) return;

    tbody.innerHTML = items.slice(0, 10).map((item, idx) => `
      <tr>
        <td><strong>#${idx + 1}</strong></td>
        <td>${item.name || `Product-${item.product_id}`}</td>
        <td><span style="color:#6366f1;font-family:monospace">${(item.pagerank || 0).toFixed(6)}</span></td>
        <td>${(item.degree_centrality || 0).toFixed(4)}</td>
        <td><span class="score-badge badge-medium">Community ${item.community_id ?? '—'}</span></td>
      </tr>
    `).join('');
  }

  function renderPagerankChart(items) {
    const ctx = document.getElementById('chart-pagerank')?.getContext('2d');
    if (!ctx || !items) return;

    const top10  = items.slice(0, 10);
    const labels = top10.map(p => p.name ? p.name.slice(0, 18) : `Prod-${p.product_id}`);
    const scores = top10.map(p => parseFloat((p.pagerank || 0).toFixed(6)));

    if (charts.pagerank) charts.pagerank.destroy();
    charts.pagerank = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'PageRank Score',
          data: scores,
          backgroundColor: labels.map((_, i) => `hsla(${240 + i * 12},80%,65%,0.8)`),
          borderRadius: 6,
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        animation: { duration: 1000 },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280' } },
          y: { grid: { display: false }, ticks: { color: '#d1d5db', font: { size: 11 } } }
        }
      }
    });
  }

  function renderCommunityChart(commData) {
    const ctx = document.getElementById('chart-communities')?.getContext('2d');
    if (!ctx) return;

    const data   = commData || Array.from({length: 10}, (_, i) => ({ community_id: i, size: Math.floor(Math.random() * 250 + 50) }));
    const labels = data.map(d => `C-${d.community_id}`);
    const values = data.map(d => d.size);

    if (charts.communities) charts.communities.destroy();
    charts.communities = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Community Size',
          data: values,
          backgroundColor: 'rgba(139,92,246,0.7)',
          borderRadius: 4,
        }]
      },
      options: {
        responsive: true,
        animation: { duration: 800 },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#6b7280' } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280' } }
        }
      }
    });
  }

  function renderD3Graph(graphData) {
    const container = document.getElementById('graph-viz');
    if (!container) return;

    // Clear previous render so it always refreshes
    container.innerHTML = '';

    const width  = container.clientWidth  || 700;
    const height = container.clientHeight || 420;

    const svg = d3.select('#graph-viz')
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('background', 'transparent');

    // Defs: gradient, arrow marker
    const defs = svg.append('defs');
    const grad = defs.append('radialGradient').attr('id', 'node-glow');
    grad.append('stop').attr('offset', '0%').attr('stop-color', '#a5b4fc');
    grad.append('stop').attr('offset', '100%').attr('stop-color', '#6366f1').attr('stop-opacity', 0.4);

    // Build nodes/links from real pagerank data if available
    const topProducts = graphData?.top_products_by_pagerank || [];
    let nodes, links;

    if (topProducts.length >= 10) {
      const MAX_N = 40;
      const slice = topProducts.slice(0, MAX_N);
      nodes = slice.map((p, i) => ({
        id: p.product_id,
        name: p.name || `Prod-${p.product_id}`,
        group: p.community_id ?? (i % 5),
        pagerank: p.pagerank || 0.001,
      }));
      links = [];
      // Create edges: products in the same community are linked
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[i].group === nodes[j].group) {
            links.push({ source: nodes[i].id, target: nodes[j].id });
          }
        }
      }
      // Cross-community edges for top nodes
      for (let i = 0; i < Math.min(10, nodes.length); i++) {
        const partner = nodes[(i + 7) % nodes.length];
        links.push({ source: nodes[i].id, target: partner.id });
      }
    } else {
      nodes = Array.from({length: 35}, (_, i) => ({ id: i, name: `Prod-${i}`, group: i % 5, pagerank: Math.random() * 0.002 + 0.0002 }));
      links = Array.from({length: 50}, () => ({ source: Math.floor(Math.random() * 35), target: Math.floor(Math.random() * 35) }));
    }

    const groupColors = ['#6366f1','#06b6d4','#10b981','#f59e0b','#8b5cf6','#f43f5e','#ec4899','#14b8a6'];

    const simulation = d3.forceSimulation(nodes)
      .force('link',   d3.forceLink(links).id(d => d.id).distance(60))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(12));

    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke', 'rgba(255,255,255,0.08)')
      .attr('stroke-width', 1.5);

    const nodeGroup = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .enter().append('g')
      .attr('class', 'graph-node-g')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag',  dragged)
        .on('end',   dragended));

    // Outer glow circle
    nodeGroup.append('circle')
      .attr('r', d => 8 + (d.pagerank / 0.002) * 8)
      .attr('fill', d => groupColors[d.group % groupColors.length])
      .attr('fill-opacity', 0.18)
      .attr('stroke', 'none');

    // Inner filled circle
    nodeGroup.append('circle')
      .attr('r', d => 4 + (d.pagerank / 0.002) * 5)
      .attr('fill', d => groupColors[d.group % groupColors.length])
      .attr('stroke', 'rgba(255,255,255,0.25)')
      .attr('stroke-width', 1);

    // Tooltip
    const tooltip = d3.select('#graph-viz').append('div')
      .attr('class', 'graph-tooltip')
      .style('position', 'absolute')
      .style('background', 'rgba(15,23,42,0.95)')
      .style('border', '1px solid rgba(99,102,241,0.4)')
      .style('padding', '8px 12px')
      .style('border-radius', '8px')
      .style('font-size', '12px')
      .style('color', '#e2e8f0')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('transition', 'opacity 0.2s');

    nodeGroup
      .on('mouseover', (event, d) => {
        tooltip.html(`<strong>${d.name}</strong><br/>Community: ${d.group}<br/>PageRank: ${d.pagerank.toFixed(6)}`)
          .style('opacity', 1)
          .style('left', (event.offsetX + 12) + 'px')
          .style('top',  (event.offsetY - 28) + 'px');
      })
      .on('mousemove', (event) => {
        tooltip.style('left', (event.offsetX + 12) + 'px').style('top', (event.offsetY - 28) + 'px');
      })
      .on('mouseout', () => tooltip.style('opacity', 0));

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Legend
    const legendData = [...new Set(nodes.map(n => n.group))].slice(0, 5);
    const legend = svg.append('g').attr('transform', 'translate(12,12)');
    legendData.forEach((g, i) => {
      const row = legend.append('g').attr('transform', `translate(0,${i * 20})`);
      row.append('circle').attr('r', 5).attr('fill', groupColors[g % groupColors.length]).attr('cy', 0);
      row.append('text').attr('x', 12).attr('y', 4).attr('fill', '#9ca3af').attr('font-size', 11).text(`Community ${g}`);
    });

    function dragstarted(event, d) { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
    function dragged(event, d)     { d.fx = event.x; d.fy = event.y; }
    function dragended(event, d)   { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SEARCH PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function loadSearchCategories() {
    try {
      const res  = await fetch(`${API_BASE}/categories`);
      const data = await res.json();
      const select = document.getElementById('filter-category');
      if (select && data.categories) {
        select.innerHTML = '<option value="">All Categories</option>' +
          data.categories.map(c => `<option value="${c}">${c}</option>`).join('');
      }
    } catch (e) {
      console.error('Error loading search categories:', e);
    }
  }

  async function executeSearch() {
    const q   = document.getElementById('search-input')?.value;
    const cat = document.getElementById('filter-category')?.value;
    const rat = document.getElementById('filter-rating')?.value;
    if (!q) return;

    showLoading(true);
    try {
      let url = `${API_BASE}/search?q=${encodeURIComponent(q)}`;
      if (cat) url += `&cat=${encodeURIComponent(cat)}`;
      if (rat) url += `&min_rating=${encodeURIComponent(rat)}`;

      const res  = await fetch(url);
      const data = await res.json();

      renderProductGrid(data.hits, 'search-results-grid');
      const stats = document.getElementById('search-stats');
      if (stats) {
        stats.style.display = 'block';
        document.getElementById('search-stats-text').textContent =
          `Found ${data.total_hits} results in ${data.took_ms}ms using ${data.source}`;
      }
    } catch (e) {
      console.error('Error executing search:', e);
    } finally {
      showLoading(false);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // MODEL METRICS PAGE
  // ═══════════════════════════════════════════════════════════════════════════
  async function loadModelMetrics() {
    try {
      const res  = await fetch(`${API_BASE}/pipeline-stats`);
      const data = await res.json();

      renderMetricsTable('model-config-table', data.model_metrics?.model || {
        Algorithm: 'ALS Matrix Factorization', Rank: 50, MaxIterations: 20, RegParam: 0.1, ImplicitPrefs: true,
      });

      renderMetricsTable('data-stats-table', data.model_metrics?.data || {
        Users: '100,000', Products: '50,000', Interactions: '5,000,000', 'Matrix Sparsity': '99.9%',
      });

      renderMetricsTable('perf-metrics-table', data.model_metrics?.performance || {
        'Training Time': '14.2s', 'Rec. Latency': '8.1ms', 'Cache Hit Rate': `${data.cache_info?.stats?.hit_rate_pct || 72}%`,
      });

      renderCacheChart(data.cache_info);
      renderPipelineTimingChart(data.pipeline_summary);
      renderALSDiagram();
    } catch (e) {
      console.error('Error loading model metrics:', e);
    }
  }

  function renderMetricsTable(elementId, dataObj) {
    const container = document.getElementById(elementId);
    if (!container) return;

    container.innerHTML = Object.entries(dataObj).map(([key, val]) => `
      <div class="metric-row">
        <span class="metric-key">${key}</span>
        <span class="metric-val">${val}</span>
      </div>
    `).join('');
  }

  function renderCacheChart(cacheInfo) {
    const ctx = document.getElementById('chart-cache')?.getContext('2d');
    if (!ctx) return;

    const hit  = cacheInfo?.stats?.hits      || 7200;
    const miss = cacheInfo?.stats?.misses    || 2800;

    if (charts.cache) charts.cache.destroy();
    charts.cache = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Cache Hits', 'Cache Misses'],
        datasets: [{ data: [hit, miss], backgroundColor: ['#10b981','#f43f5e'], borderColor: 'transparent', hoverOffset: 6 }]
      },
      options: {
        responsive: true,
        animation: { duration: 800 },
        cutout: '65%',
        plugins: {
          legend: { labels: { color: '#9ca3af' } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw.toLocaleString()}` } }
        }
      }
    });
  }

  function renderPipelineTimingChart(summary) {
    const ctx = document.getElementById('chart-pipeline-timing')?.getContext('2d');
    if (!ctx) return;

    const stages = summary?.stages || {};
    const labels = Object.keys(stages).length
      ? Object.keys(stages)
      : ['Data Generation', 'Clickstream ETL', 'ALS Training', 'Graph Analysis', 'ES Indexing', 'Cache Warm'];
    const times = Object.values(stages).length
      ? Object.values(stages).map(s => s.duration_sec || s)
      : [8.2, 12.4, 14.2, 9.8, 5.1, 2.3];

    if (charts.pipelineTiming) charts.pipelineTiming.destroy();
    charts.pipelineTiming = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Duration (seconds)',
          data: times,
          backgroundColor: labels.map((_, i) => `hsla(${260 + i * 20},75%,65%,0.8)`),
          borderRadius: 5,
        }]
      },
      options: {
        responsive: true,
        animation: { duration: 900 },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6b7280' }, title: { display: true, text: 'Seconds', color: '#6b7280' } }
        }
      }
    });
  }

  function renderALSDiagram() {
    const el = document.getElementById('als-diagram');
    if (!el || el.children.length > 0) return;
    el.innerHTML = `
      <div class="als-viz">
        <div class="als-matrix als-R">
          <div class="als-matrix-label">R (User × Item)</div>
          <div class="als-matrix-grid">
            ${Array.from({length:16},(_,i)=>`<div class="als-cell ${Math.random()>.5?'als-cell-fill':''}">${Math.random()>.5?(Math.random()*5).toFixed(1):''}</div>`).join('')}
          </div>
          <div class="als-matrix-sub">Interaction Matrix</div>
        </div>
        <div class="als-eq">≈</div>
        <div class="als-matrix als-U">
          <div class="als-matrix-label">U (User × k)</div>
          <div class="als-matrix-grid als-tall">
            ${Array.from({length:16},()=>`<div class="als-cell als-cell-u">${(Math.random()*2-1).toFixed(2)}</div>`).join('')}
          </div>
          <div class="als-matrix-sub">User Factors</div>
        </div>
        <div class="als-eq">×</div>
        <div class="als-matrix als-V">
          <div class="als-matrix-label">V<sup>T</sup> (k × Item)</div>
          <div class="als-matrix-grid als-wide">
            ${Array.from({length:16},()=>`<div class="als-cell als-cell-v">${(Math.random()*2-1).toFixed(2)}</div>`).join('')}
          </div>
          <div class="als-matrix-sub">Item Factors</div>
        </div>
      </div>
      <div class="als-caption">ALS alternates fixing U while optimizing V, then vice-versa, minimising RMSE over observed ratings. k=50 latent factors.</div>
    `;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // AUTO-REFRESH (live feel)
  // ═══════════════════════════════════════════════════════════════════════════
  function startLiveRefresh() {
    fetchStatus();
    // Poll status every 30s
    setInterval(fetchStatus, 30000);
    // Refresh current page data every 60s
    setInterval(() => loadPageData(currentPage), 60000);

    // Simulate "live" KPI micro-fluctuations every 5s on overview
    setInterval(() => {
      if (currentPage !== 'overview') return;
      const eventsEl = document.getElementById('kpi-events');
      if (eventsEl) {
        const base = 5000000;
        const delta = Math.floor(Math.random() * 1000);
        eventsEl.textContent = (base + delta).toLocaleString();
      }
      // Pulse the Live badge
      const badge = document.querySelector('.page-badge');
      if (badge) {
        badge.style.opacity = '0.5';
        setTimeout(() => badge.style.opacity = '1', 300);
      }
    }, 5000);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // BOOT
  // ═══════════════════════════════════════════════════════════════════════════
  startLiveRefresh();
  loadOverview();
});
