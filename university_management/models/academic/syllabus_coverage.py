# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SyllabusCoverageLog(models.Model):
    """Class-wise syllabus coverage log.

    Faculty add one entry per class (date, period, unit, topics covered and the
    cumulative % of the unit finished). Unit / subject progress shown to
    faculty and students is derived from these entries.
    """
    _name = 'syllabus.coverage.log'
    _description = 'Syllabus Coverage Log'
    _order = 'date desc, start_time desc, id desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    course_id = fields.Many2one('university.course', string='Course',
                                required=True, index=True, ondelete='cascade')
    subject_id = fields.Many2one(related='course_id.subject_id', string='Subject', store=True)
    batch_id = fields.Many2one(related='course_id.batch_id', string='Batch', store=True)
    syllabus_id = fields.Many2one('university.syllabus', string='Syllabus', index=True)
    unit_id = fields.Many2one('university.syllabus.unit', string='Unit', required=True,
                              domain="[('syllabus_id', '=', syllabus_id)]", ondelete='cascade')
    faculty_id = fields.Many2one('faculty.faculty', string='Taught By', required=True, index=True)

    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True)
    timetable_id = fields.Many2one('university.timetable', string='Timetable Slot',
                                   ondelete='set null')
    start_time = fields.Float(string='Start Time')
    end_time = fields.Float(string='End Time')
    is_substitution = fields.Boolean(string='Taken as Substitute')

    topics_covered = fields.Text(string='Topics Covered', required=True)
    completion_percent = fields.Integer(
        string='Unit Completion %', default=0,
        help='Cumulative % of this unit completed after this class.')
    unit_completed = fields.Boolean(string='Unit Completed')
    remarks = fields.Text(string='Remarks')

    @api.depends('course_id', 'unit_id', 'date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s / %s / %s' % (
                rec.course_id.code or rec.course_id.name or '',
                rec.unit_id.name or '',
                rec.date or '')

    @api.constrains('completion_percent')
    def _check_percent(self):
        for rec in self:
            if rec.completion_percent < 0 or rec.completion_percent > 100:
                raise ValidationError(_('Completion % must be between 0 and 100.'))

    @api.constrains('date')
    def _check_date(self):
        for rec in self:
            if rec.date and rec.date > fields.Date.context_today(rec):
                raise ValidationError(_('Syllabus coverage cannot be logged for a future date.'))

    @api.constrains('unit_id', 'syllabus_id')
    def _check_unit_syllabus(self):
        for rec in self:
            if rec.syllabus_id and rec.unit_id.syllabus_id != rec.syllabus_id:
                raise ValidationError(_('The selected unit does not belong to the syllabus.'))

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            self.syllabus_id = self.env['syllabus.coverage.log']._get_course_syllabus(self.course_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize(vals)
        return super().write(vals)

    @api.model
    def _normalize(self, vals):
        if vals.get('unit_completed'):
            vals['completion_percent'] = 100
        elif vals.get('completion_percent') == 100:
            vals['unit_completed'] = True

    # ------------------------------------------------------------------
    # Helpers used by the portals
    # ------------------------------------------------------------------
    @api.model
    def _get_course_syllabus(self, course):
        """Return the syllabus that applies to a course."""
        course = course.sudo()
        if course.syllabus_id:
            return course.syllabus_id
        syllabi = course.subject_id.syllabus_ids
        if not syllabi:
            return self.env['university.syllabus']
        best = syllabi.filtered(lambda s: s.state in ('approved', 'published')) or syllabi
        return best.sorted(lambda s: (s.effective_from or fields.Date.from_string('1970-01-01'), s.id),
                           reverse=True)[:1]

    @api.model
    def get_course_progress(self, course, syllabus=None):
        """Unit-wise and overall syllabus progress for a course.

        Returns a dict:
          {
            'syllabus': record, 'units': [ {...} ], 'overall': int,
            'classes_held': int, 'next_unit': dict|None, 'last_date': date|False
          }
        """
        course = course.sudo()
        syllabus = (syllabus or self._get_course_syllabus(course)).sudo()
        logs = self.sudo().search([('course_id', '=', course.id)], order='date asc, id asc')
        per_unit = {}
        for log in logs:
            info = per_unit.setdefault(log.unit_id.id, {
                'percent': 0, 'last_date': False, 'sessions': 0, 'recent': []})
            info['sessions'] += 1
            info['percent'] = 100 if log.unit_completed else max(info['percent'], log.completion_percent)
            info['last_date'] = log.date
            info['recent'].append({
                'date': log.date, 'topics': log.topics_covered,
                'faculty': log.faculty_id.name, 'substitute': log.is_substitution,
            })

        units = []
        total_weight = 0.0
        weighted = 0.0
        for unit in syllabus.unit_ids.sorted(lambda u: (u.sequence, u.id)):
            info = per_unit.get(unit.id, {})
            percent = info.get('percent', 0)
            if percent >= 100:
                status = 'completed'
            elif percent > 0 or info.get('sessions'):
                status = 'in_progress'
            else:
                status = 'not_started'
            weight = float(unit.hours or 1)
            total_weight += weight
            weighted += weight * percent
            units.append({
                'id': unit.id, 'name': unit.name, 'hours': unit.hours,
                'topics': unit.topics, 'outcomes': unit.learning_outcomes,
                'percent': percent, 'status': status,
                'sessions': info.get('sessions', 0),
                'last_date': info.get('last_date'),
                'recent': list(reversed(info.get('recent', [])))[:5],
            })
        overall = int(round(weighted / total_weight)) if total_weight else 0
        next_unit = next((u for u in units if u['status'] != 'completed'), None)
        return {
            'syllabus': syllabus, 'units': units, 'overall': overall,
            'classes_held': len(logs),
            'next_unit': next_unit,
            'last_date': logs[-1].date if logs else False,
        }