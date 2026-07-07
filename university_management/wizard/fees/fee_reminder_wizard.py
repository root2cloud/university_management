# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)


class FeeReminderWizard(models.TransientModel):
    """
    Wizard to send fee payment reminders to students/parents
    """
    _name = 'fee.reminder.wizard'
    _description = 'Fee Reminder Wizard'

    reminder_type = fields.Selection([
        ('pending', 'Pending Payments'),
        ('overdue', 'Overdue Payments'),
        ('upcoming', 'Upcoming Due Dates'),
        ('custom', 'Custom Selection')
    ], string='Reminder Type', default='overdue', required=True)

    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')
    batch_id = fields.Many2one('university.batch', string='Batch')
    semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Semester')

    student_ids = fields.Many2many('student.student', string='Students')
    fee_payment_ids = fields.Many2many('fee.payment', string='Fee Payments')

    send_to = fields.Selection([
        ('student', 'Student'),
        ('parent', 'Parent/Guardian'),
        ('both', 'Both')
    ], string='Send To', default='both', required=True)

    send_email = fields.Boolean(string='Send Email', default=True)
    send_sms = fields.Boolean(string='Send SMS', default=True)

    email_template_id = fields.Many2one('mail.template', string='Email Template',
                                        domain=[('model', '=', 'fee.payment')])
    sms_template_id = fields.Many2one('sms.template', string='SMS Template')

    custom_message = fields.Text(string='Custom Message')

    preview_count = fields.Integer(string='Recipients Count', compute='_compute_preview_count')

    @api.depends('reminder_type', 'program_id', 'department_id', 'batch_id', 'student_ids', 'fee_payment_ids')
    def _compute_preview_count(self):
        """Compute number of reminders to be sent"""
        for wizard in self:
            if wizard.reminder_type == 'custom':
                wizard.preview_count = len(wizard.fee_payment_ids)
            else:
                payments = wizard._get_fee_payments()
                wizard.preview_count = len(payments)

    @api.onchange('reminder_type')
    def _onchange_reminder_type(self):
        """Update default template based on reminder type"""
        if self.reminder_type == 'overdue':
            self.email_template_id = self.env.ref(
                'university_management.email_template_fee_overdue_reminder',
                raise_if_not_found=False)
        elif self.reminder_type == 'upcoming':
            self.email_template_id = self.env.ref(
                'university_management.email_template_fee_upcoming_reminder',
                raise_if_not_found=False)
        else:
            self.email_template_id = self.env.ref(
                'university_management.email_template_fee_pending_reminder',
                raise_if_not_found=False)

    def _get_fee_payments(self):
        """Get fee payments based on reminder type and filters"""
        domain = [('state', '=', 'pending')]

        if self.reminder_type == 'overdue':
            domain.append(('due_date', '<', fields.Date.today()))
        elif self.reminder_type == 'upcoming':
            upcoming_date = fields.Date.today() + timedelta(days=7)
            domain.extend([
                ('due_date', '>=', fields.Date.today()),
                ('due_date', '<=', upcoming_date)
            ])

        # Apply filters
        if self.program_id:
            domain.append(('student_id.program_id', '=', self.program_id.id))
        if self.department_id:
            domain.append(('student_id.department_id', '=', self.department_id.id))
        if self.batch_id:
            domain.append(('student_id.batch_id', '=', self.batch_id.id))
        if self.semester:
            domain.append(('semester', '=', self.semester))
        if self.student_ids:
            domain.append(('student_id', 'in', self.student_ids.ids))

        return self.env['fee.payment'].search(domain)

    def action_send_reminders(self):
        """Send fee reminders via email and SMS"""
        self.ensure_one()

        # Get fee payments
        if self.reminder_type == 'custom':
            payments = self.fee_payment_ids
        else:
            payments = self._get_fee_payments()

        if not payments:
            raise UserError(_('No fee payments found matching the criteria.'))

        sent_email = 0
        sent_sms = 0
        errors = []

        for payment in payments:
            try:
                # Send email
                if self.send_email:
                    if self._send_email_reminder(payment):
                        sent_email += 1

                # Send SMS
                if self.send_sms:
                    if self._send_sms_reminder(payment):
                        sent_sms += 1

                # Log activity
                payment.message_post(
                    body=_('Fee reminder sent on %s') % fields.Date.today(),
                    subject=_('Fee Reminder Sent')
                )

            except Exception as e:
                error_msg = f"Payment {payment.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg)

        # Show result
        message = _('Reminders sent successfully!\n\nEmails sent: %s\nSMS sent: %s') % (sent_email, sent_sms)

        if errors:
            message += _('\n\nErrors:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fee Reminders Sent'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

    def _send_email_reminder(self, payment):
        """Send email reminder for fee payment"""
        try:
            recipients = []

            # Add student email
            if self.send_to in ['student', 'both'] and payment.student_id.email:
                recipients.append(payment.student_id.email)

            # Add parent email
            if self.send_to in ['parent', 'both'] and payment.student_id.parent_id.email:
                recipients.append(payment.student_id.parent_id.email)

            if not recipients:
                return False

            # Send email using template or custom message
            if self.email_template_id:
                self.email_template_id.send_mail(payment.id,
                                                 force_send=True,
                                                 email_values={'email_to': ','.join(recipients)})
            else:
                # Send custom email
                mail_values = {
                    'subject': _('Fee Payment Reminder'),
                    'body_html': self.custom_message or _('Please pay your pending fees.'),
                    'email_to': ','.join(recipients),
                    'auto_delete': True,
                }
                self.env['mail.mail'].create(mail_values).send()

            return True

        except Exception as e:
            _logger.error(f"Email sending error: {str(e)}")
            return False

    def _send_sms_reminder(self, payment):
        """Send SMS reminder for fee payment"""
        try:
            recipients = []

            # Add student mobile
            if self.send_to in ['student', 'both'] and payment.student_id.mobile:
                recipients.append(payment.student_id.mobile)

            # Add parent mobile
            if self.send_to in ['parent', 'both'] and payment.student_id.guardian_mobile:
                recipients.append(payment.student_id.guardian_mobile)

            if not recipients:
                return False

            # Prepare SMS message
            message = self.custom_message or self._get_default_sms_message(payment)

            # Send SMS (implement based on SMS provider)
            for mobile in recipients:
                self.env['sms.sms'].create({
                    'number': mobile,
                    'body': message,
                }).send()

            return True

        except Exception as e:
            _logger.error(f"SMS sending error: {str(e)}")
            return False

    def _get_default_sms_message(self, payment):
        """Get default SMS message"""
        return _(
            "Dear %s, Your fee payment of Rs. %s is %s. Due date: %s. "
            "Please pay at the earliest. - %s"
        ) % (
            payment.student_id.name,
            payment.amount,
            'overdue' if payment.due_date < fields.Date.today() else 'pending',
            payment.due_date,
            self.env.company.name
        )

    def action_preview_reminders(self):
        """Preview reminders before sending"""
        payments = self._get_fee_payments() if self.reminder_type != 'custom' else self.fee_payment_ids

        return {
            'name': _('Fee Reminder Preview'),
            'type': 'ir.actions.act_window',
            'res_model': 'fee.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'create': False, 'edit': False},
            'target': 'new',
        }
