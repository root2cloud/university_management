from odoo import models, fields, api


class UniversityClassroom(models.Model):
    _name = 'university.classroom'
    _description = 'University Classroom'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Classroom Name", required=True)
    room_number = fields.Char(string='Room Number')
    building_name = fields.Char(string='Building Name')
    floor = fields.Char(string='Floor')
    capacity = fields.Integer(string="Capacity")
    active = fields.Boolean(default=True)
