from odoo import models, fields, api


class Hostel(models.Model):
    _name = 'hostel'
    _description = 'Hostel Information'

    name = fields.Char(string="Hostel Name", required=True)
    code = fields.Char(string="Hostel Code", required=True)
    address = fields.Char(string="Address")
    contact_phone = fields.Char(string="Contact Number")
    total_rooms = fields.Integer(string="Total Rooms")
    manager_id = fields.Many2one('res.users', string="Hostel Manager")
    student_ids = fields.One2many('hostel.student', 'hostel_id', string="Students")
    active = fields.Boolean(string="Active", default=True)


class HostelRoom(models.Model):
    _name = 'hostel.room'
    _description = 'Hostel Room'

    name = fields.Char(string="Room Number", required=True)
    hostel_id = fields.Many2one('hostel', string="Hostel", required=True)
    capacity = fields.Integer(string="Capacity", default=2)
    current_occupancy = fields.Integer(string="Occupied", compute='_compute_occupancy')
    available_beds = fields.Integer(string="Available", compute='_compute_available_beds')
    student_ids = fields.One2many('hostel.student', 'room_id', string="Students")

    @api.depends('student_ids')
    def _compute_occupancy(self):
        for room in self:
            room.current_occupancy = len(room.student_ids)

    @api.depends('capacity', 'current_occupancy')
    def _compute_available_beds(self):
        for room in self:
            room.available_beds = room.capacity - room.current_occupancy


class HostelStudent(models.Model):
    _name = 'hostel.student'
    _description = 'Hostel Student Allocation'

    student_id = fields.Many2one('school.student', string="Student", required=True, domain=[('is_student', '=', True)])
    hostel_id = fields.Many2one('hostel', string="Hostel", required=True)
    room_id = fields.Many2one('hostel.room', string="Room", domain="[('hostel_id', '=', hostel_id)]")
    date_from = fields.Date(string="From Date", default=fields.Date.today)
    date_to = fields.Date(string="To Date")
    status = fields.Selection([
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='active')