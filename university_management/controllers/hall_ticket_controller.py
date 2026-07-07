# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HallTicketController(http.Controller):
    """Hall Ticket Download Controller"""

    # ==================== HALL TICKET PORTAL ====================
    @http.route(['/my/hall-tickets'], type='http', auth="user", website=True)
    def hall_ticket_list(self, **kw):
        """List available hall tickets for student"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get hall tickets
        hall_tickets = request.env['examination.hall.ticket'].search([
            ('student_id', '=', student.id)
        ], order='examination_id desc')

        values = {
            'student': student,
            'hall_tickets': hall_tickets,
            'page_name': 'hall_tickets',
        }

        return request.render("university_management.hall_ticket_list", values)

    # ==================== HALL TICKET DETAIL ====================
    @http.route(['/my/hall-ticket/<int:hall_ticket_id>'], type='http', auth="user", website=True)
    def hall_ticket_detail(self, hall_ticket_id, **kw):
        """View hall ticket details"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        hall_ticket = request.env['examination.hall.ticket'].browse(hall_ticket_id)

        if not student or hall_ticket.student_id != student:
            return request.redirect('/my/hall-tickets')

        values = {
            'student': student,
            'hall_ticket': hall_ticket,
            'examination': hall_ticket.examination_id,
            'page_name': 'hall_ticket_detail',
        }

        return request.render("university_management.hall_ticket_detail", values)

    # ==================== DOWNLOAD HALL TICKET ====================
    @http.route(['/my/hall-ticket/<int:hall_ticket_id>/download'], type='http', auth="user")
    def hall_ticket_download(self, hall_ticket_id, **kw):
        """Download hall ticket as PDF"""
        # Use sudo() for both so cross-env comparison works correctly
        student = request.env['student.student'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1)
        hall_ticket = request.env['examination.hall.ticket'].sudo().browse(hall_ticket_id)

        # Security check: compare IDs to avoid cross-env recordset mismatch
        if not student or hall_ticket.student_id.id != student.id:
            return request.redirect('/my/hall-tickets')

        # Check if hall ticket is in a downloadable state
        if hall_ticket.state not in ['issued', 'downloaded', 'printed']:
            return request.render("university_management.hall_ticket_not_ready", {
                'message': _('Hall ticket is not yet available for download. Please check back later.')
            })

        # Generate PDF report using sudo to ensure report template has full access
        report = request.env.ref('university_management.action_report_hall_ticket').sudo()
        pdf, _ = report.sudo()._render_qweb_pdf(report.report_name, [hall_ticket_id])

        # Track download (mark as downloaded and increment counter)
        if hall_ticket.state == 'issued':
            hall_ticket.action_download()

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="HallTicket_{hall_ticket.name}.pdf"')
        ]

        return request.make_response(pdf, headers=pdfhttpheaders)

    # ==================== PUBLIC HALL TICKET VERIFICATION ====================
    @http.route(['/hall-ticket/verify'], type='http', auth="public", website=True)
    def hall_ticket_verify_page(self, **kw):
        """Hall ticket verification page"""
        values = {
            'page_name': 'hall_ticket_verify',
        }
        return request.render("university_management.hall_ticket_verify_page", values)

    @http.route(['/hall-ticket/verify/check'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def hall_ticket_verify_check(self, **post):
        """Verify hall ticket"""
        hall_ticket_number = post.get('hall_ticket_number')
        dob = post.get('date_of_birth')

        if not hall_ticket_number or not dob:
            return request.render("university_management.hall_ticket_verify_page", {
                'error': _('Please provide both Hall Ticket Number and Date of Birth'),
            })

        # Search hall ticket
        hall_ticket = request.env['examination.hall.ticket'].sudo().search([
            ('name', '=', hall_ticket_number),
            ('student_id.date_of_birth', '=', dob)
        ], limit=1)

        if not hall_ticket:
            return request.render("university_management.hall_ticket_verify_page", {
                'error': _('Invalid Hall Ticket Number or Date of Birth'),
            })

        values = {
            'hall_ticket': hall_ticket,
            'student': hall_ticket.student_id,
            'examination': hall_ticket.examination_id,
            'verified': True,
        }

        return request.render("university_management.hall_ticket_verify_result", values)

    # ==================== BULK DOWNLOAD (For Admin) ====================
    @http.route(['/examination/<int:exam_id>/hall-tickets/bulk-download'], type='http', auth="user")
    def hall_ticket_bulk_download(self, exam_id, **kw):
        """Bulk download hall tickets for an examination"""
        # Check permission
        if not request.env.user.has_group('university_management.group_examination_manager'):
            raise AccessError(_("You don't have permission to download bulk hall tickets"))

        examination = request.env['examination.examination'].browse(exam_id)

        if not examination.exists():
            return request.not_found()

        # Get all hall tickets for this examination
        hall_tickets = request.env['examination.hall.ticket'].search([
            ('examination_id', '=', exam_id),
            ('state', '=', 'generated')
        ])

        if not hall_tickets:
            return request.render("university_management.no_hall_tickets", {
                'message': _('No hall tickets generated for this examination yet.')
            })

        # Generate PDF report for all hall tickets
        report = request.env.ref('university_management.action_report_hall_ticket')
        pdf, _ = report.sudo()._render_qweb_pdf(report.report_name, hall_tickets.ids)

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="HallTickets_{examination.name.replace(" ", "_")}.pdf"')
        ]

        return request.make_response(pdf, headers=pdfhttpheaders)

    # ==================== GENERATE HALL TICKET ====================
    @http.route(['/examination/<int:exam_id>/generate-hall-tickets'], type='http', auth="user", methods=['POST'],
                csrf=True)
    def generate_hall_tickets(self, exam_id, **post):
        """Generate hall tickets for an examination"""
        # Check permission
        if not request.env.user.has_group('university_management.group_examination_manager'):
            raise AccessError(_("You don't have permission to generate hall tickets"))

        examination = request.env['examination.examination'].browse(exam_id)

        if not examination.exists():
            return request.not_found()

        try:
            # Generate hall tickets
            examination.action_generate_hall_tickets()

            return request.redirect(f'/examination/{exam_id}/hall-tickets?success=1')
        except Exception as e:
            _logger.error("Error generating hall tickets: %s", str(e))
            return request.redirect(f'/examination/{exam_id}/hall-tickets?error=1')

    # ==================== HALL TICKET STATUS CHECK ====================
    @http.route(['/api/hall-ticket/status'], type='json', auth="user")
    def hall_ticket_status(self, examination_id=None, **kw):
        """Check hall ticket status (API)"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return {'success': False, 'error': 'Student not found'}

        domain = [('student_id', '=', student.id)]
        if examination_id:
            domain += [('examination_id', '=', examination_id)]

        hall_tickets = request.env['examination.hall.ticket'].search(domain)

        tickets_data = []
        for ticket in hall_tickets:
            tickets_data.append({
                'id': ticket.id,
                'number': ticket.name,
                'examination': ticket.examination_id.name,
                'exam_date': ticket.examination_id.start_date,
                'status': ticket.state,
                'can_download': ticket.state == 'generated',
            })

        return {
            'success': True,
            'data': tickets_data
        }

    # ==================== SEND HALL TICKET VIA EMAIL ====================
    @http.route(['/my/hall-ticket/<int:hall_ticket_id>/send-email'], type='http', auth="user", methods=['POST'],
                csrf=True)
    def hall_ticket_send_email(self, hall_ticket_id, **post):
        """Send hall ticket to student email"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        hall_ticket = request.env['examination.hall.ticket'].browse(hall_ticket_id)

        if not student or hall_ticket.student_id != student:
            return request.redirect('/my/hall-tickets')

        try:
            # Send email with hall ticket attached
            template = request.env.ref('university_management.email_template_hall_ticket', raise_if_not_found=False)
            if template:
                template.send_mail(hall_ticket_id, force_send=True)

            return request.redirect(f'/my/hall-ticket/{hall_ticket_id}?email_sent=1')
        except Exception as e:
            _logger.error("Error sending hall ticket email: %s", str(e))
            return request.redirect(f'/my/hall-ticket/{hall_ticket_id}?email_error=1')