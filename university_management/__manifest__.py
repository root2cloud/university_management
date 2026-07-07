{
    'name': 'University Management System',
    'version': '18.0.1.0.1',
    'category': 'Education',
    'summary': 'Complete University/College ERP - Student, Faculty, Exam, Fee, Library, Hostel, Placement',
    'description': """
        Complete University Management System for Indian Universities/Colleges
        ===========================================================================

        Features:
        ---------
        * Student Admission & Registration Management
        * Academic Program, Department, Course Management
        * Faculty & Staff Management
        * Fee Collection & Payment Tracking
        * Examination, Hall Ticket & Result Management
        * Library Management with Book Issue/Return
        * Hostel & Mess Management
        * Transport & Bus Route Management
        * Campus Placement & Training
        * Student Projects & Internships
        * Events, Hackathons & Competitions
        * Alumni Management
        * Timetable & Class Schedule
        * Attendance Tracking (Student & Faculty)
        * Parent Portal Access
        * Automated Fee Reminders
        * ID Card & Hall Ticket Generation
        * Marksheet & Certificate Generation
        * Comprehensive Dashboard & Reports
        * IIC Activity Management (MSME)
        * NAAC Accreditation Management

        Integration with Odoo Core Modules:
        -----------------------------------
        * HR Module - Faculty linked to employees
        * Accounting - Fee payments & invoicing
        * Sale - Fee structure as products
        * Project - Student projects
        * Stock - Library inventory
        * Purchase - Hostel/Mess supplies
        * Contacts - Companies, Alumni, Parents
        * Calendar - Events & Timetables
        * Survey - Student feedback
        * Website - Student/Parent portals
        * Mail - Chatter on all models
    """,

    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'web',
        'board',
        'portal',
        'hr',
        'account',
        'sale_management',
        'stock',
        'purchase',
        'contacts',
        'event',
        'calendar',
        'survey',
        'website',
        'project',
        'web_view_leaflet_map',
        'web_view_leaflet_map_partner',
        'web_leaflet_lib',
        'payment',
        'account_payment',
        'website_payment',
        'crm',
        'odoo_website_helpdesk'
    ],

    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/sequence.xml',
        'data/online_exam_sequences.xml',
        'data/email_templates.xml',
        'data/sms_templates.xml',
        'data/automated_actions.xml',
        'data/default_data.xml',
        'data/indian_states_data.xml',
        'data/iic_naac_sequences.xml',
        'data/naac_cron.xml',
        'data/faculty_hr_data.xml',
        'data/student_enquiry_data.xml',
        'data/student_seat_blocking_data.xml',
        'data/student_counselling_session_data.xml',
        'data/asset_data.xml',
        'data/asset_cron_sequences.xml',
        'data/student_assignment_data.xml',

        # Views - Academic
        'views/academic/university_batch_views.xml',
        'views/academic/university_program_views.xml',
        'views/academic/university_department_views.xml',
        'views/academic/university_course_views.xml',
        'views/academic/university_classroom_views.xml',
        'views/academic/university_subject_views.xml',
        'views/academic/university_semester_views.xml',
        'views/academic/university_academic_year_views.xml',
        'views/academic/university_syllabus_views.xml',
        'views/academic/university_timetable_views.xml',

        # Views - Fee
        'views/fee/fee_structure_views.xml',
        'views/fee/fee_discount_views.xml',
        'views/fee/scholarship_views.xml',
        'views/fee/fee_payment_views.xml',
        'views/fee/fee_payment_line_views.xml',
        'views/fee/fee_reminder_views.xml',

        # Views - Examination
        'views/examination/exam_timetable_views.xml',
        'views/examination/hall_ticket_views.xml',
        'views/examination/exam_result_views.xml',
        'views/examination/exam_seating_views.xml',
        'views/examination/grade_system_views.xml',
        'views/examination/examination_views.xml',
        'views/examination/marksheet_views.xml',
        'views/examination/revaluation_views.xml',
        'views/examination/exam_evaluation_views.xml',
        'views/examination/mcq_question_views.xml',
        'views/examination/mcq_question_bank_views.xml',
        'views/examination/online_exam_views.xml',
        'views/examination/online_exam_attempt_views.xml',

        # Views - Student
        'views/student/student_attendance_views.xml',
        'views/student/student_document_views.xml',
        'views/student/student_parent_views.xml',
        'views/student/student_admission_views.xml',
        'views/student/student_registration_views.xml',
        'views/student/student_id_card_views.xml',
        'views/student/student_discipline_views.xml',
        'views/student/student_views.xml',
        'views/student/student_ledger_views.xml',
        'views/student/student_seat_blocking_views.xml',
        'views/student/student_enquiry_views.xml',
        'views/student/student_counselling_session_views.xml',
        'views/student/student_assignment_views.xml',
        'views/student/student_assignment_submission_views.xml',
        'views/student/student_assignment_grading_views.xml',

        # Views - Asset Management
        'views/asset/asset_views.xml',
        'views/asset/asset_maintenance_transfer_views.xml',
        'views/asset/asset_request_views.xml',
        'views/asset/asset_qr_scan_log_views.xml',
        'views/asset/helpdesk_purchase_views.xml',
        'views/asset/asset_audit_views.xml',
        'views/asset/asset_handover_views.xml',
        'views/asset/asset_purchase_request_views.xml',

        # Views - Faculty
        'views/faculty/faculty_views.xml',
        'views/faculty/faculty_attendance_views.xml',
        'views/faculty/faculty_salary_views.xml',
        'views/faculty/faculty_designation_views.xml',
        'views/faculty/faculty_leave_views.xml',
        'views/faculty/faculty_attendance_regularization_views.xml',
        'views/faculty/faculty_workload_views.xml',
        'views/faculty/faculty_evaluation_views.xml',
        'views/faculty/faculty_form16_views.xml',

        # Views - Library
        'views/library/library_book_views.xml',
        'views/library/library_issue_views.xml',
        'views/library/library_member_views.xml',
        'views/library/library_fine_views.xml',
        'views/library/library_category_views.xml',
        'views/library/library_reservation_views.xml',
        'views/library/library_digital_collection_views.xml',
        'views/library/library_digital_resource_views.xml',
        'views/library/library_digital_access_views.xml',

        # Views - Hostel
        'views/hostel/hostel_views.xml',
        'views/hostel/hostel_room_views.xml',
        'views/hostel/hostel_allocation_views.xml',
        'views/hostel/hostel_attendance_views.xml',
        'views/hostel/hostel_visitor_views.xml',
        'views/hostel/hostel_complaint_views.xml',
        'views/hostel/hostel_mess_views.xml',
        'views/hostel/mess_item_views.xml',
        'views/hostel/mess_menu_views.xml',
        'views/hostel/mess_attendance_views.xml',
        'views/hostel/mess_feedback_views.xml',

        # Views - Transport
        'views/transport/transport_route_views.xml',
        'views/transport/transport_vehicle_views.xml',
        'views/transport/transport_driver_views.xml',
        'views/transport/transport_allocation_views.xml',
        'views/transport/transport_stop_views.xml',
        'views/transport/transport_fee_views.xml',

        # Views - Placement
        'views/placement/placement_drive_views.xml',
        'views/placement/placement_company_views.xml',
        'views/placement/placement_application_views.xml',
        'views/placement/placement_offer_views.xml',
        'views/placement/placement_training_views.xml',
        'views/placement/placement_coordinator_views.xml',

        # Views - Alumni
        'views/alumni/alumni_views.xml',
        'views/alumni/alumni_event_views.xml',
        'views/alumni/alumni_donation_views.xml',
        'views/alumni/alumni_achievement_views.xml',

        # Views - Project
        'views/project/student_project_views.xml',
        'views/project/project_guide_views.xml',
        'views/project/project_evaluation_views.xml',
        'views/project/project_presentation_views.xml',

        # Views - Internship
        'views/internship/internship_views.xml',
        'views/internship/internship_company_views.xml',
        'views/internship/internship_report_views.xml',
        'views/internship/internship_evaluation_views.xml',

        # Views - Events
        'views/events/university_event_views.xml',
        'views/events/event_registration_views.xml',
        'views/events/event_sponsor_views.xml',
        'views/events/hackathon_views.xml',
        'views/events/hackathon_team_views.xml',
        'views/events/hackathon_judge_views.xml',
        'views/events/hackathon_winner_views.xml',

        # Views - Timetable
        'views/timetable/class_timetable_views.xml',
        'views/timetable/faculty_timetable_views.xml',
        'views/timetable/lab_schedule_views.xml',
        'views/timetable/timetable_substitution_views.xml',

        # Views - Dashboard
        'views/dashboard/university_dashboard_views.xml',

        # ─── Views: IIC ──────────────────────────────────────
        'views/iic/iic_speaker_views.xml',
        'views/iic/iic_event_views.xml',
        'views/iic/iic_attendance_views.xml',
        'views/iic/iic_media_views.xml',
        'views/iic/iic_event_report_views.xml',
        'views/iic/iic_poster_views.xml',
        'views/iic/iic_approval_log_views.xml',
        'views/iic/iic_dashboard_views.xml',

        # ─── Views: NAAC ─────────────────────────────────────
        'views/naac/naac_criterion_views.xml',
        'views/naac/naac_metric_views.xml',
        'views/naac/naac_department_activity_views.xml',
        'views/naac/naac_evidence_views.xml',
        'views/naac/naac_faculty_research_views.xml',
        'views/naac/naac_student_progression_views.xml',
        'views/naac/naac_aqar_views.xml',
        'views/naac/naac_ssr_views.xml',
        'views/naac/naac_dashboard_views.xml',

        # ── Views: NBA ──────────────────────────
        'views/nba/nba_sar_views.xml',
        'views/nba/nba_co_views.xml',
        'views/nba/nba_research_views.xml',
        'views/nba/nba_evidence_views.xml',
        'views/nba/nba_criteria_views.xml',
        'views/nba/nba_dashboard_views.xml',

        # Wizards (BEFORE reports)
        'wizard/admission/bulk_admission_wizard_views.xml',
        'wizard/id_card/bulk_id_card_wizard_views.xml',
        'wizard/registration/bulk_registration_wizard_views.xml',
        'wizard/fees/fee_reminder_wizard_views.xml',
        'wizard/hall_ticket/generate_hall_ticket_wizard_views.xml',
        'wizard/hall_ticket/generate_hall_ticket_wizard_line_views.xml',
        'wizard/promotion/promote_student_wizard_views.xml',
        'wizard/result/publish_result_wizard_views.xml',
        'wizard/examination/auto_evaluate_wizard_views.xml',
        'wizard/examination/generate_seating_wizard_views.xml',
        'wizard/attendance/attendance_report_wizard_views.xml',
        'wizard/attendance/bulk_attendance_wizard_views.xml',
        'wizard/placements/placement_report_wizard_views.xml',
        'wizard/iic/iic_report_wizard_views.xml',
        'wizard/naac/naac_aqar_wizard_views.xml',
        'wizard/naac/naac_evidence_bulk_wizard_views.xml',
        'wizard/date_range/fee_date_range_wizard_views.xml',
        'wizard/nba/nba_compute_wizard_views.xml',
        'wizard/nba/nba_evidence_bulk_wizard_views.xml',
        'wizard/nba/nba_generate_sar_wizard_views.xml',
        'wizard/asset/asset_stock_issue_wizard_views.xml',

        # Reports
        'report/student_id_card.xml',
        'report/hall_ticket_report.xml',
        'report/fee_receipt.xml',
        'report/marksheet_report.xml',
        'report/salary_slip_report.xml',
        'report/faculty_form16_report.xml',
        'report/student_report.xml',
        'report/attendance_report.xml',
        'report/placement_report.xml',
        'report/iic_event_report.xml',
        'report/iic_attendance_report.xml',
        'report/iic_poster_report.xml',
        'report/naac_activity_report.xml',
        'report/naac_aqar_report.xml',
        'report/naac_reports.xml',
        'report/nba_sar_report.xml',
        'report/asset_reports.xml',
        'report/asset_new_reports.xml',

        'templates/mains/admission_templates.xml',
        'templates/mains/library_templates.xml',
        'templates/library/opac_templates.xml',
        'templates/mains/program_templates.xml',
        'templates/mains/department_templates.xml',
        'templates/mains/faculty_templates.xml',
        'templates/mains/placement_templates.xml',
        'templates/mains/document_templates.xml',
        'templates/mains/event_templates.xml',
        'templates/mains/contact_templates.xml',
        'templates/mains/about_templates.xml',
        'templates/mains/home_templates.xml',


        'templates/studentportal/studentdashboard_templates.xml',
        'templates/alumniportal/alumni_portal_templates.xml',
        'templates/parentportal/parentdashboard_templates.xml',
        'templates/facultyportal/facultydashboard_templates.xml',
        'templates/hallticket/hallticket_templates.xml',
        'templates/examination/online_exam_templates.xml',
        'templates/marksheet/marksheet_templates.xml',
        'templates/idcard/idcard_templates.xml',
        'templates/iic/iic_portal_templates.xml',
        'templates/naac/naac_evidence_templates.xml',
        'templates/portalfee/portal_fee_templates.xml',
        'templates/asset/asset_qr_templates.xml',

        # Menu
        'views/menu_views.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'university_management/static/src/css/dashboard.css',
            'university_management/static/src/css/iic_naac_dashboard.css',
            'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
            'university_management/static/src/js/charts.js',
            'university_management/static/src/js/dashboard.js',
            'university_management/static/src/xml/dashboard_templates.xml',
            'university_management/static/src/xml/iic_dashboard_templates.xml',
            'university_management/static/src/xml/naac_dashboard_templates.xml',
            'university_management/static/src/js/iic_dashboard.js',
            'university_management/static/src/js/naac_dashboard.js',
            'university_management/static/src/xml/nba_dashboard_templates.xml',
            'university_management/static/src/js/nba_dashboard.js',
            'university_management/static/src/css/ai_assistant.css',
            'university_management/static/src/xml/ai_assistant_templates.xml',
            'university_management/static/src/js/ai_assistant.js',
        ],
    },

    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
}
# -*- coding: utf-8 -*-
