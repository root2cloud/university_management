{
    'name': 'Hackathon Management',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'Complete Hackathon Management System for Colleges',
    'description': """
        Comprehensive Hackathon Management Module
        ==========================================
        * Event Management
        * Team Registration & Management
        * Participant Tracking
        * Multiple Tracks/Themes
        * Mentor Assignment
        * Judge Panel Management
        * Project Submissions
        * Scoring & Evaluation
        * Winner Declaration
        * Certificate Generation
        * Resource Management
        * Venue & Schedule Management
    """,
    'author': 'Your College Name',
    'website': 'https://www.yourcollege.edu',
    'depends': ['base', 'mail', 'contacts', 'website'],
    'data': [
        'security/hackathon_security.xml',
        'security/ir.model.access.csv',
        'data/hackathon_data.xml',
        'views/hackathon_event_views.xml',
        'views/hackathon_track_views.xml',
        'views/hackathon_team_views.xml',
        'views/hackathon_participant_views.xml',
        'views/hackathon_mentor_views.xml',
        'views/hackathon_judge_views.xml',
        'views/hackathon_submission_views.xml',
        'views/hackathon_scoring_views.xml'
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}