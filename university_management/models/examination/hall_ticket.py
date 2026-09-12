# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup
import qrcode
import base64
from io import BytesIO


class ExaminationHallTicket(models.Model):
    _name = 'examination.hall.ticket'
    _description = 'Hall Ticket Generation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'issue_date desc'

    name = fields.Char(string='Hall Ticket Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    student_name = fields.Char(related='student_id.name', string='Student Name')
    student_photo = fields.Binary(related='student_id.student_photo', string='Photo')

    # Academic Details
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)
    batch_id = fields.Many2one(related='student_id.batch_id', string='Batch', store=True)

    # Examination
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True, index=True)
    academic_year_id = fields.Many2one(related='examination_id.academic_year_id',
                                       string='Academic Year', store=True)
    semester_id = fields.Many2one(related='examination_id.semester_id',
                                  string='Semester', store=True)

    # Exam Subjects
    exam_timetable_ids = fields.Many2many('examination.timetable',
                                          'hall_ticket_timetable_rel',
                                          'hall_ticket_id', 'timetable_id',
                                          string='Exam Schedule')

    # Issue Details
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today(),
                             tracking=True)
    issued_by = fields.Many2one('res.users', string='Issued By',
                                default=lambda self: self.env.user, readonly=True)

    # QR Code
    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True)
    qr_data = fields.Char(string='QR Data', compute='_compute_qr_data', store=True)

    # Instructions
    instructions = fields.Html(related='examination_id.instructions',
                               string='Exam Instructions')

    # Eligibility
    is_eligible = fields.Boolean(string='Eligible', default=True, tracking=True)
    ineligibility_reason = fields.Text(string='Ineligibility Reason')

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('downloaded', 'Downloaded'),
        ('printed', 'Printed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Download Info
    download_count = fields.Integer(string='Download Count', default=0)
    last_downloaded = fields.Datetime(string='Last Downloaded')

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Hall Ticket Number must be unique!'),
        ('unique_hall_ticket', 'unique(student_id, examination_id)',
         'Hall ticket already generated for this student and examination!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            student = self.env['student.student'].browse(vals.get('student_id'))
            vals['name'] = student.university_usn or \
                self.env['ir.sequence'].next_by_code('examination.hall.ticket') or '/'
        return super(ExaminationHallTicket, self).create(vals)

    @api.depends('student_id', 'name', 'examination_id')
    def _compute_qr_data(self):
        for record in self:
            if record.student_id and record.examination_id:
                qr_data = (f"HALL_TICKET:{record.name}|"
                           f"REG:{record.student_id.registration_number}|"
                           f"NAME:{record.student_id.name}|"
                           f"EXAM:{record.examination_id.name}")
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

    def action_issue(self):
        """Issue hall ticket"""
        self.write({'state': 'issued'})
        self._send_hall_ticket()

    def action_print(self):
        """Print hall ticket"""
        self.write({'state': 'printed'})
        return self.env.ref('university_management.action_report_hall_ticket').report_action(self)

    def action_download(self):
        """Mark as downloaded"""
        self.write({
            'state': 'downloaded',
            'download_count': self.download_count + 1,
            'last_downloaded': fields.Datetime.now()
        })

    def action_cancel(self):
        """Cancel hall ticket"""
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _send_hall_ticket(self):
        """Send hall ticket via email by building body directly in Python."""
        import logging
        _logger = logging.getLogger(__name__)

        recipient_email = self.student_id.email
        if not recipient_email:
            _logger.warning(
                "No recipient email found for hall ticket %s. Skipping email.", self.name
            )
            return

        student_name = self.student_id.name or ''
        exam_name = self.examination_id.name or ''
        hall_ticket_number = self.name or ''
        reg_number = self.student_id.registration_number or ''
        academic_year = self.examination_id.academic_year_id.name if self.examination_id.academic_year_id else ''
        semester = self.examination_id.semester_id.name if self.examination_id.semester_id else ''
        start_date = str(self.examination_id.start_date) if self.examination_id.start_date else 'N/A'
        end_date = str(self.examination_id.end_date) if self.examination_id.end_date else 'N/A'
        company_name = self.examination_id.company_id.name if self.examination_id.company_id else self.env.company.name
        email_from = (
                (self.examination_id.company_id.email if self.examination_id.company_id else False)
                or self.env.company.email
                or self.env.user.email
                or self.env['ir.config_parameter'].sudo().get_param('mail.default.from')
                or False
        )

        if not email_from:
            _logger.warning(
                "No sender email configured for hall ticket %s. Skipping email.", self.name
            )
            return
        portal_url = self.get_portal_url()

        body_html = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #2196F3; color: white; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">{company_name}</h2>
            <h3 style="margin: 10px 0 0 0;">Examination Hall Ticket</h3>
        </div>
        <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
            <p>Dear <strong>{student_name}</strong>,</p>
            <p>Your hall ticket for <strong>{exam_name}</strong> has been generated.</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="margin-top: 0;">Hall Ticket Details:</h4>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Hall Ticket Number:</strong></td>
                        <td style="padding: 5px 0;">{hall_ticket_number}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Student Name:</strong></td>
                        <td style="padding: 5px 0;">{student_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Registration Number:</strong></td>
                        <td style="padding: 5px 0;">{reg_number}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Examination:</strong></td>
                        <td style="padding: 5px 0;">{exam_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Academic Year:</strong></td>
                        <td style="padding: 5px 0;">{academic_year}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Semester:</strong></td>
                        <td style="padding: 5px 0;">{semester}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Exam Period:</strong></td>
                        <td style="padding: 5px 0;">{start_date} to {end_date}</td>
                    </tr>
                </table>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{portal_url}" style="background: #2196F3; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Download Hall Ticket
                </a>
            </div>
            <div style="background: #FFF3E0; border-left: 4px solid #FF9800; padding: 15px; margin: 20px 0;">
                <h4 style="margin-top: 0; color: #FF9800;">Important Instructions:</h4>
                <ul style="margin-bottom: 0;">
                    <li>Carry this hall ticket and a valid photo ID to the exam center</li>
                    <li>Report to the exam center 30 minutes before the scheduled time</li>
                    <li>Follow all examination rules and regulations</li>
                    <li>Mobile phones and electronic devices are not allowed</li>
                </ul>
            </div>
            <p>If you have any questions, please contact the examination department.</p>
            <p>Best regards,<br/>
            <strong>Examination Department</strong><br/>
            {company_name}</p>
        </div>
        <div style="background: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #ddd;">
            <p style="margin: 0;">This is an automated email. Please do not reply to this message.</p>
        </div>
    </div>
    """.format(
            student_name=student_name,
            exam_name=exam_name,
            hall_ticket_number=hall_ticket_number,
            reg_number=reg_number,
            academic_year=academic_year,
            semester=semester,
            start_date=start_date,
            end_date=end_date,
            company_name=company_name,
            portal_url=portal_url,
        )

        mail_values = {
            'subject': 'Hall Ticket for %s - %s' % (exam_name, student_name),
            'email_from': email_from,
            'email_to': recipient_email,
            'body_html': body_html,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    @api.model
    def _check_eligibility(self, student_id, examination_id):
        """Check if student is eligible for examination"""
        student = self.env['student.student'].browse(student_id)

        # Check attendance
        if student.attendance_percentage < 75:
            return False, "Attendance below 75%"

        # Check fee payment
        if student.total_fee_due > 0:
            return False, "Fee dues pending"

        # Check discipline issues
        major_disciplines = self.env['student.discipline'].search([
            ('student_id', '=', student_id),
            ('severity', 'in', ['major', 'critical']),
            ('state', '!=', 'closed')
        ])
        if major_disciplines:
            return False, "Pending discipline issues"

        return True, ""

    def get_portal_url(self):
        """Get portal URL for this hall ticket"""
        return f"/my/hall-ticket/{self.id}"