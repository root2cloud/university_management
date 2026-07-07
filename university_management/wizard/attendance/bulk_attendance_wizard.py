# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BulkAttendanceWizard(models.TransientModel):
    _name = 'bulk.attendance.wizard'
    _description = 'Bulk Student Class Attendance Wizard'

    # ── Step 1: Filters ───────────────────────────────────────────────────
    date = fields.Date(
        string='Date', required=True,
        default=fields.Date.today
    )
    department_id = fields.Many2one(
        'university.department', string='Department'
    )
    program_id = fields.Many2one(
        'university.program', string='Program',
        domain="[('department_id', '=', department_id)]"
    )
    batch_id = fields.Many2one(
        'university.batch', string='Batch',
        domain="[('program_id', '=', program_id)]"
    )
    course_id = fields.Many2one(
        'university.course', string='Course / Subject',
        domain="[('batch_id', '=', batch_id)]"
    )
    faculty_id = fields.Many2one(
        'faculty.faculty', string='Faculty'
    )

    # ── Step 2: Student Lines ─────────────────────────────────────────────
    line_ids = fields.One2many(
        'bulk.attendance.wizard.line', 'wizard_id',
        string='Students'
    )

    # ── Live Summary ──────────────────────────────────────────────────────
    total_count   = fields.Integer(compute='_compute_summary')
    present_count = fields.Integer(compute='_compute_summary')
    absent_count  = fields.Integer(compute='_compute_summary')
    late_count    = fields.Integer(compute='_compute_summary')

    @api.depends('line_ids.status')
    def _compute_summary(self):
        for rec in self:
            rec.total_count   = len(rec.line_ids)
            rec.present_count = len(rec.line_ids.filtered(lambda l: l.status == 'present'))
            rec.absent_count  = len(rec.line_ids.filtered(lambda l: l.status == 'absent'))
            rec.late_count    = len(rec.line_ids.filtered(lambda l: l.status == 'late'))

    # ── Onchange: clear downstream filters when parent changes ────────────
    @api.onchange('department_id')
    def _onchange_department(self):
        self.program_id = False
        self.batch_id   = False
        self.course_id  = False
        self.line_ids   = [(5, 0, 0)]

    @api.onchange('program_id')
    def _onchange_program(self):
        self.batch_id  = False
        self.course_id = False
        self.line_ids  = [(5, 0, 0)]

    @api.onchange('batch_id')
    def _onchange_batch(self):
        self.course_id = False
        self.line_ids  = [(5, 0, 0)]

    # ── Load Students — always defaults to Present ────────────────────────
    def action_load_students(self):
        if not self.batch_id and not self.department_id:
            raise UserError(_(
                'Please select at least a Department or Batch before loading students.'
            ))

        domain = []
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.program_id:
            domain.append(('program_id', '=', self.program_id.id))
        if self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))

        students = self.env['student.student'].search(domain)
        if not students:
            raise UserError(_('No students found for the selected filters.'))

        self.line_ids = [(5, 0, 0)]
        lines = []
        for student in students.sorted('registration_number'):
            lines.append((0, 0, {
                'student_id': student.id,
                'status':     'present',  # always default present
            }))
        self.line_ids = lines

        return {
            'type':      'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id':    self.id,
            'target':    'new',
        }

    # ── Mark All Present — reset if faculty made mistakes ─────────────────
    def action_mark_all_present(self):
        self.line_ids.write({'status': 'present'})
        return {
            'type':      'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id':    self.id,
            'target':    'new',
        }

    # ── Save Attendance ───────────────────────────────────────────────────
    def action_save_attendance(self):
        if not self.line_ids:
            raise UserError(_('No students loaded. Please load students first.'))

        StudentAttendance = self.env['student.attendance']
        for line in self.line_ids:
            existing = StudentAttendance.search([
                ('student_id', '=', line.student_id.id),
                ('course_id',  '=', self.course_id.id if self.course_id else False),
                ('date',       '=', self.date),
            ], limit=1)
            if existing:
                existing.state = line.status
            else:
                StudentAttendance.create({
                    'student_id': line.student_id.id,
                    'course_id':  self.course_id.id if self.course_id else False,
                    'faculty_id': self.faculty_id.id if self.faculty_id else False,
                    'date':       self.date,
                    'state':      line.status,
                })
        return {'type': 'ir.actions.act_window_close'}


class BulkAttendanceWizardLine(models.TransientModel):
    _name = 'bulk.attendance.wizard.line'
    _description = 'Bulk Attendance Wizard Line'
    _order = 'student_id'

    wizard_id = fields.Many2one(
        'bulk.attendance.wizard', required=True, ondelete='cascade'
    )
    student_id = fields.Many2one(
        'student.student', string='Student', required=True
    )
    registration_number = fields.Char(
        related='student_id.registration_number',
        string='Reg. No.', readonly=True
    )
    department_id = fields.Many2one(
        'university.department',
        related='student_id.department_id',
        string='Department', readonly=True
    )
    batch_id = fields.Many2one(
        'university.batch',
        related='student_id.batch_id',
        string='Batch', readonly=True
    )
    # Default present — faculty only changes the few who are absent/late
    status = fields.Selection([
        ('present',  'Present'),
        ('absent',   'Absent'),
        ('late',     'Late'),
        ('on_leave', 'On Leave'),
    ], string='Status', default='present', required=True)