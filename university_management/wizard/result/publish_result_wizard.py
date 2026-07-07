# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class PublishResultWizard(models.TransientModel):
    """
    Wizard for bulk result publication
    """
    _name = 'publish.result.wizard'
    _description = 'Publish Result Wizard'

    examination_id = fields.Many2one('examination.examination', string='Examination', required=True,
                                     domain=[('state', '=', 'completed')])
    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')
    semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Semester', required=True)

    publish_date = fields.Datetime(string='Publish Date', default=fields.Datetime.now, required=True)

    result_ids = fields.Many2many('examination.result', string='Results',
                                  domain="[('examination_id', '=', examination_id), ('state', '=', 'verified')]")

    generate_marksheet = fields.Boolean(string='Generate Marksheets', default=True)
    send_email = fields.Boolean(string='Send Email Notification', default=True)
    send_sms = fields.Boolean(string='Send SMS Notification', default=True)

    publish_on_portal = fields.Boolean(string='Publish on Student Portal', default=True)

    preview_count = fields.Integer(string='Results to Publish', compute='_compute_preview_count')
    pass_count = fields.Integer(string='Passed', compute='_compute_statistics')
    fail_count = fields.Integer(string='Failed', compute='_compute_statistics')
    pass_percentage = fields.Float(string='Pass %', compute='_compute_statistics')

    @api.depends('examination_id', 'program_id', 'department_id', 'semester', 'result_ids')
    def _compute_preview_count(self):
        """Compute number of results to publish"""
        for wizard in self:
            if wizard.result_ids:
                wizard.preview_count = len(wizard.result_ids)
            else:
                results = wizard._get_results()
                wizard.preview_count = len(results)

    @api.depends('examination_id', 'program_id', 'department_id', 'semester', 'result_ids')
    def _compute_statistics(self):
        """Compute pass/fail statistics"""
        for wizard in self:
            results = wizard.result_ids if wizard.result_ids else wizard._get_results()

            wizard.pass_count = len(results.filtered(lambda r: r.result == 'pass'))
            wizard.fail_count = len(results.filtered(lambda r: r.result == 'fail'))

            total = wizard.pass_count + wizard.fail_count
            wizard.pass_percentage = (wizard.pass_count / total * 100) if total > 0 else 0.0

    def _get_results(self):
        """Get results to be published"""
        domain = [
            ('examination_id', '=', self.examination_id.id),
            ('semester', '=', self.semester),
            ('state', '=', 'evaluated')
        ]

        if self.program_id:
            domain.append(('student_id.program_id', '=', self.program_id.id))
        if self.department_id:
            domain.append(('student_id.department_id', '=', self.department_id.id))

        return self.env['examination.result'].search(domain)

    def action_publish_results(self):
        """Publish examination results"""
        self.ensure_one()

        # Get results
        results = self.result_ids if self.result_ids else self._get_results()

        if not results:
            raise UserError(_('No results found to publish.'))

        published_count = 0
        marksheets_generated = 0
        errors = []

        for result in results:
            try:
                # Publish result
                result.write({
                    'state': 'published',
                    'publish_date': self.publish_date,
                    'is_published': True
                })
                published_count += 1

                # Generate marksheet
                if self.generate_marksheet:
                    marksheet = self._generate_marksheet(result)
                    if marksheet:
                        marksheets_generated += 1

                # Send notifications
                if self.send_email:
                    self._send_email_notification(result)

                if self.send_sms:
                    self._send_sms_notification(result)

                # Post on portal
                if self.publish_on_portal:
                    result.write({'portal_published': True})

            except Exception as e:
                errors.append(f"{result.student_id.name}: {str(e)}")
                _logger.error(f"Result publication error: {str(e)}")

        # Update examination status
        if published_count > 0:
            self.examination_id.write({'result_published': True})

        # Show result message
        message = _(
            'Results Published Successfully!\n\n'
            'Published: %s\n'
            'Marksheets Generated: %s\n'
            'Pass Rate: %.2f%%'
        ) % (published_count, marksheets_generated, self.pass_percentage)

        if errors:
            message += _('\n\nErrors:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Results Published'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

    def _generate_marksheet(self, result):
        """Generate marksheet for student"""
        try:
            Marksheet = self.env['marksheet.marksheet']

            # Check if marksheet already exists
            existing = Marksheet.search([
                ('student_id', '=', result.student_id.id),
                ('examination_id', '=', result.examination_id.id)
            ], limit=1)

            if existing:
                return existing

            # Create new marksheet
            marksheet = Marksheet.create({
                'student_id': result.student_id.id,
                'examination_id': result.examination_id.id,
                'program_id': result.student_id.program_id.id,
                'semester': result.semester,
                'academic_year_id': result.academic_year_id.id,
                'result_id': result.id,
                'issue_date': fields.Date.today(),
                'total_marks': result.total_marks,
                'obtained_marks': result.obtained_marks,
                'percentage': result.percentage,
                'cgpa': result.cgpa,
                'grade': result.grade,
                'result': result.result,
                'state': 'generated'
            })

            return marksheet

        except Exception as e:
            _logger.error(f"Marksheet generation error: {str(e)}")
            return False

    def _send_email_notification(self, result):
        """Send email notification to student"""
        try:
            if not result.student_id.email:
                return False

            template = self.env.ref('university_management.email_template_result_published',
                                    raise_if_not_found=False)
            if template:
                template.send_mail(result.id, force_send=True)
                return True

            return False

        except Exception as e:
            _logger.error(f"Email sending error: {str(e)}")
            return False

    def _send_sms_notification(self, result):
        """Send SMS notification to student"""
        try:
            if not result.student_id.mobile:
                return False

            message = _(
                "Dear %s, Your %s result is published. Result: %s, Percentage: %.2f%%. "
                "Login to student portal for details."
            ) % (
                          result.student_id.name,
                          result.examination_id.name,
                          result.result.upper(),
                          result.percentage
                      )

            self.env['sms.sms'].create({
                'number': result.student_id.mobile,
                'body': message,
            }).send()

            return True

        except Exception as e:
            _logger.error(f"SMS sending error: {str(e)}")
            return False

    def action_preview_results(self):
        """Preview results before publishing"""
        results = self.result_ids if self.result_ids else self._get_results()

        return {
            'name': _('Results Preview'),
            'type': 'ir.actions.act_window',
            'res_model': 'examination.result',
            'view_mode': 'list,form',
            'domain': [('id', 'in', results.ids)],
            'context': {'create': False, 'edit': False},
            'target': 'new',
        }
