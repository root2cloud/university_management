# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssetQRScanLog(models.Model):
    """
    Asset QR Scan Log — immutable ledger of every QR scan event.

    Records are created via the HTTP controller when a user scans
    an asset QR code from a mobile device. Once created, records
    cannot be modified or deleted (enforced via write/unlink overrides).

    Captures: who scanned, when, GPS coordinates, device info,
    what action was taken, and whether the QR token was valid.
    """
    _name = 'asset.qr.scan.log'
    _description = 'Asset QR Scan Log'
    _order = 'scan_time desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Scan Reference',
        compute='_compute_name', store=True,
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Asset',
        required=True, ondelete='restrict', index=True,
    )
    asset_code = fields.Char(
        related='asset_id.asset_code', store=True, string='Asset Code',
    )
    scanned_by = fields.Many2one(
        'res.users', string='Scanned By', readonly=True,
    )
    scan_time = fields.Datetime(
        string='Scanned On', default=fields.Datetime.now, readonly=True,
    )
    gps_lat = fields.Float(
        string='GPS Latitude', digits=(10, 6), readonly=True,
    )
    gps_lng = fields.Float(
        string='GPS Longitude', digits=(10, 6), readonly=True,
    )
    gps_captured = fields.Boolean(
        string='GPS Captured',
        compute='_compute_gps_captured', store=True,
    )
    action_taken = fields.Selection([
        ('view_only', 'View Only'),
        ('request_raised', 'Asset Request Raised'),
        ('handover_initiated', 'Handover / Transfer Initiated'),
        ('audit_scanned', 'Audit Scan'),
        ('maintenance_reported', 'Maintenance Reported'),
    ], string='Action Taken', default='view_only', readonly=True)
    device_info = fields.Char(string='Device / Browser', readonly=True)
    ip_address = fields.Char(string='IP Address', readonly=True)
    scan_token_valid = fields.Boolean(
        string='Token Valid', default=True, readonly=True,
        help='False if someone tampered with the QR URL token.',
    )
    notes = fields.Char(string='Notes', readonly=True)

    @api.depends('asset_id', 'scan_time')
    def _compute_name(self):
        for rec in self:
            ts = rec.scan_time.strftime('%Y%m%d-%H%M%S') if rec.scan_time else 'unknown'
            rec.name = f'SCAN/{rec.asset_code or "?"}/{ts}'

    @api.depends('gps_lat', 'gps_lng')
    def _compute_gps_captured(self):
        for rec in self:
            rec.gps_captured = bool(rec.gps_lat or rec.gps_lng)

    # Immutability enforcement
    def write(self, vals):
        raise UserError(_('QR scan log records are immutable and cannot be modified.'))

    def unlink(self):
        raise UserError(_('QR scan log records cannot be deleted for audit trail purposes.'))

    def action_open_map_link(self):
        self.ensure_one()
        if not self.gps_lat or not self.gps_lng:
            raise UserError(_('No GPS coordinates recorded for this scan.'))
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://maps.google.com/maps?q=%s,%s&z=18' % (self.gps_lat, self.gps_lng),
            'target': 'new',
        }
