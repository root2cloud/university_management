from odoo import models, fields, api


class StudentDocument(models.Model):
    _name = 'school.student.document'
    _description = 'Student Document'

    student_id = fields.Many2one('school.student', string="Student")
    name = fields.Char(string="Document Name")
    document_type = fields.Selection([
        ('birth_certificate', 'Birth Certificate'),
        ('id_proof', 'ID Proof'),
        ('address_proof', 'Address Proof')
    ], string="Document Type", required=True)
    file_path = fields.Binary(string="File")
