/**
 * Conference Room Display - Frontend JavaScript
 */

class ConferenceRoomDisplay {
    constructor(roomId) {
        this.roomId = roomId;
        this.refreshInterval = 30000; // 30 seconds
        this.timeUpdateInterval = 1000; // 1 second
        this.data = null;
        this.weekData = null;
        this.currentView = 'today';
        this.selectedDate = new Date();
        this.bookerName = localStorage.getItem('bookerName') || '';

        this.init();
    }

    init() {
        this.updateTime();
        setInterval(() => this.updateTime(), this.timeUpdateInterval);

        // Set initial date picker value
        this.updateDatePicker();

        this.fetchData();
        setInterval(() => this.fetchData(), this.refreshInterval);

        this.setupEventListeners();
    }

    updateDatePicker() {
        const datePicker = document.getElementById('datePicker');
        if (datePicker) {
            datePicker.value = this.formatDateForInput(this.selectedDate);
        }
        this.updateScheduleDate();
    }

    formatDateForInput(date) {
        return date.toISOString().split('T')[0];
    }

    updateScheduleDate() {
        const scheduleDate = document.getElementById('scheduleDate');
        if (scheduleDate) {
            scheduleDate.textContent = this.selectedDate.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric'
            });
        }
    }

    updateTime() {
        const timeEl = document.getElementById('currentTime');
        if (timeEl) {
            const now = new Date();
            timeEl.textContent = now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
        }
    }

    async fetchData() {
        try {
            const dateStr = this.formatDateForInput(this.selectedDate);

            if (this.currentView === 'today') {
                const response = await fetch(`/api/rooms/${this.roomId}/events?date=${dateStr}`);
                if (!response.ok) throw new Error('Failed to fetch data');
                this.data = await response.json();
                this.render();
            } else {
                const response = await fetch(`/api/rooms/${this.roomId}/week?start_date=${dateStr}`);
                if (!response.ok) throw new Error('Failed to fetch week data');
                this.weekData = await response.json();
                this.renderWeekView();
            }
        } catch (error) {
            console.error('Error fetching room data:', error);
            this.showToast('Failed to update data', 'error');
        }
    }

    switchView(view) {
        this.currentView = view;

        // Update buttons
        document.getElementById('todayViewBtn').classList.toggle('active', view === 'today');
        document.getElementById('weekViewBtn').classList.toggle('active', view === 'week');

        // Show/hide views
        document.getElementById('todayView').style.display = view === 'today' ? 'block' : 'none';
        document.getElementById('weekView').style.display = view === 'week' ? 'block' : 'none';

        this.fetchData();
    }

    navigateDate(delta) {
        if (this.currentView === 'week') {
            this.selectedDate.setDate(this.selectedDate.getDate() + (delta * 7));
        } else {
            this.selectedDate.setDate(this.selectedDate.getDate() + delta);
        }
        this.updateDatePicker();
        this.fetchData();
    }

    setDate(dateStr) {
        this.selectedDate = new Date(dateStr + 'T00:00:00');
        this.updateScheduleDate();
        this.fetchData();
    }

    goToToday() {
        this.selectedDate = new Date();
        this.updateDatePicker();
        this.fetchData();
    }

    render() {
        if (!this.data) return;

        this.renderStatus();
        this.renderQuickBook();
        this.renderSchedule();
    }

    renderStatus() {
        const header = document.getElementById('statusHeader');
        const statusText = document.getElementById('statusText');
        const currentMeeting = document.getElementById('currentMeeting');

        // Only show status for today
        const isToday = this.formatDateForInput(this.selectedDate) === this.formatDateForInput(new Date());

        if (!isToday) {
            header.className = 'status-header available';
            statusText.textContent = 'VIEWING: ' + this.selectedDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
            currentMeeting.style.display = 'none';
            return;
        }

        if (this.data.is_available) {
            header.className = 'status-header available';
            statusText.textContent = 'AVAILABLE';
            currentMeeting.style.display = 'none';

            // Show time until next meeting
            if (this.data.next_event) {
                const nextStart = new Date(this.data.next_event.start);
                const minutesUntil = Math.round((nextStart - new Date()) / 60000);
                if (minutesUntil > 0 && minutesUntil < 120) {
                    statusText.textContent = `AVAILABLE for ${minutesUntil} min`;
                }
            }
        } else {
            header.className = 'status-header occupied';
            statusText.textContent = 'OCCUPIED';

            if (this.data.current_event) {
                currentMeeting.style.display = 'block';
                const event = this.data.current_event;
                const endTime = new Date(event.end);
                const timeStr = endTime.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });

                let organizer = event.organizer ? `<div class="meeting-organizer">${this.escapeHtml(event.organizer)}</div>` : '';

                currentMeeting.innerHTML = `
                    <h3>${this.escapeHtml(event.title)}</h3>
                    ${organizer}
                    <div class="meeting-time">Until ${timeStr}</div>
                `;
            }
        }
    }

    renderQuickBook() {
        const section = document.getElementById('quickBookSection');
        const isToday = this.formatDateForInput(this.selectedDate) === this.formatDateForInput(new Date());

        if (!isToday) {
            // Show schedule booking button for other dates
            section.innerHTML = `
                <div class="section-title">Schedule a Meeting</div>
                <div class="quick-book-buttons">
                    <button class="book-btn primary" onclick="display.openBookingModal()">
                        Schedule Meeting
                        <span class="duration">for ${this.selectedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                    </button>
                </div>
            `;
            return;
        }

        if (this.data.is_available) {
            section.innerHTML = `
                <div class="section-title">Quick Book</div>
                <div class="quick-book-buttons">
                    <button class="book-btn primary" onclick="display.quickBook(15)">
                        15 min
                        <span class="duration">Quick</span>
                    </button>
                    <button class="book-btn primary" onclick="display.quickBook(30)">
                        30 min
                        <span class="duration">Standard</span>
                    </button>
                    <button class="book-btn secondary" onclick="display.quickBook(60)">
                        1 hour
                        <span class="duration">Extended</span>
                    </button>
                    <button class="book-btn fullday" onclick="display.bookFullDay()">
                        Full Day
                        <span class="duration">Until 6 PM</span>
                    </button>
                </div>
                <div class="schedule-later">
                    <button class="book-btn outline" onclick="display.openBookingModal()">
                        Schedule for Later
                    </button>
                </div>
            `;
        } else {
            section.innerHTML = `
                <div class="section-title">Meeting Actions</div>
                <div class="meeting-actions">
                    <button class="action-btn" onclick="display.extendMeeting(15)">
                        +15 min
                    </button>
                    <button class="action-btn" onclick="display.extendMeeting(30)">
                        +30 min
                    </button>
                    <button class="action-btn end-meeting" onclick="display.endMeeting()">
                        End Now
                    </button>
                </div>
            `;
        }
    }

    renderSchedule() {
        const list = document.getElementById('scheduleList');
        const events = this.data.events || [];

        if (events.length === 0) {
            list.innerHTML = `
                <div class="no-events">
                    <div class="no-events-icon">📅</div>
                    <div class="no-events-text">No meetings scheduled</div>
                </div>
            `;
            return;
        }

        const now = new Date();
        let html = '';

        events.forEach(event => {
            const start = new Date(event.start);
            const end = new Date(event.end);
            const isCurrent = start <= now && end > now;
            const isUpcoming = start > now && (start - now) < 3600000; // Within 1 hour

            const startStr = start.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });

            const endStr = end.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });

            let statusClass = '';
            if (isCurrent) statusClass = 'current';
            else if (isUpcoming) statusClass = 'upcoming';

            html += `
                <div class="event-card ${statusClass}">
                    <div class="event-time-bar"></div>
                    <div class="event-content">
                        <div class="event-info">
                            <div class="event-title">${this.escapeHtml(event.title)}</div>
                            ${event.organizer ? `<div class="event-organizer">${this.escapeHtml(event.organizer)}</div>` : ''}
                        </div>
                        <div class="event-time">
                            ${startStr}<br>
                            <span style="opacity: 0.6">to</span><br>
                            ${endStr}
                        </div>
                    </div>
                </div>
            `;
        });

        list.innerHTML = html;
    }

    renderWeekView() {
        if (!this.weekData) return;

        const grid = document.getElementById('weekGrid');
        const weekEvents = this.weekData.week_events || {};

        let html = '<div class="week-days">';

        // Create a sorted array of dates
        const dates = Object.keys(weekEvents).sort();

        dates.forEach(dateStr => {
            const date = new Date(dateStr + 'T00:00:00');
            const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
            const dayNum = date.getDate();
            const isToday = this.formatDateForInput(date) === this.formatDateForInput(new Date());
            const events = weekEvents[dateStr] || [];

            html += `
                <div class="week-day ${isToday ? 'today' : ''}" onclick="display.setDate('${dateStr}'); display.switchView('today');">
                    <div class="day-header">
                        <span class="day-name">${dayName}</span>
                        <span class="day-num">${dayNum}</span>
                    </div>
                    <div class="day-events">
            `;

            if (events.length === 0) {
                html += `<div class="no-day-events">No meetings</div>`;
            } else {
                events.slice(0, 4).forEach(event => {
                    const start = new Date(event.start);
                    const timeStr = start.toLocaleTimeString('en-US', {
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    });
                    html += `
                        <div class="week-event">
                            <span class="week-event-time">${timeStr}</span>
                            <span class="week-event-title">${this.escapeHtml(event.title)}</span>
                        </div>
                    `;
                });
                if (events.length > 4) {
                    html += `<div class="more-events">+${events.length - 4} more</div>`;
                }
            }

            html += `
                    </div>
                </div>
            `;
        });

        html += '</div>';
        grid.innerHTML = html;
    }

    openBookingModal() {
        const modal = document.getElementById('bookingModal');
        const dateInput = document.getElementById('bookingDate');
        const timeInput = document.getElementById('bookingTime');
        const nameInput = document.getElementById('bookerName');

        // Set default values
        dateInput.value = this.formatDateForInput(this.selectedDate);

        // Set default time to next 30-minute interval
        const now = new Date();
        const minutes = now.getMinutes();
        const nextSlot = Math.ceil(minutes / 30) * 30;
        now.setMinutes(nextSlot, 0, 0);
        timeInput.value = now.toTimeString().slice(0, 5);

        // Pre-fill booker name if saved
        nameInput.value = this.bookerName;

        modal.style.display = 'flex';
    }

    closeModal() {
        document.getElementById('bookingModal').style.display = 'none';
    }

    async submitBooking() {
        const name = document.getElementById('bookerName').value.trim();
        const title = document.getElementById('bookingTitle').value.trim() || 'Quick Booking';
        const date = document.getElementById('bookingDate').value;
        const time = document.getElementById('bookingTime').value;
        const duration = parseInt(document.getElementById('bookingDuration').value);

        if (!name) {
            this.showToast('Please enter your name', 'error');
            return;
        }

        // Save booker name for future use
        this.bookerName = name;
        localStorage.setItem('bookerName', name);

        const [hour, minute] = time.split(':').map(Number);

        try {
            const params = new URLSearchParams({
                duration_minutes: duration,
                title: title,
                date: date,
                start_hour: hour,
                start_minute: minute,
                booker_name: name
            });

            const response = await fetch(`/api/rooms/${this.roomId}/book?${params}`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to book room');
            }

            this.showToast(`Room booked for ${duration} minutes by ${name}`, 'success');
            this.closeModal();
            await this.fetchData();
        } catch (error) {
            console.error('Error booking room:', error);
            this.showToast(error.message, 'error');
        }
    }

    async quickBook(duration) {
        // Open modal for name input if no saved name
        if (!this.bookerName) {
            this.openBookingModal();
            document.getElementById('bookingDuration').value = duration;
            // Set time to now
            const now = new Date();
            document.getElementById('bookingTime').value = now.toTimeString().slice(0, 5);
            document.getElementById('bookingDate').value = this.formatDateForInput(new Date());
            return;
        }

        await this.bookRoom(duration, 'Quick Booking', this.bookerName);
    }

    async bookRoom(duration, title = 'Quick Booking', bookerName = '') {
        try {
            const params = new URLSearchParams({
                duration_minutes: duration,
                title: title
            });

            if (bookerName) {
                params.append('booker_name', bookerName);
            }

            const response = await fetch(`/api/rooms/${this.roomId}/book?${params}`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to book room');
            }

            const nameInfo = bookerName ? ` by ${bookerName}` : '';
            this.showToast(`Room booked for ${duration} minutes${nameInfo}`, 'success');
            await this.fetchData();
        } catch (error) {
            console.error('Error booking room:', error);
            this.showToast(error.message, 'error');
        }
    }

    async bookFullDay() {
        // Open modal for name input if no saved name
        if (!this.bookerName) {
            this.openBookingModal();
            // Calculate duration until 6 PM
            const now = new Date();
            const endOfDay = new Date(now);
            endOfDay.setHours(18, 0, 0, 0);
            if (now >= endOfDay) {
                endOfDay.setHours(23, 59, 0, 0);
            }
            const durationMinutes = Math.round((endOfDay - now) / 60000);
            document.getElementById('bookingDuration').value = durationMinutes > 180 ? 240 : 180;
            document.getElementById('bookingTime').value = now.toTimeString().slice(0, 5);
            document.getElementById('bookingDate').value = this.formatDateForInput(new Date());
            return;
        }

        // Calculate minutes until 6 PM (18:00)
        const now = new Date();
        const endOfDay = new Date(now);
        endOfDay.setHours(18, 0, 0, 0);

        // If it's already past 6 PM, book until midnight
        if (now >= endOfDay) {
            endOfDay.setHours(23, 59, 0, 0);
        }

        const durationMinutes = Math.round((endOfDay - now) / 60000);

        if (durationMinutes < 15) {
            this.showToast('Not enough time left today', 'error');
            return;
        }

        await this.bookRoom(durationMinutes, 'Full Day Booking', this.bookerName);
    }

    async extendMeeting(minutes) {
        try {
            const response = await fetch(`/api/rooms/${this.roomId}/extend?minutes=${minutes}`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to extend meeting');
            }

            this.showToast(`Meeting extended by ${minutes} minutes`, 'success');
            await this.fetchData();
        } catch (error) {
            console.error('Error extending meeting:', error);
            this.showToast(error.message, 'error');
        }
    }

    async endMeeting() {
        if (!confirm('End the current meeting?')) return;

        try {
            const response = await fetch(`/api/rooms/${this.roomId}/end`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to end meeting');
            }

            this.showToast('Meeting ended', 'success');
            await this.fetchData();
        } catch (error) {
            console.error('Error ending meeting:', error);
            this.showToast(error.message, 'error');
        }
    }

    showToast(message, type = 'info') {
        // Remove existing toast
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        // Show toast
        setTimeout(() => toast.classList.add('show'), 10);

        // Hide after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    setupEventListeners() {
        // Prevent screen from sleeping (request wake lock if available)
        if ('wakeLock' in navigator) {
            navigator.wakeLock.request('screen').catch(err => {
                console.log('Wake Lock not available:', err);
            });
        }

        // Refresh on visibility change (when tablet wakes up)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.fetchData();
            }
        });

        // Close modal on outside click
        document.getElementById('bookingModal').addEventListener('click', (e) => {
            if (e.target.id === 'bookingModal') {
                this.closeModal();
            }
        });
    }
}

// Setup page functions
async function addRoom() {
    const name = document.getElementById('roomName').value.trim();
    const provider = document.getElementById('calendarProvider').value;
    const calendarId = document.getElementById('calendarId').value.trim();

    if (!name) {
        alert('Please enter a room name');
        return;
    }

    try {
        const params = new URLSearchParams({
            name: name,
            calendar_provider: provider || '',
            calendar_id: calendarId || ''
        });

        const response = await fetch(`/api/rooms?${params}`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to create room');

        window.location.reload();
    } catch (error) {
        alert('Failed to create room: ' + error.message);
    }
}

async function deleteRoom(roomId) {
    if (!confirm('Delete this room configuration?')) return;

    try {
        const response = await fetch(`/api/rooms/${roomId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete room');

        window.location.reload();
    } catch (error) {
        alert('Failed to delete room: ' + error.message);
    }
}

// Global display instance (set on display page)
let display = null;
