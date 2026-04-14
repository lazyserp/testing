document.addEventListener('DOMContentLoaded', () => {
    if (!API.isAuthenticated()) {
        window.location.href = 'index.html';
        return;
    }

    const els = {
        bookDate: document.getElementById('bookDate'),
        btnCheck: document.getElementById('btnCheckAvailable'),
        loading: document.getElementById('loadingIndicator'),
        seatMap: document.getElementById('seatMap'),
        actionPanel: document.getElementById('bookingAction'),
        seatLabel: document.getElementById('selectedSeatLabel'),
        btnConfirm: document.getElementById('btnConfirmBook')
    };

    let availableSeats = [];
    let selectedSeatId = null;

    // Prefill date if passed in URL
    const urlParams = new URLSearchParams(window.location.search);
    const dParam = urlParams.get('d');
    if (dParam) {
        els.bookDate.value = dParam;
        checkAvailability();
    } else {
        els.bookDate.value = new Date().toISOString().split('T')[0];
    }

    els.btnCheck.addEventListener('click', checkAvailability);
    els.btnConfirm.addEventListener('click', confirmActivity);

    async function checkAvailability() {
        const dateStr = els.bookDate.value;
        if (!dateStr) return API.showToast("Please select a date.", "warning");

        els.loading.style.display = 'block';
        els.seatMap.style.display = 'none';
        els.actionPanel.style.display = 'none';
        selectedSeatId = null;

        try {
            availableSeats = await API.getAvailableSeats(dateStr);
            renderMap();
            els.seatMap.style.display = 'grid';
        } catch (e) {
            API.showToast(e.message, "error");
        } finally {
            els.loading.style.display = 'none';
        }
    }

    function renderMap() {
        els.seatMap.innerHTML = '';
        if (availableSeats.length === 0) {
            els.seatMap.innerHTML = '<div style="grid-column: 1/-1; text-align:center;">No seats available for this date.</div>';
            return;
        }

        // We could render all 50 seats and grey out unavailable ones, but the API currently 
        // only returns available ones. We will render just the available ones as interactive chips.
        availableSeats.forEach(seat => {
            const el = document.createElement('div');
            el.className = 'seat-node available';
            el.textContent = seat.seat_number;
            
            el.addEventListener('click', () => {
                document.querySelectorAll('.seat-node').forEach(n => n.classList.remove('selected'));
                el.classList.add('selected');
                selectedSeatId = seat.id;
                els.seatLabel.textContent = seat.seat_number;
                els.actionPanel.style.display = 'block';
            });
            
            els.seatMap.appendChild(el);
        });
    }

    async function confirmActivity() {
        if (!selectedSeatId) return;
        const dateStr = els.bookDate.value;

        els.btnConfirm.disabled = true;
        els.btnConfirm.textContent = 'Processing...';

        try {
            await API.bookFloaterSeat(selectedSeatId, dateStr);
            API.showToast("Seat booked successfully!", "success");
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1000);
        } catch (e) {
            API.showToast(e.message, "error");
            els.btnConfirm.disabled = false;
            els.btnConfirm.textContent = 'Confirm Booking';
        }
    }
});
