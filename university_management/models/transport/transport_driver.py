# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TransportDriver(models.Model):
    _name = 'transport.driver'
    _description = 'Transport Driver Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}  # Integration with contacts
    _order = 'name'

    # Partner (for contact details)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Driver Code
    driver_code = fields.Char(string='Driver Code', required=True, readonly=True,
                              copy=False, default='/')

    # Photo
    photo = fields.Binary(string='Photo', attachment=True)

    # License Details
    license_number = fields.Char(string='Driving License Number', required=True, tracking=True)
    license_type = fields.Selection([
        ('light', 'Light Motor Vehicle'),
        ('heavy', 'Heavy Vehicle'),
        ('transport', 'Transport Vehicle'),
    ], string='License Type', required=True)

    license_issue_date = fields.Date(string='License Issue Date')
    license_expiry_date = fields.Date(string='License Expiry Date', tracking=True)

    # Experience
    experience_years = fields.Integer(string='Years of Experience')

    # Vehicles Assigned
    vehicle_ids = fields.One2many('transport.vehicle', 'driver_id', string='Vehicles Assigned')
    current_vehicle_id = fields.Many2one('transport.vehicle', string='Current Vehicle')

    # Emergency Contact
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')

    # Government IDs
    aadhar_number = fields.Char(string='Aadhar Number')
    pan_number = fields.Char(string='PAN Number')

    # Employment
    joining_date = fields.Date(string='Joining Date')

    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('resigned', 'Resigned'),
    ], string='Status', default='active', tracking=True)

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('driver_code_unique', 'unique(driver_code)', 'Driver Code must be unique!'),
        ('license_unique', 'unique(license_number)', 'License Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('driver_code', '/') == '/':
            vals['driver_code'] = self.env['ir.sequence'].next_by_code('transport.driver') or '/'
        return super(TransportDriver, self).create(vals)
