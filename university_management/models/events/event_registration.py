# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EventRegistration(models.Model):
    _name = 'university.event.registration'
    _description = 'Event Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'registration_date desc'

    name = fields.Char(string='Registration Number', required=True, readonly=True,
                       copy=False, default='/')

    # Event
    event_id = fields.Many2one('university.event', string='Event',
                               required=True, tracking=True, index=True)

    # Participant Type
    participant_type = fields.Selection([
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('external', 'External Participant'),
    ], string='Participant Type', required=True)

    # Participant
    student_id = fields.Many2one('student.student', string='Student')
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty')
    partner_id = fields.Many2one('res.partner', string='External Participant')

    participant_name = fields.Char(string='Name', compute='_compute_participant_name', store=True)
    participant_email = fields.Char(string='Email', compute='_compute_participant_details')
    participant_phone = fields.Char(string='Phone', compute='_compute_participant_details')

    # Registration Details
    registration_date = fields.Datetime(string='Registration Date', default=fields.Datetime.now,
                                        required=True)

    # Fee Payment
    registration_fee = fields.Monetary(related='event_id.registration_fee',
                                       string='Registration Fee')
    fee_paid = fields.Boolean(string='Fee Paid', tracking=True)
    payment_date = fields.Date(string='Payment Date')
    payment_reference = fields.Char(string='Payment Reference')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Attendance
    attended = fields.Boolean(string='Attended', tracking=True)
    attendance_time = fields.Datetime(string='Attendance Time')

    # Certificate
    certificate_issued = fields.Boolean(string='Certificate Issued')
    certificate = fields.Binary(string='Certificate', attachment=True)
    certificate_number = fields.Char(string='Certificate Number')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('attended', 'Attended'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Registration Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('university.event.registration') or '/'
        return super(EventRegistration, self).create(vals)

    @api.depends('participant_type', 'student_id', 'faculty_id', 'partner_id')
    def _compute_participant_name(self):
        for record in self:
            if record.participant_type == 'student' and record.student_id:
                record.participant_name = record.student_id.name
            elif record.participant_type == 'faculty' and record.faculty_id:
                record.participant_name = record.faculty_id.name
            elif record.participant_type == 'external' and record.partner_id:
                record.participant_name = record.partner_id.name
            else:
                record.participant_name = ''

    @api.depends('participant_type', 'student_id', 'faculty_id', 'partner_id')
    def _compute_participant_details(self):
        for record in self:
            if record.participant_type == 'student' and record.student_id:
                record.participant_email = record.student_id.email
                record.participant_phone = record.student_id.mobile
            elif record.participant_type == 'faculty' and record.faculty_id:
                record.participant_email = record.faculty_id.work_email
                record.participant_phone = record.faculty_id.work_mobile
            elif record.participant_type == 'external' and record.partner_id:
                record.participant_email = record.partner_id.email
                record.participant_phone = record.partner_id.phone
            else:
                record.participant_email = ''
                record.participant_phone = ''

    @api.constrains('event_id', 'student_id', 'faculty_id', 'partner_id')
    def _check_max_participants(self):
        for record in self:
            if record.event_id.max_participants:
                total = len(record.event_id.registration_ids.filtered(
                    lambda r: r.state in ['registered', 'attended']))
                if total > record.event_id.max_participants:
                    raise ValidationError(_('Maximum participants limit reached!'))

    def action_register(self):
        self.write({'state': 'registered'})

    def action_mark_attended(self):
        self.write({
            'state': 'attended',
            'attended': True,
            'attendance_time': fields.Datetime.now()
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
