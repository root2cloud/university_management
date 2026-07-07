# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectGuide(models.Model):
    _name = 'project.guide'
    _description = 'Project Guide Assignment'
    _order = 'academic_year_id desc'

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, index=True)

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)

    # Projects
    project_ids = fields.One2many('student.project', 'project_guide_id', string='Projects as Guide')
    co_guide_project_ids = fields.One2many('student.project',
                                            compute='_compute_co_guide_projects',
                                            string='Projects as Co-Guide')

    total_projects = fields.Integer(string='Total Projects', compute='_compute_total', store=True)
    max_projects_allowed = fields.Integer(string='Max Projects Allowed', default=5)

    # Availability
    available = fields.Boolean(string='Available for New Projects', default=True)

    @api.depends('project_ids')
    def _compute_total(self):
        for record in self:
            # Count main guide projects (from One2many)
            main_guide_count = len(record.project_ids)

            # Count co-guide projects (where this faculty is co-guide)
            co_guide_count = self.env['student.project'].search_count([
                ('co_guide_id', '=', record.faculty_id.id),
                ('academic_year_id', '=', record.academic_year_id.id)
            ])

            record.total_projects = main_guide_count + co_guide_count

    def _compute_co_guide_projects(self):
        """Compute projects where this faculty is the co-guide"""
        for record in self:
            co_guide_projects = self.env['student.project'].search([
                ('co_guide_id', '=', record.faculty_id.id),
                ('academic_year_id', '=', record.academic_year_id.id)
            ])
            record.co_guide_project_ids = co_guide_projects

    def action_view_projects(self):
        """Open all projects (both as guide and co-guide)."""
        self.ensure_one()
        # Main guide projects
        main_project_ids = self.project_ids.ids

        # Co-guide projects
        co_guide_projects = self.env['student.project'].search([
            ('co_guide_id', '=', self.faculty_id.id),
            ('academic_year_id', '=', self.academic_year_id.id)
        ])
        co_project_ids = co_guide_projects.ids

        # Combine both
        all_project_ids = list(set(main_project_ids + co_project_ids))

        return {
            'name': _('Guided Projects'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.project',
            'view_mode': 'list,form,kanban',
            'domain': [('id', 'in', all_project_ids)],
            'context': {},
        }

    def action_view_guide_projects(self):
        """Open projects where this faculty is the main guide."""
        self.ensure_one()
        return {
            'name': _('Projects as Main Guide'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.project',
            'view_mode': 'list,form,kanban',
            'domain': [('id', 'in', self.project_ids.ids)],
            'context': {'default_guide_id': self.faculty_id.id},
        }

    def action_view_co_guide_projects(self):
        """Open projects where this faculty is the co-guide."""
        self.ensure_one()
        co_guide_projects = self.env['student.project'].search([
            ('co_guide_id', '=', self.faculty_id.id),
            ('academic_year_id', '=', self.academic_year_id.id)
        ])
        return {
            'name': _('Projects as Co-Guide'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.project',
            'view_mode': 'list,form,kanban',
            'domain': [('id', 'in', co_guide_projects.ids)],
            'context': {'default_co_guide_id': self.faculty_id.id},
        }
