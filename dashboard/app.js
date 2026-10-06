/* RecoSpark Client JavaScript */

document.addEventListener('DOMContentLoaded', () => {
  const API_BASE = '/api';
  let charts = {};

  // Navigation Logic
  const navItems = document.querySelectorAll('.nav-item');
  const pages = document.querySelectorAll('.page');
  const pageTitle = document.getElementById('page-title');

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetPage = item.getAttribute('data-page');

      navItems.forEach(n => n.classList.remove('active'));
      pages.forEach(p => p.classList.remove('active'));

      item.classList.add('active');
      document.getElementById(`page-${targetPage}`).classList.add('active');

      pageTitle.textContent = item.textContent.trim();
      loadPageData(targetPage);
    });
  });

  // Fetch API status & setup overview
  fetchStatus();
  loadOverview();

  // Button Listeners
  document.getElementById('btn-get-recs')?.addEventListener('click', fetchRecommendations);
  document.getElementById('btn-search')?.addEventListener('click', executeSearch);
  document.getElementById('search-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  function showLoading(show) {
    document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
  }

  async function fetchStatus() {
    try {
      const res = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      if (data.components) {
        document.getElementById('cache-hit-rate').textContent = `${data.components.cache.hit_rate}%`;
      }
    } catch (e) {
      console.warn('Status fetch error:', e);
    }
  }

  function loadPageData(page) {
    switch (page) {
      case 'overview': loadOverview(); break;
      case 'recommendations': fetchRecommendations(); break;
      case 'clickstream': loadClickstream(); break;
      case 'graph': loadGraphAnalytics(); break;
      case 'search': loadSearchCategories(); break;
      case 'model': loadModelMetrics(); break;
    }
  }

  // OVERVIEW PAGE
  async function loadOverview() {
    try {
      const res = await fetch(`${API_BASE}/pipeline-stats`);
      const data = await res.json();

      // KPI updates
      document.getElementById('kpi-users').textContent = (data.model_metrics?.data?.n_users || 100000).toLocaleString();
      document.getElementById('kpi-products').textContent = (data.model_metrics?.data?.n_items || 50000).toLocaleString();
      document.getElementById('kpi-events').textContent = (data.clickstream?.total_events || 5000000).toLocaleString();
      document.getElementById('kpi-conversion').textContent = `${data.clickstream?.conversion_funnel?.conversion_rate_pct || 17.0}%`;
      document.getElementById('total-events-stat').textContent = `${(data.clickstream?.total_events / 1000000).toFixed(1)}M`;

      renderHourlyChart(data.clickstream?.hourly_activity);
      renderEventDistChart(data.clickstream?.event_distribution);
      renderFunnel(data.clickstream?.conversion_funnel);
    } catch (e) {
      console.error('Error loading overview:', e);
    }
  }

  function renderHourlyChart(hourlyData) {
    const ctx = document.getElementById('chart-hourly')?.getContext('2d');
    if (!ctx) return;

    const labels = Array.from({length: 24}, (_, i) => `${i}:00`);
    const values = labels.map((_, i) => hourlyData?.[i] || Math.floor(Math.random() * 200000 + 50000));

    if (charts.hourly) charts.hourly.destroy();
    charts.hourly = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Interactions',
          data: values,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.15)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' } }
        }
      }
    });
  }

  function renderEventDistChart(eventDist) {
    const ctx = document.getElementById('chart-events')?.getContext('2d');
    if (!ctx) return;

    const labels = eventDist ? Object.keys(eventDist) : ['view', 'add_to_cart', 'purchase', 'review', 'wishlist'];
    const values = eventDist ? Object.values(eventDist) : [3000000, 600000, 400000, 350000, 350000];

    if (charts.events) charts.events.destroy();
    charts.events = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6']
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom', labels: { color: '#9ca3af' } } }
      }
    });
  }

  function renderFunnel(funnel) {
    const container = document.getElementById('funnel-container');
    if (!container) return;

    const total = funnel?.total_sessions || 500000;
    const cart = funnel?.sessions_with_add_to_cart || 200000;
    const purchase = funnel?.sessions_with_purchase || 85000;

    container.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:12px; padding:10px 0;">
        <div>
          <div style="display:flex; justify-between; font-size:0.85rem; margin-bottom:4px;">
            <span>Total Sessions</span><span>${total.toLocaleString()}</span>
          </div>
          <div style="height:8px; background:rgba(255,255,255,0.1); border-radius:4px;"><div style="width:100%; height:100%; background:#6366f1; border-radius:4px;"></div></div>
        </div>
        <div>
          <div style="display:flex; justify-between; font-size:0.85rem; margin-bottom:4px;">
            <span>Add to Cart (${funnel?.cart_add_rate_pct || 40}%)</span><span>${cart.toLocaleString()}</span>
          </div>
          <div style="height:8px; background:rgba(255,255,255,0.1); border-radius:4px;"><div style="width:${funnel?.cart_add_rate_pct || 40}%; height:100%; background:#06b6d4; border-radius:4px;"></div></div>
        </div>
        <div>
          <div style="display:flex; justify-between; font-size:0.85rem; margin-bottom:4px;">
            <span>Completed Purchases (${funnel?.conversion_rate_pct || 17}%)</span><span>${purchase.toLocaleString()}</span>
          </div>
          <div style="height:8px; background:rgba(255,255,255,0.1); border-radius:4px;"><div style="width:${funnel?.conversion_rate_pct || 17}%; height:100%; background:#10b981; border-radius:4px;"></div></div>
        </div>
      </div>
    `;
  }

  // RECOMMENDATIONS PAGE
  async function fetchRecommendations() {
    const userId = document.getElementById('user-id-input')?.value || 42;
    const n = document.getElementById('n-recs-input')?.value || 12;

    showLoading(true);
    try {
      const res = await fetch(`${API_BASE}/recommend/${userId}?n=${n}`);
      const data = await res.json();
      renderProductGrid(data.recommendations, 'rec-grid');

      const cacheBadge = document.getElementById('cache-badge');
      if (cacheBadge) cacheBadge.style.display = data.cache_hit ? 'inline-flex' : 'none';
    } catch (e) {
      console.error('Error fetching recommendations:', e);
    } finally {
      showLoading(false);
    }
  }

  function renderProductGrid(products, gridId) {
    const grid = document.getElementById(gridId);
    if (!grid) return;

    grid.innerHTML = products.map(p => `
      <div class="product-card">
        <span class="product-cat">${p.category || 'General'}</span>
        <h4 class="product-title">${p.title || `Product #${p.product_id}`}</h4>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:auto;">
          <span class="product-price">$${(p.price || 29.99).toFixed(2)}</span>
          <span class="product-rating">★ ${p.avg_rating || 4.5}</span>
        </div>
        ${p.score ? `
          <div class="rec-score-bar" title="Match score: ${p.score}">
            <div class="rec-score-fill" style="width: ${Math.min(100, (p.score / 5) * 100)}%"></div>
          </div>
        ` : ''}
      </div>
    `).join('');
  }

  // CLICKSTREAM PAGE
  async function loadClickstream() {
    try {
      const res = await fetch(`${API_BASE}/trending?n=20`);
      const data = await res.json();
      renderTrendingTable(data.trending);
    } catch (e) {
      console.error('Error loading clickstream:', e);
    }
  }

  function renderTrendingTable(items) {
    const tbody = document.getElementById('trending-tbody');
    if (!tbody) return;

    tbody.innerHTML = items.map(item => `
      <tr>
        <td>#${item.rank}</td>
        <td>PROD-${item.product_id}</td>
        <td>${(item.total_interactions || 0).toLocaleString()}</td>
        <td>${(item.purchase_count || 0).toLocaleString()}</td>
        <td>${(item.view_count || 0).toLocaleString()}</td>
        <td>★ ${item.avg_rating || '4.2'}</td>
        <td><span class="page-badge">High</span></td>
      </tr>
    `).join('');
  }

  // GRAPH ANALYTICS PAGE
  async function loadGraphAnalytics() {
    try {
      const res = await fetch(`${API_BASE}/graph-stats`);
      const data = await res.json();
      renderPagerankTable(data.top_products_by_pagerank);
      renderD3Graph();
    } catch (e) {
      console.error('Error loading graph stats:', e);
    }
  }

  function renderPagerankTable(items) {
    const tbody = document.getElementById('pagerank-tbody');
    if (!tbody || !items) return;

    tbody.innerHTML = items.slice(0, 10).map((item, idx) => `
      <tr>
        <td>#${idx + 1}</td>
        <td>${item.name || `Product-${item.product_id}`}</td>
        <td>${item.pagerank}</td>
        <td>${item.degree_centrality}</td>
        <td>Community ${item.community_id}</td>
      </tr>
    `).join('');
  }

  function renderD3Graph() {
    const container = document.getElementById('graph-viz');
    if (!container || container.children.length > 0) return;

    const width = container.clientWidth;
    const height = container.clientHeight || 400;

    const svg = d3.select('#graph-viz')
      .append('svg')
      .attr('width', width)
      .attr('height', height);

    // Dummy force graph simulation for preview
    const nodes = Array.from({length: 30}, (_, i) => ({id: i, group: i % 4}));
    const links = Array.from({length: 40}, () => ({
      source: Math.floor(Math.random() * 30),
      target: Math.floor(Math.random() * 30)
    }));

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(50))
      .force('charge', d3.forceManyBody().strength(-80))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke', 'rgba(255,255,255,0.1)');

    const node = svg.append('g')
      .selectAll('circle')
      .data(nodes)
      .enter().append('circle')
      .attr('r', 6)
      .attr('fill', d => ['#6366f1', '#06b6d4', '#10b981', '#f59e0b'][d.group]);

    simulation.on('tick', () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);

      node.attr('cx', d => d.x).attr('cy', d => d.y);
    });
  }

  // SEARCH PAGE
  async function loadSearchCategories() {
    try {
      const res = await fetch(`${API_BASE}/categories`);
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
    const q = document.getElementById('search-input')?.value;
    const cat = document.getElementById('filter-category')?.value;
    if (!q) return;

    showLoading(true);
    try {
      let url = `${API_BASE}/search?q=${encodeURIComponent(q)}`;
      if (cat) url += `&cat=${encodeURIComponent(cat)}`;

      const res = await fetch(url);
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

  // MODEL METRICS PAGE
  async function loadModelMetrics() {
    try {
      const res = await fetch(`${API_BASE}/pipeline-stats`);
      const data = await res.json();

      renderMetricsTable('model-config-table', data.model_metrics?.model || {
        Algorithm: 'ALS Matrix Factorization', Rank: 50, MaxIter: 20, RegParam: 0.1
      });

      renderMetricsTable('data-stats-table', data.model_metrics?.data || {
        Users: '100,000', Products: '50,000', Interactions: '5,000,000'
      });

      renderMetricsTable('perf-metrics-table', data.model_metrics?.performance || {
        TrainingTime: '14.2s', RecommendationTime: '8.1s'
      });
    } catch (e) {
      console.error('Error loading model metrics:', e);
    }
  }

  function renderMetricsTable(elementId, dataObj) {
    const container = document.getElementById(elementId);
    if (!container) return;

    container.innerHTML = Object.entries(dataObj).map(([key, val]) => `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:0.85rem;">
        <span style="color:#9ca3af;">${key}</span>
        <span style="font-weight:600;">${val}</span>
      </div>
    `).join('');
  }
});
