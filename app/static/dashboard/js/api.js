/**
 * Centralized API Client for RazorRisk Dashboard.
 * Connects directly to FastAPI backend endpoints.
 * Never hardcodes secrets or credentials.
 */

const ApiClient = (() => {
  // Use window.location.origin as default when served by FastAPI
  const getBaseUrl = () => {
    if (typeof window !== 'undefined' && window.location && window.location.origin) {
      return window.location.origin;
    }
    return '';
  };

  /**
   * Helper request handler with robust JSON parsing and error wrapping.
   */
  async function request(endpoint, options = {}) {
    const url = `${getBaseUrl()}${endpoint}`;
    const defaultHeaders = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, config);
      let data = null;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
      }

      if (!response.ok) {
        const errorMessage = (data && data.detail) 
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
          : `HTTP ${response.status} (${response.statusText})`;
        const error = new Error(errorMessage);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      console.error(`[ApiClient Error] ${options.method || 'GET'} ${endpoint}:`, err.message);
      throw err;
    }
  }

  // Query parameter serializer
  function buildQuery(params = {}) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    }
    const qs = searchParams.toString();
    return qs ? `?${qs}` : '';
  }

  return {
    /** GET /health */
    getHealth: () => request('/health'),

    /** GET /api/v1/analytics/overview */
    getOverview: () => request('/api/v1/analytics/overview'),

    /** GET /api/v1/transactions */
    getTransactions: (params = {}) => request(`/api/v1/transactions${buildQuery(params)}`),

    /** GET /api/v1/transactions/{id} */
    getTransactionDetail: (id) => request(`/api/v1/transactions/${encodeURIComponent(id)}`),

    /** GET /api/v1/review/queue */
    getReviewQueue: (params = {}) => request(`/api/v1/review/queue${buildQuery(params)}`),

    /** GET /api/v1/review/evaluation-queue */
    getEvaluationQueue: () => request('/api/v1/review/evaluation-queue'),

    /** POST /api/v1/review/{id}/action */
    submitReviewAction: (id, payload) => request(`/api/v1/review/${encodeURIComponent(id)}/action`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

    /** GET /api/v1/model/metrics */
    getModelMetrics: () => request('/api/v1/model/metrics'),

    /** GET /api/v1/model/live-distribution */
    getLiveRiskDistribution: () => request('/api/v1/model/live-distribution'),

    /** GET /api/v1/model/offline-coverage */
    getOfflineRiskCoverage: () => request('/api/v1/model/offline-coverage'),

    /** POST /api/v1/risk/score */
    scoreTransaction: (payload) => request('/api/v1/risk/score', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),


    /** POST /api/v1/transactions/{id}/archive */
    archiveTransaction: (id, payload = {}) => request(`/api/v1/transactions/${encodeURIComponent(id)}/archive`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

    /** POST /api/v1/transactions/{id}/rereview */
    rereviewTransaction: (id, payload = {}) => request(`/api/v1/transactions/${encodeURIComponent(id)}/rereview`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

    /** GET /api/v1/audit/logs */
    getAuditLogs: (params = {}) => request(`/api/v1/audit/logs${buildQuery(params)}`),

    /** GET /api/v1/system/status */
    getSystemStatus: () => request('/api/v1/system/status'),
  };
})();


window.ApiClient = ApiClient;
