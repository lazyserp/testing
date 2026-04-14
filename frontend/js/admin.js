document.addEventListener('DOMContentLoaded', async () => {
    if (!API.isAuthenticated()) {
        window.location.href = 'index.html';
        return;
    }

    try {
        const profile = await API.getProfile();
        if (profile.role !== 'ADMIN') {
            API.showToast("Unauthorized. Admin access required.", "error");
            window.location.href = 'dashboard.html';
            return;
        }
    } catch (e) {
        window.location.href = 'index.html';
        return;
    }

    // Tabs logic
    const navBtns = document.querySelectorAll('.nav-btn');
    const sections = document.querySelectorAll('.panel-section');

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            navBtns.forEach(b => b.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
            
            // Lazy load tab data
            if (btn.dataset.target === 'tabHolidays') loadHolidays();
            if (btn.dataset.target === 'tabEmployees') loadEmployees();
            if (btn.dataset.target === 'tabAudit') loadAuditLogs();
        });
    });

    // Default Date for Allocations
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('allocDate').value = today;

    // Daily Allocations
    document.getElementById('btnLoadAlloc').addEventListener('click', async () => {
        const dateStr = document.getElementById('allocDate').value;
        if(!dateStr) return;
        
        try {
            const alloc = await API.getDailyAllocation(dateStr);
            document.getElementById('allocContent').style.display = 'block';
            
            document.getElementById('allocBatch').textContent = alloc.batch_in_office || 'N/A';
            document.getElementById('allocHoliday').textContent = alloc.is_holiday ? alloc.holiday_name : 'No';
            document.getElementById('allocTotal').textContent = alloc.total_employees_in_office;
            
            document.getElementById('allocBooked').textContent = alloc.floater_bookings.length;
            document.getElementById('allocReleased').textContent = alloc.released_seats.length;
            document.getElementById('allocFree').textContent = alloc.available_floaters.length;

        } catch (e) {
            API.showToast(e.message, "error");
        }
    });

    // Holidays
    async function loadHolidays() {
        try {
            const holidays = await API._fetch('/admin/holidays');
            const tbody = document.getElementById('tblHolidays');
            tbody.innerHTML = '';
            holidays.forEach(hol => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${hol.holiday_date}</td>
                    <td>${hol.name}</td>
                    <td><button class="btn-outline btn-danger btn-sm" style="padding: 4px 8px; font-size: 11px;" onclick="deleteHoliday(${hol.id})">Delete</button></td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            API.showToast(e.message, "error");
        }
    }

    document.getElementById('frmHoliday').addEventListener('submit', async (e) => {
        e.preventDefault();
        const dateStr = document.getElementById('holDate').value;
        const name = document.getElementById('holName').value;
        try {
            await API._fetch('/admin/holidays', {
                method: 'POST',
                body: { holiday_date: dateStr, name }
            });
            API.showToast("Holiday added", "success");
            loadHolidays();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    });

    window.deleteHoliday = async (id) => {
        if(!confirm("Delete this holiday?")) return;
        try {
            await API._fetch(`/admin/holidays/${id}`, { method: 'DELETE' });
            API.showToast("Holiday removed", "info");
            loadHolidays();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    };

    // Employees
    async function loadEmployees() {
        try {
            const emps = await API._fetch('/admin/employees');
            const tbody = document.getElementById('tblEmployees');
            tbody.innerHTML = '';
            
            // Just show first 20 for brevity or all. We'll show all.
            emps.forEach(emp => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${emp.name} <br><small style="color:var(--text-secondary)">${emp.email}</small></td>
                    <td>${emp.group_name || '-'}</td>
                    <td>${emp.squad_name || '-'}</td>
                    <td class="text-brand">${emp.fixed_seat_number || 'Floater'}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            API.showToast(e.message, "error");
        }
    }

    // Audit Logs
    async function loadAuditLogs() {
        try {
            const logs = await API._fetch('/admin/audit-logs');
            const tbody = document.getElementById('tblAudit');
            tbody.innerHTML = '';
            
            logs.forEach(log => {
                const tr = document.createElement('tr');
                const time = new Date(log.timestamp).toLocaleString();
                tr.innerHTML = `
                    <td style="font-size: 12px; color: var(--text-secondary)">${time}</td>
                    <td>${log.employee_id || 'System'}</td>
                    <td><span style="background: rgba(255,255,255,0.1); padding: 3px 6px; border-radius: 4px; font-size: 11px;">${log.action}</span></td>
                    <td style="font-size: 12px;">${log.details}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            API.showToast(e.message, "error");
        }
    }
});
