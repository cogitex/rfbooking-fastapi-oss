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

// Notification toast
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white z-50 ${
        type === 'success' ? 'bg-green-600' :
        type === 'error' ? 'bg-red-600' :
        'bg-blue-600'
    }`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('opacity-0', 'transition-opacity');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
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
