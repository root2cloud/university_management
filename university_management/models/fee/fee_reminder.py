# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class FeeReminder(models.Model):
    _name = 'fee.reminder'
    _description = 'Automatic Fee Reminders to Parents'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reminder_date desc'

    name = fields.Char(string='Reminder Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    student_name = fields.Char(related='student_id.name', string='Student Name')
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')

    # Fee Structure
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure',
                                       required=True, tracking=True)
    total_fee = fields.Monetary(related='fee_structure_id.total_amount',
                                string='Total Fee', currency_field='currency_id')
    due_date = fields.Date(related='fee_structure_id.due_date', string='Due Date')

    partner_id = fields.Many2one(related='student_id.partner_id', string='Partner', store=False)

    # Accounting Integration
    invoice_id = fields.Many2one('account.move',
                                 string='Related Invoice',
                                 domain="[('move_type', '=', 'out_invoice'), ('partner_id', '=', student_id.partner_id)]")

    outstanding_amount = fields.Monetary(
        string='Outstanding Amount',
        compute='_compute_outstanding_amount',
        store=True,
        currency_field='currency_id')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='fee_structure_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Reminder Details
    reminder_date = fields.Date(string='Reminder Date', default=fields.Date.today(),
                                required=True, tracking=True)
    reminder_type = fields.Selection([
        ('before_due', 'Before Due Date'),
        ('on_due', 'On Due Date'),
        ('after_due', 'After Due Date - First Reminder'),
        ('second', 'Second Reminder'),
        ('final', 'Final Notice'),
    ], string='Reminder Type', required=True, default='before_due', tracking=True)

    # Days
    days_before_due = fields.Integer(string='Days Before Due')
    days_after_due = fields.Integer(string='Days After Due')

    # Communication
    send_email = fields.Boolean(string='Send Email', default=True)
    send_sms = fields.Boolean(string='Send SMS', default=True)

    email_sent = fields.Boolean(string='Email Sent', readonly=True)
    email_sent_date = fields.Datetime(string='Email Sent Date', readonly=True)

    sms_sent = fields.Boolean(string='SMS Sent', readonly=True)
    sms_sent_date = fields.Datetime(string='SMS Sent Date', readonly=True)

    # Recipients
    parent_ids = fields.Many2many('student.parent', string='Parents',
                                  compute='_compute_parents', store=True)
    recipient_emails = fields.Char(string='Recipient Emails', compute='_compute_recipients')
    recipient_phones = fields.Char(string='Recipient Phones', compute='_compute_recipients')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', tracking=True)

    # Message Content
    email_subject = fields.Char(string='Email Subject', compute='_compute_message_content')
    email_body = fields.Html(string='Email Body', compute='_compute_message_content')
    sms_body = fields.Text(string='SMS Body', compute='_compute_message_content')

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Reminder Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('fee.reminder') or '/'
        return super(FeeReminder, self).create(vals)

    @api.depends('invoice_id')
    def _compute_outstanding_amount(self):
        """Compute outstanding amount from invoice"""
        for record in self:
            if record.invoice_id and record.invoice_id.state == 'posted':
                record.outstanding_amount = record.invoice_id.amount_residual
            else:
                # If no invoice, use the amount from fee structure
                record.outstanding_amount = record.total_fee

    @api.depends('student_id')
    def _compute_parents(self):
        for record in self:
            record.parent_ids = record.student_id.parent_ids

    @api.depends('parent_ids')
    def _compute_recipients(self):
        for record in self:
            emails = record.parent_ids.filtered(lambda p: p.email).mapped('email')
            record.recipient_emails = ', '.join(emails) if emails else ''

            phones = record.parent_ids.filtered(lambda p: p.phone).mapped('phone')
            record.recipient_phones = ', '.join(phones) if phones else ''

    @api.depends('student_id', 'fee_structure_id', 'reminder_type', 'outstanding_amount')
    def _compute_message_content(self):
        for record in self:
            # Email Subject
            record.email_subject = f"Fee Payment Reminder - {record.student_id.name}"

            # Email Body
            record.email_body = f"""
                <p>Dear Parent,</p>
                <p>This is a reminder regarding the fee payment for your ward <strong>{record.student_id.name}</strong> 
                (Registration: {record.student_id.registration_number}).</p>

                <p><strong>Fee Details:</strong></p>
                <ul>
                    <li>Total Fee: {record.total_fee} {record.currency_id.symbol}</li>
                    <li>Outstanding Amount: {record.outstanding_amount} {record.currency_id.symbol}</li>
                    <li>Due Date: {record.due_date}</li>
                </ul>

                <p>Please make the payment at the earliest to avoid late fees.</p>

                <p>Best Regards,<br/>
                University Administration</p>
            """

            # SMS Body
            record.sms_body = f"Fee Reminder: {record.student_id.name} has pending fee of Rs.{record.outstanding_amount}. Due: {record.due_date}. Please pay soon. -University"

    def action_reset_to_draft(self):
        """Reset reminder back to draft"""
        for record in self:
            record.write({
                'state': 'draft',
                'email_sent': False,
                'email_sent_date': False,
                'sms_sent': False,
                'sms_sent_date': False,
            })
        return True

    def action_schedule(self):
        """Schedule reminder for sending"""
        for record in self:
            if not record.parent_ids:
                raise ValidationError(_(
                    'No parent contact details found for this student. '
                    'Please update parent information before scheduling reminders.'
                ))
            record.write({'state': 'scheduled'})
        return True

    def action_send_reminder(self):
        """Send reminder via email and SMS"""
        for record in self:
            if not record.parent_ids:
                raise ValidationError(_(
                    'No parent contact details found for this student. '
                    'Please update parent information before sending reminders.'
                ))

            try:
                if record.send_email:
                    record._send_email_reminder()

                if record.send_sms:
                    record._send_sms_reminder()

                record.write({'state': 'sent'})
            except Exception as e:
                _logger.error(f"Failed to send reminder {record.name}: {str(e)}", exc_info=True)
                record.write({'state': 'failed'})
                raise ValidationError(_(
                    'Failed to send reminder: %s\nPlease check email/SMS configuration and try again.'
                ) % str(e))

        return True

    def action_resend(self):
        """Resend reminder"""
        for record in self:
            record.write({
                'email_sent': False,
                'email_sent_date': False,
                'sms_sent': False,
                'sms_sent_date': False,
                'state': 'scheduled'
            })
            record.action_send_reminder()
        return True

    def _send_email_reminder(self):
        """Send email reminder by building body directly in Python."""
        recipient_emails = self.recipient_emails or self.student_id.email
        if not recipient_emails:
            _logger.warning(
                "No recipient email found for reminder %s. Skipping email.", self.name
            )
            return

        student_name = self.student_id.name or ''
        outstanding = '{:,.2f}'.format(self.outstanding_amount)
        due_date = str(self.due_date) if self.due_date else 'N/A'
        company_name = self.company_id.name or self.env.company.name
        email_from = self.company_id.email or self.env.company.email or self.env.user.email_formatted

        portal_url = self.student_id.get_portal_url() if hasattr(self.student_id, 'get_portal_url') else '#'

        body_html = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #FF5722; color: white; padding: 20px; text-align: center;">
        <h1>Fee Payment Reminder</h1>
    </div>
    <div style="padding: 20px; background: #f9f9f9;">
        <p>Dear <strong>{student_name}</strong>,</p>
        <p>This is a friendly reminder regarding your pending fee payment.</p>
        <div style="background: white; padding: 15px; border-left: 4px solid #FF5722; margin: 20px 0;">
            <h3 style="margin-top: 0;">Outstanding Amount: <span style="color: #FF5722;">&#8377; {outstanding}</span></h3>
        </div>
        <p><strong>Due Date:</strong> {due_date}</p>
        <p>Please make the payment at your earliest convenience to avoid any late fees or restrictions.</p>
        <div style="text-align: center; margin: 20px 0;">
            <a href="{portal_url}" style="background: #FF5722; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                Pay Now
            </a>
        </div>
        <p>For any queries, please contact the Accounts Office.</p>
        <p>Best Regards,<br/>
        <strong>Accounts Department</strong><br/>
        {company_name}</p>
    </div>
</div>
""".format(
            student_name=student_name,
            outstanding=outstanding,
            due_date=due_date,
            company_name=company_name,
            portal_url=portal_url,
        )

        mail_values = {
            'subject': 'Fee Payment Reminder - %s' % student_name,
            'email_from': email_from,
            'email_to': recipient_emails,
            'body_html': body_html,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

        self.write({
            'email_sent': True,
            'email_sent_date': fields.Datetime.now(),
        })

    def _send_sms_reminder(self):
        """Send SMS reminder"""
        # Implement SMS sending logic here
        # This would integrate with SMS gateway
        self.write({
            'sms_sent': True,
            'sms_sent_date': fields.Datetime.now()
        })

    @api.model
    def _cron_generate_reminders(self):
        """Scheduled action to generate automatic reminders"""
        today = fields.Date.today()

        # Get all invoices with outstanding amounts
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '!=', False),
        ])

        for invoice in invoices:
            # Find student from partner
            student = self.env['student.student'].search([
                ('partner_id', '=', invoice.partner_id.id)
            ], limit=1)

            if not student:
                continue

            # Calculate days difference
            days_diff = (invoice.invoice_date_due - today).days

            # Get fee structure
            fee_structure = self.env['fee.structure'].search([
                ('program_id', '=', student.program_id.id),
                ('state', '=', 'active')
            ], limit=1)

            if fee_structure:
                # Generate reminders based on due date
                # Before due date (7 days before)
                if days_diff == 7:
                    self._create_reminder(student, fee_structure, 'before_due', invoice.amount_residual, invoice)

                # On due date
                elif days_diff == 0:
                    self._create_reminder(student, fee_structure, 'on_due', invoice.amount_residual, invoice)

                # After due date
                elif days_diff < 0:
                    days_overdue = abs(days_diff)
                    if days_overdue == 7:
                        self._create_reminder(student, fee_structure, 'after_due', invoice.amount_residual, invoice)
                    elif days_overdue == 14:
                        self._create_reminder(student, fee_structure, 'second', invoice.amount_residual, invoice)
                    elif days_overdue == 30:
                        self._create_reminder(student, fee_structure, 'final', invoice.amount_residual, invoice)

    def _create_reminder(self, student, fee_structure, reminder_type, outstanding, invoice=False):
        """Create and send reminder"""
        existing = self.search([
            ('student_id', '=', student.id),
            ('fee_structure_id', '=', fee_structure.id),
            ('reminder_type', '=', reminder_type),
            ('reminder_date', '=', fields.Date.today())
        ])

        if not existing:
            reminder = self.create({
                'student_id': student.id,
                'fee_structure_id': fee_structure.id,
                'invoice_id': invoice.id if invoice else False,
                'reminder_type': reminder_type,
                'state': 'scheduled'
            })
            reminder.action_send_reminder()