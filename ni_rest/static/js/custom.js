document.addEventListener('DOMContentLoaded', function() {
    // Add confirmation for certain actions
    const confirmForms = document.querySelectorAll('form[data-confirm]');
    confirmForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.dataset.confirm || 'Are you sure you want to perform this action?';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Auto-refresh job status for running jobs
    const jobStatusBadges = document.querySelectorAll('.badge[data-auto-refresh="true"]');
    jobStatusBadges.forEach(badge => {
        const jobId = badge.dataset.jobId;
        const refreshUrl = `/api/jobs/${jobId}/status/`;
        
        function updateStatus() {
            fetch(refreshUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                let statusClass = '';
                
                if (data.status === 'completed') statusClass = 'bg-success';
                else if (data.status === 'failed') statusClass = 'bg-danger';
                else if (data.status === 'running') statusClass = 'bg-warning';
                else statusClass = 'bg-secondary';
                
                badge.textContent = data.status;
                badge.className = badge.className.replace(/bg-\w+/, statusClass);
                
                if (data.status === 'running' || data.status === 'queued') {
                    setTimeout(updateStatus, 5000);
                }
            })
            .catch(error => console.error('Error refreshing job status:', error));
        }
        
        setTimeout(updateStatus, 5000);
    });
});