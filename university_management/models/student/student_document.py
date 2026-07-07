# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentDocument(models.Model):
    _name = 'student.document'
    _description = 'Student Document Verification (Aadhaar, TC, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)

    # Student
    student_id = fields.Many2one('student.student', string='Student', index=True)
    admission_id = fields.Many2one('student.admission', string='Admission Application', index=True)

    # Document Type
    document_type = fields.Selection([
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('birth_certificate', 'Birth Certificate'),
        ('tc', 'Transfer Certificate'),
        ('cc', 'Character Certificate'),
        ('migration', 'Migration Certificate'),
        ('marksheet_10', '10th Marksheet'),
        ('marksheet_12', '12th Marksheet'),
        ('degree', 'Degree Certificate'),
        ('caste', 'Caste Certificate'),
        ('income', 'Income Certificate'),
        ('passport', 'Passport'),
        ('photo', 'Passport Size Photo'),
        ('signature', 'Signature'),
        ('other', 'Other'),
    ], string='Document Type', required=True, tracking=True)

    # Document Details
    document_number = fields.Char(string='Document Number', tracking=True)
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    issuing_authority = fields.Char(string='Issuing Authority')

    # File Attachment
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=False)
    attachment_name = fields.Char(related='attachment_id.name', string='File Name')

    # Verification
    is_verified = fields.Boolean(string='Verified', tracking=True)
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verification_date = fields.Date(string='Verification Date', readonly=True)
    verification_notes = fields.Text(string='Verification Notes')

    # Mandatory
    is_mandatory = fields.Boolean(string='Mandatory Document', default=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    # Rejection
    rejection_reason = fields.Text(string='Rejection Reason')

    # Description
    description = fields.Text(string='Description')

    @api.constrains('document_number', 'document_type')
    def _check_document_number(self):
        for record in self:
            if record.document_type == 'aadhar' and record.document_number:
                import re
                if not re.match(r'^\d{12}$', record.document_number):
                    raise ValidationError(_('Aadhar number must be 12 digits!'))

            if record.document_type == 'pan' and record.document_number:
                import re
                if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', record.document_number):
                    raise ValidationError(_('Invalid PAN format! Format: ABCDE1234F'))

    def action_set_pending(self):
        """Move from draft to pending"""
        self.write({'state': 'pending'})

    def action_verify(self):
        """Verify document"""
        self.write({
            'is_verified': True,
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today()
        })

    def action_reject(self):
        """Reject document"""
        self.write({'state': 'rejected', 'is_verified': False})

    def action_submit(self):
        """Submit document for verification"""
        self.write({'state': 'submitted'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'is_verified': False,
                    'verified_by': False, 'verification_date': False})
