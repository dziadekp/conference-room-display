/**
 * Conference Room Display - Frontend JavaScript
 */

class ConferenceRoomDisplay {
    constructor(roomId) {
        this.roomId = roomId;
        this.refreshInterval = 30000; // 30 seconds
        this.timeUpdateInterval = 1000; // 1 second
        this.data = null;

        this.init();
    }

    init() {
        this.updateTime();
        setInterval(() => this.updateTime(), this.timeUpdateInterval);

        this.fetchData();
        setInterval(() => this.fetchData(), this.refreshInterval);

        this.setupEventListeners();
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
            const response = await fetch(`/api/rooms/${this.roomId}/events`);
            if (!response.ok) throw new Error('Failed to fetch data');

            this.data = await response.json();
            this.render();
        } catch (error) {
            console.error('Error fetching room data:', error);
            this.showToast('Failed to update data', 'error');
        }
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

                currentMeeting.innerHTML = `
                    <h3>${this.escapeHtml(event.title)}</h3>
                    <div class="meeting-time">Until ${timeStr}</div>
                `;
            }
        }
    }

    renderQuickBook() {
        const section = document.getElementById('quickBookSection');

        if (this.data.is_available) {
            section.innerHTML = `
                <div class="section-title">Quick Book</div>
                <div class="quick-book-buttons">
                    <button class="book-btn primary" onclick="display.bookRoom(15)">
                        15 min
                        <span class="duration">Quick meeting</span>
                    </button>
                    <button class="book-btn primary" onclick="display.bookRoom(30)">
                        30 min
                        <span class="duration">Standard</span>
                    </button>
                    <button class="book-btn secondary" onclick="display.bookRoom(60)">
                        1 hour
                        <span class="duration">Extended</span>
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
                    <div class="no-events-text">No meetings scheduled today</div>
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

    async bookRoom(duration) {
        try {
            const response = await fetch(`/api/rooms/${this.roomId}/book?duration_minutes=${duration}&title=Quick Booking`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to book room');
            }

            this.showToast(`Room booked for ${duration} minutes`, 'success');
            await this.fetchData();
        } catch (error) {
            console.error('Error booking room:', error);
            this.showToast(error.message, 'error');
        }
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
