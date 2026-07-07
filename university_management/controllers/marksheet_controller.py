# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MarksheetController(http.Controller):
    """Marksheet Download Controller"""

    # ==================== MARKSHEET PORTAL ====================
    @http.route(['/my/marksheets'], type='http', auth="user", website=True)
    def marksheet_list(self, **kw):
        """List available marksheets for student"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get marksheets
        marksheets = request.env['examination.marksheet'].search([
            ('student_id', '=', student.id)
        ], order='semester_id desc, issue_date desc')

        # Get current website for main_object
        website = request.env['website'].get_current_website()

        values = {
            'student': student,
            'marksheets': marksheets,
            'page_name': 'marksheets',
            'main_object': website,  # Changed to website instead of student
        }

        return request.render("university_management.marksheet_list", values)

    # ==================== MARKSHEET DETAIL ====================
    @http.route(['/my/marksheet/<int:marksheet_id>'], type='http', auth="user", website=True)
    def marksheet_detail(self, marksheet_id, **kw):
        """View marksheet details"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        marksheet = request.env['examination.marksheet'].browse(marksheet_id)

        if not student or marksheet.student_id != student:
            return request.redirect('/my/marksheets')

        # Get current website for main_object
        website = request.env['website'].get_current_website()

        values = {
            'student': student,
            'marksheet': marksheet,
            'page_name': 'marksheet_detail',
            'main_object': website,  # Changed to website instead of student
        }

        return request.render("university_management.marksheet_detail", values)

    # ==================== DOWNLOAD MARKSHEET ====================
    @http.route(['/my/marksheet/<int:marksheet_id>/download'], type='http', auth="user")
    def marksheet_download(self, marksheet_id, **kw):
        """Download marksheet as PDF"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        marksheet = request.env['examination.marksheet'].sudo().browse(marksheet_id)

        # Security check
        if not student or marksheet.student_id != student:
            return request.redirect('/my/marksheets')

        # Check if marksheet is published
        if marksheet.state not in ['verified', 'issued', 'downloaded']:
            website = request.env['website'].get_current_website()
            return request.render("university_management.marksheet_not_ready", {
                'message': _('Marksheet is not yet published. Please check back later.'),
                'main_object': website,  # Changed to website
            })

        # Generate PDF report
        report = request.env(su=True).ref('university_management.action_report_marksheet')
        pdf, pdf_data = report._render_qweb_pdf(report.report_name, [marksheet_id])

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="Marksheet_{marksheet.name}.pdf"')
        ]

        return request.make_response(pdf, headers=pdfhttpheaders)

    # ==================== PUBLIC MARKSHEET VERIFICATION ====================
    @http.route(['/marksheet/verify'], type='http', auth="public", website=True)
    def marksheet_verify_page(self, **kw):
        """Marksheet verification page"""
        website = request.env['website'].get_current_website()
        values = {
            'page_name': 'marksheet_verify',
            'main_object': website,
        }
        return request.render("university_management.marksheet_verify_page", values)

    @http.route(['/marksheet/verify/check'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def marksheet_verify_check(self, **post):
        """Verify marksheet"""
        marksheet_number = post.get('marksheet_number')
        registration_number = post.get('registration_number')

        website = request.env['website'].get_current_website()

        if not marksheet_number or not registration_number:
            return request.render("university_management.marksheet_verify_page", {
                'error': _('Please provide both Marksheet Number and Registration Number'),
                'main_object': website,
            })

        # Search marksheet
        marksheet = request.env['examination.marksheet'].sudo().search([
            ('name', '=', marksheet_number),
            ('student_id.registration_number', '=', registration_number),
            ('state', 'in', ['verified', 'issued', 'downloaded'])
        ], limit=1)

        if not marksheet:
            return request.render("university_management.marksheet_verify_page", {
                'error': _('Invalid Marksheet Number or Registration Number'),
                'main_object': website,
            })

        values = {
            'marksheet': marksheet,
            'student': marksheet.student_id,
            'verified': True,
            'main_object': website,  # Changed to website instead of marksheet
        }

        return request.render("university_management.marksheet_verify_result", values)

    # ==================== DOWNLOAD ALL MARKSHEETS ====================
    @http.route(['/my/marksheets/download-all'], type='http', auth="user")
    def marksheet_download_all(self, **kw):
        """Download all marksheets as single PDF"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get all published marksheets
        marksheets = request.env['examination.marksheet'].search([
            ('student_id', '=', student.id),
            ('state', 'in', ['verified', 'issued', 'downloaded'])
        ])

        if not marksheets:
            website = request.env['website'].get_current_website()
            return request.render("university_management.no_marksheets", {
                'message': 'No marksheets available for download.',
                'main_object': website,  # Changed to website
            })

        # Generate PDF report for all marksheets
        report = request.env(su=True).ref('university_management.action_report_marksheet')
        pdf, pdf_data = report._render_qweb_pdf(report.report_name, marksheets.ids)

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="Marksheets_{student.registration_number}.pdf"')
        ]

        return request.make_response(pdf, headers=pdfhttpheaders)

    # ==================== SEND MARKSHEET VIA EMAIL ====================
    @http.route(['/my/marksheet/<int:marksheet_id>/send-email'], type='http', auth="user", methods=['POST'], csrf=True)
    def marksheet_send_email(self, marksheet_id, **post):
        """Send marksheet to student email"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        marksheet = request.env['examination.marksheet'].browse(marksheet_id)

        if not student or marksheet.student_id != student:
            return request.redirect('/my/marksheets')

        try:
            # Send email with marksheet attached
            template = request.env.ref('university_management.email_template_marksheet', raise_if_not_found=False)
            if template:
                template.send_mail(marksheet_id, force_send=True)

            return request.redirect(f'/my/marksheet/{marksheet_id}?email_sent=1')
        except Exception as e:
            _logger.error("Error sending marksheet email: %s", str(e))
            return request.redirect(f'/my/marksheet/{marksheet_id}?email_error=1')

    # ==================== MARKSHEET API ====================
    @http.route(['/api/marksheet/status'], type='json', auth="user")
    def marksheet_status(self, **kw):
        """Check marksheet status (API)"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return {'success': False, 'error': 'Student not found'}

        marksheets = request.env['examination.marksheet'].search([
            ('student_id', '=', student.id)
        ])

        marksheets_data = []
        for marksheet in marksheets:
            marksheets_data.append({
                'id': marksheet.id,
                'number': marksheet.name,
                'semester': marksheet.semester_id.name,
                'examination': marksheet.examination_id.name,
                'sgpa': marksheet.sgpa,
                'cgpa': marksheet.cgpa,
                'percentage': marksheet.percentage,
                'result': marksheet.result,
                'state': marksheet.state,
                'can_download': marksheet.state in ['verified', 'issued', 'downloaded'],
                'issue_date': marksheet.issue_date,
            })

        return {
            'success': True,
            'data': marksheets_data
        }

    # ==================== REQUEST DUPLICATE MARKSHEET ====================
    @http.route(['/my/marksheet/request-duplicate'], type='http', auth="user", website=True)
    def marksheet_request_duplicate_page(self, **kw):
        """Request duplicate marksheet page"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        marksheets = request.env['examination.marksheet'].search([
            ('student_id', '=', student.id),
            ('state', 'in', ['verified', 'issued', 'downloaded'])
        ])

        website = request.env['website'].get_current_website()

        values = {
            'student': student,
            'marksheets': marksheets,
            'page_name': 'request_duplicate',
            'main_object': website,  # Changed to website
        }

        return request.render("university_management.request_duplicate_marksheet", values)

    @http.route(['/my/marksheet/request-duplicate/submit'], type='http', auth="user", methods=['POST'], website=True,
                csrf=True)
    def marksheet_request_duplicate_submit(self, **post):
        """Submit duplicate marksheet request"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        try:
            request_vals = {
                'student_id': student.id,
                'marksheet_id': int(post.get('marksheet_id')),
                'reason': post.get('reason'),
                'request_type': 'duplicate',
            }

            request.env['document.request'].sudo().create(request_vals)

            return request.redirect('/my/marksheet/request-duplicate?success=1')
        except Exception as e:
            _logger.error("Error submitting duplicate marksheet request: %s", str(e))
            return request.redirect('/my/marksheet/request-duplicate?error=1')