import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class Students(models.Model):
    _name = "students.info"
    _description = "Students Information"

    name = fields.Char(string="Name")
    age = fields.Integer(string="Age")
    date_of_birth = fields.Date(string="Date of birth")
    cls = fields.Char(string="Class")
    rol_no = fields.Integer(string="Roll Number")

    @api.model
    def create(self, vals):
        print("create called")
        _logger.info("Creating a new student with values: %s", vals)

        if vals.get("name"):
            vals["name"] = vals["name"].title()

        record = super(Students, self).create(vals)

        _logger.info("Student created: %s", record.name)
        return record

    def write(self, vals):
        print("write called")
        _logger.info("Updating student %s with values: %s", self.name, vals)

        res = super(Students, self).write(vals)

        _logger.info("Student updated successfully: %s", self.name)
        return res

    def unlink(self):
        print("unlink called")
        for rec in self:
            _logger.info("Deleting student: %s", rec.name)

        return super(Students, self).unlink()

    def copy(self, default=None):
        print("copy called")
        default = dict(default or {})

        default["name"] = (self.name or "") + " (copy)"
        default["rol_no"] = 0

        _logger.info("Duplicating student '%s' with defaults: %s", self.name, default)
        return super(Students, self).copy(default)

    @api.model
    def create_student(self, vals):
        print("school management")
        """Creating a new student with given values"""
        return self.create(vals)

    # create a student
    # student = env['students.info'].create_student({
    #     'name': 'ravi',
    #     'age': '20',
    #     'date_of_birth': '2005-01-01',
    #     'cls': '10th',
    #     'rol_no': '15',
    # })


