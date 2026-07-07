# -*- coding: utf-8 -*-
"""
asset_alerts.py — Cron Alert Methods for asset.asset
=====================================================
Mixin / extension class that adds the 4 cron alert methods
required by the client spec to the asset.asset model.

Include this via _inherit in asset.py OR add these methods
directly to the Asset class in asset.py.

The 4 alerts and their recipients:
  1. Low Stock         → Faculty (registered by) + HOD (dept HOD)
  2. License Expiry    → Faculty (registered by) + Principal
  3. Maintenance Due   → HOD + Trust Secretary
  4. Unscanned (30d)  → HOD + Principal
"""

from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta


class AssetAlertsMixin(models.Model):
    """
    Extension of asset.asset to add the 4 cron alert methods.
    Inherited by asset.asset.
    """
    _inherit = 'asset.asset'

    # ── Additional fields needed for client spec ─────────────────────

    # Status field (client doc uses 'status' separate from 'state')
    status = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available'),
        ('needs_purchase', 'Needs Purchase'),
        ('in_audit', 'In Audit'),
    ], string='Availability Status', default='available', tracking=True,
        help='Operational availability of this asset. '
             'Separate from lifecycle state (draft/active/disposed).')

    # Digital asset fields
    asset_type = fields.Selection([
        ('physical', 'Physical Asset'),
        ('digital', 'Digital / Software'),
        ('consumable', 'Consumable'),
    ], string='Asset Type', default='physical', tracking=True,
        help='Physical: furniture, equipment, etc.\n'
             'Digital: software licenses, subscriptions.\n'
             'Consumable: stationery, printing supplies, etc.')

    license_expiry = fields.Date(
        string='License Expiry Date',
        help='For digital/software assets. Triggers 30-day expiry alert.',
    )

    # Stock fields for consumables
    stock_qty = fields.Float(
        string='Current Stock Quantity',
        default=0.0,
        help='For consumable assets only. Decremented via Issue wizard.',
    )
    min_stock_qty = fields.Float(
        string='Minimum Stock Threshold',
        default=0.0,
        help='When stock_qty drops below this, a low-stock alert is sent.',
    )
    low_stock = fields.Boolean(
        string='Low Stock', compute='_compute_low_stock',
        store=True,
        help='True when stock_qty < min_stock_qty for consumable assets.',
    )

    @api.depends('stock_qty', 'min_stock_qty', 'asset_type')
    def _compute_low_stock(self):
        for rec in self:
            rec.low_stock = (
                rec.asset_type == 'consumable'
                and rec.min_stock_qty > 0
                and rec.stock_qty < rec.min_stock_qty
            )

    # ══════════════════════════════════════════════════════════════════
    #  CRON ALERT METHODS
    # ══════════════════════════════════════════════════════════════════

    @api.model
    def _cron_check_low_stock(self):
        """
        Daily: consumable assets where stock_qty < min_stock_qty.
        Notify: Faculty (who registered) + HOD
        """
        all_consumables = self.search([
            ('asset_type', '=', 'consumable'),
            ('state', '=', 'active'),
            ('min_stock_qty', '>', 0),
        ])
        low_stock_assets = all_consumables.filtered(
            lambda a: a.stock_qty < a.min_stock_qty
        )

        for asset in low_stock_assets:
            asset._send_low_stock_alert()

        return '%d consumable(s) below minimum stock threshold.' % len(low_stock_assets)

    def _send_low_stock_alert(self):
        """Send low-stock alert for this asset to Faculty + HOD."""
        self.ensure_one()
        subject = _('⚠️ Low Stock Alert: %s (%s)') % (self.name, self.asset_code)
        body = _(
            '<p><b>LOW STOCK ALERT</b></p>'
            '<p>Consumable asset <b>%s (%s)</b> is below minimum stock threshold.</p>'
            '<p><b>Current Stock:</b> %s units<br/>'
            '<b>Minimum Threshold:</b> %s units<br/>'
            '<b>Location:</b> %s</p>'
            '<p>Please raise a purchase request to replenish stock.</p>'
        ) % (
            self.name, self.asset_code,
            self.stock_qty, self.min_stock_qty,
            self.room or '—',
        )
        self.message_post(body=body)
        # Notify creator (faculty) and HOD group
        notify_partners = []
        if self.create_uid and self.create_uid.partner_id:
            notify_partners.append(self.create_uid.partner_id.id)
        hod_group = self.env.ref('university_management.group_asset_hod', raise_if_not_found=False)
        if hod_group:
            for user in hod_group.users:
                if user.partner_id:
                    notify_partners.append(user.partner_id.id)
        if notify_partners:
            self.message_notify(
                partner_ids=list(set(notify_partners)),
                subject=subject, body=body,
                message_type='email',
                subtype_xmlid='mail.mt_comment',
            )

    @api.model
    def _cron_check_license_expiry(self):
        """
        Daily: digital assets where license_expiry <= today + 30 days.
        Notify: Faculty (creator) + Principal
        """
        today = date.today()
        warning_date = today + relativedelta(days=30)

        expiring = self.search([
            ('asset_type', '=', 'digital'),
            ('state', 'not in', ['disposed', 'condemned', 'lost']),
            ('license_expiry', '!=', False),
            ('license_expiry', '>=', today),
            ('license_expiry', '<=', warning_date),
        ])

        for asset in expiring:
            days_left = (asset.license_expiry - today).days
            subject = _('⚠️ License Expiring in %d Days: %s') % (days_left, asset.name)
            body = _(
                '<p><b>LICENSE EXPIRY WARNING</b></p>'
                '<p>Digital asset <b>%s (%s)</b> has a license expiring in <b>%d days</b> '
                'on <b>%s</b>.</p>'
                '<p><b>Location:</b> %s<br/>'
                '<b>Department:</b> %s</p>'
                '<p>Please arrange for renewal or raise a purchase request.</p>'
            ) % (
                asset.name, asset.asset_code, days_left, asset.license_expiry,
                asset.room or '—',
                asset.department_id.name if asset.department_id else '—',
            )
            asset.message_post(body=body)
            # Notify faculty creator + principal group
            notify_partners = []
            if asset.create_uid and asset.create_uid.partner_id:
                notify_partners.append(asset.create_uid.partner_id.id)
            principal_group = self.env.ref(
                'university_management.group_asset_principal', raise_if_not_found=False
            )
            if principal_group:
                for user in principal_group.users:
                    if user.partner_id:
                        notify_partners.append(user.partner_id.id)
            if notify_partners:
                asset.message_notify(
                    partner_ids=list(set(notify_partners)),
                    subject=subject, body=body,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                )

        return '%d digital asset license(s) expiring within 30 days.' % len(expiring)

    @api.model
    def _cron_check_maintenance_due_alert(self):
        """
        Daily: assets where next_service_date <= today (maintenance overdue).
        Notify: HOD + Trust Secretary
        """
        today = date.today()
        due = self.search([
            ('next_service_date', '<=', today),
            ('state', '=', 'active'),
        ])

        for asset in due:
            subject = _('🔧 Maintenance Due: %s (%s)') % (asset.name, asset.asset_code)
            body = _(
                '<p><b>MAINTENANCE DUE ALERT</b></p>'
                '<p>Asset <b>%s (%s)</b> has a maintenance/service due on <b>%s</b>.</p>'
                '<p><b>Location:</b> %s<br/>'
                '<b>Department:</b> %s</p>'
                '<p>Please raise a maintenance request or schedule service.</p>'
            ) % (
                asset.name, asset.asset_code, asset.next_service_date,
                asset.room or '—',
                asset.department_id.name if asset.department_id else '—',
            )
            asset.message_post(body=body)
            notify_partners = []
            for group_xml in [
                'university_management.group_asset_hod',
                'university_management.group_asset_secretary',
            ]:
                grp = self.env.ref(group_xml, raise_if_not_found=False)
                if grp:
                    for user in grp.users:
                        if user.partner_id:
                            notify_partners.append(user.partner_id.id)
            if notify_partners:
                asset.message_notify(
                    partner_ids=list(set(notify_partners)),
                    subject=subject, body=body,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                )

        return '%d asset(s) with maintenance due.' % len(due)

    @api.model
    def _cron_check_unscanned_assets(self):
        """
        Daily: assets not scanned via QR in 30+ days.
        Notify: HOD + Principal
        """
        from datetime import datetime
        threshold = fields.Datetime.now() - relativedelta(days=30)

        unscanned = self.search([
            ('state', '=', 'active'),
            '|',
            ('last_scan_date', '=', False),
            ('last_scan_date', '<', threshold),
        ])

        for asset in unscanned:
            days_since = (
                (fields.Datetime.now() - asset.last_scan_date).days
                if asset.last_scan_date else 'Never'
            )
            subject = _('📋 Unverified Asset: %s — Not Scanned for %s Days') % (
                asset.name, days_since
            )
            body = _(
                '<p><b>UNVERIFIED ASSET ALERT</b></p>'
                '<p>Asset <b>%s (%s)</b> has not been scanned via QR code for '
                '<b>%s days</b> (last scan: %s).</p>'
                '<p><b>Location:</b> %s<br/>'
                '<b>Department:</b> %s</p>'
                '<p>Please verify this asset\'s physical location and condition.</p>'
            ) % (
                asset.name, asset.asset_code, days_since,
                asset.last_scan_date or 'Never',
                asset.room or '—',
                asset.department_id.name if asset.department_id else '—',
            )
            asset.message_post(body=body)
            notify_partners = []
            for group_xml in [
                'university_management.group_asset_hod',
                'university_management.group_asset_principal',
            ]:
                grp = self.env.ref(group_xml, raise_if_not_found=False)
                if grp:
                    for user in grp.users:
                        if user.partner_id:
                            notify_partners.append(user.partner_id.id)
            if notify_partners:
                asset.message_notify(
                    partner_ids=list(set(notify_partners)),
                    subject=subject, body=body,
                    message_type='email',
                    subtype_xmlid='mail.mt_comment',
                )

        return '%d asset(s) unscanned for 30+ days.' % len(unscanned)

    def action_set_status_available(self):
        self.write({'status': 'available'})

    def action_set_status_not_available(self):
        self.write({'status': 'not_available'})

    def action_set_status_needs_purchase(self):
        """
        Mark asset as Needs Purchase → auto-creates a draft purchase request.
        """
        for rec in self:
            rec.write({'status': 'needs_purchase'})
            # Auto-create draft purchase request
            existing = self.env['asset.purchase.request'].search([
                ('asset_id', '=', rec.id),
                ('state', 'in', ('draft', 'principal_review', 'vendor_quotes',
                                  'acc_review', 'secretary_review', 'trust_execution')),
            ], limit=1)
            if not existing:
                self.env['asset.purchase.request'].create({
                    'asset_id': rec.id,
                    'item_description': 'Asset replacement/purchase required: %s' % rec.name,
                    'justification': 'Asset status marked as "Needs Purchase" via QR scan or dashboard.',
                    'requested_by': self.env.user.id,
                    'department_id': rec.department_id.id if rec.department_id else False,
                })
                rec.message_post(
                    body=_('Asset marked as "Needs Purchase". Draft purchase request auto-created.')
                )

    def action_open_issue_wizard(self):
        """Open the consumable stock issue wizard."""
        self.ensure_one()
        if self.asset_type != 'consumable':
            raise models.ValidationError(_('Stock issue is only available for consumable assets.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Consumable Stock'),
            'res_model': 'asset.stock.issue.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }