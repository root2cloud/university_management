# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  TOOL DEFINITIONS  (Anthropic format — auto-converted for OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_students",
        "description": "Search for students by name, registration number, USN, course, semester, or department. Returns student list with basic info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Student name (partial match)"},
                "registration_number": {"type": "string", "description": "Student registration number"},
                "university_usn": {"type": "string", "description": "University USN"},
                "course_id_name": {"type": "string", "description": "Course/program name"},
                "semester": {"type": "string", "description": "Semester name"},
                "limit": {"type": "integer", "description": "Max records to return (default 10)"}
            }
        }
    },
    {
        "name": "get_fee_details",
        "description": "Get fee payment details for a student: total fee, amount paid, outstanding amount, payment dates, payment history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name to search"}
            }
        }
    },
    {
        "name": "get_attendance",
        "description": "Get attendance percentage and records for a student or group of students.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name"},
                "below_percentage": {"type": "number", "description": "Find all students below this attendance %"}
            }
        }
    },
    {
        "name": "get_exam_results",
        "description": "Get exam results, marks, CGPA, pass/fail status for a student.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name"}
            }
        }
    },
    {
        "name": "get_scholarship_info",
        "description": "Get scholarship details: granted amount, disbursed amount, pending amount for a student or all scholarships.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name"},
                "state": {"type": "string", "description": "Filter by state: draft/approved/disbursed"}
            }
        }
    },
    {
        "name": "get_hostel_transport",
        "description": "Get hostel allocation and transport allocation details for a student.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name"}
            }
        }
    },
    {
        "name": "get_enrolled_courses",
        "description": "Get courses/subjects a student is enrolled in, with faculty and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID"},
                "student_name": {"type": "string", "description": "Student name"}
            }
        }
    },
    {
        "name": "get_university_stats",
        "description": "Get overall university statistics: total students, faculty, fee collection, placements, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category: students/fees/faculty/placements/hostel/library/all"
                }
            }
        }
    },
    {
        "name": "search_faculty",
        "description": "Search faculty by name or department. Returns faculty info, designation, subjects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Faculty name (partial match)"},
                "department": {"type": "string", "description": "Department name"},
                "limit": {"type": "integer", "description": "Max records (default 10)"}
            }
        }
    }
]


def _tools_to_openai(tools):
    """Convert Anthropic tool schema → OpenAI function calling schema."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            }
        })
    return result


class AIAssistantController(http.Controller):

    # ── Public endpoint ───────────────────────────────────────────────────────

    @http.route('/university/ai/chat', type='json', auth='user', methods=['POST'])
    def chat(self, messages, **kwargs):
        """
        Main chat endpoint.

        Reads provider config from Odoo System Parameters:
          university.ai.provider   = anthropic | openai_compatible  (default: anthropic)
          university.ai.api_key    = <your key>
          university.ai.model      = <model name>
          university.ai.base_url   = <base url>  (only for openai_compatible)

        Supported providers (openai_compatible):
          OpenRouter  → https://openrouter.ai/api/v1
          Groq        → https://api.groq.com/openai/v1
          Together AI → https://api.together.xyz/v1
          Mistral     → https://api.mistral.ai/v1
          Ollama      → http://localhost:11434/v1
          OpenAI      → https://api.openai.com/v1
          Any other OpenAI-compatible endpoint.
        """
        try:
            params = request.env['ir.config_parameter'].sudo()

            api_key  = params.get_param('university.ai.api_key', '')
            provider = params.get_param('university.ai.provider', 'anthropic').strip().lower()
            model    = params.get_param('university.ai.model', '').strip()
            base_url = params.get_param('university.ai.base_url', '').strip()

            if not api_key:
                return {
                    'error': (
                        'API key not configured. '
                        'Go to Settings → Technical → System Parameters and set:\n'
                        '  university.ai.api_key   = your-key\n'
                        '  university.ai.provider  = anthropic  OR  openai_compatible\n'
                        '  university.ai.model     = model-name\n'
                        '  university.ai.base_url  = https://...  (if openai_compatible)'
                    )
                }

            system_prompt = self._build_system_prompt()

            if provider == 'anthropic':
                model = model or 'claude-sonnet-4-20250514'
                response_text = self._run_anthropic(api_key, model, system_prompt, messages)
            elif provider == 'openai_compatible':
                if not base_url:
                    return {'error': 'university.ai.base_url is required for openai_compatible provider.'}
                if not model:
                    return {'error': 'university.ai.model is required for openai_compatible provider.'}
                response_text = self._run_openai_compatible(api_key, model, base_url, system_prompt, messages)
            else:
                return {'error': f'Unknown provider "{provider}". Use "anthropic" or "openai_compatible".'}

            return {'response': response_text}

        except Exception as e:
            _logger.exception("AI Assistant error")
            return {'error': str(e)}

    # ── System prompt ─────────────────────────────────────────────────────────

    def _build_system_prompt(self):
        return """You are an intelligent AI assistant for a University Management System built on Odoo.
You have access to real-time university data through tools. Use them to answer any question about:
- Students (fees, attendance, results, enrollment, scholarships, hostel, transport)
- Faculty (details, workload, salary, leave)
- University statistics and reports

Rules:
1. Always use tools to fetch real data before answering — never guess or make up numbers.
2. When a user asks about a student by name, first call search_students to get their ID, then use that ID for subsequent tool calls.
3. Present financial amounts in Indian Rupee format (₹).
4. Be concise but complete. Format tables using plain text when showing lists.
5. If no data is found, say so clearly.
6. You are read-only — you cannot modify any data."""

    # ── Anthropic agentic loop ────────────────────────────────────────────────

    def _run_anthropic(self, api_key, model, system_prompt, messages):
        """Agentic loop using Anthropic Messages API with native tool use."""
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }

        current_messages = list(messages)
        max_iterations = 8

        for _ in range(max_iterations):
            payload = {
                'model': model,
                'max_tokens': 2048,
                'system': system_prompt,
                'tools': TOOLS,
                'messages': current_messages,
            }

            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload,
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            stop_reason = data.get('stop_reason')

            if stop_reason == 'end_turn':
                for block in data.get('content', []):
                    if block.get('type') == 'text':
                        return block['text']
                return 'I processed your request but had no text response.'

            elif stop_reason == 'tool_use':
                current_messages.append({
                    'role': 'assistant',
                    'content': data['content']
                })

                tool_results = []
                for block in data['content']:
                    if block.get('type') == 'tool_use':
                        try:
                            result = self._execute_tool(block['name'], block.get('input', {}))
                        except Exception as e:
                            result = {'error': str(e)}

                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block['id'],
                            'content': json.dumps(result, default=str)
                        })

                current_messages.append({'role': 'user', 'content': tool_results})
            else:
                break

        return 'I was unable to complete the request within the allowed steps.'

    # ── OpenAI-compatible agentic loop ────────────────────────────────────────

    def _run_openai_compatible(self, api_key, model, base_url, system_prompt, messages):
        """
        Agentic loop using OpenAI-compatible /chat/completions API.
        Works with OpenRouter, Groq, Together, Mistral, Ollama, OpenAI, etc.
        """
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        # Build message list: system message first, then conversation
        current_messages = [{'role': 'system', 'content': system_prompt}]
        for m in messages:
            current_messages.append({'role': m['role'], 'content': m['content']})

        openai_tools = _tools_to_openai(TOOLS)
        url = base_url.rstrip('/') + '/chat/completions'
        max_iterations = 8

        for _ in range(max_iterations):
            payload = {
                'model': model,
                'max_tokens': 2048,
                'messages': current_messages,
                'tools': openai_tools,
                'tool_choice': 'auto',
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get('choices', [{}])[0]
            message = choice.get('message', {})
            finish_reason = choice.get('finish_reason', '')

            # Add assistant reply to history
            current_messages.append(message)

            if finish_reason == 'tool_calls' or message.get('tool_calls'):
                tool_calls = message.get('tool_calls', [])

                for tc in tool_calls:
                    fn = tc.get('function', {})
                    tool_name = fn.get('name', '')
                    try:
                        tool_input = json.loads(fn.get('arguments', '{}'))
                        result = self._execute_tool(tool_name, tool_input)
                    except Exception as e:
                        result = {'error': str(e)}

                    current_messages.append({
                        'role': 'tool',
                        'tool_call_id': tc.get('id', ''),
                        'content': json.dumps(result, default=str),
                    })

            elif finish_reason in ('stop', 'end_turn', 'eos', 'length') or not message.get('tool_calls'):
                content = message.get('content', '')
                if content:
                    return content
                return 'I processed your request but had no text response.'
            else:
                break

        return 'I was unable to complete the request within the allowed steps.'

    # ── Tool dispatcher ───────────────────────────────────────────────────────

    def _execute_tool(self, tool_name, tool_input):
        env = request.env
        dispatch = {
            'search_students':    self._search_students,
            'get_fee_details':    self._get_fee_details,
            'get_attendance':     self._get_attendance,
            'get_exam_results':   self._get_exam_results,
            'get_scholarship_info': self._get_scholarship_info,
            'get_hostel_transport': self._get_hostel_transport,
            'get_enrolled_courses': self._get_enrolled_courses,
            'get_university_stats': self._get_university_stats,
            'search_faculty':     self._search_faculty,
        }
        fn = dispatch.get(tool_name)
        if fn:
            return fn(env, tool_input)
        return {'error': f'Unknown tool: {tool_name}'}

    # ── Tool implementations (unchanged) ─────────────────────────────────────

    def _search_students(self, env, inp):
        domain = []
        if inp.get('name'):
            domain.append(('name', 'ilike', inp['name']))
        if inp.get('registration_number'):
            domain.append(('registration_number', 'ilike', inp['registration_number']))
        if inp.get('university_usn'):
            domain.append(('university_usn', 'ilike', inp['university_usn']))
        if inp.get('course_id_name'):
            domain.append(('course_id.name', 'ilike', inp['course_id_name']))
        if inp.get('semester'):
            domain.append(('current_semester_id.name', 'ilike', inp['semester']))

        limit = inp.get('limit', 10)
        students = env['student.student'].sudo().search(domain, limit=limit)
        return {
            'count': len(students),
            'students': [{
                'id': s.id,
                'name': s.name,
                'registration_number': s.registration_number,
                'university_usn': s.university_usn or '',
                'course': s.course_id.name if s.course_id else '',
                'semester': s.current_semester_id.name if s.current_semester_id else '',
                'department': s.department_id.name if s.department_id else '',
                'email': s.email or '',
                'mobile': s.mobile or '',
                'cgpa': s.cgpa or 0,
                'attendance_percentage': s.attendance_percentage or 0,
                'state': s.state if hasattr(s, 'state') else '',
            } for s in students]
        }

    def _get_fee_details(self, env, inp):
        students = self._resolve_students(env, inp)
        result = []
        for s in students:
            payments = env['fee.payment'].sudo().search([('student_id', '=', s.id)])
            payment_list = []
            for p in payments:
                payment_list.append({
                    'name': p.name,
                    'date': str(p.payment_date) if hasattr(p, 'payment_date') and p.payment_date else '',
                    'amount': p.amount_paid if hasattr(p, 'amount_paid') else 0,
                    'state': p.state if hasattr(p, 'state') else '',
                })
            result.append({
                'student_id': s.id,
                'student_name': s.name,
                'total_fee': s.total_fee if hasattr(s, 'total_fee') else 0,
                'fee_paid': s.fee_paid if hasattr(s, 'fee_paid') else 0,
                'fee_due': s.fee_due if hasattr(s, 'fee_due') else 0,
                'payments': payment_list,
            })
        return result if len(result) > 1 else (result[0] if result else {'error': 'Student not found'})

    def _get_attendance(self, env, inp):
        if inp.get('below_percentage'):
            pct = inp['below_percentage']
            students = env['student.student'].sudo().search([
                ('attendance_percentage', '<', pct)
            ], limit=50)
            return {
                'query': f'Students with attendance below {pct}%',
                'count': len(students),
                'students': [{
                    'id': s.id,
                    'name': s.name,
                    'registration_number': s.registration_number,
                    'attendance_percentage': s.attendance_percentage or 0,
                    'course': s.course_id.name if s.course_id else '',
                    'semester': s.current_semester_id.name if s.current_semester_id else '',
                } for s in students]
            }

        students = self._resolve_students(env, inp)
        result = []
        for s in students:
            records = env['student.attendance'].sudo().search(
                [('student_id', '=', s.id)], limit=30, order='date desc'
            )
            result.append({
                'student_id': s.id,
                'student_name': s.name,
                'attendance_percentage': s.attendance_percentage or 0,
                'recent_records': [{
                    'date': str(r.date),
                    'subject': r.subject_id.name if hasattr(r, 'subject_id') and r.subject_id else '',
                    'status': r.state if hasattr(r, 'state') else '',
                } for r in records]
            })
        return result if len(result) > 1 else (result[0] if result else {'error': 'Student not found'})

    def _get_exam_results(self, env, inp):
        students = self._resolve_students(env, inp)
        result = []
        for s in students:
            results = env['exam.result'].sudo().search([('student_id', '=', s.id)])
            result.append({
                'student_id': s.id,
                'student_name': s.name,
                'cgpa': s.cgpa or 0,
                'results': [{
                    'subject': r.subject_id.name if hasattr(r, 'subject_id') and r.subject_id else '',
                    'marks_obtained': r.marks_obtained if hasattr(r, 'marks_obtained') else 0,
                    'max_marks': r.max_marks if hasattr(r, 'max_marks') else 0,
                    'grade': r.grade if hasattr(r, 'grade') else '',
                    'result': r.result if hasattr(r, 'result') else '',
                    'semester': r.semester_id.name if hasattr(r, 'semester_id') and r.semester_id else '',
                } for r in results]
            })
        return result if len(result) > 1 else (result[0] if result else {'error': 'Student not found'})

    def _get_scholarship_info(self, env, inp):
        domain = []
        if inp.get('student_id'):
            domain.append(('student_id', '=', inp['student_id']))
        elif inp.get('student_name'):
            students = env['student.student'].sudo().search([
                ('name', 'ilike', inp['student_name'])
            ], limit=5)
            if not students:
                return {'error': 'Student not found'}
            domain.append(('student_id', 'in', students.ids))
        if inp.get('state'):
            domain.append(('state', '=', inp['state']))

        scholarships = env['student.scholarship'].sudo().search(domain, limit=20)
        return {
            'count': len(scholarships),
            'scholarships': [{
                'id': s.id,
                'name': s.name,
                'student': s.student_id.name if s.student_id else '',
                'amount': s.scholarship_amount if hasattr(s, 'scholarship_amount') else 0,
                'disbursed_amount': s.disbursed_amount if hasattr(s, 'disbursed_amount') else 0,
                'state': s.state if hasattr(s, 'state') else '',
                'scholarship_type': s.scholarship_type if hasattr(s, 'scholarship_type') else '',
                'award_date': str(s.award_date) if hasattr(s, 'award_date') and s.award_date else '',
            } for s in scholarships]
        }

    def _get_hostel_transport(self, env, inp):
        students = self._resolve_students(env, inp)
        result = []
        for s in students:
            hostel_alloc = env['hostel.allocation'].sudo().search(
                [('student_id', '=', s.id)], limit=1
            )
            transport_alloc = env['transport.allocation'].sudo().search(
                [('student_id', '=', s.id)], limit=1
            )
            result.append({
                'student_id': s.id,
                'student_name': s.name,
                'is_hosteller': s.hosteller if hasattr(s, 'hosteller') else False,
                'uses_transport': s.uses_transport if hasattr(s, 'uses_transport') else False,
                'hostel_allocation': {
                    'id': hostel_alloc.id if hostel_alloc else None,
                    'room': hostel_alloc.room_id.name if hostel_alloc and hasattr(hostel_alloc, 'room_id') and hostel_alloc.room_id else '',
                    'hostel': hostel_alloc.hostel_id.name if hostel_alloc and hasattr(hostel_alloc, 'hostel_id') and hostel_alloc.hostel_id else '',
                    'state': hostel_alloc.state if hostel_alloc and hasattr(hostel_alloc, 'state') else '',
                } if hostel_alloc else None,
                'transport_allocation': {
                    'id': transport_alloc.id if transport_alloc else None,
                    'route': transport_alloc.route_id.name if transport_alloc and hasattr(transport_alloc, 'route_id') and transport_alloc.route_id else '',
                    'stop': transport_alloc.stop_id.name if transport_alloc and hasattr(transport_alloc, 'stop_id') and transport_alloc.stop_id else '',
                    'vehicle': transport_alloc.vehicle_id.name if transport_alloc and hasattr(transport_alloc, 'vehicle_id') and transport_alloc.vehicle_id else '',
                } if transport_alloc else None,
            })
        return result if len(result) > 1 else (result[0] if result else {'error': 'Student not found'})

    def _get_enrolled_courses(self, env, inp):
        students = self._resolve_students(env, inp)
        result = []
        for s in students:
            courses = []
            if hasattr(s, 'enrolled_course_ids'):
                for c in s.enrolled_course_ids:
                    courses.append({
                        'course_code': c.course_code if hasattr(c, 'course_code') else '',
                        'course_name': c.course_name if hasattr(c, 'course_name') else (c.name if hasattr(c, 'name') else ''),
                        'subject': c.subject_id.name if hasattr(c, 'subject_id') and c.subject_id else '',
                        'semester': c.semester_id.name if hasattr(c, 'semester_id') and c.semester_id else '',
                        'faculty': c.faculty_id.name if hasattr(c, 'faculty_id') and c.faculty_id else '',
                        'status': c.state if hasattr(c, 'state') else '',
                        'credits': c.credits if hasattr(c, 'credits') else 0,
                    })
            result.append({
                'student_id': s.id,
                'student_name': s.name,
                'course': s.course_id.name if s.course_id else '',
                'semester': s.current_semester_id.name if s.current_semester_id else '',
                'enrolled_courses': courses,
            })
        return result if len(result) > 1 else (result[0] if result else {'error': 'Student not found'})

    def _get_university_stats(self, env, inp):
        category = inp.get('category', 'all')
        stats = {}

        if category in ('students', 'all'):
            students = env['student.student'].sudo()
            stats['students'] = {
                'total': students.search_count([]),
                'active': students.search_count([('active', '=', True)]),
                'low_attendance': students.search_count([('attendance_percentage', '<', 75)]),
            }

        if category in ('fees', 'all'):
            payments = env['fee.payment'].sudo().search([])
            total_paid = sum(p.amount_paid for p in payments if hasattr(p, 'amount_paid'))
            stats['fees'] = {
                'total_payments': len(payments),
                'total_collected': total_paid,
            }

        if category in ('faculty', 'all'):
            faculty = env['university.faculty'].sudo()
            stats['faculty'] = {
                'total': faculty.search_count([]),
            }

        if category in ('hostel', 'all'):
            stats['hostel'] = {
                'total_allocations': env['hostel.allocation'].sudo().search_count([]),
                'total_rooms': env['hostel.room'].sudo().search_count([]),
            }

        if category in ('library', 'all'):
            stats['library'] = {
                'total_books': env['library.book'].sudo().search_count([]),
                'active_issues': env['library.issue'].sudo().search_count([('state', '=', 'issued')]),
            }

        if category in ('placements', 'all'):
            stats['placements'] = {
                'total_offers': env['placement.offer'].sudo().search_count([]),
                'active_drives': env['placement.drive'].sudo().search_count([('state', '=', 'active')]),
            }

        return stats

    def _search_faculty(self, env, inp):
        domain = []
        if inp.get('name'):
            domain.append(('name', 'ilike', inp['name']))
        if inp.get('department'):
            domain.append(('department_id.name', 'ilike', inp['department']))

        limit = inp.get('limit', 10)
        faculty = env['university.faculty'].sudo().search(domain, limit=limit)
        return {
            'count': len(faculty),
            'faculty': [{
                'id': f.id,
                'name': f.name,
                'designation': f.designation_id.name if hasattr(f, 'designation_id') and f.designation_id else '',
                'department': f.department_id.name if hasattr(f, 'department_id') and f.department_id else '',
                'email': f.work_email if hasattr(f, 'work_email') else '',
                'mobile': f.mobile_phone if hasattr(f, 'mobile_phone') else '',
            } for f in faculty]
        }

    # ── Helper ────────────────────────────────────────────────────────────────

    def _resolve_students(self, env, inp):
        if inp.get('student_id'):
            return env['student.student'].sudo().browse(inp['student_id'])
        elif inp.get('student_name'):
            return env['student.student'].sudo().search([
                ('name', 'ilike', inp['student_name'])
            ], limit=5)
        return env['student.student'].sudo().browse([])