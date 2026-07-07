from odoo import models, fields


class DesignComponent(models.Model):
    _name = 'design.component'
    _description = 'Design Component'

    project_id = fields.Many2one('design.project', string='Project', required=True)
    name = fields.Char(string='Component Name', required=True)
    component_type = fields.Char(string='Type')
    quantity = fields.Integer(string='Quantity')
    dimensions = fields.Char(string='Dimensions')
