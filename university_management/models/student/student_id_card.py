# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import qrcode
import base64
from io import BytesIO


class StudentIdCard(models.Model):
    _name = 'student.id.card'
    _description = 'Student ID Card Generation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc'

    name = fields.Char(string='ID Card Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    student_name = fields.Char(related='student_id.name', string='Student Name')
    student_photo = fields.Binary(related='student_id.student_photo', string='Photo')

    # Academic
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)
    batch_id = fields.Many2one(related='student_id.batch_id', string='Batch', store=True)

    # Card Details
    card_type = fields.Selection([
        ('regular', 'Regular ID Card'),
        ('temporary', 'Temporary ID Card'),
        ('duplicate', 'Duplicate ID Card'),
    ], string='Card Type', default='regular', required=True, tracking=True)

    # Validity
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today(),
                             required=True, tracking=True)
    expiry_date = fields.Date(string='Expiry Date', required=True, tracking=True)
    is_valid = fields.Boolean(string='Valid', compute='_compute_validity', store=True)

    # QR Code
    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True)
    qr_data = fields.Char(string='QR Data', compute='_compute_qr_data', store=True)

    # Barcode
    barcode = fields.Char(string='Barcode')

    # Contact
    emergency_contact = fields.Char(related='student_id.emergency_contact',
                                    string='Emergency Contact')
    blood_group = fields.Selection(related='student_id.blood_group', string='Blood Group')

    # Issue Details
    issued_by = fields.Many2one('res.users', string='Issued By',
                                default=lambda self: self.env.user, readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('printed', 'Printed'),
        ('issued', 'Issued'),
        ('expired', 'Expired'),
        ('lost', 'Lost/Stolen'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Lost/Duplicate
    is_duplicate = fields.Boolean(string='Is Duplicate')
    original_card_id = fields.Many2one('student.id.card', string='Original Card')
    lost_date = fields.Date(string='Lost Date')
    lost_reason = fields.Text(string='Lost Reason')

    # Fee for Duplicate
    duplicate_fee = fields.Monetary(string='Duplicate Card Fee', currency_field='currency_id')
    duplicate_fee_paid = fields.Boolean(string='Fee Paid')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'ID Card Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('student.id.card') or '/'
        return super(StudentIdCard, self).create(vals)

    @api.depends('expiry_date')
    def _compute_validity(self):
        today = fields.Date.today()
        for record in self:
            record.is_valid = record.expiry_date >= today if record.expiry_date else False

    @api.depends('student_id', 'name', 'issue_date', 'expiry_date')
    def _compute_qr_data(self):
        for record in self:
            if record.student_id:
                qr_data = f"ID:{record.name}|REG:{record.student_id.registration_number}|NAME:{record.student_id.name}|PROGRAM:{record.program_id.name}|VALID:{record.issue_date} to {record.expiry_date}"
                record.qr_data = qr_data
            else:
                record.qr_data = False

    @api.depends('qr_data')
    def _compute_qr_code(self):
        for record in self:
            if record.qr_data:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(record.qr_data)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code = base64.b64encode(buffer.getvalue())
            else:
                record.qr_code = False

    def action_print(self):
        """Mark as printed"""
        self.write({'state': 'printed'})
        return self.env.ref('university_management.action_report_student_id_card').report_action(self)

    def action_issue(self):
        """Issue ID card to student"""
        self.write({'state': 'issued'})

    def action_report_lost(self):
        """Report ID card as lost"""
        self.write({
            'state': 'lost',
            'lost_date': fields.Date.today()
        })

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_generate_duplicate(self):
        """Generate duplicate ID card"""
        self.ensure_one()

        duplicate = self.copy({
            'card_type': 'duplicate',
            'is_duplicate': True,
            'original_card_id': self.id,
            'state': 'draft',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicate ID Card'),
            'res_model': 'student.id.card',
            'res_id': duplicate.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel ID card"""
        self.write({'state': 'cancelled'})


class StudentLeave(models.Model):
    _name = 'student.leave'
    _description = 'Student Leave Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'

    name = fields.Char(string='Leave Number', required=True, readonly=True, default='/')

    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)

    date_from = fields.Date(string='From Date', required=True, tracking=True)
    date_to = fields.Date(string='To Date', required=True, tracking=True)
    number_of_days = fields.Integer(string='Number of Days', compute='_compute_days', store=True)

    leave_type = fields.Selection([
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('emergency', 'Emergency Leave'),
        ('other', 'Other'),
    ], string='Leave Type', required=True)

    reason = fields.Text(string='Reason', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    rejection_reason = fields.Text(string="Rejection Reason")

    # You might also want to add:
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    note = fields.Text(string="Comments")

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approval Date', readonly=True)

    @api.depends('date_from', 'date_to')
    def _compute_days(self):
        for record in self:
            if record.date_from and record.date_to:
                record.number_of_days = (record.date_to - record.date_from).days + 1
            else:
                record.number_of_days = 0

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('student.leave') or '/'
        return super(StudentLeave, self).create(vals)

    def action_submit(self):
        """Submit leave application for approval"""
        self.write({
            'state': 'submitted'
        })
        # Optionally send email notification

    def action_approve(self):
        """Approve leave application"""
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today()
        })

    def action_reject(self):
        """Reject leave application"""
        self.write({
            'state': 'rejected',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today()
        })

    def action_set_draft(self):
        """Reset leave application to draft"""
        self.write({
            'state': 'draft',
            'approved_by': False,
            'approval_date': False
        })


class IDCardRequest(models.Model):
    _name = 'id.card.request'
    _description = 'ID Card Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Request Number",
                       readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('id.card.request'))

    student_id = fields.Many2one('student.student', required=True)
    request_type = fields.Selection([
        ('duplicate', 'Duplicate'),
        ('renewal', 'Renewal'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
        ('other', 'Other')
    ], required=True)
    reason = fields.Text(required=True)
    request_date = fields.Date(default=fields.Date.today())
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed')
    ], default='draft')
    approved_by = fields.Many2one('res.users')
    approval_date = fields.Date()

    urgency_level = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='normal')

    processing_fee = fields.Float(string="Processing Fee")
    estimated_delivery_date = fields.Date(string="Estimated Delivery")
    delivery_method = fields.Selection([
        ('pickup', 'College Pickup'),
        ('courier', 'Courier'),
        ('post', 'Post')
    ])

    new_card_issue_date = fields.Date(string="New Card Issue Date")
    new_card_expiry_date = fields.Date(string="New Card Expiry Date")
    new_card_number = fields.Char(string="New Card Number")

    rejection_reason = fields.Text(string="Rejection Reason")
    completion_notes = fields.Text(string="Completion Notes")

    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    lost_police_complaint = fields.Binary(string="Police Complaint")

    def action_submit(self):
        """Submit the ID card request for approval."""
        for request in self:
            if request.state == 'draft':
                request.write({
                    'state': 'submitted'
                })
        return True

    def action_approve(self):
        """Approve the ID card request."""
        for request in self:
            if request.state == 'submitted':
                request.write({
                    'state': 'approved',
                    'approved_by': self.env.user.id,
                    'approval_date': fields.Date.today()
                })
        return True

    def action_reject(self):
        """Reject the ID card request."""
        # Note: You might want to open a wizard for rejection reason
        # For now, we'll just change the state
        for request in self:
            if request.state == 'submitted':
                request.write({
                    'state': 'rejected',
                    'approved_by': self.env.user.id,
                    'approval_date': fields.Date.today()
                })
        return True

    def action_complete(self):
        """Mark the ID card request as completed."""
        for request in self:
            if request.state == 'approved':
                request.write({
                    'state': 'completed'
                })
        return True

    def action_set_draft(self):
        """Reset the request to draft state."""
        for request in self:
            if request.state in ['submitted', 'approved', 'rejected', 'completed']:
                request.write({
                    'state': 'draft',
                    'approved_by': False,
                    'approval_date': False,
                    'rejection_reason': False
                })
        return True

    # You might also want to add a computed field for number of days
    @api.depends('request_date')
    def _compute_days_since_request(self):
        for request in self:
            if request.request_date:
                delta = fields.Date.today() - request.request_date
                request.days_since_request = delta.days
            else:
                request.days_since_request = 0

    days_since_request = fields.Integer(
        string="Days Since Request",
        compute='_compute_days_since_request',
        store=True
    )
