// RFBooking FastAPI OSS - Self-hosted Equipment Booking System
// Copyright (C) 2025 Oleg Tokmakov
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Dashboard JavaScript utilities
 */

// Date formatting utilities
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

function formatTime(timeStr) {
    if (!timeStr) return '';
    return timeStr.slice(0, 5);
}

// Today's date in YYYY-MM-DD format
function getTodayDate() {
    return new Date().toISOString().split('T')[0];
}

// Notification toast (fallback for non-dashboard pages)
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:14px 24px;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.12);z-index:1000;font-size:0.875rem;background:rgba(255,255,255,0.95);color:#1f2937;border:1px solid #e5e7eb;display:flex;align-items:center;gap:12px;max-width:480px;';
    const colors = { success: '#10b981', error: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
    const iconColor = colors[type] || colors.info;
    toast.innerHTML = `<div style="width:28px;height:28px;min-width:28px;border-radius:50%;background:${iconColor};display:flex;align-items:center;justify-content:center"><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="${type === 'success' ? 'M5 13l4 4L19 7' : 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'}"/></svg></div><span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 6000);
}

// Confirmation dialog
function showConfirm(message) {
    return new Promise((resolve) => {
        resolve(window.confirm(message));
    });
}

// Loading state helper
function setLoading(elementId, loading) {
    const element = document.getElementById(elementId);
    if (!element) return;

    if (loading) {
        element.classList.add('opacity-50', 'pointer-events-none');
    } else {
        element.classList.remove('opacity-50', 'pointer-events-none');
    }
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export to CSV
function exportToCSV(data, filename) {
    if (!data || !data.length) {
        showToast('No data to export', 'error');
        return;
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
        headers.join(','),
        ...data.map(row => headers.map(h => `"${row[h] || ''}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename || 'export.csv';
    link.click();
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to close modals
    if (e.key === 'Escape') {
        const modal = document.getElementById('booking-modal');
        if (modal && !modal.classList.contains('hidden')) {
            hideBookingModal();
        }
    }
});

console.log('RFBooking Dashboard loaded');
