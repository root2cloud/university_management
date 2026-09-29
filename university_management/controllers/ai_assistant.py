# -*- coding: utf-8 -*-
import json
import logging
import re
import time
import requests
from datetime import date
from odoo import http
from odoo.exceptions import AccessError
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
                "course_id_name": {"type": "string", "description": "Program name, e.g. 'Bachelor of Technology(ECE)'. Only set this if the user explicitly gave a program; do NOT put a department name here"},
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
        "name": "get_hall_ticket",
        "description": "Get hall ticket number(s), examination, issue date, status and eligibility for a student. Use for questions like 'hall ticket number of X'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Student database ID (from search_students)"},
                "student_name": {"type": "string", "description": "Student name (partial match)"},
                "registration_number": {"type": "string", "description": "Student registration number"}
            }
        }
    },
    # ── Generic, read-only data tools (no code change needed for new questions) ──
    {
        "name": "list_models",
        "description": "List the data models (tables) you are allowed to read, e.g. student, hall ticket, library, placement, assets. Pass an optional keyword to filter. Use this first when no specific tool fits the question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Optional word to filter by, e.g. 'hall', 'library', 'placement'"}
            }
        }
    },
    {
        "name": "describe_model",
        "description": "Get the fields of a model (name, label, type, related model, selection values). Call before search_records so you use correct field names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Technical model name from list_models, e.g. 'examination.hall.ticket'"}
            },
            "required": ["model"]
        }
    },
    {
        "name": "search_records",
        "description": "Read records from any allowed model. domain is a JSON string like [[\"student_id.name\",\"ilike\",\"chandu\"]] (use dotted paths to follow relations). Returns matching records plus the total match count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Technical model name, e.g. 'examination.hall.ticket'"},
                "domain": {"type": "string", "description": "JSON list of [field, operator, value] filters. Operators: =, !=, >, >=, <, <=, ilike, like, in, not in. Empty string or [] for all."},
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names to return. Omit to get a default set."},
                "limit": {"type": "integer", "description": "Max records (default 20, max 50)"},
                "order": {"type": "string", "description": "e.g. 'create_date desc'"}
            },
            "required": ["model"]
        }
    },
    {
        "name": "aggregate_records",
        "description": "Count, sum, average, min or max over an allowed model, optionally grouped. Use for 'how many', 'total', 'average', 'by department'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Technical model name"},
                "domain": {"type": "string", "description": "JSON list of filters, same format as search_records"},
                "group_by": {"type": "array", "items": {"type": "string"}, "description": "Fields to group by, e.g. ['department_id']; dates accept 'date_field:month'"},
                "aggregates": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['__count', 'amount:sum', 'cgpa:avg']. Default ['__count']"}
            },
            "required": ["model"]
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
            if not request.env.user._is_internal():
                return {'error': 'The AI assistant is available to staff and administrators only.'}

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
        return """You are an intelligent AI assistant for a University Management System built on Odoo, used by administrators and staff.
Today's date is %s.
You have real-time, read-only access to university data through tools.

Workflow:
1. For common questions use the specific tools (search_students, get_fee_details, get_attendance, get_exam_results, get_hall_ticket, etc.).
2. For anything else (library, placement, assets, hostel, transport, events, projects, alumni, ...) use the generic tools:
   a) list_models with a keyword to find the right model,
   b) describe_model to see its exact field names,
   c) search_records to read records, or aggregate_records for counts, totals and averages.
   Never guess model or field names — look them up first. If a tool returns an error, read it, fix the call and retry.

Rules:
1. Always use tools to fetch real data before answering — never guess or make up numbers.
2. When a user asks about a student by name, you can filter with dotted fields, e.g. [["student_id.name","ilike","chandu"]], or call search_students first to get the ID.
3. Present financial amounts in Indian Rupee format (₹).
4. Answer exactly what was asked and nothing more. If the user asks for one value (e.g. a hall ticket number), reply in one short sentence with that value. Add extra details only if asked.
   FORMAT: never use markdown tables or pipe (|) characters. For several items, use one short line per item, like "Name - value", or a simple numbered list. You may use **bold** for key values.
5. If no data is found, say so clearly.
6. You are read-only — you cannot modify any data.
7. Only use filters the user actually mentioned. Do not invent course or department filters.
8. If a name search returns nothing, retry with just part of the name before saying it was not found.
9. Some fields are hidden for privacy; if asked for them, say they are not available.""" % date.today().strftime('%A, %d %B %Y')

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
            if not resp.ok:
                raise Exception(f"API error {resp.status_code} from {resp.url}: {resp.text[:500]}")
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
                            'content': self._dump(result)
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
        # Free/low tiers have a tokens-per-minute cap, and 'max_tokens' counts toward
        # it, so keep the request small: short reply budget + only recent history.
        try:
            max_tokens = int(request.env['ir.config_parameter'].sudo().get_param(
                'university.ai.max_tokens', '1024'))
        except (TypeError, ValueError):
            max_tokens = 1024
        current_messages = [{'role': 'system', 'content': system_prompt}]
        for m in list(messages)[-8:]:
            current_messages.append({'role': m['role'], 'content': m['content']})

        openai_tools = _tools_to_openai(TOOLS)
        url = base_url.rstrip('/') + '/chat/completions'
        max_iterations = 8

        for _ in range(max_iterations):
            payload = {
                'model': model,
                'max_tokens': max_tokens,
                'temperature': 0.2,
                'messages': current_messages,
                'tools': openai_tools,
                'tool_choice': 'auto',
            }

            # Some models (e.g. openai/gpt-oss-*) occasionally emit a malformed
            # tool name like 'search_students<|channel|>commentary'. Groq rejects
            # that with 400 "tool_use_failed". The failure is random, so retry.
            resp = None
            for attempt in range(4):
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.ok:
                    break
                if resp.status_code == 400 and 'tool_use_failed' in resp.text and attempt < 3:
                    _logger.warning("AI tool call malformed, retrying (%s/3): %s",
                                    attempt + 1, resp.text[:300])
                    continue
                if resp.status_code == 429 and attempt < 2:
                    # Rate limit (tokens per minute). Groq says how long to wait.
                    m_wait = re.search(r'try again in ([\d.]+)s', resp.text)
                    wait = min(float(m_wait.group(1)) + 1 if m_wait else 10, 30)
                    _logger.warning("AI rate limit hit, waiting %.0fs then retrying", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code == 429:
                    raise Exception('The AI service is busy (rate limit reached). '
                                    'Please wait about a minute and ask again.')
                raise Exception(f"API error {resp.status_code} from {resp.url}: {resp.text[:500]}")
            data = resp.json()

            choice = data.get('choices', [{}])[0]
            message = choice.get('message', {})
            finish_reason = choice.get('finish_reason', '')

            # Clean any leaked special tokens from tool names, e.g.
            # 'search_students<|channel|>commentary' -> 'search_students'
            for _tc in message.get('tool_calls') or []:
                _fn = _tc.get('function') or {}
                if _fn.get('name'):
                    _fn['name'] = _fn['name'].split('<|')[0].strip()

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
                        'content': self._dump(result),
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
            'get_hall_ticket':    self._get_hall_ticket,
            'list_models':        self._list_models,
            'describe_model':     self._describe_model,
            'search_records':     self._search_records,
            'aggregate_records':  self._aggregate_records,
            'search_faculty':     self._search_faculty,
        }
        fn = dispatch.get(tool_name)
        if fn:
            return fn(env, tool_input)
        return {'error': f'Unknown tool: {tool_name}'}

    # ── Tool implementations (unchanged) ─────────────────────────────────────

    def _get_hall_ticket(self, env, inp):
        domain = []
        if inp.get('student_id'):
            domain.append(('student_id', '=', inp['student_id']))
        if inp.get('student_name'):
            domain.append(('student_id.name', 'ilike', inp['student_name']))
        if inp.get('registration_number'):
            domain.append(('student_id.registration_number', 'ilike', inp['registration_number']))
        if not domain:
            return {'error': 'Provide student_id, student_name or registration_number.'}

        tickets = env['examination.hall.ticket'].sudo().search(
            domain, order='issue_date desc, id desc', limit=20)
        state_labels = dict(env['examination.hall.ticket']._fields['state'].selection)
        return {
            'count': len(tickets),
            'hall_tickets': [{
                'hall_ticket_number': t.name,
                'student': t.student_id.name,
                'registration_number': t.registration_number,
                'examination': t.examination_id.name,
                'academic_year': t.academic_year_id.name,
                'semester': t.semester_id.name,
                'issue_date': str(t.issue_date) if t.issue_date else None,
                'status': state_labels.get(t.state, t.state),
                'eligible': t.is_eligible,
                'ineligibility_reason': t.ineligibility_reason or None,
            } for t in tickets],
        }

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
        faculty = env['faculty.faculty'].sudo().search(domain, limit=limit)
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

    # ── Generic read-only data tools ─────────────────────────────────────────
    #
    # Safety model:
    #   * Only models that belong to this module are readable by default.
    #     Extra models:   System Parameter  university.ai.extra_models    = hr.employee,account.move
    #     Hide models:    System Parameter  university.ai.blocked_models  = some.model
    #     Hide fields:    System Parameter  university.ai.blocked_fields  = extra_field_1,extra_field_2
    #   * Queries run as the logged-in user (NOT sudo), so Odoo access rights and
    #     record rules apply.
    #   * Sensitive-looking fields (passwords, tokens, bank / ID numbers) are never exposed.

    MAX_RECORDS = 50
    MAX_RESULT_CHARS = 6000
    BLOCKED_FIELD_RE = re.compile(
        r'(password|passwd|secret|token|api_key|apikey|oauth|totp|signup|'
        r'aadhaar|aadhar|pan_no|pan_number|bank_acc|acc_number|ifsc|iban|cvv|otp)',
        re.I)
    BLOCKED_MODEL_PREFIXES = ('ir.', 'base.', 'res.users', 'res.config', 'bus.', 'mail.', 'auth.')
    SAFE_OPERATORS = {'=', '!=', '>', '>=', '<', '<=', 'like', 'not like', 'ilike', 'not ilike',
                      'in', 'not in', '=like', '=ilike', 'child_of'}

    def _dump(self, result):
        text = json.dumps(result, default=str)
        if len(text) > self.MAX_RESULT_CHARS:
            text = text[:self.MAX_RESULT_CHARS] + '... [truncated - narrow the filter or reduce fields]'
        return text

    def _param_list(self, env, key):
        raw = env['ir.config_parameter'].sudo().get_param(key, '') or ''
        return {x.strip() for x in raw.split(',') if x.strip()}

    def _allowed_models(self, env):
        """Technical names of models the assistant may read."""
        module = 'university_management'
        data = env['ir.model.data'].sudo().search([
            ('module', '=', module), ('model', '=', 'ir.model')])
        models = env['ir.model'].sudo().browse(data.mapped('res_id')).exists()
        allowed = set()
        for m in models:
            if m.model not in env:
                continue
            M = env[m.model]
            if M._transient or M._abstract:
                continue
            allowed.add(m.model)
        allowed |= self._param_list(env, 'university.ai.extra_models')
        blocked = self._param_list(env, 'university.ai.blocked_models')
        return {m for m in allowed
                if m in env and m not in blocked
                and not m.startswith(self.BLOCKED_MODEL_PREFIXES)}

    def _is_blocked_field(self, env, name):
        if self.BLOCKED_FIELD_RE.search(name or ''):
            return True
        return name in self._param_list(env, 'university.ai.blocked_fields')

    def _get_model(self, env, model_name):
        """Return (Model, error). Model is bound to the *current user's* env."""
        model_name = (model_name or '').strip()
        if model_name not in self._allowed_models(env):
            return None, ('Model "%s" is not available. Call list_models to see allowed models.' % model_name)
        Model = env[model_name]
        try:
            Model.check_access('read')
        except AccessError:
            return None, 'You do not have permission to read "%s".' % model_name
        return Model, None

    def _parse_domain(self, env, Model, raw):
        if raw in (None, '', []):
            return [], None
        try:
            domain = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            return None, 'domain must be valid JSON, e.g. [["name","ilike","x"]]'
        if not isinstance(domain, list):
            return None, 'domain must be a JSON list.'
        clean = []
        for leaf in domain:
            if isinstance(leaf, str) and leaf in ('&', '|', '!'):
                clean.append(leaf)
                continue
            if not (isinstance(leaf, (list, tuple)) and len(leaf) == 3):
                return None, 'Each domain item must be [field, operator, value].'
            path, op, val = leaf
            if not isinstance(path, str) or op not in self.SAFE_OPERATORS:
                return None, 'Invalid field or operator in %r. Allowed operators: %s' % (
                    leaf, ', '.join(sorted(self.SAFE_OPERATORS)))
            parts = path.split('.')
            if parts[0] not in Model._fields:
                return None, 'Unknown field "%s" on %s. Use describe_model.' % (parts[0], Model._name)
            if any(self._is_blocked_field(env, p) for p in parts):
                return None, 'Field "%s" is not available.' % path
            clean.append((path, op, val))
        return clean, None

    def _fmt_value(self, v):
        if isinstance(v, tuple) and len(v) == 2:      # many2one -> name
            return v[1]
        if isinstance(v, list):                        # x2many -> count
            return '%d record(s)' % len(v)
        return v

    def _list_models(self, env, inp):
        kw = (inp.get('keyword') or '').strip().lower()
        rows = []
        for name in sorted(self._allowed_models(env)):
            try:
                Model = env[name]
                Model.check_access('read')
            except Exception:
                continue
            label = Model._description or name
            if kw and kw not in name.lower() and kw not in label.lower():
                continue
            rows.append({'model': name, 'label': label})
        return {'count': len(rows), 'models': rows[:80],
                'note': 'Call describe_model on one of these to see its fields.'}

    def _describe_model(self, env, inp):
        Model, err = self._get_model(env, inp.get('model'))
        if err:
            return {'error': err}
        fields_out = []
        for fname, f in Model._fields.items():
            if self._is_blocked_field(env, fname) or f.type in ('binary', 'html', 'properties'):
                continue
            item = {'name': fname, 'label': f.string, 'type': f.type}
            if f.type in ('many2one', 'one2many', 'many2many'):
                item['relation'] = f.comodel_name
            if f.type == 'selection' and isinstance(f.selection, list):
                item['values'] = [k for k, _ in f.selection][:15]
            if not f.store:
                item['computed_not_searchable'] = True
            fields_out.append(item)
        return {'model': Model._name, 'label': Model._description,
                'fields': fields_out[:120]}

    def _default_fields(self, env, Model):
        picked = []
        for fname, f in Model._fields.items():
            if (f.store and fname not in ('id', 'create_uid', 'write_uid', 'write_date')
                    and f.type in ('char', 'integer', 'float', 'monetary', 'boolean',
                                   'date', 'datetime', 'selection', 'many2one')
                    and not self._is_blocked_field(env, fname)):
                picked.append(fname)
            if len(picked) >= 12:
                break
        return picked

    def _search_records(self, env, inp):
        Model, err = self._get_model(env, inp.get('model'))
        if err:
            return {'error': err}
        domain, err = self._parse_domain(env, Model, inp.get('domain'))
        if err:
            return {'error': err}
        try:
            limit = max(1, min(int(inp.get('limit') or 20), self.MAX_RECORDS))
        except (TypeError, ValueError):
            limit = 20
        order = inp.get('order') or None
        if order and not re.match(r'^[\w\s,\.]+$', order):
            order = None

        req_fields = inp.get('fields') or []
        if req_fields:
            bad = [f for f in req_fields if f not in Model._fields or self._is_blocked_field(env, f)]
            if bad:
                return {'error': 'Unknown or unavailable fields: %s. Use describe_model.' % ', '.join(bad)}
            fields_list = [f for f in req_fields if Model._fields[f].type != 'binary']
        else:
            fields_list = self._default_fields(env, Model)

        try:
            total = Model.search_count(domain)
            records = Model.search(domain, limit=limit, order=order)
            rows = []
            for r in records.read(fields_list):
                row = {k: self._fmt_value(v) for k, v in r.items() if k != 'id'}
                row['id'] = r['id']
                rows.append(row)
        except AccessError:
            return {'error': 'You do not have permission to read this data.'}
        except Exception as e:
            return {'error': 'Query failed: %s' % str(e).splitlines()[0][:300]}
        return {'model': Model._name, 'total_matching': total,
                'returned': len(rows), 'records': rows}

    def _aggregate_records(self, env, inp):
        Model, err = self._get_model(env, inp.get('model'))
        if err:
            return {'error': err}
        domain, err = self._parse_domain(env, Model, inp.get('domain'))
        if err:
            return {'error': err}

        group_by = inp.get('group_by') or []
        aggregates = inp.get('aggregates') or ['__count']
        for g in group_by:
            base = g.split(':')[0]
            if base not in Model._fields or self._is_blocked_field(env, base):
                return {'error': 'Unknown or unavailable group_by field "%s".' % g}
        for a in aggregates:
            if a == '__count':
                continue
            base, _, op = a.partition(':')
            if (base not in Model._fields or self._is_blocked_field(env, base)
                    or op not in ('sum', 'avg', 'min', 'max', 'count', 'count_distinct')):
                return {'error': 'Invalid aggregate "%s". Use "field:sum|avg|min|max" or "__count".' % a}
        try:
            rows = Model._read_group(domain, groupby=group_by, aggregates=aggregates)
        except AccessError:
            return {'error': 'You do not have permission to read this data.'}
        except Exception as e:
            return {'error': 'Aggregate failed: %s' % str(e).splitlines()[0][:300]}

        labels = list(group_by) + list(aggregates)
        out = []
        for row in rows[:100]:
            item = {}
            for label, val in zip(labels, row):
                item[label] = val.display_name if hasattr(val, 'display_name') else val
            out.append(item)
        return {'model': Model._name, 'groups': len(rows), 'rows': out}

    # ── Helper ────────────────────────────────────────────────────────────────

    def _resolve_students(self, env, inp):
        if inp.get('student_id'):
            return env['student.student'].sudo().browse(inp['student_id'])
        elif inp.get('student_name'):
            return env['student.student'].sudo().search([
                ('name', 'ilike', inp['student_name'])
            ], limit=5)
        return env['student.student'].sudo().browse([])