# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentAdmission(models.Model):
    _name = 'student.admission'
    _description = 'Student Admission Process'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'application_date desc'

    name = fields.Char(string='Application Number', required=True, readonly=True,
                       copy=False, default='/')

    # Applicant Details
    applicant_name = fields.Char(string='Applicant Name', required=True, tracking=True)
    email = fields.Char(string='Email', required=True, tracking=True)
    mobile = fields.Char(string='Mobile', required=True, tracking=True)
    date_of_birth = fields.Date(string='Date of Birth', required=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender', required=True)

    # Photo
    applicant_photo = fields.Binary(string='Photo', attachment=True)

    # Program Selection
    program_id = fields.Many2one('university.program', string='Applied Program',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one(related='program_id.department_id',
                                    string='Department', store=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)
    batch_id = fields.Many2one('university.batch', string='Batch')

    # Application Details
    application_date = fields.Date(string='Application Date', default=fields.Date.today(),
                                   required=True, tracking=True)

    # Category
    admission_category = fields.Selection([
        ('general', 'General'),
        ('obc', 'OBC'),
        ('sc', 'SC'),
        ('st', 'ST'),
        ('ews', 'EWS'),
    ], string='Category', required=True, default='general')

    # Previous Education
    previous_qualification = fields.Char(string='Previous Qualification', required=True)
    previous_school = fields.Char(string='Previous School/College', required=True)
    previous_board = fields.Char(string='Board/University', required=True)
    previous_percentage = fields.Float(string='Percentage/CGPA', required=True)
    previous_year = fields.Integer(string='Year of Passing', required=True)

    # Entrance Exam
    entrance_exam_taken = fields.Boolean(string='Entrance Exam Taken')
    entrance_exam_name = fields.Char(string='Exam Name')
    entrance_exam_score = fields.Float(string='Score')
    entrance_exam_rank = fields.Integer(string='Rank')
    entrance_exam_percentile = fields.Float(string='Percentile')

    # Address
    current_address = fields.Text(string='Current Address', required=True)
    permanent_address = fields.Text(string='Permanent Address', required=True)
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.ref('base.in'))

    # Documents
    document_ids = fields.One2many('student.document', 'admission_id', string='Documents')
    documents_verified = fields.Boolean(string='All Documents Verified',
                                        compute='_compute_documents_verified', store=True)

    # Parent/Guardian Details
    father_name = fields.Char(string="Father's Name", required=True)
    father_occupation = fields.Char(string="Father's Occupation")
    father_mobile = fields.Char(string="Father's Mobile")
    father_email = fields.Char(string="Father's Email")

    mother_name = fields.Char(string="Mother's Name", required=True)
    mother_occupation = fields.Char(string="Mother's Occupation")
    mother_mobile = fields.Char(string="Mother's Mobile")
    mother_email = fields.Char(string="Mother's Email")

    guardian_name = fields.Char(string="Guardian's Name")
    guardian_relation = fields.Char(string="Relation with Guardian")
    guardian_mobile = fields.Char(string="Guardian's Mobile")
    guardian_email = fields.Char(string="Guardian's Email")

    annual_income = fields.Monetary(string='Family Annual Income', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Fee Details
    application_fee = fields.Monetary(string='Application Fee', currency_field='currency_id',
                                      default=500.0)
    application_fee_paid = fields.Boolean(string='Application Fee Paid', tracking=True)
    application_payment_ref = fields.Char(string='Payment Reference')
    application_payment_date = fields.Date(string='Payment Date')

    admission_fee = fields.Monetary(string='Admission Fee', currency_field='currency_id')
    admission_fee_paid = fields.Boolean(string='Admission Fee Paid', tracking=True)
    admission_payment_ref = fields.Char(string='Admission Payment Reference')
    admission_payment_date = fields.Date(string='Admission Payment Date')

    # Admission Decision
    admission_date = fields.Date(string='Admission Date', tracking=True)
    admission_letter_sent = fields.Boolean(string='Admission Letter Sent')
    admission_letter_date = fields.Date(string='Admission Letter Date')

    # Student Record
    student_id = fields.Many2one('student.student', string='Student Record', readonly=True)

    # ── Temporary ID & University Verification ────────────────────────
    temp_student_id = fields.Char(
        string='Temporary Student ID', readonly=True, copy=False,
        help='Mirrored from student record on admission.',
    )
    university_submitted_date = fields.Date(
        string='Sent to University On', readonly=True,
    )
    university_verified_date = fields.Date(
        string='University Verified On', tracking=True,
    )
    university_usn = fields.Char(
        string='University USN', tracking=True,
        help='Official USN received from the university. Enter and click Map USN.',
    )

    # Rejection
    rejection_reason = fields.Text(string='Rejection Reason')
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_date = fields.Date(string='Rejection Date', readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Application Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('admitted', 'Admitted'),
        ('university_verification', 'University Verification'),
        ('usn_mapped', 'USN Mapped'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # Notes
    notes = fields.Text(string='Notes')
    internal_notes = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Application Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('student.admission') or '/'
        return super(StudentAdmission, self).create(vals)

    @api.depends('document_ids', 'document_ids.is_verified')
    def _compute_documents_verified(self):
        for record in self:
            if record.document_ids:
                record.documents_verified = all(doc.is_verified for doc in record.document_ids)
            else:
                record.documents_verified = False

    @api.constrains('previous_percentage')
    def _check_percentage(self):
        for record in self:
            if record.previous_percentage < 0 or record.previous_percentage > 100:
                raise ValidationError(_('Percentage must be between 0 and 100!'))

    def action_submit(self):
        """Submit application"""
        if not self.application_fee_paid:
            raise ValidationError(_('Application fee must be paid before submission!'))
        self.write({'state': 'submitted'})
        self._send_application_confirmation()

    def action_review(self):
        """Move to review"""
        self.write({'state': 'under_review'})

    def action_approve(self):
        """Approve application"""
        self.write({'state': 'approved'})
        self._send_approval_notification()

    def action_reject(self):
        """Reject application"""
        self.write({
            'state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejection_date': fields.Date.today()
        })
        self._send_rejection_notification()

    def action_admit_student(self):
        """Create student record and admit"""
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('Only approved applications can be admitted!'))

        if not self.admission_fee_paid:
            raise ValidationError(_('Admission fee must be paid!'))

        if not self.documents_verified:
            raise ValidationError(_('All documents must be verified!'))

        # Create Student Record
        student_vals = {
            'name': self.applicant_name,
            'email': self.email,
            'mobile': self.mobile,
            'date_of_birth': self.date_of_birth,
            'gender': self.gender,
            'student_photo': self.applicant_photo,
            'program_id': self.program_id.id,
            'department_id': self.department_id.id,
            'batch_id': self.batch_id.id,
            'academic_year_id': self.academic_year_id.id,
            'admission_id': self.id,
            'admission_date': fields.Date.today(),
            'admission_category': self.admission_category,
            'previous_qualification': self.previous_qualification,
            'previous_institution': self.previous_school,
            'previous_percentage': self.previous_percentage,
            'previous_year': self.previous_year,
            'current_address': self.current_address,
            'permanent_address': self.permanent_address,
            'state': 'admitted',
        }

        student = self.env['student.student'].create(student_vals)

        # Mirror auto-generated temp_student_id back to the admission record
        self.temp_student_id = student.temp_student_id

        # Create Parent Records
        self._create_parent_records(student)

        # Link Documents
        self.document_ids.write({'student_id': student.id})

        self.write({
            'state': 'admitted',
            'admission_date': fields.Date.today(),
            'student_id': student.id
        })

        self._send_admission_confirmation()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Record'),
            'res_model': 'student.student',
            'res_id': student.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_to_university(self):
        """Move to University Verification stage after internal admission."""
        self.ensure_one()
        if self.state != 'admitted':
            raise ValidationError(_(
                'Only fully admitted students can be sent for university verification.'
            ))
        self.write({
            'state': 'university_verification',
            'university_submitted_date': fields.Date.today(),
        })
        self.message_post(
            body=_('Admission data submitted to university. '
                   'Temporary Student ID: <b>%s</b>. Awaiting USN.') % self.temp_student_id
        )

    def action_map_usn_from_admission(self):
        """Map university USN and complete the student lifecycle."""
        self.ensure_one()
        if self.state != 'university_verification':
            raise ValidationError(_(
                'USN can only be mapped after submission to the university.'
            ))
        if not self.university_usn:
            raise ValidationError(_('Please enter the University USN received from the university.'))
        if not self.student_id:
            raise ValidationError(_('No linked student record found. Please admit the student first.'))
        self.student_id.university_usn = self.university_usn
        self.student_id.action_map_usn()
        self.write({
            'state': 'usn_mapped',
            'university_verified_date': fields.Date.today(),
        })
        self.message_post(
            body=_('University USN <b>%s</b> mapped. '
                   'Temporary ID <b>%s</b> retired. Student lifecycle is now active.')
            % (self.university_usn, self.temp_student_id)
        )

    def _create_parent_records(self, student):
        """Create parent/guardian records for student"""
        ParentObj = self.env['student.parent']

        # Father
        if self.father_name:
            ParentObj.create({
                'student_id': student.id,
                'name': self.father_name,
                'relationship': 'father',
                'occupation': self.father_occupation,
                'phone': self.father_mobile,
                'email': self.father_email,
                'is_primary_contact': True,
                'is_emergency_contact': True,
            })

        # Mother
        if self.mother_name:
            ParentObj.create({
                'student_id': student.id,
                'name': self.mother_name,
                'relationship': 'mother',
                'occupation': self.mother_occupation,
                'phone': self.mother_mobile,
                'email': self.mother_email,
            })

        # Guardian
        if self.guardian_name:
            ParentObj.create({
                'student_id': student.id,
                'name': self.guardian_name,
                'relationship': self.guardian_relation or 'guardian',
                'phone': self.guardian_mobile,
                'email': self.guardian_email,
            })

    def action_view_student(self):
        """View created student record"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student Record'),
            'res_model': 'student.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _send_application_confirmation(self):
        """Send application confirmation email"""
        template = self.env.ref('university_management.email_template_application_confirmation',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_approval_notification(self):
        """Send approval notification"""
        template = self.env.ref('university_management.email_template_application_approved',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_rejection_notification(self):
        """Send rejection notification"""
        template = self.env.ref('university_management.email_template_application_rejected',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_admission_confirmation(self):
        """Send admission confirmation"""
        template = self.env.ref('university_management.email_template_admission_confirmation',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)