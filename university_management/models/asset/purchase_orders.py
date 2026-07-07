# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class PurchaseOrderAssetInherit(models.Model):
    """
    Extends purchase.order with asset management context fields.

    Adds:
      - asset_request_id     : originating asset.request
      - helpdesk_ticket_id   : originating helpdesk ticket
      - asset_ids            : assets registered from this PO's receipt
      - asset_count          : smart button count

    New method:
      - action_register_assets_from_po() : creates asset.asset records after
        goods receipt, pre-filling all purchase details.
    """
    _inherit = 'purchase.order'

    asset_request_id = fields.Many2one(
        'asset.request', string='Asset Request',
        copy=False, index=True,
        help='Asset request that triggered this purchase order.',
    )
    helpdesk_ticket_id = fields.Many2one(
        'ticket.helpdesk', string='Helpdesk Ticket',
        copy=False, index=True,
        help='Helpdesk ticket from which this PO was created.',
    )
    asset_ids = fields.One2many(
        'asset.asset', 'purchase_order_id',
        string='Registered Assets',
        help='Assets registered in the system from this purchase order.',
    )
    asset_count = fields.Integer(
        string='Assets Registered', compute='_compute_asset_count',
    )

    def _compute_asset_count(self):
        for rec in self:
            rec.asset_count = len(rec.asset_ids)

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registered Assets'),
            'res_model': 'asset.asset',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        }

    def action_view_helpdesk_ticket(self):
        self.ensure_one()
        if not self.helpdesk_ticket_id:
            raise UserError(_('No helpdesk ticket linked to this PO.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Helpdesk Ticket'),
            'res_model': 'ticket.helpdesk',
            'res_id': self.helpdesk_ticket_id.id,
            'view_mode': 'form',
        }

    def action_view_asset_request(self):
        self.ensure_one()
        if not self.asset_request_id:
            raise UserError(_('No asset request linked to this PO.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Request'),
            'res_model': 'asset.request',
            'res_id': self.asset_request_id.id,
            'view_mode': 'form',
        }

    def action_register_assets_from_po(self):
        """
        IT Team action: Register assets after goods receipt confirmation.
        Creates asset.asset draft records pre-filled from PO data.
        One asset per order line quantity (up to 10 per line to avoid flooding).
        """
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_('Purchase order must be confirmed before registering assets.'))

        req = self.asset_request_id
        created_assets = self.env['asset.asset']

        for line in self.order_line:
            if not line.product_id:
                continue

            # Find category linked to this product
            category = self.env['asset.category'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            # Fallback: find by category from asset request
            if not category and req:
                category = req.asset_category_id

            qty = max(1, int(line.product_qty))
            qty = min(qty, 20)  # Safety cap

            for i in range(qty):
                suffix = f' #{i+1}' if qty > 1 else ''
                asset_vals = {
                    'name': f'{line.product_id.name}{suffix}',
                    'category_id': category.id if category else False,
                    'purchase_order_id': self.id,
                    'purchase_date': self.date_order.date() if self.date_order else date.today(),
                    'purchase_cost': line.price_unit,
                    'vendor_id': self.partner_id.id if self.partner_id else False,
                    'make': line.product_id.manufacturer if hasattr(line.product_id, 'manufacturer') else False,
                    'location_id': (
                        category.default_location_id.id if category and category.default_location_id
                        else False
                    ),
                    'state': 'draft',
                    'funded_by': 'institute',
                    'notes': (
                        f'Registered from PO: {self.name}\n'
                        f'Helpdesk Ticket: {self.helpdesk_ticket_id.name if self.helpdesk_ticket_id else "—"}\n'
                        f'Asset Request: {req.name if req else "—"}'
                    ),
                }
                asset = self.env['asset.asset'].create(asset_vals)
                created_assets |= asset

        if not created_assets:
            raise UserError(_(
                'No asset records created. Ensure order lines have products '
                'and asset categories are configured with matching products.'
            ))

        # Update asset request
        if req and created_assets:
            req.assigned_asset_id = created_assets[0].id
            if req.state == 'pending_purchase':
                req.action_fulfill()

        self.message_post(
            body=_('%d asset record(s) created from this PO. Please activate each asset after verification.') % len(created_assets)
        )

        if self.helpdesk_ticket_id:
            self.helpdesk_ticket_id.message_post(
                body=_('%d asset(s) registered. IT team: please activate and assign to requester.') % len(created_assets)
            )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Registered Assets'),
            'res_model': 'asset.asset',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_assets.ids)],
        }
