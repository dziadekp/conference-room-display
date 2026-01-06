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
        this.monthData = null;
        this.currentView = 'today';
        this.selectedDate = new Date();
        this.selectedYear = this.selectedDate.getFullYear();
        this.selectedMonth = this.selectedDate.getMonth() + 1; // 1-based
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
            } else if (this.currentView === 'week') {
                const response = await fetch(`/api/rooms/${this.roomId}/week?start_date=${dateStr}`);
                if (!response.ok) throw new Error('Failed to fetch week data');
                this.weekData = await response.json();
                this.renderWeekView();
            } else if (this.currentView === 'month') {
                const response = await fetch(`/api/rooms/${this.roomId}/month?year=${this.selectedYear}&month=${this.selectedMonth}`);
                if (!response.ok) throw new Error('Failed to fetch month data');
                this.monthData = await response.json();
                this.renderMonthView();
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
        document.getElementById('monthViewBtn').classList.toggle('active', view === 'month');

        // Show/hide views
        document.getElementById('todayView').style.display = view === 'today' ? 'flex' : 'none';
        document.getElementById('weekView').style.display = view === 'week' ? 'flex' : 'none';
        document.getElementById('monthView').style.display = view === 'month' ? 'flex' : 'none';

        // Sync month/year from selected date when switching to month view
        if (view === 'month') {
            this.selectedYear = this.selectedDate.getFullYear();
            this.selectedMonth = this.selectedDate.getMonth() + 1;
        }

        this.fetchData();
    }

    navigateDate(delta) {
        if (this.currentView === 'month') {
            // Navigate by months
            this.selectedMonth += delta;
            if (this.selectedMonth > 12) {
                this.selectedMonth = 1;
                this.selectedYear++;
            } else if (this.selectedMonth < 1) {
                this.selectedMonth = 12;
                this.selectedYear--;
            }
            // Update selectedDate to match
            this.selectedDate = new Date(this.selectedYear, this.selectedMonth - 1, 1);
        } else if (this.currentView === 'week') {
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
        this.selectedYear = this.selectedDate.getFullYear();
        this.selectedMonth = this.selectedDate.getMonth() + 1;
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
        const hasActiveMeeting = isToday && !this.data.is_available;

        let html = '';

        // Always show meeting actions if there's an active meeting right now
        if (hasActiveMeeting) {
            html += `
                <div class="section-title">Current Meeting Actions</div>
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

        // Always show quick book options - all buttons in one compact row
        html += `
            <div class="quick-book-buttons">
                <button class="book-btn primary" onclick="display.quickBook(15)">15m</button>
                <button class="book-btn primary" onclick="display.quickBook(30)">30m</button>
                <button class="book-btn secondary" onclick="display.quickBook(60)">1hr</button>
                <button class="book-btn fullday" onclick="display.bookFullDay()">All Day</button>
                <button class="book-btn outline" onclick="display.openBookingModal()">Custom</button>
            </div>
        `;

        section.innerHTML = html;
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

            // Calculate duration
            const durationMs = end - start;
            const durationHours = Math.floor(durationMs / 3600000);
            const durationMins = Math.floor((durationMs % 3600000) / 60000);
            let durationStr = '';
            if (durationHours > 0) {
                durationStr = `${durationHours}h`;
                if (durationMins > 0) durationStr += ` ${durationMins}m`;
            } else {
                durationStr = `${durationMins}m`;
            }

            let statusClass = '';
            if (isCurrent) statusClass = 'current';
            else if (isUpcoming) statusClass = 'upcoming';

            // Build organizer/booker info
            let bookerInfo = '';
            if (event.organizer) {
                bookerInfo = `<div class="event-organizer">👤 ${this.escapeHtml(event.organizer)}</div>`;
            }

            // Build description if available
            let descriptionHtml = '';
            if (event.description && event.description.trim()) {
                descriptionHtml = `<div class="event-description">${this.escapeHtml(event.description)}</div>`;
            }

            html += `
                <div class="event-card ${statusClass}">
                    <div class="event-time-bar"></div>
                    <div class="event-content">
                        <div class="event-info">
                            <div class="event-title">${this.escapeHtml(event.title)}</div>
                            ${bookerInfo}
                            ${descriptionHtml}
                        </div>
                        <div class="event-actions">
                            <div class="event-time">
                                <div class="time-range">
                                    <span class="time-label">Start</span>
                                    <span class="time-start">${startStr}</span>
                                </div>
                                <div class="time-range" style="margin-top: 8px;">
                                    <span class="time-label">End</span>
                                    <span class="time-end">${endStr}</span>
                                </div>
                                <div style="margin-top: 8px; font-size: 0.8rem; opacity: 0.7;">${durationStr}</div>
                            </div>
                            <button class="cancel-btn" onclick="event.stopPropagation(); display.cancelBooking('${event.id}', '${this.escapeHtml(event.title).replace(/'/g, "\\'")}');" title="Cancel booking">
                                &times;
                            </button>
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

        // Create a sorted array of dates - ensure we have 7 days
        const dates = Object.keys(weekEvents).sort();

        // Build HTML directly into the grid (no wrapper div needed - #weekGrid already has .week-grid class)
        let html = '';

        dates.forEach(dateStr => {
            const date = new Date(dateStr + 'T00:00:00');
            const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
            const dayNum = date.getDate();
            const monthName = date.toLocaleDateString('en-US', { month: 'short' });
            const isToday = this.formatDateForInput(date) === this.formatDateForInput(new Date());
            const events = weekEvents[dateStr] || [];

            html += `
                <div class="week-day ${isToday ? 'today' : ''}" onclick="display.setDate('${dateStr}'); display.switchView('today');">
                    <div class="day-header">
                        <span class="day-name">${dayName}</span>
                        <span class="day-num">${dayNum}</span>
                        <span class="day-month">${monthName}</span>
                    </div>
                    <div class="day-events">
            `;

            if (events.length === 0) {
                html += `<div class="no-day-events">No meetings</div>`;
            } else {
                events.slice(0, 5).forEach(event => {
                    const start = new Date(event.start);
                    const end = new Date(event.end);
                    const startStr = start.toLocaleTimeString('en-US', {
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    });
                    const endStr = end.toLocaleTimeString('en-US', {
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    });

                    // Build organizer info
                    let organizerHtml = '';
                    if (event.organizer) {
                        organizerHtml = `<div class="week-event-organizer">👤 ${this.escapeHtml(event.organizer)}</div>`;
                    }

                    // Build description if available
                    let descHtml = '';
                    if (event.description && event.description.trim()) {
                        const shortDesc = event.description.length > 50
                            ? event.description.substring(0, 50) + '...'
                            : event.description;
                        descHtml = `<div class="week-event-desc">${this.escapeHtml(shortDesc)}</div>`;
                    }

                    html += `
                        <div class="week-event">
                            <div class="week-event-title">${this.escapeHtml(event.title)}</div>
                            ${organizerHtml}
                            <div class="week-event-time">${startStr} - ${endStr}</div>
                            ${descHtml}
                        </div>
                    `;
                });
                if (events.length > 5) {
                    html += `<div class="more-events">+${events.length - 5} more</div>`;
                }
            }

            html += `
                    </div>
                </div>
            `;
        });

        grid.innerHTML = html;
    }

    renderMonthView() {
        if (!this.monthData) return;

        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December'];
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

        // Update month header
        const monthHeader = document.getElementById('monthHeader');
        monthHeader.textContent = `${monthNames[this.selectedMonth - 1]} ${this.selectedYear}`;

        const grid = document.getElementById('monthGrid');
        const monthEvents = this.monthData.month_events || {};

        // Get sorted dates
        const dates = Object.keys(monthEvents).sort();
        if (dates.length === 0) {
            grid.innerHTML = '<div class="no-events">No data available</div>';
            return;
        }

        // Build calendar grid
        let html = '';

        // Add day name headers
        html += '<div class="month-day-headers">';
        dayNames.forEach(day => {
            html += `<div class="month-day-header">${day}</div>`;
        });
        html += '</div>';

        // Add calendar days
        html += '<div class="month-days">';

        const today = this.formatDateForInput(new Date());

        dates.forEach(dateStr => {
            const date = new Date(dateStr + 'T00:00:00');
            const dayNum = date.getDate();
            const isToday = dateStr === today;
            const isCurrentMonth = (date.getMonth() + 1) === this.selectedMonth;
            const events = monthEvents[dateStr] || [];

            let dayClass = 'month-day';
            if (isToday) dayClass += ' today';
            if (!isCurrentMonth) dayClass += ' other-month';
            if (events.length > 0) dayClass += ' has-events';

            html += `
                <div class="${dayClass}" onclick="display.setDate('${dateStr}'); display.switchView('today');">
                    <div class="month-day-num">${dayNum}</div>
                    <div class="month-day-events">
            `;

            // Show up to 3 events
            events.slice(0, 3).forEach(event => {
                const start = new Date(event.start);
                const end = new Date(event.end);

                // Calculate duration in hours
                const durationHours = (end - start) / (1000 * 60 * 60);
                const isFullDay = durationHours >= 8; // 8+ hours = full day

                const startStr = start.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                });
                const endStr = end.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                });

                const eventClass = isFullDay ? 'month-event fullday' : 'month-event';
                const timeDisplay = isFullDay ? 'Full Day' : `${startStr} - ${endStr}`;

                // Build organizer info for month view
                let organizerHtml = '';
                if (event.organizer) {
                    organizerHtml = `<div class="month-event-organizer">👤 ${this.escapeHtml(event.organizer)}</div>`;
                }

                // Build tooltip with full details
                let tooltip = this.escapeHtml(event.title) + '\n' + timeDisplay;
                if (event.organizer) tooltip += '\nBy: ' + this.escapeHtml(event.organizer);
                if (event.description) tooltip += '\n' + this.escapeHtml(event.description);

                html += `
                    <div class="${eventClass}" title="${tooltip}">
                        <div class="month-event-title">${this.escapeHtml(event.title)}</div>
                        ${organizerHtml}
                        <div class="month-event-time">${timeDisplay}</div>
                    </div>
                `;
            });

            if (events.length > 3) {
                html += `<div class="month-more">+${events.length - 3} more</div>`;
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
        const durationInput = document.getElementById('bookingDuration');

        // Set default values
        dateInput.value = this.formatDateForInput(this.selectedDate);
        durationInput.value = '30'; // Reset to default

        // Set default time to next 30-minute interval
        const now = new Date();
        const minutes = now.getMinutes();
        const nextSlot = Math.ceil(minutes / 30) * 30;
        now.setMinutes(nextSlot, 0, 0);
        timeInput.value = now.toTimeString().slice(0, 5);

        // Pre-fill booker name if saved
        nameInput.value = this.bookerName;

        // Reset recurring options
        document.getElementById('isRecurring').checked = false;
        document.getElementById('recurringOptions').style.display = 'none';
        document.getElementById('recurringStart').value = this.formatDateForInput(this.selectedDate);

        // Set default end date to 3 months from now
        const endDate = new Date(this.selectedDate);
        endDate.setMonth(endDate.getMonth() + 3);
        document.getElementById('recurringEnd').value = this.formatDateForInput(endDate);

        // Uncheck all day checkboxes
        document.querySelectorAll('.day-checkbox input').forEach(cb => cb.checked = false);

        modal.style.display = 'flex';
    }

    toggleRecurring() {
        const isRecurring = document.getElementById('isRecurring').checked;
        const options = document.getElementById('recurringOptions');
        options.style.display = isRecurring ? 'block' : 'none';
    }

    onDurationChange() {
        const duration = document.getElementById('bookingDuration').value;
        const timeInput = document.getElementById('bookingTime');

        if (duration === 'fullday') {
            // Set time to 9 AM for full day
            timeInput.value = '09:00';
        }
    }

    closeModal() {
        document.getElementById('bookingModal').style.display = 'none';
    }

    async submitBooking() {
        const name = document.getElementById('bookerName').value.trim();
        const title = document.getElementById('bookingTitle').value.trim() || 'Quick Booking';
        const date = document.getElementById('bookingDate').value;
        const time = document.getElementById('bookingTime').value;
        const durationValue = document.getElementById('bookingDuration').value;
        const isRecurring = document.getElementById('isRecurring').checked;

        if (!name) {
            this.showToast('Please enter your name', 'error');
            return;
        }

        // Save booker name for future use
        this.bookerName = name;
        localStorage.setItem('bookerName', name);

        // Handle full day duration (9 AM to 6 PM = 540 minutes)
        let duration;
        let startHour, startMinute;

        if (durationValue === 'fullday') {
            duration = 540; // 9 hours = 540 minutes
            startHour = 9;
            startMinute = 0;
        } else {
            duration = parseInt(durationValue);
            [startHour, startMinute] = time.split(':').map(Number);
        }

        try {
            if (isRecurring) {
                // Handle recurring booking
                await this.submitRecurringBooking(name, title, startHour, startMinute, duration);
            } else {
                // Single booking
                const params = new URLSearchParams({
                    duration_minutes: duration,
                    title: title,
                    date: date,
                    start_hour: startHour,
                    start_minute: startMinute,
                    booker_name: name
                });

                const response = await fetch(`/api/rooms/${this.roomId}/book?${params}`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to book room');
                }

                const durationText = durationValue === 'fullday' ? 'full day' : `${duration} minutes`;
                this.showToast(`Room booked for ${durationText} by ${name}`, 'success');
            }

            this.closeModal();
            await this.fetchData();
        } catch (error) {
            console.error('Error booking room:', error);
            this.showToast(error.message, 'error');
        }
    }

    async submitRecurringBooking(name, title, startHour, startMinute, duration) {
        // Get selected days
        const selectedDays = [];
        document.querySelectorAll('.day-checkbox input:checked').forEach(cb => {
            selectedDays.push(parseInt(cb.value));
        });

        if (selectedDays.length === 0) {
            throw new Error('Please select at least one day for recurring booking');
        }

        const startDate = document.getElementById('recurringStart').value;
        const endDate = document.getElementById('recurringEnd').value;

        if (!startDate || !endDate) {
            throw new Error('Please set start and end dates for recurring booking');
        }

        const params = new URLSearchParams({
            title: title,
            start_hour: startHour,
            start_minute: startMinute,
            duration_minutes: duration,
            booker_name: name,
            recurring_days: selectedDays.join(','),
            recurring_start: startDate,
            recurring_end: endDate
        });

        const response = await fetch(`/api/rooms/${this.roomId}/book-recurring?${params}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create recurring booking');
        }

        const result = await response.json();
        this.showToast(`Created ${result.count} recurring bookings for ${name}`, 'success');

        // Navigate calendar to the recurring start date to show the created events
        this.selectedDate = new Date(startDate + 'T00:00:00');
        this.updateDatePicker();
    }

    async quickBook(duration) {
        const isToday = this.formatDateForInput(this.selectedDate) === this.formatDateForInput(new Date());

        // Open modal for name input if no saved name, or if booking for a future date
        if (!this.bookerName || !isToday) {
            this.openBookingModal();
            document.getElementById('bookingDuration').value = duration;
            document.getElementById('bookingDate').value = this.formatDateForInput(this.selectedDate);

            if (isToday) {
                // Set time to next 30-minute interval for today
                const now = new Date();
                const minutes = now.getMinutes();
                const nextSlot = Math.ceil(minutes / 30) * 30;
                now.setMinutes(nextSlot, 0, 0);
                document.getElementById('bookingTime').value = now.toTimeString().slice(0, 5);
            } else {
                // Set time to 9 AM for future dates
                document.getElementById('bookingTime').value = '09:00';
            }
            return;
        }

        // Quick book for today with saved name
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
        const isToday = this.formatDateForInput(this.selectedDate) === this.formatDateForInput(new Date());

        // Open modal for name input if no saved name, or if booking for a future date
        if (!this.bookerName || !isToday) {
            this.openBookingModal();
            document.getElementById('bookingDuration').value = 'fullday';
            document.getElementById('bookingDate').value = this.formatDateForInput(this.selectedDate);
            document.getElementById('bookingTime').value = '09:00';
            return;
        }

        // Quick book full day for today with saved name
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

    async cancelBooking(eventId, eventTitle) {
        if (!confirm(`Cancel booking "${eventTitle}"?`)) return;

        try {
            const response = await fetch(`/api/rooms/${this.roomId}/events/${eventId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to cancel booking');
            }

            this.showToast('Booking cancelled', 'success');
            await this.fetchData();
        } catch (error) {
            console.error('Error cancelling booking:', error);
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

        // Update fullscreen button on fullscreen change
        document.addEventListener('fullscreenchange', () => this.updateFullscreenButton());
        document.addEventListener('webkitfullscreenchange', () => this.updateFullscreenButton());
    }

    toggleFullscreen() {
        const elem = document.documentElement;

        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
            // Enter fullscreen
            if (elem.requestFullscreen) {
                elem.requestFullscreen();
            } else if (elem.webkitRequestFullscreen) {
                elem.webkitRequestFullscreen(); // Safari/older Chrome
            } else if (elem.msRequestFullscreen) {
                elem.msRequestFullscreen(); // IE11
            }
        } else {
            // Exit fullscreen
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
        }
    }

    updateFullscreenButton() {
        const btn = document.getElementById('fullscreenBtn');
        if (btn) {
            const isFullscreen = document.fullscreenElement || document.webkitFullscreenElement;
            btn.textContent = isFullscreen ? '⛶' : '⛶';
            btn.title = isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen';
        }
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
