# -*- coding: utf-8 -*-
"""Shared helpers for the student / faculty schedule, calendar and syllabus portals.

Timetable source  : university.timetable (weekly recurring slots)
Overlay           : timetable.substitution (approved / completed substitutions
                    are matched to a slot by course + start time + date)
Extras            : examinations (students) and Odoo calendar events (both)
"""
from datetime import datetime, timedelta, date

import pytz

from odoo import fields
from odoo.osv import expression

DEFAULT_TZ = 'Asia/Kolkata'
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
CLASS_TYPE_LABELS = {
    'theory': 'Theory', 'practical': 'Practical', 'lab': 'Laboratory',
    'tutorial': 'Tutorial', 'seminar': 'Seminar',
}
SUB_STATES = ('approved', 'completed')
LIVE_EXAM_STATES = ('scheduled', 'registration_open', 'registration_closed', 'ongoing')
MAX_RANGE_DAYS = 70


# ----------------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------------
def get_tz(env):
    try:
        return pytz.timezone(env.user.tz or DEFAULT_TZ)
    except Exception:
        return pytz.timezone(DEFAULT_TZ)


def local_now(env):
    return datetime.now(pytz.utc).astimezone(get_tz(env))


def float_to_hm(value):
    value = value or 0.0
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return hours, minutes


def float_to_label(value):
    h, m = float_to_hm(value)
    suffix = 'AM' if h < 12 else 'PM'
    h12 = h % 12 or 12
    return '%d:%02d %s' % (h12, m, suffix)


def initials(name):
    parts = [p for p in (name or '').replace('.', ' ').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def day_label(d, today):
    if d == today:
        return 'Today'
    if d == today + timedelta(days=1):
        return 'Tomorrow'
    return d.strftime('%A, %d %b')


def parse_range(start, end, today):
    """Parse ?start=&end= (ISO dates); fall back to the current month."""
    try:
        d_from = fields.Date.from_string(start) if start else None
        d_to = fields.Date.from_string(end) if end else None
    except Exception:
        d_from = d_to = None
    if not d_from or not d_to:
        d_from = today.replace(day=1)
        d_to = d_from + timedelta(days=41)
    if d_to < d_from:
        d_from, d_to = d_to, d_from
    if (d_to - d_from).days > MAX_RANGE_DAYS:
        d_to = d_from + timedelta(days=MAX_RANGE_DAYS)
    return d_from, d_to


# ----------------------------------------------------------------------
# Who is the user
# ----------------------------------------------------------------------
def get_student(env):
    return env['student.student'].sudo().search([('user_id', '=', env.uid)], limit=1)


def get_faculty(env):
    su = env['faculty.faculty'].sudo()
    faculty = su.search([('user_id', '=', env.uid)], limit=1)
    if not faculty:
        employee = env['hr.employee'].sudo().search([('user_id', '=', env.uid)], limit=1)
        if employee:
            faculty = su.search([('employee_id', '=', employee.id)], limit=1)
    return faculty


# ----------------------------------------------------------------------
# Timetable queries
# ----------------------------------------------------------------------
def student_slots(env, student):
    """Active timetable slots that apply to a student (batch + semester, or enrolled)."""
    Timetable = env['university.timetable'].sudo()
    domains = [[('course_id.student_ids', 'in', [student.id])]]
    if student.batch_id:
        domains.append([
            ('batch_id', '=', student.batch_id.id),
            '|', ('semester_id', '=', False),
            ('semester_id.semester_number', '=', student.current_semester),
        ])
    domain = expression.AND([[('active', '=', True)], expression.OR(domains)])
    return Timetable.search(domain, order='day_of_week, start_time')


def faculty_slots(env, faculty):
    return env['university.timetable'].sudo().search(
        [('faculty_id', '=', faculty.id), ('active', '=', True)],
        order='day_of_week, start_time')


def substitution_map(env, d_from, d_to):
    """{(course_id, start_time_2dp, date): substitution} for approved/completed ones."""
    subs = env['timetable.substitution'].sudo().search([
        ('date', '>=', d_from), ('date', '<=', d_to), ('state', 'in', SUB_STATES)])
    result = {}
    for sub in subs:
        tt = sub.timetable_id
        result[(tt.course_id.id, round(tt.start_time, 2), sub.date)] = sub
    return result


def _slot_applies(tt, d):
    if d.weekday() != int(tt.day_of_week):
        return False
    if not tt.is_recurring and tt.start_date:
        return d == tt.start_date
    if tt.start_date and d < tt.start_date:
        return False
    if tt.end_date and d > tt.end_date:
        return False
    return True


def _daterange(d_from, d_to):
    d = d_from
    while d <= d_to:
        yield d
        d += timedelta(days=1)


# ----------------------------------------------------------------------
# Event construction
# ----------------------------------------------------------------------
def _room(tt):
    room = tt.room_number_id or tt.classroom_id
    return room.name if room else 'TBA'


def _status(d, start, end, today, now_f):
    if d < today:
        return 'done'
    if d > today:
        return 'upcoming'
    if now_f >= end:
        return 'done'
    if now_f >= start:
        return 'ongoing'
    return 'upcoming'


def _class_event(tt, d, sub, today, now_f, viewer_faculty=None, force_substitute=None):
    """Build one class occurrence.

    viewer_faculty: faculty record when the viewer is a faculty member (changes the
    meaning of a substitution: covered-by vs. taking-over).
    """
    original = tt.faculty_id
    teacher = sub.substitute_faculty_id if sub else original
    cancelled = False
    note = ''
    if sub:
        if viewer_faculty and viewer_faculty == original and sub.substitute_faculty_id != viewer_faculty:
            cancelled = True
            note = 'Covered by %s' % sub.substitute_faculty_id.name
        elif viewer_faculty and viewer_faculty == sub.substitute_faculty_id:
            note = 'You are substituting for %s' % original.name
        else:
            note = 'Substitution: %s instead of %s' % (sub.substitute_faculty_id.name, original.name)
    status = 'cancelled' if cancelled else _status(d, tt.start_time, tt.end_time, today, now_f)
    return {
        'id': 'tt-%s-%s' % (tt.id, d.isoformat()),
        'kind': 'class',
        'title': tt.subject_id.name or tt.course_id.name or 'Class',
        'subject': tt.subject_id.name or '',
        'course': tt.course_id.name or '',
        'course_id': tt.course_id.id,
        'batch': tt.batch_id.name or '',
        'date': d.isoformat(),
        'start': tt.start_time,
        'end': tt.end_time,
        'start_label': float_to_label(tt.start_time),
        'end_label': float_to_label(tt.end_time),
        'class_type': tt.class_type or 'theory',
        'type_label': CLASS_TYPE_LABELS.get(tt.class_type, 'Class'),
        'faculty': teacher.name or '',
        'faculty_initials': initials(teacher.name),
        'faculty_id': teacher.id,
        'room': _room(tt),
        'status': status,
        'substitution': bool(sub),
        'cancelled': cancelled,
        'note': note,
        'original_faculty': original.name or '',
        'period': 0,
        'tt_id': tt.id,
    }


def _assign_periods(events):
    by_day = {}
    for ev in events:
        if ev['kind'] == 'class':
            by_day.setdefault(ev['date'], set()).add(ev['start'])
    order = {d: {s: i + 1 for i, s in enumerate(sorted(starts))} for d, starts in by_day.items()}
    for ev in events:
        if ev['kind'] == 'class':
            ev['period'] = order[ev['date']][ev['start']]


def _calendar_events(env, d_from, d_to, exclude_ids, exclude_recurrences, today):
    """Odoo calendar events (calendar.event) of the current user's partner."""
    tz = get_tz(env)
    partner = env.user.partner_id
    lo = tz.localize(datetime.combine(d_from, datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)
    hi = tz.localize(datetime.combine(d_to + timedelta(days=1), datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)
    domain = [('partner_ids', 'in', [partner.id]), ('start', '<', hi), ('stop', '>=', lo)]
    out = []
    for ev in env['calendar.event'].sudo().search(domain, order='start', limit=300):
        if ev.id in exclude_ids or (ev.recurrence_id and ev.recurrence_id.id in exclude_recurrences):
            continue
        start = pytz.utc.localize(ev.start).astimezone(tz)
        stop = pytz.utc.localize(ev.stop).astimezone(tz)
        d = start.date()
        out.append({
            'id': 'cal-%s' % ev.id, 'kind': 'event', 'title': ev.name or 'Event',
            'subject': '', 'course': '', 'course_id': 0, 'batch': '',
            'date': d.isoformat(), 'start': start.hour + start.minute / 60.0,
            'end': (stop.hour + stop.minute / 60.0) if stop.date() == d else 23.99,
            'start_label': 'All day' if ev.allday else float_to_label(start.hour + start.minute / 60.0),
            'end_label': '' if ev.allday else float_to_label(stop.hour + stop.minute / 60.0),
            'class_type': 'event', 'type_label': 'Calendar event',
            'faculty': '', 'faculty_initials': '', 'room': ev.location or '',
            'status': 'done' if d < today else 'upcoming', 'substitution': False,
            'cancelled': False, 'note': (ev.description or '')[:200] if ev.description else '',
            'original_faculty': '', 'period': 0, 'tt_id': 0, 'all_day': bool(ev.allday),
        })
    return out


def _exam_events(env, student, d_from, d_to, today):
    Exam = env['examination.examination'].sudo()
    exams = Exam.search([
        ('state', 'in', LIVE_EXAM_STATES),
        ('start_date', '<=', d_to), ('end_date', '>=', d_from)])
    out = []
    for exam in exams:
        if exam.semester_id and exam.semester_id.semester_number != student.current_semester:
            continue
        if exam.program_ids and student.program_id not in exam.program_ids:
            continue
        lo = max(exam.start_date, d_from)
        hi = min(exam.end_date, d_to, lo + timedelta(days=30))
        for d in _daterange(lo, hi):
            out.append({
                'id': 'exam-%s-%s' % (exam.id, d.isoformat()), 'kind': 'exam',
                'title': exam.name, 'subject': '', 'course': '', 'course_id': 0, 'batch': '',
                'date': d.isoformat(), 'start': 0.0, 'end': 0.0,
                'start_label': 'All day', 'end_label': '',
                'class_type': 'exam', 'type_label': 'Examination',
                'faculty': '', 'faculty_initials': '', 'room': '',
                'status': 'done' if d < today else 'upcoming', 'substitution': False,
                'cancelled': False,
                'note': '%s to %s' % (exam.start_date.strftime('%d %b'), exam.end_date.strftime('%d %b %Y')),
                'original_faculty': '', 'period': 0, 'tt_id': 0, 'all_day': True,
            })
    return out


def build_student_events(env, student, d_from, d_to, extras=True):
    today_local = local_now(env)
    today = today_local.date()
    now_f = today_local.hour + today_local.minute / 60.0
    slots = student_slots(env, student)
    subs = substitution_map(env, d_from, d_to)
    events = []
    for d in _daterange(d_from, d_to):
        for tt in slots:
            if _slot_applies(tt, d):
                sub = subs.get((tt.course_id.id, round(tt.start_time, 2), d))
                events.append(_class_event(tt, d, sub, today, now_f))
    _assign_periods(events)
    if extras:
        events += _exam_events(env, student, d_from, d_to, today)
        rec_ids = set(slots.mapped('calendar_event_id.recurrence_id').ids)
        events += _calendar_events(env, d_from, d_to, set(slots.calendar_event_id.ids), rec_ids, today)
    events.sort(key=lambda e: (e['date'], e['start']))
    return events


def build_faculty_events(env, faculty, d_from, d_to, extras=True):
    today_local = local_now(env)
    today = today_local.date()
    now_f = today_local.hour + today_local.minute / 60.0
    slots = faculty_slots(env, faculty)
    subs = substitution_map(env, d_from, d_to)
    events = []
    for d in _daterange(d_from, d_to):
        for tt in slots:
            if _slot_applies(tt, d):
                sub = subs.get((tt.course_id.id, round(tt.start_time, 2), d))
                events.append(_class_event(tt, d, sub, today, now_f, viewer_faculty=faculty))
    # classes where this faculty is the substitute
    Timetable = env['university.timetable'].sudo()
    for (course_id, start2, d), sub in subs.items():
        if sub.substitute_faculty_id != faculty or sub.original_faculty_id == faculty:
            continue
        for tt in Timetable.search([('course_id', '=', course_id), ('active', '=', True)]):
            if round(tt.start_time, 2) == start2 and _slot_applies(tt, d):
                events.append(_class_event(tt, d, sub, today, now_f, viewer_faculty=faculty))
    _assign_periods(events)
    if extras:
        rec_ids = set(slots.mapped('calendar_event_id.recurrence_id').ids)
        events += _calendar_events(env, d_from, d_to, set(slots.calendar_event_id.ids), rec_ids, today)
    events.sort(key=lambda e: (e['date'], e['start']))
    return events


# ----------------------------------------------------------------------
# "Now / next" summary used by the dashboards
# ----------------------------------------------------------------------
def now_and_next(env, builder, owner, days_ahead=14):
    """Return dict(today=[...], current=ev|None, next=ev|None, tz_now=datetime)."""
    now = local_now(env)
    today = now.date()
    events = builder(env, owner, today, today + timedelta(days=days_ahead), extras=False)
    classes = [e for e in events if e['kind'] == 'class' and not e['cancelled']]
    today_all = [e for e in events if e['kind'] == 'class' and e['date'] == today.isoformat()]
    current = next((e for e in classes if e['status'] == 'ongoing'), None)
    upcoming = [e for e in classes if e['status'] == 'upcoming']
    nxt = upcoming[0] if upcoming else None
    if current:
        current['when'] = 'Now'
        left = int(round((current['end'] - (now.hour + now.minute / 60.0)) * 60))
        current['when_detail'] = 'ends in %d min' % max(left, 0)
    if nxt:
        d = fields.Date.from_string(nxt['date'])
        nxt['when'] = day_label(d, today)
        if d == today:
            mins = int(round((nxt['start'] - (now.hour + now.minute / 60.0)) * 60))
            nxt['when_detail'] = 'starts in %d min' % max(mins, 0) if mins < 180 else 'at %s' % nxt['start_label']
        else:
            nxt['when_detail'] = 'at %s' % nxt['start_label']
    remaining = len([e for e in today_all if e['status'] in ('upcoming', 'ongoing')])
    return {
        'today': today_all, 'current': current, 'next': nxt,
        'today_count': len(today_all), 'remaining_today': remaining,
        'now': now,
    }


# ----------------------------------------------------------------------
# iCalendar export
# ----------------------------------------------------------------------
def _ics_escape(text):
    return (text or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def build_ics(env, events, cal_name):
    tz = get_tz(env)
    stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//University Management//Schedule//EN',
             'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:%s' % _ics_escape(cal_name)]
    for ev in events:
        if ev['kind'] != 'class' or ev['cancelled']:
            continue
        d = fields.Date.from_string(ev['date'])
        sh, sm = float_to_hm(ev['start'])
        eh, em = float_to_hm(ev['end'])
        start = tz.localize(datetime(d.year, d.month, d.day, sh % 24, sm)).astimezone(pytz.utc)
        end = tz.localize(datetime(d.year, d.month, d.day, eh % 24, em)).astimezone(pytz.utc)
        desc = 'Faculty: %s\nType: %s' % (ev['faculty'], ev['type_label'])
        if ev['note']:
            desc += '\n' + ev['note']
        lines += [
            'BEGIN:VEVENT', 'UID:%s@university-management' % ev['id'], 'DTSTAMP:%s' % stamp,
            'DTSTART:%s' % start.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:%s' % end.strftime('%Y%m%dT%H%M%SZ'),
            'SUMMARY:%s' % _ics_escape(ev['title']),
            'LOCATION:%s' % _ics_escape(ev['room']),
            'DESCRIPTION:%s' % _ics_escape(desc), 'END:VEVENT']
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


# ----------------------------------------------------------------------
# Convenience wrappers used by the dashboards
# ----------------------------------------------------------------------
def student_now_next(env, student):
    return now_and_next(env, lambda e, s, a, b, extras=False: build_student_events(e, s, a, b, extras), student)


def faculty_now_next(env, faculty):
    return now_and_next(env, lambda e, f, a, b, extras=False: build_faculty_events(e, f, a, b, extras), faculty)


def attach_progress(env, events):
    """Add syllabus progress info (overall %, next unit) to class events."""
    Log = env['syllabus.coverage.log'].sudo()
    Course = env['university.course'].sudo()
    cache = {}
    for ev in events:
        if not ev or ev['kind'] != 'class':
            continue
        cid = ev['course_id']
        if cid not in cache:
            data = Log.get_course_progress(Course.browse(cid))
            nu = data['next_unit']
            cache[cid] = {
                'overall': data['overall'],
                'unit': nu['name'] if nu else ('All units completed' if data['units'] else ''),
                'unit_percent': nu['percent'] if nu else (100 if data['units'] else 0),
                'has_syllabus': bool(data['units']),
            }
        ev['progress'] = cache[cid]
    return events