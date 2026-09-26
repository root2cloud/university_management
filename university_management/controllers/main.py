# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.web.controllers.home import Home
import logging

_logger = logging.getLogger(__name__)


class UniversityLoginRedirect(Home):
    """Send Faculty / Student / Parent users straight to their own
    dashboard the moment they log in, instead of the backend or the
    website homepage. Admins and any explicit ``redirect`` target
    (e.g. a shared deep link) are left untouched.

    This hooks into ``_login_redirect``, the helper Odoo's own
    ``web_login`` already calls right after a successful
    authentication to decide where to send the user, so the login
    response, session and cookies are still built exactly once, the
    normal Odoo way.
    """

    @classmethod
    def _login_redirect(cls, uid, redirect=None):
        if not redirect:
            user = request.env['res.users'].sudo().browse(uid)
            if user.has_group('university_management.group_student_portal'):
                redirect = '/my/student/dashboard'
            elif user.has_group('university_management.group_parent_portal'):
                redirect = '/my/parent/dashboard'
            elif user.has_group('university_management.group_faculty') and not \
                    user.has_group('university_management.group_university_admin'):
                redirect = '/my/faculty/dashboard'
        return super()._login_redirect(uid, redirect=redirect)


class UniversityWebsiteController(http.Controller):
    # """Main website controller for public pages"""

    # ==================== HOME PAGE ====================
    @http.route(['/'], type='http', auth="public", website=True)
    def index(self, **kw):
        """Homepage"""
        featured_programs = request.env['university.program'].sudo().search(
            [('active', '=', True)], limit=3, order='name'
        )
        values = {
            'page_name': 'home',
            'featured_programs': featured_programs,
        }
        return request.render("university_management.homepage", values)

    # ==================== ABOUT US ====================
    @http.route(['/about'], type='http', auth="public", website=True)
    def about_us(self, **kw):
        """About Us page"""
        values = {
            'page_name': 'about',
        }
        return request.render("university_management.about_page", values)

    # ==================== PROGRAMS ====================
    @http.route(['/programs', '/programs/page/<int:page>'], type='http', auth="public", website=True)
    def programs_list(self, page=1, search='', **kw):
        """List all programs"""
        Program = request.env['university.program'].sudo()

        domain = [('active', '=', True)]
        if search:
            domain += ['|', ('name', 'ilike', search), ('code', 'ilike', search)]

        # Pager
        programs_count = Program.search_count(domain)
        pager = portal_pager(
            url="/programs",
            url_args={'search': search},
            total=programs_count,
            page=page,
            step=12,
        )

        programs = Program.search(domain, limit=12, offset=pager['offset'], order='program_type, department_id, name')

        values = {
            'programs': programs,
            'pager': pager,
            'search': search,
            'page_name': 'programs',
        }
        return request.render("university_management.programs_page", values)

    @http.route(['/program/<model("university.program"):program>'], type='http', auth="public", website=True)
    def program_detail(self, program, **kw):
        """Program detail page"""
        program = program.sudo()
        values = {
            'program': program,
            'page_name': 'program_detail',
        }
        return request.render("university_management.program_detail_page", values)

    # ==================== DEPARTMENTS ====================
    @http.route(['/departments'], type='http', auth="public", website=True)
    def departments_list(self, **kw):
        """List all departments"""
        departments = request.env['university.department'].sudo().search([('active', '=', True)])

        values = {
            'departments': departments,
            'page_name': 'departments',
        }
        return request.render("university_management.departments_page", values)

    @http.route(['/department/<model("university.department"):department>'], type='http', auth="public", website=True)
    def department_detail(self, department, **kw):
        """Department detail page"""
        values = {
            'department': department,
            'page_name': 'department_detail',
        }
        return request.render("university_management.department_detail_page", values)

    # # ==================== FACULTY ====================
    @http.route(['/faculty', '/faculty/page/<int:page>'], type='http', auth="public", website=True)
    def faculty_list(self, page=1, department=None, **kw):
        """List all faculty members"""
        Faculty = request.env['faculty.faculty'].sudo()

        domain = [('active', '=', True)]
        if department:
            domain += [('department_id', '=', int(department))]

        # Pager
        faculty_count = Faculty.search_count(domain)
        pager = portal_pager(
            url="/faculty",
            url_args={'department': department},
            total=faculty_count,
            page=page,
            step=15,
        )

        faculty = Faculty.search(domain, limit=15, offset=pager['offset'], order='name')
        departments = request.env['university.department'].sudo().search([('active', '=', True)])

        values = {
            'faculty': faculty,
            'departments': departments,
            'pager': pager,
            'selected_department': int(department) if department else None,
            'page_name': 'faculty',
        }
        return request.render("university_management.faculty_page", values)

    @http.route(['/faculty/<model("faculty.faculty"):faculty>'], type='http', auth="public", website=True)
    def faculty_detail(self, faculty, **kw):
        """Faculty detail page"""
        if not faculty.active:
            return request.redirect('/faculty')

        values = {
            'faculty': faculty,
            'page_name': 'faculty_detail',
        }
        return request.render("university_management.faculty_detail_page", values)

    # ==================== ADMISSIONS ====================
    @http.route(['/admissions'], type='http', auth="public", website=True)
    def admissions_page(self, **kw):
        """Admissions information page"""
        # Remove the non-existent field 'is_open_for_admission' from the search
        programs = request.env['university.program'].sudo().search(
            [('active', '=', True)])  # Removed: , ('is_open_for_admission', '=', True)

        values = {
            'programs': programs,
            'page_name': 'admissions',
        }
        return request.render("university_management.admissions_page", values)

    @http.route(['/admission/apply'], type='http', auth="public", website=True)
    def admission_apply(self, **kw):
        """Admission application form"""
        # Remove the non-existent field 'is_open_for_admission' from the search
        programs = request.env['university.program'].sudo().search(
            [('active', '=', True)])  # Removed: , ('is_open_for_admission', '=', True)
        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])

        values = {
            'programs': programs,
            'countries': countries,
            'states': states,
            'page_name': 'admission_apply',
        }
        return request.render("university_management.admission_apply_page", values)

    @http.route(['/admission/submit'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def admission_submit(self, **post):
        """Submit admission application — creates a Student Enquiry (pipeline entry).

        The website form is the first step of the admission pipeline:
            Website Form → student.enquiry (state: new)
                → contacted → counselling → seat_blocked → student.admission (internal)

        A full student.admission record is created internally by the admission team
        after counselling and seat blocking, NOT directly from the public website form.
        """
        try:
            # ── Server-side validation (safety net even if JS is bypassed) ──
            required_fields = {
                'applicant_name': 'Full Name',
                'email': 'Email Address',
                'mobile': 'Mobile Number',
                'date_of_birth': 'Date of Birth',
                'gender': 'Gender',
                'program_id': 'Program',
                'previous_school': 'Previous School/College',
                'previous_percentage': 'Percentage/CGPA',
                'permanent_address': 'Permanent Address',
                'city': 'City',
                'country_id': 'Country',
                'father_name': "Father's Name",
                'mother_name': "Mother's Name",
                'guardian_mobile': "Guardian's Mobile Number",
            }
            missing = [label for field, label in required_fields.items() if not post.get(field, '').strip()]
            if missing:
                return request.render("university_management.admission_error_page", {
                    'error': "Please fill in all required fields: " + ", ".join(missing),
                })

            # Declaration checkbox must be checked
            if not post.get('terms'):
                return request.render("university_management.admission_error_page", {
                    'error': "You must accept the declaration before submitting your application.",
                })

            enquiry_vals = {
                'applicant_name': post.get('applicant_name', '').strip(),
                'email': post.get('email', '').strip(),
                'mobile': post.get('mobile', '').strip(),
                'program_id': int(post.get('program_id')) if post.get('program_id') else False,
                'gender': post.get('gender') or False,
                'date_of_birth': post.get('date_of_birth') or False,
                'previous_school': post.get('previous_school', ''),
                'previous_percentage': float(post.get('previous_percentage') or 0),
                'city': post.get('city', ''),
                'state_id': int(post.get('state_id')) if post.get('state_id') else False,
                'state': 'new',
                'notes': (
                    f"Permanent Address: {post.get('permanent_address', '')}\n"
                    f"ZIP: {post.get('zip', '')}\n"
                    f"Father: {post.get('father_name', '')}\n"
                    f"Mother: {post.get('mother_name', '')}\n"
                    f"Guardian Mobile: {post.get('guardian_mobile', '')}\n"
                    f"Submitted via: Website"
                ),
            }

            # Filter to only valid model fields to be safe
            valid_fields = request.env['student.enquiry'].sudo().fields_get().keys()
            enquiry_vals = {k: v for k, v in enquiry_vals.items() if k in valid_fields}

            enquiry = request.env['student.enquiry'].sudo().create(enquiry_vals)

            return request.render("university_management.admission_success_page", {
                'admission': enquiry,
            })
        except Exception as e:
            _logger.error("Error submitting admission enquiry: %s", str(e))
            return request.render("university_management.admission_error_page", {
                'error': str(e),
            })

    # ==================== EVENTS ====================
    @http.route(['/events', '/events/page/<int:page>'], type='http', auth="public", website=True)
    def events_list(self, page=1, event_type=None, **kw):
        """List all events"""

        # (menu is hidden via CSS template in home_templates.xml, this blocks direct URL access)
        # if not request.env.user._is_public():
        #     if request.env.user.has_group('university_management.group_faculty'):
        #         return request.redirect('/')

        Event = request.env['university.event'].sudo()

        domain = [
            ('state', 'in', ['published', 'registration_open', 'ongoing']),
            ('website_published', '=', True)
        ]

        if event_type:
            domain += [('event_type', '=', event_type)]

        # Pager
        events_count = Event.search_count(domain)
        pager = portal_pager(
            url="/events",
            url_args={'event_type': event_type},
            total=events_count,
            page=page,
            step=9,
        )

        events = Event.search(domain, limit=9, offset=pager['offset'], order='start desc')

        values = {
            'events': events,
            'pager': pager,
            'event_type': event_type,
            'page_name': 'events',
        }
        return request.render("university_management.events_page", values)

    @http.route(['/event/<int:event_id>'], type='http', auth="public", website=True)
    def event_detail(self, event_id, **kw):
        """Event detail page"""
        event = request.env['university.event'].sudo().browse(event_id)
        # Check if event exists and is published on website
        if not event.exists() or not event.website_published or event.state not in ['published', 'registration_open', 'ongoing']:
            return request.not_found()

        values = {
            'event': event,
            'page_name': 'event_detail',
        }
        return request.render("university_management.event_detail_page", values)

    @http.route(['/event/<int:event_id>/register'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def event_register(self, event_id, **post):
        """Register for an event"""
        try:
            event = request.env['university.event'].sudo().browse(event_id)
            if not event.exists() or not event.website_published:
                return request.redirect('/events')

            # Check if event allows registration
            if not event.requires_registration or not "university.event.registration_open":
                return request.render("university_management.event_error_page", {
                    'error': _('Registration is not open for this event.'),
                })

            # Check maximum participants
            if event.max_participants and event.total_registrations >= event.max_participants:
                return request.render("university_management.event_error_page", {
                    'error': _('Event has reached maximum participants.'),
                })

            # Check if user is a student
            student = request.env['student.student'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
            if not student:
                return request.render("university_management.event_error_page", {
                    'error': _('Only students can register for events.'),
                })

            # Check if already registered
            existing_reg = request.env['university.event.registration'].sudo().search([
                ('event_id', '=', event_id),
                ('student_id', '=', student.id),
                ('state', '!=', 'cancelled')
            ])
            if existing_reg:
                return request.render("university_management.event_error_page", {
                    'error': _('You are already registered for this event.'),
                })

            # Create registration
            registration_vals = {
                'event_id': event_id,
                'student_id': student.id,
                'participant_type': 'student',
                'state': 'registered',  # Directly mark as registered for website registrations
            }

            registration = request.env['university.event.registration'].sudo().create(registration_vals)

            return request.redirect('/my/registrations')
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("Error registering for event: %s", str(e))
            return request.render("university_management.event_error_page", {
                'error': str(e),
            })


    # ==================== CONTACT US ====================
    @http.route(['/contact'], type='http', auth="public", website=True)
    def contact_us(self, **kw):
        """Contact Us page"""
        values = {
            'page_name': 'contact',
        }
        return request.render("university_management.contact_page", values)

    @http.route(['/contact/submit'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def contact_submit(self, **post):
        """Submit contact form"""
        try:
            # Create lead or helpdesk ticket
            vals = {
                'name': post.get('name'),
                'email_from': post.get('email'),
                'phone': post.get('phone'),
                'description': post.get('description'),  # Changed from 'message' to 'description'
                'subject': post.get('subject'),  # Added subject field
            }

            if 'crm.lead' in request.env:
                request.env['crm.lead'].sudo().create(vals)

            return request.render("university_management.contact_success_page")
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("Error submitting contact form: %s", str(e))
            return request.render("university_management.contact_error_page", {
                'error': str(e),
            })

    # ==================== LIBRARY ====================
    @http.route(['/library'], type='http', auth="public", website=True)
    def library_page(self, **kw):
        """Library information page"""
        values = {
            'page_name': 'library',
        }
        return request.render("university_management.library_page", values)

    @http.route(['/library/books', '/library/books/page/<int:page>'], type='http', auth="public", website=True)
    def library_books(self, page=1, search='', category=None, **kw):
        """Browse library books"""
        Book = request.env['library.book'].sudo()

        domain = [('active', '=', True), ('available_copies', '>', 0)]
        if search:
            domain += ['|', ('title', 'ilike', search), ('primary_author', 'ilike', search)]
        if category:
            domain += [('category_id', '=', int(category))]

        # Pager
        books_count = Book.search_count(domain)
        pager = portal_pager(
            url="/library/books",
            url_args={'search': search, 'category': category},
            total=books_count,
            page=page,
            step=20,
        )

        books = Book.search(domain, limit=20, offset=pager['offset'], order='title')
        categories = request.env['library.category'].sudo().search([])

        values = {
            'books': books,
            'categories': categories,
            'pager': pager,
            'search': search,
            'selected_category': int(category) if category else None,
            'page_name': 'library_books',
        }
        return request.render("university_management.library_books_page", values)

    # ==================== PLACEMENTS ====================
    @http.route(['/placements'], type='http', auth="public", website=True)
    def placements_page(self, **kw):
        """Placements information page"""
        # Get placement statistics
        current_year = request.env['university.academic.year'].sudo().search([('state', '=', 'active')], limit=1)

        # Get all active academic year ids to avoid missing data across years
        all_active_years = request.env['university.academic.year'].sudo().search([('state', '=', 'active')])
        active_year_ids = all_active_years.ids

        stats = {
            'total_students': request.env['student.student'].sudo().search_count([
                ('academic_year_id', 'in', active_year_ids),
                ('state', 'in', ['enrolled', 'active'])
            ]) if active_year_ids else 0,
            'placed_students': request.env['placement.application'].sudo().search_count([
                ('state', '=', 'selected')
            ]),
            'companies': request.env['placement.drive'].sudo().search_count([]),
        }

        # Fetch all drives regardless of state
        drives = request.env['placement.drive'].sudo().search([], order='id desc')

        values = {
            'stats': stats,
            'current_year': current_year,
            'drives': drives,
            'page_name': 'placements',
        }
        return request.render("university_management.placements_page", values)

    @http.route(['/placements/drive/<int:drive_id>'], type='http', auth="public", website=True)
    def placement_drive_detail(self, drive_id, **kw):
        """Placement drive detail page"""
        drive = request.env['placement.drive'].sudo().browse(drive_id)
        if not drive.exists():
            return request.not_found()

        values = {
            'drive': drive,
            'page_name': 'placement_drive_detail',
        }
        return request.render("university_management.placement_drive_detail", values)

    # ==================== DOWNLOADS ====================
    @http.route(['/downloads'], type='http', auth="public", website=True)
    def downloads_page(self, **kw):
        """Downloads page for forms and documents"""
        # Remove the domain filter for is_public since the field doesn't exist
        # Use only existing fields: state='verified' to show verified documents
        documents = request.env['student.document'].sudo().search([
            ('state', '=', 'verified'),  # Only show verified documents
            ('attachment_id', '!=', False),  # Only show documents with attachments
        ], order='sequence, name')

        values = {
            'documents': documents,
            'page_name': 'downloads',
        }
        return request.render("university_management.downloads_page", values)

    @http.route(['/download/<int:document_id>'], type='http', auth="public")
    def download_document(self, document_id, **kw):
        """Download a document"""
        document = request.env['student.document'].sudo().browse(document_id)

        # Check if document exists and is verified (instead of is_public)
        if not document.exists() or document.state != 'verified':
            return request.not_found()

        # Use attachment_id to get the file since file field doesn't exist
        if document.attachment_id and document.attachment_id.datas:
            # Get the attachment
            attachment = document.attachment_id
            return http.request.make_response(
                attachment.datas.decode('base64') if isinstance(attachment.datas, str) else attachment.datas,
                headers=[
                    ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                    ('Content-Disposition', f'attachment; filename="{attachment.name}"')
                ]
            )
        return request.not_found()


class UniversityPortalExtension(CustomerPortal):
    """Extend Odoo portal for university-specific features"""

    def _prepare_home_portal_values(self, counters):
        """Add university-specific counters to portal home"""
        values = super()._prepare_home_portal_values(counters)

        if request.env.user.has_group('university_management.group_university_student'):
            student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
            if student:
                values.update({
                    'student': student,
                    'fee_due_count': len(student.fee_payment_ids.filtered(lambda f: f.state == 'pending')),
                    'attendance_percentage': student.attendance_percentage,
                    'cgpa': student.cgpa,
                })

        return values