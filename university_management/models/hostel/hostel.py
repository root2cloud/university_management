# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Hostel(models.Model):
    _name = 'hostel.hostel'
    _description = 'Hostel Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Hostel Name', required=True, tracking=True)
    code = fields.Char(string='Hostel Code', required=True)

    # Type
    hostel_type = fields.Selection([
        ('boys', "Boy's Hostel"),
        ('girls', "Girl's Hostel"),
        ('mixed', 'Mixed/Co-ed'),
    ], string='Hostel Type', required=True, tracking=True)

    # Warden (using faculty)
    warden_id = fields.Many2one('faculty.faculty', string='Warden', tracking=True)
    warden_name = fields.Char(related='warden_id.name', string='Warden Name')
    warden_contact = fields.Char(related='warden_id.work_mobile', string='Warden Contact')

    # Assistant Wardens
    assistant_warden_ids = fields.Many2many('faculty.faculty', 'hostel_assistant_warden_rel',
                                            'hostel_id', 'faculty_id',
                                            string='Assistant Wardens')

    # Location
    address = fields.Text(string='Address')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.ref('base.in'))

    # Capacity
    total_rooms = fields.Integer(string='Total Rooms', compute='_compute_capacity', store=True)
    total_capacity = fields.Integer(string='Total Capacity', compute='_compute_capacity', store=True)
    occupied_beds = fields.Integer(string='Occupied Beds', compute='_compute_capacity', store=True)
    available_beds = fields.Integer(string='Available Beds', compute='_compute_capacity', store=True)

    # Rooms
    room_ids = fields.One2many('hostel.room', 'hostel_id', string='Rooms')

    # Allocations
    allocation_ids = fields.One2many('hostel.allocation', 'hostel_id', string='Student Allocations')
    current_students = fields.Integer(string='Current Students', compute='_compute_students')

    # Facilities
    has_wifi = fields.Boolean(string='WiFi Available', store=True)
    has_gym = fields.Boolean(string='Gym Available', store=True)
    has_common_room = fields.Boolean(string='Common Room')
    has_study_room = fields.Boolean(string='Study Room')
    has_laundry = fields.Boolean(string='Laundry Facility')
    has_mess = fields.Boolean(string='Mess/Canteen', default=True, store=True)

    # Mess (if applicable)
    mess_id = fields.Many2one('hostel.mess', string='Mess')

    # Fees
    monthly_rent = fields.Monetary(string='Monthly Rent', currency_field='currency_id')
    security_deposit = fields.Monetary(string='Security Deposit', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Rules & Regulations
    rules = fields.Html(string='Rules & Regulations')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('closed', 'Closed'),
    ], string='Status', default='active', tracking=True)

    active = fields.Boolean(string='Active', default=True, store=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Hostel Code must be unique!'),
    ]

    @api.depends('room_ids', 'room_ids.capacity')
    def _compute_capacity(self):
        for record in self:
            record.total_rooms = len(record.room_ids)
            record.total_capacity = sum(record.room_ids.mapped('capacity'))
            record.occupied_beds = sum(record.room_ids.mapped('occupied_beds'))
            record.available_beds = record.total_capacity - record.occupied_beds

    @api.depends('allocation_ids', 'allocation_ids.state')
    def _compute_students(self):
        for record in self:
            record.current_students = len(record.allocation_ids.filtered(
                lambda a: a.state == 'allocated'))

    # Workflow Actions
    def action_activate(self):
        """Activate the hostel (move from draft to active)"""
        self.write({'state': 'active'})

    def action_maintenance(self):
        """Put hostel under maintenance"""
        self.write({'state': 'maintenance'})

    def action_close(self):
        """Close the hostel"""
        self.write({'state': 'closed'})

    def action_reset_to_draft(self):
        """Reset hostel to draft state"""
        self.write({'state': 'draft'})













