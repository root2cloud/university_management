# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import xlrd
import csv
import io
import logging

_logger = logging.getLogger(__name__)


class BulkAdmissionWizard(models.TransientModel):
    """
    Wizard for bulk student admission import from Excel/CSV
    """
    _name = 'bulk.admission.wizard'
    _description = 'Bulk Admission Wizard'

    import_file = fields.Binary(string='Import File', required=True, help='Upload Excel (.xls, .xlsx) or CSV file')
    filename = fields.Char(string='Filename')
    file_type = fields.Selection([
        ('excel', 'Excel'),
        ('csv', 'CSV')
    ], string='File Type', default='excel', required=True)

    program_id = fields.Many2one('university.program', string='Program', required=True)
    department_id = fields.Many2one('university.department', string='Department', required=True)
    batch_id = fields.Many2one('university.batch', string='Batch', required=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year', required=True)
    admission_date = fields.Date(string='Admission Date', default=fields.Date.today, required=True)

    auto_generate_registration = fields.Boolean(string='Auto Generate Registration Number', default=True)
    auto_approve = fields.Boolean(string='Auto Approve Admissions', default=False)
    send_email = fields.Boolean(string='Send Email Notification', default=True)
    send_sms = fields.Boolean(string='Send SMS Notification', default=False)

    sample_file_url = fields.Char(string='Sample File',
                                  default='/university_management/static/src/samples/bulk_admission_sample.xlsx',
                                  readonly=True)

    def action_download_sample(self):
        """Download sample template file"""
        return {
            'type': 'ir.actions.act_url',
            'url': self.sample_file_url,
            'target': 'new',
        }

    def action_import_admissions(self):
        """Process bulk admission import"""
        self.ensure_one()

        if not self.import_file:
            raise UserError(_('Please upload a file to import.'))

        try:
            if self.file_type == 'excel':
                records = self._parse_excel_file()
            else:
                records = self._parse_csv_file()

            if not records:
                raise UserError(_('No valid records found in the file.'))

            # Process admissions
            created_admissions = self._create_admissions(records)

            # Show result
            return self._show_result(created_admissions)

        except Exception as e:
            _logger.error(f"Bulk admission import error: {str(e)}")
            raise UserError(_('Import failed: %s') % str(e))

    def _parse_excel_file(self):
        import openpyxl, io
        file_data = base64.b64decode(self.import_file)
        wb = openpyxl.load_workbook(io.BytesIO(file_data), read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h).strip().lower() if h else '' for h in rows[0]]
        records = []
        for row in rows[1:]:
            row_data = {headers[i]: row[i] for i in range(len(headers)) if headers[i]}
            if row_data.get('name') or row_data.get('student_name'):
                records.append(row_data)
        return records

    def _parse_csv_file(self):
        """Parse CSV file and return list of records"""
        file_data = base64.b64decode(self.import_file)
        csv_data = io.StringIO(file_data.decode('utf-8'))
        csv_reader = csv.DictReader(csv_data)

        records = []
        for row in csv_reader:
            # Convert keys to lowercase
            row_data = {k.strip().lower(): v for k, v in row.items()}
            if row_data.get('name') or row_data.get('student_name'):
                records.append(row_data)

        return records

    def _create_admissions(self, records):
        """Create admission records from parsed data"""
        Admission = self.env['student.admission']
        Student = self.env['student.student']

        created_admissions = []
        errors = []

        for idx, record in enumerate(records, start=2):
            try:
                # Prepare admission data
                admission_vals = self._prepare_admission_vals(record)

                # Create admission
                admission = Admission.create(admission_vals)
                created_admissions.append(admission)

                # Auto approve if enabled
                if self.auto_approve:
                    admission.action_approve()

                # Send notifications
                if self.send_email and admission.student_id.email:
                    self._send_admission_email(admission)

                if self.send_sms and admission.student_id.mobile:
                    self._send_admission_sms(admission)

            except Exception as e:
                error_msg = f"Row {idx}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg)
                errors.append(f'Row {idx}: {e}')
                _logger.error('Row %s failed: %s', idx, e)

        if errors:
            # Log errors but continue
            error_log = "\n".join(errors)
            _logger.warning(f"Bulk admission errors:\n{error_log}")

        # Convert list of admission records into a recordset so `.ids` works
        # Odoo expects a recordset for domain operations, but we currently
        # accumulate admissions in a Python list. Convert the list of
        # admissions into a proper recordset before returning.
        if isinstance(created_admissions, list):
            created_admissions = Admission.browse([adm.id for adm in created_admissions])
        return created_admissions

    def _prepare_admission_vals(self, record):
        student_vals = {
            'name': record.get('name') or record.get('student_name'),
            'email': record.get('email'),
            'mobile': str(record.get('mobile') or record.get('phone') or '').strip() or False,
            'date_of_birth': self._parse_date(record.get('date_of_birth') or record.get('dob')),
            'gender': self._parse_gender(record.get('gender')),
            'blood_group': str(record.get('blood_group') or '').strip().lower() or False,
            'aadhar_number': str(record.get('aadhar_number') or record.get('aadhar') or '').strip() or False,
            'current_address': record.get('address') or record.get('current_address'),
            'permanent_address': record.get('permanent_address') or record.get('address'),
            # DO NOT pass 'state' — wizard sets it via program_id/batch_id
            # DO NOT pass father_name/mother_name — those are on student.parent, not student.student
            'program_id': self.program_id.id,
            'batch_id': self.batch_id.id,
            'academic_year_id': self.academic_year_id.id,
            'admission_date': self.admission_date,
        }

        student = self.env['student.student'].create(student_vals)

        # Create parent records directly here
        ParentObj = self.env['student.parent']
        father_name = str(record.get('father_name') or '').strip()
        mother_name = str(record.get('mother_name') or '').strip()
        guardian_mobile = str(record.get('guardian_mobile') or record.get('parent_mobile') or '').strip()

        if father_name:
            ParentObj.create({
                'student_id': student.id,
                'name': father_name,
                'relationship': 'father',
                'phone': guardian_mobile or False,
                'is_primary_contact': True,
                'is_emergency_contact': True,
            })
        if mother_name:
            ParentObj.create({
                'student_id': student.id,
                'name': mother_name,
                'relationship': 'mother',
            })

        admission_vals = {
            'applicant_name': student_vals['name'],
            'email': student_vals.get('email') or 'noemail@placeholder.com',
            'mobile': student_vals.get('mobile') or '0000000000',
            'date_of_birth': student_vals['date_of_birth'],
            'gender': student_vals['gender'],
            'program_id': self.program_id.id,
            'department_id': self.department_id.id,
            'batch_id': self.batch_id.id,
            'academic_year_id': self.academic_year_id.id,
            'admission_date': self.admission_date,
            'admission_category': str(record.get('category') or record.get('admission_category') or 'general').lower(),
            'previous_qualification': str(record.get('previous_qualification') or 'Intermediate'),
            'previous_school': str(record.get('previous_school') or record.get('previous_institution') or '-'),
            'previous_board': str(record.get('previous_board') or '-'),
            'previous_percentage': float(record.get('previous_percentage') or 0),
            'previous_year': int(float(record.get('previous_year') or 0)) or fields.Date.today().year,
            'current_address': student_vals.get('current_address') or '-',
            'permanent_address': student_vals.get('permanent_address') or '-',
            'father_name': father_name or '-',
            'mother_name': mother_name or '-',
            'student_id': student.id,
            'application_fee_paid': True,  # bulk admission bypasses fee gate
            'state': 'admitted',
        }

        return admission_vals

    def _parse_date(self, date_str):
        """Parse date from various formats"""
        if not date_str:
            return False

        try:
            # Try different date formats
            from dateutil import parser
            return parser.parse(str(date_str)).date()
        except:
            return False

    def _parse_gender(self, gender_str):
        """Parse gender value"""
        if not gender_str:
            return 'other'

        gender_lower = str(gender_str).lower().strip()
        if gender_lower in ['m', 'male']:
            return 'male'
        elif gender_lower in ['f', 'female']:
            return 'female'
        else:
            return 'other'

    def _send_admission_email(self, admission):
        """Send admission confirmation email"""
        template = self.env.ref('university_management.email_template_admission_confirmation',
                                raise_if_not_found=False)
        if template:
            template.send_mail(admission.id, force_send=True)

    def _send_admission_sms(self, admission):
        """Send admission confirmation SMS"""
        # Implement SMS sending logic
        pass

    def _show_result(self, created_admissions):
        """Show import result to user"""
        return {
            'name': _('Bulk Admission Result'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.admission',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_admissions.ids)],
            'context': {'create': False},
            'target': 'current',
        }