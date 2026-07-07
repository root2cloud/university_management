from odoo import models, fields


class DesignServiceRequest(models.Model):
    _name = 'design.service.request'
    _description = 'Design Service Request'

    project_id = fields.Many2one('design.project', string='Project', required=True)
    request_date = fields.Date(string='Request Date', default=fields.Date.today)
    description = fields.Text(string='Service Description')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='Status', default='draft')
