# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PlacementOffer(models.Model):
    _name = 'placement.offer'
    _description = 'Placement Offer Letters'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'offer_date desc'

    name = fields.Char(string='Offer Letter Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')

    # Placement Drive
    drive_id = fields.Many2one('placement.drive', string='Placement Drive',
                               required=True, tracking=True, index=True)
    company_id = fields.Many2one(related='drive_id.company_id', string='Company', store=True)
    application_id = fields.Many2one('placement.application', string='Application')

    # Offer Details
    offer_date = fields.Date(string='Offer Date', default=fields.Date.today(),
                             required=True, tracking=True)

    job_title = fields.Char(string='Job Title', required=True)
    job_location = fields.Char(string='Job Location')

    # Salary Package
    ctc = fields.Monetary(string='CTC (Per Annum)', required=True, currency_field='currency_id')
    fixed_component = fields.Monetary(string='Fixed Component', currency_field='currency_id')
    variable_component = fields.Monetary(string='Variable Component', currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Joining Details
    joining_date = fields.Date(string='Expected Joining Date', tracking=True)
    joining_location = fields.Char(string='Joining Location')

    # Bond Details
    has_bond = fields.Boolean(string='Service Bond')
    bond_duration = fields.Integer(string='Bond Duration (Months)')
    bond_amount = fields.Monetary(string='Bond Amount', currency_field='currency_id')

    # Offer Letter
    offer_letter = fields.Binary(string='Offer Letter', attachment=True)
    offer_letter_filename = fields.Char(string='Filename')

    # Acceptance
    acceptance_deadline = fields.Date(string='Acceptance Deadline')
    acceptance_date = fields.Date(string='Acceptance Date')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('offered', 'Offered'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ], string='Status', default='draft', tracking=True)

    # Rejection Reason
    rejection_reason = fields.Text(string='Rejection Reason')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Offer Letter Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('placement.offer') or '/'
        return super(PlacementOffer, self).create(vals)

    def action_send_offer(self):
        """Send offer letter to student via email."""
        import logging
        _logger = logging.getLogger(__name__)

        self.write({'state': 'offered'})

        recipient_email = self.student_id.email
        if not recipient_email:
            _logger.warning("No email for student on offer %s. Skipping.", self.name)
            return

        student_name = self.student_id.name or ''
        company_name = self.company_id.name if self.company_id else self.env.company.name
        job_title = self.job_title or ''
        ctc = '{:,.2f}'.format(self.ctc) if self.ctc else '0.00'
        job_location = self.job_location or 'N/A'
        joining_date = str(self.joining_date) if self.joining_date else 'N/A'
        acceptance_deadline = str(self.acceptance_deadline) if self.acceptance_deadline else 'N/A'
        email_from = (
                (self.company_id.email if self.company_id else False)
                or self.env.company.email
                or self.env.user.email
                or self.env['ir.config_parameter'].sudo().get_param('mail.default.from')
                or False
        )

        if not email_from:
            _logger.warning("No sender email configured for offer %s. Skipping.", self.name)
            return

        body_html = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #FF9800; color: white; padding: 20px; text-align: center;">
            <h1>Congratulations!</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <p>Dear <strong>{student_name}</strong>,</p>
            <p>We are delighted to inform you that you have been selected by <strong>{company_name}</strong>!</p>
            <div style="background: white; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #FF9800;">
                <h3 style="margin-top: 0;">Offer Details:</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Position:</strong></td>
                        <td style="padding: 5px 0;">{job_title}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>CTC:</strong></td>
                        <td style="padding: 5px 0;">&#8377; {ctc} LPA</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Location:</strong></td>
                        <td style="padding: 5px 0;">{job_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Joining Date:</strong></td>
                        <td style="padding: 5px 0;">{joining_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Acceptance Deadline:</strong></td>
                        <td style="padding: 5px 0;">{acceptance_deadline}</td>
                    </tr>
                </table>
            </div>
            <p>Please review the offer and respond before the deadline.</p>
            <p>Congratulations once again on your achievement!</p>
            <p>Best Regards,<br/>
            <strong>Placement Cell</strong><br/>
            {company_name}</p>
        </div>
    </div>
    """.format(
            student_name=student_name,
            company_name=company_name,
            job_title=job_title,
            ctc=ctc,
            job_location=job_location,
            joining_date=joining_date,
            acceptance_deadline=acceptance_deadline,
        )

        mail_values = {
            'subject': 'Congratulations! Placement Offer from %s' % company_name,
            'email_from': email_from,
            'email_to': recipient_email,
            'body_html': body_html,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def action_accept(self):
        self.write({
            'state': 'accepted',
            'acceptance_date': fields.Date.today()
        })

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_withdraw(self):
        self.write({'state': 'withdrawn'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
