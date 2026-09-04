/**
 * Client-Side Hash Router for RazorRisk Dashboard.
 * Supports smooth, zero-reload transitions between views, browser history,
 * and active sidebar tracking.
 */

const Router = (() => {
  const routes = {
    'overview': { view: window.OverviewView, title: 'Risk Overview' },
    'transactions': { view: window.TransactionsView, title: 'Transactions Monitoring' },
    'review-queue': { view: window.ReviewQueueView, title: 'Manual Review Queue' },
    'model-performance': { view: window.ModelPerformanceView, title: 'Model Performance' },
    'audit-log': { view: window.AuditLogView, title: 'Audit Log' },
    'system-status': { view: window.SystemStatusView, title: 'System Status' }
  };

  let currentRoute = null;

  function parseHash() {
    const hash = window.location.hash.slice(1).trim() || 'overview';
    const parts = hash.split('/');
    const routeName = parts[0] || 'overview';
    const param = parts[1] ? decodeURIComponent(parts[1]) : null;
    return { routeName, param };
  }

  async function handleRouting() {
    const { routeName, param } = parseHash();
    const mainContent = document.getElementById('main-content');
    if (!mainContent) return;

    // Handle transaction detail sub-route: #transactions/:id
    if (routeName === 'transactions' && param) {
      updateNavHighlight('transactions');
      document.title = `RazorRisk - Transaction ${param}`;
      currentRoute = `transactions/${param}`;
      await window.TransactionDetailView.render(mainContent, param);
      window.scrollTo(0, 0);
      return;
    }

    const route = routes[routeName];
    if (route) {
      updateNavHighlight(routeName);
      document.title = `RazorRisk - ${route.title}`;
      currentRoute = routeName;
      await route.view.render(mainContent);
    } else {
      // 404 fallback
      updateNavHighlight('');
      document.title = 'RazorRisk - Page Not Found';
      mainContent.innerHTML = `
        <div class="p-12 text-center space-y-4">
          <span class="material-symbols-outlined text-5xl text-outline-variant">travel_explore</span>
          <h2 class="text-xl font-bold text-on-surface">View Not Found</h2>
          <p class="text-sm text-on-surface-variant">The requested view '#${routeName}' does not exist.</p>
          <a href="#overview" class="inline-block px-4 py-2 bg-primary text-on-primary rounded text-xs font-semibold hover:bg-primary-container">
            Back to Overview
          </a>
        </div>
      `;
    }
    window.scrollTo(0, 0);
  }

  function updateNavHighlight(activeName) {
    document.querySelectorAll('[data-nav-route]').forEach(link => {
      const target = link.dataset.navRoute;
      if (target === activeName) {
        link.classList.add('bg-primary-fixed', 'text-primary', 'font-bold', 'border-r-2', 'border-primary');
        link.classList.remove('text-on-surface-variant', 'hover:bg-surface-variant');
      } else {
        link.classList.remove('bg-primary-fixed', 'text-primary', 'font-bold', 'border-r-2', 'border-primary');
        link.classList.add('text-on-surface-variant', 'hover:bg-surface-variant');
      }
    });
  }

  function init() {
    window.addEventListener('hashchange', handleRouting);
    // Initial route handling
    handleRouting();
  }

  return {
    init,
    navigate: (hash) => {
      window.location.hash = hash;
    }
  };
})();

window.Router = Router;
