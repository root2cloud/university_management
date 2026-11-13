/* University portal – calendar widget + syllabus log helpers (plain JS, no dependencies) */
(function () {
  'use strict';

  var COLORS = {
    theory: '#4f46e5', practical: '#059669', lab: '#d97706', tutorial: '#0891b2',
    seminar: '#9333ea', exam: '#dc2626', event: '#475569'
  };
  var LEGEND = [
    ['theory', 'Theory'], ['practical', 'Practical'], ['lab', 'Lab'], ['tutorial', 'Tutorial'],
    ['seminar', 'Seminar'], ['exam', 'Exams'], ['event', 'Other events']
  ];
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December'];
  var DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  var DAYS_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  var HOUR_PX = 64;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function iso(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function parse(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function addDays(d, n) { var x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }
  function weekIdx(d) { return (d.getDay() + 6) % 7; }           // Monday = 0
  function startOfWeek(d) { return addDays(d, -weekIdx(d)); }
  function hourLabel(h) { var s = h < 12 ? 'AM' : 'PM'; return ((h % 12) || 12) + ' ' + s; }
  function color(ev) { return COLORS[ev.class_type] || COLORS.event; }
  function typeKey(ev) { return COLORS[ev.class_type] ? ev.class_type : 'event'; }

  /* ------------------------------------------------------------------ */
  function Calendar(root) {
    this.root = root;
    this.url = root.getAttribute('data-events-url');
    this.role = root.getAttribute('data-role') || 'student';
    this.today = parse(root.getAttribute('data-today') || iso(new Date()));
    this.cursor = new Date(this.today.getTime());
    this.view = window.innerWidth < 700 ? 'day' : 'month';
    this.events = {};
    this.loaded = {};
    this.hidden = {};
    this.build();
    this.load();
  }

  Calendar.prototype.build = function () {
    var self = this;
    this.root.innerHTML =
      '<div class="um-cal-bar">' +
        '<div class="um-cal-nav">' +
          '<button class="um-icon-btn" data-act="prev" title="Previous">&#8249;</button>' +
          '<button class="um-icon-btn" data-act="next" title="Next">&#8250;</button>' +
          '<button class="um-btn um-btn-ghost" data-act="today" style="padding:6px 14px">Today</button>' +
        '</div>' +
        '<div class="um-cal-title"></div>' +
        '<div class="um-seg">' +
          '<button data-view="month">Month</button><button data-view="week">Week</button><button data-view="day">Day</button>' +
        '</div>' +
      '</div>' +
      '<div class="um-legend"></div>' +
      '<div class="um-cal-body"><div class="um-cal-loading">Loading schedule…</div><div class="um-cal-view"></div></div>';
    this.titleEl = this.root.querySelector('.um-cal-title');
    this.viewEl = this.root.querySelector('.um-cal-view');
    this.loadingEl = this.root.querySelector('.um-cal-loading');

    var legend = this.root.querySelector('.um-legend');
    legend.innerHTML = LEGEND.map(function (l) {
      return '<button data-type="' + l[0] + '" style="--c:' + COLORS[l[0]] + '"><i></i>' + l[1] + '</button>';
    }).join('');

    this.root.addEventListener('click', function (e) {
      var t = e.target.closest('[data-act],[data-view],[data-type],[data-id],[data-day]');
      if (!t || !self.root.contains(t)) return;
      if (t.hasAttribute('data-act')) {
        var a = t.getAttribute('data-act');
        if (a === 'today') self.cursor = new Date(self.today.getTime());
        else self.shift(a === 'next' ? 1 : -1);
        self.load();
      } else if (t.hasAttribute('data-view')) {
        self.view = t.getAttribute('data-view');
        self.load();
      } else if (t.hasAttribute('data-type')) {
        var k = t.getAttribute('data-type');
        self.hidden[k] = !self.hidden[k];
        t.classList.toggle('off', !!self.hidden[k]);
        self.render();
      } else if (t.hasAttribute('data-id')) {
        e.stopPropagation();
        self.openModal(self.events[t.getAttribute('data-id')]);
      } else if (t.hasAttribute('data-day')) {
        self.cursor = parse(t.getAttribute('data-day'));
        self.view = 'day';
        self.load();
      }
    });
    this.modal = document.createElement('div');
    this.modal.className = 'um-modal-back';
    this.modal.addEventListener('click', function (e) {
      if (e.target === self.modal || e.target.hasAttribute('data-close')) self.modal.classList.remove('on');
    });
    document.body.appendChild(this.modal);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') self.modal.classList.remove('on'); });
  };

  Calendar.prototype.shift = function (dir) {
    var c = this.cursor;
    if (this.view === 'month') this.cursor = new Date(c.getFullYear(), c.getMonth() + dir, 1);
    else this.cursor = addDays(c, dir * (this.view === 'week' ? 7 : 1));
  };

  Calendar.prototype.range = function () {
    var c = this.cursor, s, e;
    if (this.view === 'month') { s = startOfWeek(new Date(c.getFullYear(), c.getMonth(), 1)); e = addDays(s, 41); }
    else if (this.view === 'week') { s = startOfWeek(c); e = addDays(s, 6); }
    else { s = c; e = c; }
    return [s, e];
  };

  Calendar.prototype.load = function () {
    var self = this, r = this.range(), key = iso(r[0]) + '_' + iso(r[1]);
    this.updateChrome();
    if (this.loaded[key]) return this.render();
    this.loadingEl.classList.add('on');
    fetch(this.url + '?start=' + iso(r[0]) + '&end=' + iso(r[1]), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        (data.events || []).forEach(function (ev) { self.events[ev.id] = ev; });
        self.loaded[key] = true;
        self.loadingEl.classList.remove('on');
        self.render();
      })
      .catch(function () {
        self.loadingEl.classList.remove('on');
        self.viewEl.innerHTML = '<div class="um-empty">Could not load the schedule. Please refresh the page.</div>';
      });
  };

  Calendar.prototype.updateChrome = function () {
    var c = this.cursor, r = this.range(), t;
    if (this.view === 'month') t = MONTHS[c.getMonth()] + ' ' + c.getFullYear();
    else if (this.view === 'week') {
      var a = r[0], b = r[1];
      t = a.getDate() + (a.getMonth() !== b.getMonth() ? ' ' + MONTHS[a.getMonth()].slice(0, 3) : '') + ' – ' +
          b.getDate() + ' ' + MONTHS[b.getMonth()].slice(0, 3) + ' ' + b.getFullYear();
    } else t = DAYS_LONG[weekIdx(c)] + ', ' + c.getDate() + ' ' + MONTHS[c.getMonth()] + ' ' + c.getFullYear();
    this.titleEl.textContent = t;
    Array.prototype.forEach.call(this.root.querySelectorAll('[data-view]'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-view') === this.view);
    }, this);
  };

  Calendar.prototype.eventsOn = function (day) {
    var self = this;
    return Object.keys(this.events).map(function (k) { return self.events[k]; })
      .filter(function (e) { return e.date === day && !self.hidden[typeKey(e)]; })
      .sort(function (a, b) { return a.start - b.start; });
  };

  Calendar.prototype.render = function () {
    if (this.view === 'month') this.renderMonth();
    else if (this.view === 'week') this.renderWeek();
    else this.renderDay();
  };

  function facultyAvatar(ev) {
    if (ev.kind !== 'class' || !ev.faculty_id) return '';
    return '<span class="um-ev-av">' + esc(ev.faculty_initials || '') +
      '<img src="/my/schedule/faculty-photo/' + esc(ev.faculty_id) + '" alt="" loading="lazy" onerror="this.remove()"/></span>';
  }

  function chip(ev) {
    var cls = 'um-ev um-c-' + typeKey(ev) + (ev.cancelled ? ' cancelled' : '') + (ev.substitution ? ' sub' : '');
    var time = ev.all_day || ev.kind === 'exam' ? '' : '<b>' + esc(ev.start_label.replace(':00', '').replace(' ', '')) + '</b> ';
    var avatar = facultyAvatar(ev);
    return '<div class="' + cls + '" data-id="' + esc(ev.id) + '" title="' + esc(ev.title) + '">' + avatar + time + esc(ev.title) + '</div>';
  }

  Calendar.prototype.renderMonth = function () {
    var c = this.cursor, s = this.range()[0], todayIso = iso(this.today), html = '<div class="um-month-head">';
    DAYS.forEach(function (d) { html += '<div>' + d + '</div>'; });
    html += '</div><div class="um-month-grid">';
    for (var i = 0; i < 42; i++) {
      var d = addDays(s, i), di = iso(d), evs = this.eventsOn(di);
      var cls = 'um-cell' + (d.getMonth() !== c.getMonth() ? ' other' : '') + (di === todayIso ? ' today' : '') + (weekIdx(d) >= 5 ? ' weekend' : '');
      html += '<div class="' + cls + '" data-day="' + di + '"><span class="um-daynum">' + d.getDate() + '</span>';
      html += evs.slice(0, 3).map(chip).join('');
      if (evs.length > 3) html += '<div class="um-more">+' + (evs.length - 3) + ' more</div>';
      html += '<div class="um-dots">' + evs.slice(0, 6).map(function (e) { return '<i class="um-c-' + typeKey(e) + '"></i>'; }).join('') + '</div></div>';
    }
    this.viewEl.innerHTML = html + '</div>';
  };

  Calendar.prototype.renderWeek = function () {
    var s = this.range()[0], todayIso = iso(this.today), self = this, days = [], i;
    for (i = 0; i < 7; i++) days.push(addDays(s, i));
    var timed = [], allDay = {};
    days.forEach(function (d) {
      var di = iso(d);
      allDay[di] = [];
      self.eventsOn(di).forEach(function (e) {
        if (e.all_day || e.kind === 'exam') allDay[di].push(e); else timed.push(e);
      });
    });
    var minH = 8, maxH = 17;
    timed.forEach(function (e) { minH = Math.min(minH, Math.floor(e.start)); maxH = Math.max(maxH, Math.ceil(e.end)); });
    minH = Math.max(minH, 5); maxH = Math.min(maxH, 23);
    var html = '<div class="um-week"><div class="um-week-inner"><div class="um-week-head"><div></div>';
    days.forEach(function (d) {
      html += '<div class="' + (iso(d) === todayIso ? 'today' : '') + '">' + DAYS[weekIdx(d)] + '<b>' + d.getDate() + '</b></div>';
    });
    html += '</div>';
    if (days.some(function (d) { return allDay[iso(d)].length; })) {
      html += '<div class="um-allday-row"><div class="lab">all-day</div>';
      days.forEach(function (d) { html += '<div>' + allDay[iso(d)].map(chip).join('') + '</div>'; });
      html += '</div>';
    }
    html += '<div class="um-week-grid"><div class="um-hours">';
    for (var h = minH; h < maxH; h++) html += '<div>' + hourLabel(h) + '</div>';
    html += '</div>';
    var nowH = new Date().getHours() + new Date().getMinutes() / 60;
    days.forEach(function (d) {
      var di = iso(d), evs = timed.filter(function (e) { return e.date === di; });
      html += '<div class="um-daycol' + (di === todayIso ? ' today' : '') + '" style="height:' + ((maxH - minH) * HOUR_PX) + 'px">';
      html += self.layoutBlocks(evs, minH);
      if (di === todayIso && nowH >= minH && nowH <= maxH) html += '<div class="um-nowline" style="top:' + ((nowH - minH) * HOUR_PX) + 'px"></div>';
      html += '</div>';
    });
    this.viewEl.innerHTML = html + '</div></div></div>';
  };

  Calendar.prototype.layoutBlocks = function (evs, minH) {
    // cluster overlapping events and split them into lanes
    var out = '', cluster = [], clusterEnd = -1;
    function flush() {
      if (!cluster.length) return;
      var lanes = [];
      cluster.forEach(function (e) {
        var placed = false;
        for (var l = 0; l < lanes.length; l++) {
          if (lanes[l] <= e.start) { lanes[l] = e.end; e._lane = l; placed = true; break; }
        }
        if (!placed) { lanes.push(e.end); e._lane = lanes.length - 1; }
      });
      cluster.forEach(function (e) {
        var w = 100 / lanes.length, top = (e.start - minH) * HOUR_PX, ht = Math.max((e.end - e.start) * HOUR_PX - 3, 28);
        var cls = 'um-block um-c-' + typeKey(e) + (e.cancelled ? ' cancelled' : '') + (e.substitution ? ' sub' : '');
        out += '<div class="' + cls + '" data-id="' + esc(e.id) + '" style="top:' + top + 'px;height:' + ht + 'px;left:calc(' + (e._lane * w) +
          '% + 3px);width:calc(' + w + '% - 6px);right:auto">' + facultyAvatar(e) + '<b>' + esc(e.title) + '</b>' +
          esc(e.start_label) + (e.room ? ' · ' + esc(e.room) : '') + '</div>';
      });
      cluster = []; clusterEnd = -1;
    }
    evs.forEach(function (e) {
      if (cluster.length && e.start >= clusterEnd) flush();
      cluster.push(e); clusterEnd = Math.max(clusterEnd, e.end);
    });
    flush();
    return out;
  };

  Calendar.prototype.renderDay = function () {
    var di = iso(this.cursor), evs = this.eventsOn(di), self = this, html = '<div class="um-day">';
    if (!evs.length) {
      html += '<div class="um-empty">Nothing scheduled for this day.</div>';
    }
    evs.forEach(function (e) {
      var cls = 'um-day-item um-c-' + typeKey(e) + (e.cancelled ? ' cancelled' : '');
      var time = (e.all_day || e.kind === 'exam') ? 'All day' : esc(e.start_label) + '<small>to ' + esc(e.end_label) + '</small>';
      var who = '';
      if (e.kind === 'class') {
        who = self.role === 'faculty'
          ? '<div class="um-tl-sub">' + esc(e.batch) + (e.room ? ' · ' + esc(e.room) : '') + '</div>'
          : '<div class="um-tl-sub">' + esc(e.faculty) + (e.room ? ' · ' + esc(e.room) : '') + '</div>';
      } else if (e.room) who = '<div class="um-tl-sub">' + esc(e.room) + '</div>';
      html += '<div class="' + cls + '" data-id="' + esc(e.id) + '"><div class="t">' + time + '</div>' + facultyAvatar(e) + '<div class="um-tl-main">' +
        '<div class="um-tl-title">' + esc(e.title) + '</div>' + who +
        (e.note ? '<div class="um-note" style="margin-top:6px">' + esc(e.note) + '</div>' : '') + '</div>' +
        '<div><span class="um-chip">' + esc(e.type_label) + '</span></div></div>';
    });
    this.viewEl.innerHTML = html + '</div>';
  };

  Calendar.prototype.openModal = function (ev) {
    if (!ev) return;
    var d = parse(ev.date), c = color(ev), rows = '';
    function kv(k, v) { if (v) rows += '<div class="um-kv"><span>' + k + '</span><div>' + v + '</div></div>'; }
    var when = (ev.all_day || ev.kind === 'exam') ? 'All day' : esc(ev.start_label) + ' – ' + esc(ev.end_label);
    kv('Date', DAYS_LONG[weekIdx(d)] + ', ' + d.getDate() + ' ' + MONTHS[d.getMonth()] + ' ' + d.getFullYear());
    kv('Time', when);
    if (ev.kind === 'class') {
      if (this.role === 'faculty') { kv('Batch', esc(ev.batch)); kv('Course', esc(ev.course)); }
      else { kv('Faculty', esc(ev.faculty)); kv('Period', ev.period ? 'Period ' + ev.period : ''); }
      kv('Room', esc(ev.room));
      kv('Type', esc(ev.type_label));
      var st = { done: 'Completed', ongoing: 'In progress', upcoming: 'Upcoming', cancelled: 'Covered by substitute' }[ev.status];
      kv('Status', esc(st || ''));
    } else {
      kv('Type', esc(ev.type_label)); kv('Where', esc(ev.room));
    }
    if (ev.note) kv('Note', esc(ev.note));
    var link = '';
    if (ev.kind === 'class' && ev.course_id) {
      var href = this.role === 'faculty' ? '/my/faculty/syllabus/' + ev.course_id : '/my/syllabus/' + ev.course_id;
      link = '<div style="margin-top:14px;text-align:right"><a class="um-btn um-btn-primary" href="' + href + '">' +
        (this.role === 'faculty' ? 'Open syllabus tracker' : 'View syllabus') + '</a></div>';
    }
    this.modal.innerHTML = '<div class="um-modal" style="--c:' + c + '"><div class="um-modal-head"><button class="um-modal-close" data-close="1">&times;</button>' +
      '<h3>' + esc(ev.title) + '</h3><small>' + esc(ev.type_label) + (ev.substitution ? ' · Substitution' : '') + '</small></div>' +
      '<div class="um-modal-body">' + rows + link + '</div></div>';
    this.modal.classList.add('on');
  };

  /* ------------------------------------------------------------------ */
  /* Faculty syllabus log form helpers                                   */
  /* ------------------------------------------------------------------ */
  function initLogForm(form) {
    var unit = form.querySelector('select[name=unit_id]');
    var range = form.querySelector('input[name=completion_percent]');
    var out = form.querySelector('output');
    var done = form.querySelector('input[name=unit_completed]');
    function sync() { if (out) out.textContent = range.value + '%'; }
    function setForUnit() {
      var opt = unit.options[unit.selectedIndex];
      if (opt && opt.getAttribute('data-percent') !== null) { range.value = opt.getAttribute('data-percent'); sync(); }
    }
    if (range) range.addEventListener('input', function () { if (done && +range.value < 100) done.checked = false; sync(); });
    if (done) done.addEventListener('change', function () { if (done.checked) { range.value = 100; sync(); } });
    if (unit) unit.addEventListener('change', setForUnit);
    setForUnit(); sync();
    Array.prototype.forEach.call(document.querySelectorAll('[data-pick-unit]'), function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        unit.value = b.getAttribute('data-pick-unit'); setForUnit();
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
        var ta = form.querySelector('textarea'); if (ta) ta.focus({ preventScroll: true });
      });
    });
  }

  function boot() {
    Array.prototype.forEach.call(document.querySelectorAll('.um-cal[data-events-url]'), function (el) { new Calendar(el); });
    Array.prototype.forEach.call(document.querySelectorAll('.um-log-form'), initLogForm);
    var auto = document.querySelector('[data-autorefresh]');
    if (auto) {
      setInterval(function () {
        var m = document.querySelector('.um-modal-back.on'), f = document.activeElement;
        if (!document.hidden && !m && !(f && /INPUT|TEXTAREA|SELECT/.test(f.tagName))) window.location.reload();
      }, 5 * 60 * 1000);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();