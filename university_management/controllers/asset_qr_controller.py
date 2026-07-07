# -*- coding: utf-8 -*-
"""
asset_qr_controller_v2.py — Updated QR Scan Controller
=======================================================
Replaces / overrides the existing asset_qr_controller.py routes.

Changes from original:
  - Role detection now uses the 6 security groups from client spec
  - Audit button gate: only shown if user is the ASSIGNED auditor
    for an active audit on this specific asset
  - Status update buttons (Available / Not Available / Needs Purchase)
    available to Faculty and HOD only
  - Handover request available to Faculty and HOD
  - Principal, ACC, Secretary, Trust Manager: View Details only from scan page
  - GPS capture is triggered from the QR scan page JS before the route loads
"""

from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

SCAN_PAGE_TEMPLATE = 'university_management.asset_scan_page_v2'
SCAN_INVALID_TEMPLATE = 'university_management.asset_scan_invalid'


class AssetQRControllerV2(http.Controller):
    """
    Updated QR scan controller with proper 6-role action gating.
    """

    @http.route(
        '/asset/scan/<int:asset_id>/<string:token>',
        auth='user', type='http', website=True, methods=['GET'],
    )
    def scan_asset(self, asset_id, token, lat=None, lng=None, **kw):
        Asset = request.env['asset.asset'].sudo()
        asset = Asset.browse(asset_id)

        if not asset.exists():
            return request.render(SCAN_INVALID_TEMPLATE, {'error': 'Asset not found.'})

        token_valid = (asset.qr_scan_token == token)

        # ── Log scan event ────────────────────────────────────────────
        try:
            request.env.cr.execute(
                """
                INSERT INTO asset_qr_scan_log
                    (asset_id, scanned_by, scan_time, gps_lat, gps_lng,
                     ip_address, device_info, action_taken, scan_token_valid,
                     create_uid, write_uid, create_date, write_date)
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    asset_id, request.env.user.id,
                    float(lat) if lat else 0.0,
                    float(lng) if lng else 0.0,
                    request.httprequest.remote_addr or '',
                    (request.httprequest.user_agent.string or '')[:255],
                    'view_only', token_valid,
                    request.env.user.id, request.env.user.id,
                )
            )
            request.env.cr.execute(
                "UPDATE asset_asset SET last_scan_date = NOW() WHERE id = %s",
                (asset_id,)
            )
            if lat and lng:
                request.env.cr.execute(
                    "UPDATE asset_asset SET last_scan_lat = %s, last_scan_lng = %s WHERE id = %s",
                    (float(lat), float(lng), asset_id)
                )
            request.env.cr.flush()
        except Exception as e:
            _logger.warning('QR scan log failed: %s', e)

        if not token_valid:
            return request.render(SCAN_INVALID_TEMPLATE, {
                'error': 'Invalid or expired QR code token.', 'asset': asset,
            })

        # ── Role Detection ────────────────────────────────────────────
        user = request.env.user
        module = 'university_management'

        def has_group(xml_id):
            return user.has_group('%s.%s' % (module, xml_id))

        is_faculty = has_group('group_faculty')
        is_hod = has_group('group_asset_hod') or has_group('group_hod')
        is_principal = has_group('group_asset_principal')
        is_acc = has_group('group_asset_acc')
        is_secretary = has_group('group_asset_secretary')
        is_trust_manager = has_group('group_asset_trust_manager')
        is_admin = user.has_group('base.group_system')

        # ── Audit Button Gate ─────────────────────────────────────────
        # Only show "Conduct Audit" if user is the ASSIGNED auditor
        # for an active in_progress audit that includes this asset
        can_audit = False
        active_audit = None
        try:
            audit_env = request.env['asset.audit'].sudo()
            active_audit = audit_env.search([
                ('state', '=', 'in_progress'),
                ('assigned_to', '=', user.id),
                ('audit_line_ids.asset_id', '=', asset_id),
            ], limit=1)
            can_audit = bool(active_audit)
        except Exception:
            pass

        # ── Status Update permission (Faculty + HOD only) ─────────────
        can_update_status = is_faculty or is_hod or is_admin

        # ── Handover permission (Faculty + HOD only) ──────────────────
        can_raise_handover = is_faculty or is_hod or is_admin

        # ── QR Print permission ───────────────────────────────────────
        can_print_qr = is_faculty or is_hod or is_principal or is_admin

        return request.render(SCAN_PAGE_TEMPLATE, {
            'asset': asset,
            'user': user,
            # Role flags
            'is_faculty': is_faculty,
            'is_hod': is_hod,
            'is_principal': is_principal,
            'is_acc': is_acc,
            'is_secretary': is_secretary,
            'is_trust_manager': is_trust_manager,
            'is_admin': is_admin,
            # Action permissions
            'can_audit': can_audit,
            'active_audit': active_audit,
            'can_update_status': can_update_status,
            'can_raise_handover': can_raise_handover,
            'can_print_qr': can_print_qr,
            # GPS for map embed
            'lat': lat or asset.last_scan_lat,
            'lng': lng or asset.last_scan_lng,
            'token': token,
        })

    @http.route(
        '/asset/update_location',
        auth='user', type='json', methods=['POST'], csrf=False,
    )
    def update_location(self, asset_id=None, lat=None, lng=None, **kw):
        """Update GPS on the most recent scan log for this asset/user."""
        if not asset_id or lat is None or lng is None:
            return {'status': 'error', 'message': 'Missing parameters'}
        try:
            request.env.cr.execute(
                """
                UPDATE asset_qr_scan_log
                SET gps_lat = %s, gps_lng = %s
                WHERE id = (
                    SELECT id FROM asset_qr_scan_log
                    WHERE asset_id = %s AND scanned_by = %s
                    ORDER BY scan_time DESC LIMIT 1
                )
                """,
                (float(lat), float(lng), int(asset_id), request.env.user.id)
            )
            request.env.cr.execute(
                "UPDATE asset_asset SET last_scan_lat = %s, last_scan_lng = %s WHERE id = %s",
                (float(lat), float(lng), int(asset_id))
            )
            request.env.cr.flush()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        return {'status': 'ok'}

    @http.route(
        '/asset/update_status',
        auth='user', type='json', methods=['POST'], csrf=False,
    )
    def update_status(self, asset_id=None, new_status=None, **kw):
        """Update asset availability status from QR scan page (Faculty/HOD only)."""
        if not asset_id or not new_status:
            return {'status': 'error', 'message': 'Missing parameters'}

        user = request.env.user
        module = 'university_management'
        if not (user.has_group('%s.group_faculty' % module)
                or user.has_group('%s.group_asset_hod' % module)
                or user.has_group('%s.group_hod' % module)
                or user.has_group('base.group_system')):
            return {'status': 'error', 'message': 'Permission denied'}

        allowed_statuses = ('available', 'not_available', 'needs_purchase')
        if new_status not in allowed_statuses:
            return {'status': 'error', 'message': 'Invalid status'}

        try:
            asset = request.env['asset.asset'].sudo().browse(int(asset_id))
            if not asset.exists():
                return {'status': 'error', 'message': 'Asset not found'}

            asset.write({'status': new_status})

            # If needs_purchase → auto-create draft purchase request
            if new_status == 'needs_purchase':
                asset.action_set_status_needs_purchase()

            # Log action in scan log
            request.env.cr.execute(
                """
                UPDATE asset_qr_scan_log SET action_taken = %s
                WHERE id = (
                    SELECT id FROM asset_qr_scan_log
                    WHERE asset_id = %s AND scanned_by = %s
                    ORDER BY scan_time DESC LIMIT 1
                )
                """,
                (new_status, int(asset_id), request.env.user.id)
            )
            request.env.cr.flush()

            # Notify HOD of status change
            asset.message_post(
                body='Status updated to <b>%s</b> by %s via QR scan.' % (
                    new_status.replace('_', ' ').title(), user.name)
            )

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

        return {'status': 'ok', 'new_status': new_status}

    @http.route(
        '/asset/audit/scan',
        auth='user', type='json', methods=['POST'], csrf=False,
    )
    def audit_scan(self, asset_id=None, audit_id=None, scan_status=None,
                   physical_condition=None, actual_location=None,
                   auditor_notes=None, lat=None, lng=None, **kw):
        """
        Auditor submits audit verification for a specific asset.
        Only callable if the user is the assigned auditor for this audit.
        """
        if not asset_id or not audit_id:
            return {'status': 'error', 'message': 'Missing parameters'}

        user = request.env.user
        try:
            audit = request.env['asset.audit'].sudo().browse(int(audit_id))
            if not audit.exists() or audit.assigned_to.id != user.id:
                return {'status': 'error', 'message': 'Not authorized for this audit'}

            line = audit.audit_line_ids.filtered(
                lambda l: l.asset_id.id == int(asset_id)
            )
            if not line:
                return {'status': 'error', 'message': 'Asset not in this audit'}

            line.write({
                'scan_status': scan_status or 'present',
                'physical_condition': physical_condition,
                'actual_location': actual_location,
                'auditor_notes': auditor_notes,
                'scanned_by': user.id,
                'scan_date': fields.Datetime.now(),
                'actual_gps_lat': float(lat) if lat else 0.0,
                'actual_gps_lng': float(lng) if lng else 0.0,
            })

            # If missing → immediate escalation
            if scan_status == 'missing':
                audit.action_flag_missing(int(asset_id))

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

        return {'status': 'ok'}

    @http.route(
        '/asset/request/submit',
        auth='user', type='http', website=True, methods=['POST'], csrf=True,
    )
    def submit_asset_request(self, asset_id=None, category_id=None,
                              description=None, required_date=None,
                              priority='medium', **kw):
        """Quick asset request form POST from QR scan page."""
        try:
            vals = {
                'asset_id': int(asset_id) if asset_id else False,
                'asset_category_id': int(category_id) if category_id else False,
                'description': description or 'Requested via QR scan.',
                'required_date': required_date or fields.Date.today(),
                'priority': priority,
            }
            req = request.env['asset.request'].create(vals)
            req.action_submit()
            return request.render(
                'university_management.asset_request_submitted',
                {'request': req, 'asset_id': asset_id},
            )
        except Exception as e:
            return request.render(SCAN_INVALID_TEMPLATE, {'error': str(e)})