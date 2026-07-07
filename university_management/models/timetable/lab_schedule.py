# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LabSchedule(models.Model):
    _name = 'lab.schedule'
    _description = 'Laboratory Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'day_of_week, start_time'

    name = fields.Char(string='Lab Name', required=True)

    # Lab Details
    lab_number = fields.Char(string='Lab Number', required=True)
    lab_type = fields.Selection([
        ('computer', 'Computer Lab'),
        ('physics', 'Physics Lab'),
        ('chemistry', 'Chemistry Lab'),
        ('electronics', 'Electronics Lab'),
        ('mechanical', 'Mechanical Workshop'),
        ('other', 'Other'),
    ], string='Lab Type')

    capacity = fields.Integer(string='Capacity')

    # Department
    department_id = fields.Many2one('university.department', string='Department')

    # Schedule (linked to class timetable)
    timetable_ids = fields.One2many('class.timetable', 'room_number_id',
                                    string='Lab Schedule',
                                    domain=[('class_type', '=', 'practical')])

    # Lab In-charge
    lab_incharge_id = fields.Many2one('faculty.faculty', string='Lab In-charge')

    # Equipment
    equipment_details = fields.Html(string='Equipment/Apparatus Details')

    # Status
    state = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('closed', 'Closed'),
    ], string='Status', default='available', tracking=True)

    active = fields.Boolean(string='Active', default=True)
