/**
 * Main Application Orchestrator for RazorRisk Dashboard.
 * Manages global confirmation modals, toast alerts, mobile navigation, and app lifecycle.
 */

const App = (() => {
  let pendingActionTxnId = null;
  let pendingActionType = null;

  function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const isSuccess = type === 'success';
    const bgColor = isSuccess ? 'bg-secondary text-on-secondary' : 'bg-error text-on-error';
    const icon = isSuccess ? 'check_circle' : 'error';

    toast.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-xs font-semibold ${bgColor} toast-animate`;
    toast.innerHTML = `
      <span class="material-symbols-outlined text-[18px]">${icon}</span>
      <span>${message}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function openReviewModal(transactionId, action) {
    pendingActionTxnId = transactionId;
    pendingActionType = action;

    const modal = document.getElementById('review-action-modal');
    const modalTitle = document.getElementById('modal-action-title');
    const modalTxnId = document.getElementById('modal-txn-id');
    const modalBtn = document.getElementById('modal-confirm-btn');
    const reasonInput = document.getElementById('modal-reason-input');
    const notesInput = document.getElementById('modal-notes-input');

    if (!modal) return;

    if (reasonInput) reasonInput.value = '';
    if (notesInput) notesInput.value = '';

    const isApprove = action === 'APPROVE';
    if (modalTitle) modalTitle.textContent = isApprove ? 'Confirm Transaction Approval' : 'Confirm Transaction Block';
    if (modalTxnId) modalTxnId.textContent = transactionId;

    if (modalBtn) {
      modalBtn.textContent = isApprove ? 'Confirm Approval' : 'Confirm Block';
      modalBtn.className = isApprove 
        ? 'px-4 py-2 bg-secondary text-on-secondary rounded text-xs font-semibold hover:bg-opacity-90 transition-all'
        : 'px-4 py-2 bg-error text-on-error rounded text-xs font-semibold hover:bg-opacity-90 transition-all';
    }

    modal.classList.remove('hidden');
  }

  function closeReviewModal() {
    const modal = document.getElementById('review-action-modal');
    if (modal) modal.classList.add('hidden');
    pendingActionTxnId = null;
    pendingActionType = null;
  }

  async function executeReviewAction() {
    if (!pendingActionTxnId || !pendingActionType) return;

    const reason = document.getElementById('modal-reason-input')?.value?.trim() || 'MANUAL_REVIEW';
    const notes = document.getElementById('modal-notes-input')?.value?.trim() || null;
    const confirmBtn = document.getElementById('modal-confirm-btn');

    try {
      if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">progress_activity</span> Processing...';
      }

      const res = await window.ApiClient.submitReviewAction(pendingActionTxnId, {
        action: pendingActionType,
        reason: reason,
        notes: notes
      });

      showToast(`Transaction ${pendingActionTxnId} successfully marked as ${pendingActionType}.`, 'success');
      closeReviewModal();

      // Refresh current active view
      const hash = window.location.hash;
      if (hash.includes('review-queue')) {
        window.ReviewQueueView.loadQueue();
      } else if (hash.includes('transactions/')) {
        window.TransactionDetailView.loadDetail(pendingActionTxnId);
      } else if (hash.includes('transactions')) {
        window.TransactionsView.loadTransactions();
      }

    } catch (err) {
      showToast(err.message || 'Failed to submit review decision.', 'error');
    } finally {
      if (confirmBtn) confirmBtn.disabled = false;
    }
  }

  function setupGlobalListeners() {
    // Review modal action button
    document.getElementById('modal-confirm-btn')?.addEventListener('click', executeReviewAction);
    document.getElementById('modal-cancel-btn')?.addEventListener('click', closeReviewModal);

    // Mobile sidebar toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    if (mobileMenuBtn && sidebar) {
      mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.toggle('hidden');
      });
    }

    // Header global search
    const headerSearch = document.getElementById('header-search-input');
    if (headerSearch) {
      headerSearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const query = e.target.value.trim();
          if (query) {
            window.TransactionsView.currentSearch = query;
            window.location.hash = '#transactions';
          }
        }
      });
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function init() {
    setupGlobalListeners();
    window.Router.init();
  }

  return {
    init,
    openReviewModal,
    closeReviewModal,
    showToast,
    escapeHtml
  };
})();

window.App = App;
window.escapeHtml = App.escapeHtml;

document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
