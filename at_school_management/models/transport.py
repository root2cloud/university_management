from odoo import models, fields

class TransportRoute(models.Model):
    _name = 'school.transport.route'
    _description = 'Transport Route'

    name = fields.Char(string="Route Name", required=True)
    bus_number = fields.Char(string="Bus Number")
    student_ids = fields.Many2many('school.student', string="Assigned Students")
    stop_ids = fields.One2many('school.transport.stop', 'route_id', string="Route Stops")


class TransportStop(models.Model):
    _name = 'school.transport.stop'
    _description = 'Route Stop'

    name = fields.Char(string="Stop Name", required=True)
    arrival_time = fields.Float(string="Arrival Time (HH.MM)")
    departure_time = fields.Float(string="Departure Time (HH.MM)")
    route_id = fields.Many2one('school.transport.route', string="Transport Route", ondelete='cascade')
