// dashboard.js — Logic for employee dashboard
document.addEventListener('DOMContentLoaded', async () => {
    if (!API.isAuthenticated()) {
        window.location.href = 'index.html';
        return;
    }

    let currentDateStr = ''; // Defaults to today on backend

    // DOM Elements
    const els = {
        userName: document.getElementById('userName'),
        userRole: document.getElementById('userRole'),
        userAvatar: document.getElementById('userAvatar'),
        cycleInfo: document.getElementById('cycleInfo'),
        email: document.getElementById('profileEmail'),
        squad: document.getElementById('profileSquad'),
        group: document.getElementById('profileGroup'),
        seat: document.getElementById('profileSeat'),
        weekContainer: document.getElementById('weekContainer'),
        btnNext: document.getElementById('nextWeek'),
        btnPrev: document.getElementById('prevWeek')
    };

    // Load initial data
    await loadProfile();
    await loadSchedule();

    // Event Listeners
    els.btnNext.addEventListener('click', () => navigateWeek(7));
    els.btnPrev.addEventListener('click', () => navigateWeek(-7));

    async function loadProfile() {
        try {
            const profile = await API.getProfile();
            els.userName.textContent = profile.name;
            els.userRole.textContent = profile.role;
            els.userAvatar.textContent = profile.name.charAt(0).toUpperCase();
            
            els.email.textContent = profile.email;
            els.squad.textContent = `Squad ID: ${profile.squad_id}`;
            els.group.textContent = `Group ID: ${profile.group_id}`;
            els.seat.textContent = profile.fixed_seat_id ? `Seat ID: ${profile.fixed_seat_id}` : 'Floater';
        } catch (err) {
            console.error("Failed to load profile:", err);
        }
    }

    async function loadSchedule() {
        try {
            els.weekContainer.innerHTML = '<div style="text-align:center; padding: 20px; grid-column: 1/-1;">Loading schedule...</div>';
            
            const schedule = await API.getWeekSchedule(currentDateStr);
            currentDateStr = schedule.week_start; // keeps track of the current week anchor
            
            els.cycleInfo.innerHTML = `Showing week of <strong>${schedule.week_start}</strong> (Cycle Week ${schedule.cycle_week})`;
            
            renderWeek(schedule.days);
        } catch (err) {
            console.error(err);
            API.showToast("Failed to load schedule", "error");
        }
    }

    function renderWeek(days) {
        els.weekContainer.innerHTML = '';
        
        days.forEach(day => {
            const el = document.createElement('div');
            el.className = 'glass-panel day-card';
            
            // Build status representation
            let statusHtml = '';
            let actionHtml = '';

            if (day.is_weekend) {
                statusHtml = `<div class="status-badge" style="background:var(--border);">Weekend</div>`;
            } else if (day.is_holiday) {
                statusHtml = `
                    <div class="status-badge badge-holiday">Holiday</div>
                    <div style="font-size:12px; margin-top:5px;">${day.holiday_name}</div>
                `;
            } else if (day.is_on_leave) {
                statusHtml = `<div class="status-badge badge-leave">On Leave</div>`;
                actionHtml = `<button class="btn-outline btn-danger" onclick="cancelLeave('${day.date}')">Cancel Leave</button>`;
            } else if (day.booked_floater_seat) {
                statusHtml = `
                    <div class="status-badge badge-office" style="background:var(--brand); color:#fff; border-color:var(--brand-hover);">Booked Seat</div>
                    <div class="seat-block mt-4">
                        <span style="font-size:11px; color:var(--text-secondary);">Floater Seat</span>
                        <strong class="text-brand">${day.booked_floater_seat.seat_number}</strong>
                    </div>
                `;
                actionHtml = `
                    <div class="actions" style="flex-direction:column; width:100%;">
                        <button class="btn-outline btn-danger" onclick="cancelBooking('${day.date}')">Cancel Booking</button>
                        <button class="btn-outline btn-danger" style="margin-top:5px;" onclick="markLeave('${day.date}')">Mark Leave</button>
                    </div>
                `;
            } else if (day.is_office_day) {
                if (day.fixed_seat) {
                    if (day.fixed_seat_released) {
                        statusHtml = `<div class="status-badge" style="background:#475569; color:#fff;">Released Seat</div>`;
                        // Action could be 'Cancel Release' if backend supports it; currently not implemented.
                    } else {
                        statusHtml = `
                            <div class="status-badge badge-office">Office Day</div>
                            <div class="seat-block mt-4">
                                <span style="font-size:11px; color:var(--text-secondary);">Fixed Seat</span>
                                <strong>${day.fixed_seat.seat_number}</strong>
                            </div>
                        `;
                        actionHtml = `
                            <div class="actions" style="flex-direction:column; width:100%;">
                                <button class="btn-outline" onclick="releaseSeat('${day.date}')">Release Seat</button>
                                <button class="btn-outline btn-danger" style="margin-top:5px;" onclick="markLeave('${day.date}')">Mark Leave</button>
                            </div>
                        `;
                    }
                } else {
                    // Requires Floater
                    statusHtml = `
                        <div class="status-badge badge-office">Office Day</div>
                        <div class="seat-block mt-4">
                            <span style="font-size:11px; color:var(--text-secondary);">Required</span>
                            <strong>Floater Seat</strong>
                        </div>
                    `;
                    // Assume book logic handles redirects or modals
                    actionHtml = `
                        <div class="actions" style="flex-direction:column; width:100%;">
                            <button class="btn-outline" onclick="window.location.href='book.html?d=${day.date}'">Book Floater</button>
                            <button class="btn-outline btn-danger" style="margin-top:5px;" onclick="markLeave('${day.date}')">Mark Leave</button>
                        </div>
                    `;
                }
            } else {
                statusHtml = `<div class="status-badge badge-remote">Remote Day</div>`;
                actionHtml = `
                    <div class="actions" style="flex-direction:column; width:100%;">
                        <button class="btn-outline" onclick="window.location.href='book.html?d=${day.date}'">Book Floater</button>
                        <button class="btn-outline btn-danger" style="margin-top:5px;" onclick="markLeave('${day.date}')">Mark Leave</button>
                    </div>
                `;
            }

            el.innerHTML = `
                <div class="day-header">
                    <div style="font-weight:600;">${day.weekday}</div>
                    <div class="day-date">${day.date}</div>
                </div>
                <div class="day-status">
                    ${statusHtml}
                </div>
                <div class="mt-4" style="text-align:center;">
                    ${actionHtml}
                </div>
            `;
            els.weekContainer.appendChild(el);
        });
    }

    function navigateWeek(daysOffset) {
        const d = new Date(currentDateStr);
        d.setDate(d.getDate() + daysOffset);
        currentDateStr = d.toISOString().split('T')[0];
        loadSchedule();
    }

    // Export actions to window for inline HTML onclick handlers
    window.releaseSeat = async (dateStr) => {
        if (!confirm(`Are you sure you want to release your seat for ${dateStr}? This action might be irreversible before 3 PM.`)) return;
        try {
            await API.releaseFixedSeat(dateStr);
            API.showToast("Seat released.", "success");
            loadSchedule();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    };

    window.markLeave = async (dateStr) => {
        const reason = prompt(`Reason for leave on ${dateStr}? (optional)`);
        if (reason === null) return; // cancelled
        try {
            await API.markLeave(dateStr, reason);
            API.showToast("Leave marked.", "success");
            loadSchedule();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    };

    window.cancelLeave = async (dateStr) => {
        // Need leave list to find leaveId
        try {
            const leaves = await API._fetch('/leaves');
            const leave = leaves.find(l => l.leave_date === dateStr);
            if (!leave) throw new Error("Leave record not found");
            
            await API._fetch(`/leaves/${leave.id}`, { method: 'DELETE' });
            API.showToast("Leave cancelled.", "success");
            loadSchedule();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    };

    window.cancelBooking = async (dateStr) => {
        if (!confirm(`Are you sure you want to cancel this booking before 3 PM?`)) return;
        try {
            const bookings = await API.getMyBookings();
            const booking = bookings.find(b => b.booking_date === dateStr && b.status === "CONFIRMED");
            if (!booking) throw new Error("Active booking not found.");
            
            await API.cancelBooking(booking.id);
            API.showToast("Booking cancelled.", "success");
            loadSchedule();
        } catch (e) {
            API.showToast(e.message, "error");
        }
    };
});
