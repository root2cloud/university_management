from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class CourseEnrollmentReport(models.TransientModel):
    _name = 'course.enrollment.report'
    _description = 'Course Enrollment Report'

    department_id = fields.Many2one('hr.department', string="Department")
    employee_ids = fields.Many2many('hr.employee', string="Employees")
    enrolled_courses = fields.Text(string="Enrolled Courses", compute="_compute_enrollment_details")
    training_status = fields.Text(string="Training Status", compute="_compute_training_status")

    @api.depends('employee_ids', 'department_id')
    def _compute_enrollment_details(self):
        for record in self:
            if record.department_id:
                employees = self.env['hr.employee'].search([('department_id', '=', record.department_id.id)])
            else:
                employees = record.employee_ids or self.env['hr.employee'].search([])

            enrollment_info = []
            for emp in employees:
                if not emp.user_id or not emp.user_id.partner_id:
                    enrollment_info.append(f"{emp.name}: No user/partner linked")
                    continue
                channel_partners = self.env['slide.channel.partner'].search([
                    ('partner_id', '=', emp.user_id.partner_id.id)
                ])
                channels = channel_partners.mapped('channel_id')
                if channels:
                    course_names = ", ".join(channels.mapped('name'))
                    enrollment_info.append(f"{emp.name}: Enrolled in {course_names}")
                else:
                    enrollment_info.append(f"{emp.name}: No courses enrolled")
            record.enrolled_courses = "\n".join(enrollment_info) or "No enrollment data available"

    @api.depends('employee_ids', 'department_id')
    def _compute_training_status(self):
        for record in self:
            if record.department_id:
                employees = self.env['hr.employee'].search([('department_id', '=', record.department_id.id)])
            else:
                employees = record.employee_ids or self.env['hr.employee'].search([])

            status_info = []
            for emp in employees:
                if not emp.user_id or not emp.user_id.partner_id:
                    status_info.append(f"{emp.name}: No user/partner linked")
                    continue
                completed = self.env['slide.slide.partner'].search([
                    ('partner_id', '=', emp.user_id.partner_id.id),
                    ('completed', '=', True)
                ])
                if completed:
                    course_names = ", ".join(completed.mapped('channel_id.name'))
                    status_info.append(f"{emp.name}: Completed {course_names}")
                else:
                    status_info.append(f"{emp.name}: No training completed")
            record.training_status = "\n".join(status_info) or "No training data available"

    def action_generate_report(self):
        """Generate the course enrollment report"""
        self.ensure_one()
        self._compute_enrollment_details()
        self._compute_training_status()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'course.enrollment.report',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self._context,
        }