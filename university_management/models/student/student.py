# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class Student(models.Model):
    _name = 'student.student'
    _description = 'University Student Master'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _inherits = {'res.partner': 'partner_id'}
    _order = 'registration_number'

    # Partner (inherited from res.partner)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Student Details
    student_code = fields.Char(string='Student Code', readonly=True, copy=False, default='/')
    registration_number = fields.Char(string='Registration Number', readonly=True,
                                      copy=False, tracking=True)
    admission_number = fields.Char(string='Admission Number', tracking=True)

    # Personal Information
    student_photo = fields.Binary(related='partner_id.image_1920', string='Photo', readonly=False, store=True)
    date_of_birth = fields.Date(string='Date of Birth', required=True, tracking=True)
    age = fields.Integer(string='Age', compute='_compute_age')
    gender = fields.Selection([('male', 'Male'),('female', 'Female'),('other', 'Other'),], string='Gender', required=True, tracking=True)
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('o+', 'O+'), ('o-', 'O-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
    ], string='Blood Group')

    # Contact
    personal_email = fields.Char(string='Personal Email')
    personal_mobile = fields.Char(string='Personal Mobile')
    emergency_contact = fields.Char(string='Emergency Contact')
    emergency_contact_name = fields.Char(string='Emergency Contact Name')

    # Address
    current_address = fields.Text(string='Current Address')
    permanent_address = fields.Text(string='Permanent Address')

    # Academic Details
    program_id = fields.Many2one('university.program', string='Program',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one(related='program_id.department_id', string='Department',
                                    required=True, tracking=True, index=True)
    batch_id = fields.Many2one('university.batch', string='Batch', tracking=True)
    current_semester = fields.Integer(string='Current Semester', default=1)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Admission
    admission_id = fields.Many2one('student.admission', string='Admission Record')
    admission_date = fields.Date(string='Admission Date', tracking=True)
    admission_category = fields.Selection([
        ('general', 'General'),
        ('obc', 'OBC'),
        ('sc', 'SC'),
        ('st', 'ST'),
        ('ews', 'EWS'),
    ], string='Category')

    # Previous Education
    previous_qualification = fields.Char(string='Previous Qualification')
    previous_institution = fields.Char(string='Previous Institution')
    previous_percentage = fields.Float(string='Previous Percentage')
    previous_year = fields.Integer(string='Year of Passing')

    # Courses
    enrolled_course_ids = fields.Many2many('university.course', 'student_course_rel',
                                           'student_id', 'course_id',
                                           string='Enrolled Courses')

    # Registration
    registration_ids = fields.One2many('student.registration', 'student_id',
                                       string='Course Registrations')

    # Attendance
    attendance_ids = fields.One2many('student.attendance', 'student_id',
                                     string='Attendance Records')
    attendance_percentage = fields.Float(string='Attendance %', compute='_compute_attendance', store=True)

    # Documents
    document_ids = fields.One2many('student.document', 'student_id', string='Documents')
    documents_verified = fields.Boolean(string='Documents Verified', compute='_compute_documents', store=True)

    # ID Card
    id_card_ids = fields.One2many('student.id.card', 'student_id', string='ID Cards')

    # Parents/Guardians
    parent_ids = fields.One2many('student.parent', 'student_id', string='Parents/Guardians')

    # Discipline
    discipline_ids = fields.One2many('student.discipline', 'student_id',
                                     string='Discipline Records')

    # Fee
    fee_payment_ids = fields.One2many('fee.payment', 'student_id', string='Fee Payments')

    # ── Fixed: computes from actual invoice amounts, not hardcoded ────
    total_fee_due = fields.Monetary(
        string='Total Fee Due',
        compute='_compute_fees',
        store=False,  # always live — no stale data
        search='_search_total_fee_due',
    )
    total_fee_paid = fields.Monetary(
        string='Total Fee Paid',
        compute='_compute_fees',
        store=False,
    )
    fee_transaction_count = fields.Integer(
        string='Transactions',
        compute='_compute_fees',
        store=False,
    )

    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)

    # Examination
    exam_result_ids = fields.One2many('examination.result', 'student_id', string='Exam Results')
    cgpa = fields.Float(string='CGPA', compute='_compute_academic_performance', store=True)
    sgpa = fields.Float(string='SGPA (Current)', compute='_compute_academic_performance')

    # Hostel
    hostel_allocation_id = fields.Many2one('hostel.allocation', string='Hostel Allocation')
    is_hosteller = fields.Boolean(string='Hosteller')

    # Transport
    transport_allocation_id = fields.Many2one('transport.allocation',
                                              string='Transport Allocation')
    uses_transport = fields.Boolean(string='Uses Transport')

    # Library
    library_member_id = fields.Many2one('library.member', string='Library Member')

    # Portal Access
    user_id = fields.Many2one('res.users', string='Portal User')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('admitted', 'Admitted'),
        ('enrolled', 'Enrolled'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('graduated', 'Graduated'),
        ('dropped', 'Dropped Out'),
        ('expelled', 'Expelled'),
    ], string='Status', default='draft', tracking=True)

    active = fields.Boolean(string='Active', default=True)

    # Nationality
    nationality_id = fields.Many2one('res.country', string='Nationality')
    is_international = fields.Boolean(string='International Student')

    # Religion & Caste
    religion = fields.Char(string='Religion')
    caste = fields.Char(string='Caste')

    # Bank Details (for scholarships)
    bank_account_number = fields.Char(string='Bank Account Number')
    bank_name = fields.Char(string='Bank Name')
    bank_branch = fields.Char(string='Branch')
    ifsc_code = fields.Char(string='IFSC Code')

    # Linked res.partner.bank record (auto-managed by _sync_bank_account)
    # Appears under the student contact's Bank Accounts tab.
    # Used by scholarship payments as partner_bank_id.
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        readonly=True,
        help='Auto-created/updated from bank details above. '
             'Visible on the student contact under Bank Accounts.',
    )

    # Government IDs
    aadhar_number = fields.Char(string='Aadhar Number')
    pan_number = fields.Char(string='PAN Number')

    # ── University ID & USN Mapping ───────────────────────────────────
    temp_student_id = fields.Char(
        string='Temporary Student ID', readonly=True, copy=False, index=True,
        help='Auto-generated on student creation. Format: TEMP{YEAR}-{SEQ}. '
             'Used until the university assigns an official USN.',
    )
    university_usn = fields.Char(
        string='University USN', tracking=True, copy=False, index=True,
        help='Official University Seat Number assigned by the affiliating university '
             'e.g. 1MV24AR001.',
    )
    usn_mapped = fields.Boolean(
        string='USN Mapped', default=False, tracking=True,
    )
    usn_mapped_date = fields.Date(string='USN Mapping Date', readonly=True)
    usn_mapped_by = fields.Many2one('res.users', string='USN Mapped By', readonly=True)

    _sql_constraints = [
        ('registration_number_unique', 'unique(registration_number)',
         'Registration Number must be unique!'),
        ('aadhar_unique', 'unique(aadhar_number)',
         'Aadhar Number must be unique!'),
        ('temp_student_id_unique', 'unique(temp_student_id)',
         'Temporary Student ID must be unique!'),
        ('university_usn_unique', 'unique(university_usn)',
         'University USN must be unique!'),
    ]

    @api.model
    def create(self, vals):
        """
        Auto-assigns sequences and auto-creates/finds res.partner.

        Import path: wizard passes partner_id already set → skip auto-create.
        Manual path: user fills name/email in form → auto-create partner.
        """
        # ── Sequences (skip if already supplied from import) ──────────────
        if not vals.get('student_code') or vals.get('student_code') == '/':
            vals['student_code'] = (
                    self.env['ir.sequence'].next_by_code('student.student') or '/'
            )

        # registration_number: only auto-generate if not supplied or is placeholder
        if not vals.get('registration_number') or vals.get('registration_number') == '/':
            vals['registration_number'] = (
                    self.env['ir.sequence'].next_by_code('student.registration') or '/'
            )

        # Temporary Student ID
        if not vals.get('temp_student_id') and not vals.get('usn_mapped'):
            year = fields.Date.today().year
            seq = self.env['ir.sequence'].next_by_code('student.temp.id') or '00001'
            vals['temp_student_id'] = f'TEMP{year}-{seq}'

        # ── Partner: find or create ───────────────────────────────────────
        if not vals.get('partner_id'):
            name = vals.get('name', '').strip()
            email = vals.get('email') or vals.get('personal_email') or ''
            mobile = vals.get('mobile') or vals.get('personal_mobile') or ''

            partner_id = self._find_or_create_partner(
                name=name,
                email=email.strip().lower() if email else False,
                mobile=mobile.strip() if mobile else False,
            )
            vals['partner_id'] = partner_id

        student = super().create(vals)

        # Sync bank details to res.partner.bank if supplied at creation
        bank_fields = {'bank_account_number', 'bank_name', 'bank_branch', 'ifsc_code'}
        if bank_fields & set(vals):
            student._sync_bank_account()

        return student

    def write(self, vals):
        res = super().write(vals)
        # Re-sync res.partner.bank whenever any bank field changes
        bank_fields = {'bank_account_number', 'bank_name', 'bank_branch', 'ifsc_code'}
        if bank_fields & set(vals):
            for student in self:
                student._sync_bank_account()
        return res

    def _sync_bank_account(self):
        """
        Create or update the res.partner.bank record linked to this student's
        partner so that:
          1. Bank account appears on student contact under Bank Accounts tab.
          2. Scholarship payments can use partner_bank_id to direct money
             to the correct bank account.
        """
        self.ensure_one()

        acc_number = (self.bank_account_number or '').strip()
        if not acc_number:
            return

        partner_id = self.partner_id.id
        if not partner_id:
            return

        PartnerBank = self.env['res.partner.bank']

        bank_vals = {
            'acc_number': acc_number,
            'partner_id': partner_id,
            'acc_holder_name': self.name or '',
            'send_money': True,  # mark as trusted for outbound payments
        }

        if self.ifsc_code:
            bank_vals['bic'] = self.ifsc_code.strip()

        if self.bank_name:
            bank_name = self.bank_name.strip()
            ResBank = self.env['res.bank']
            res_bank = ResBank.search([('name', '=ilike', bank_name)], limit=1)
            if not res_bank:
                res_bank = ResBank.create({
                    'name': bank_name,
                    'bic': self.ifsc_code.strip() if self.ifsc_code else False,
                })
            bank_vals['bank_id'] = res_bank.id

        existing = PartnerBank.search([
            ('partner_id', '=', partner_id),
            ('acc_number', '=', acc_number),
        ], limit=1)

        if existing:
            existing.write(bank_vals)
            if self.bank_account_id.id != existing.id:
                self.bank_account_id = existing.id
        else:
            new_bank = PartnerBank.create(bank_vals)
            self.bank_account_id = new_bank.id

        _logger.info(
            'student._sync_bank_account: partner=%s acc=%s bank_account_id=%s',
            partner_id, acc_number, self.bank_account_id.id,
        )

    @api.model
    def _find_or_create_partner(self, name, email=False, mobile=False):
        """
        Find an existing res.partner by email (priority) or exact name,
        or create a new one.

        Args:
            name  (str): Student full name — required.
            email (str|False): Lowercase email or False.
            mobile(str|False): Phone number or False.

        Returns:
            int: partner.id
        """
        Partner = self.env['res.partner']

        if not name:
            raise ValidationError(_('Student name is required to create a partner.'))

        # 1. Dedup by email — most reliable
        if email:
            existing = Partner.search([('email', '=ilike', email)], limit=1)
            if existing:
                _logger.info(
                    'student._find_or_create_partner: matched by email %s → partner %s',
                    email, existing.id,
                )
                return existing.id

        # 2. Dedup by exact name — fallback (risky for common names; email preferred)
        existing = Partner.search([('name', '=', name)], limit=1)
        if existing:
            _logger.info(
                'student._find_or_create_partner: matched by name "%s" → partner %s',
                name, existing.id,
            )
            return existing.id

        # 3. Create new partner
        partner = Partner.create({
            'name': name,
            'email': email or False,
            'phone': mobile or False,
            'is_company': False,
            'customer_rank': 0,
            'supplier_rank': 0,
        })
        _logger.info(
            'student._find_or_create_partner: created new partner "%s" id=%s',
            name, partner.id,
        )
        return partner.id

    @api.model
    def load(self, fields_list, data):
        """
        Hook called by Odoo's native CSV/Excel importer.
        Auto-creates res.partner for each row that lacks partner_id.
        """
        partner_col = 'partner_id' in fields_list
        partner_name_col = 'partner_id/.id' in fields_list or 'partner_id/name' in fields_list

        if not partner_col and not partner_name_col:
            # Native importer didn't get a partner column — inject partner_id for each row
            partner_idx = len(fields_list)
            fields_list = list(fields_list) + ['partner_id/.id']

            # Find name column index
            try:
                name_idx = fields_list.index('name')
            except ValueError:
                name_idx = None

            try:
                email_idx = fields_list.index('email')
            except ValueError:
                email_idx = None

            new_data = []
            for row in data:
                row = list(row)
                name = row[name_idx] if name_idx is not None and name_idx < len(row) else ''
                email = row[email_idx] if email_idx is not None and email_idx < len(row) else ''
                partner_id = self._find_or_create_partner(
                    name=str(name).strip(),
                    email=str(email).strip().lower() if email else False,
                )
                row.append(str(partner_id))
                new_data.append(row)
            data = new_data

        return super().load(fields_list, data)

    @api.depends('date_of_birth')
    def _compute_age(self):
        from datetime import date
        for record in self:
            if record.date_of_birth:
                today = date.today()
                record.age = today.year - record.date_of_birth.year - (
                        (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day)
                )
            else:
                record.age = 0

    @api.depends('attendance_ids')
    def _compute_attendance(self):
        for record in self:
            total = len(record.attendance_ids)
            present = len(record.attendance_ids.filtered(lambda a: a.state == 'present'))
            record.attendance_percentage = (present / total * 100) if total > 0 else 0.0

    @api.depends('document_ids', 'document_ids.is_verified')
    def _compute_documents(self):
        for record in self:
            if record.document_ids:
                record.documents_verified = all(doc.is_verified for doc in record.document_ids)
            else:
                record.documents_verified = False

    def _compute_fees(self):
        for record in self:
            payments = self.env['fee.payment'].search([
                ('student_id', '=', record.id),
                ('state', 'not in', ['draft', 'cancelled']),
            ])
            record.total_fee_paid = sum(payments.mapped('amount_paid'))
            record.total_fee_due = sum(payments.mapped('outstanding_amount'))
            try:
                record.fee_transaction_count = self.env[
                    'fee.payment.line'
                ].search_count([('fee_payment_id.student_id', '=', record.id)])
            except Exception:
                record.fee_transaction_count = 0

    @api.depends('exam_result_ids')
    def _compute_academic_performance(self):
        for record in self:
            results = record.exam_result_ids.filtered(lambda r: r.state == 'published')
            if results:
                record.cgpa = sum(results.mapped('grade_point')) / len(results)
                current_sem_results = results.filtered(
                    lambda r: r.semester_id.semester_number == record.current_semester
                )
                if current_sem_results:
                    record.sgpa = sum(current_sem_results.mapped('grade_point')) / len(current_sem_results)
                else:
                    record.sgpa = 0.0
            else:
                record.cgpa = 0.0
                record.sgpa = 0.0

    @api.constrains('aadhar_number')
    def _check_aadhar(self):
        for record in self:
            if record.aadhar_number:
                if not re.match(r'^\d{12}$', record.aadhar_number):
                    raise ValidationError(_('Aadhar number must be 12 digits!'))

    def action_admit(self):
        self.write({'state': 'admitted', 'admission_date': fields.Date.today()})

    def action_enroll(self):
        self.write({'state': 'enrolled'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_graduate(self):
        self.write({'state': 'graduated'})
        for student in self:
            student._create_alumni_record()

    def _create_alumni_record(self):
        """Auto-create an alumni record when a student is graduated."""
        self.ensure_one()
        Alumni = self.env['alumni.alumni']

        # Skip if already linked to an alumni record
        if Alumni.search([('student_id', '=', self.id)], limit=1):
            return

        # Compute graduation year from batch or current year
        import datetime
        graduation_year = datetime.date.today().year
        if self.batch_id and self.batch_id.end_year:
            graduation_year = self.batch_id.end_year

        admission_year = 0
        if self.batch_id and self.batch_id.start_year:
            admission_year = self.batch_id.start_year
        elif self.admission_date:
            admission_year = self.admission_date.year

        # Reuse or create a res.partner for this alumni
        partner = self.partner_id
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.name,
                'email': self.email or self.personal_email or '',
                'mobile': self.mobile or self.personal_mobile or '',
            })

        alumni_vals = {
            'partner_id': partner.id,
            'student_id': self.id,
            'name': self.name,
            'registration_number': self.registration_number or '',
            'program_id': self.program_id.id if self.program_id else False,
            'department_id': self.department_id.id if self.department_id else False,
            'batch_id': self.batch_id.id if self.batch_id else False,
            'admission_year': admission_year,
            'graduation_year': graduation_year,
            'cgpa': self.cgpa or 0.0,
            'email': self.email or self.personal_email or '',
            'mobile': self.mobile or self.personal_mobile or '',
            'photo': self.image_1920 or False,
        }
        alumni = Alumni.create(alumni_vals)
        # Log on the student record
        self.message_post(
            body=f'Alumni record created: <a href="/odoo/alumni/{alumni.id}">{self.name}</a>',
        )

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_create_portal_user(self):
        """Create portal user for student

            NOTE: Direct SQL is used intentionally for group assignment because
            Odoo's _check_one_user_type() constraint auto-assigns all groups in
            the same category when using ORM. Since group_parent_portal and
            group_student_portal are in module_category_university, the ORM
            always assigns both. Direct SQL bypasses this constraint safely
            since res_groups_users_rel is a stable core Odoo table.

        """
        if not self.user_id and self.email:
            group_portal = self.env.ref('base.group_portal')
            group_student = self.env.ref('university_management.group_student_portal')
            group_parent = self.env.ref('university_management.group_parent_portal')

            # Create user with base portal only
            user = self.env['res.users'].create({
                'name': self.name,
                'login': self.email,
                'email': self.email,
                'partner_id': self.partner_id.id,
                'groups_id': [(6, 0, [group_portal.id])],
            })

            # Use direct SQL to bypass Odoo ORM group constraints
            self.env.cr.execute(
                "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
                (user.id, group_parent.id)
            )
            self.env.cr.execute(
                "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (group_student.id, user.id)
            )
            user.invalidate_recordset(['groups_id'])
            self.env['ir.rule'].clear_caches()
            self.user_id = user.id

    def action_student_attendance(self):
        """Open student attendance records"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Student Attendance',
            'res_model': 'student.attendance',
            'view_mode': 'list,kanban,form,calendar,pivot,graph',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
                'search_default_student_id': self.id,
            },
        }

    def action_fee_payment(self):
        """Open all fee payment records — used by Fee Paid smart button"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fee Payments — %s' % self.name,
            'res_model': 'fee.payment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_view_fee_due(self):
        """Open outstanding fee payments — used by Fee Due smart button"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Outstanding Fees — %s' % self.name,
            'res_model': 'fee.payment',
            'view_mode': 'list,form',
            'domain': [
                ('student_id', '=', self.id),
                ('outstanding_amount', '>', 0),
                ('state', 'not in', ['draft', 'cancelled', 'paid']),
            ],
            'context': {'default_student_id': self.id},
            'target': 'new',
        }

    def action_view_fee_transaction_history(self):
        """Open component-wise transaction history — used by Transactions smart button"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Transaction History — %s' % self.name,
            'res_model': 'fee.payment.line',
            'view_mode': 'list',
            'domain': [('fee_payment_id.student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
            'target': 'new',
        }

    def action_exam_result(self):
        """Open exam result records"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exam Results',
            'res_model': 'examination.result',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_student_document(self):
        """Open student document records"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'student.document',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def _search_total_fee_due(self, operator, value):
        """Enable searching/filtering on computed non-stored field total_fee_due"""
        allowed_operators = ['=', '!=', '>', '<', '>=', '<=']
        if operator not in allowed_operators:
            raise ValidationError(_('Unsupported operator for Total Fee Due search: %s') % operator)

        # Get all students first
        students = self.search([])
        matched_student_ids = []

        for student in students:
            due = student.total_fee_due or 0.0

            if operator == '=' and due == value:
                matched_student_ids.append(student.id)
            elif operator == '!=' and due != value:
                matched_student_ids.append(student.id)
            elif operator == '>' and due > value:
                matched_student_ids.append(student.id)
            elif operator == '<' and due < value:
                matched_student_ids.append(student.id)
            elif operator == '>=' and due >= value:
                matched_student_ids.append(student.id)
            elif operator == '<=' and due <= value:
                matched_student_ids.append(student.id)

        return [('id', 'in', matched_student_ids)]

    # ── USN Mapping ───────────────────────────────────────────────────

    def action_map_usn(self):
        """
        Map the university-issued USN to this student record.
        Called by admin once the affiliating university generates the USN.
        """
        self.ensure_one()
        if self.usn_mapped:
            raise ValidationError(_(
                'USN has already been mapped for this student (%s → %s).'
            ) % (self.temp_student_id, self.university_usn))
        if not self.university_usn:
            raise ValidationError(_('Please enter the University USN before mapping.'))
        existing = self.search([
            ('university_usn', '=', self.university_usn),
            ('id', '!=', self.id),
        ], limit=1)
        if existing:
            raise ValidationError(_(
                'USN %s is already assigned to student %s.'
            ) % (self.university_usn, existing.name))
        self.write({
            'usn_mapped': True,
            'usn_mapped_date': fields.Date.today(),
            'usn_mapped_by': self.env.user.id,
            'state': 'active',
        })
        self.message_post(
            body=_('University USN mapped: <b>%s</b> → <b>%s</b>. '
                   'Student record is now permanently active.')
            % (self.temp_student_id, self.university_usn)
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('USN Mapped Successfully'),
                'message': _('%s mapped to %s.') % (self.university_usn, self.name),
                'type': 'success',
                'sticky': False,
            },
        }