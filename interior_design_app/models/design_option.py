from odoo import models, fields


class DesignOption(models.Model):
    _name = 'design.option'
    _description = 'Design Option'

    project_id = fields.Many2one('design.project', string='Project', required=True)
    name = fields.Char(string='Design Name', required=True)
    design_image = fields.Binary(string='Design Image', attachment=True)
    description = fields.Text(string='Description')
