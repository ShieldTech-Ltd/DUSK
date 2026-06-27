# Backend Support Needed — Trace Frontend Integration

This document is for the backend team. The frontend execution layer is built and running in mock mode. Adding the endpoints below switches the demo to live mode — **no frontend changes needed**.

All the frontend needs is `NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000` (or whatever port the backend uses).

---

## CORS requirement

Please allow the frontend local development origin:

```
http://localhost:3000
```

Or whichever port the frontend is running on.

---

## Endpoints required

### 1. Security issue list

```
GET /api/security/issues
```

Expected response:

```json
[
  {
    "id": "issue_001",
    "title": "Prompt injection risk in customer support agent",
    "severity": "critical",
    "affected_system": "agent_workflow",
    "customer": "Acme Ltd",
    "source": "Backend scan + Tavily external content check",
    "status": "open",
    "evidence": "External content attempted to override agent policy"
  }
]
```

Severity values: `critical`, `high`, `medium`, `low`
Status values: `open`, `in_review`, `approved`, `fixed`, `closed`

---

### 2. Security issue detail

```
GET /api/security/issues/:id
```

Same shape as above, single object.

Additional optional fields that would improve the UI:

- `affected_tools: string[]`
- `affected_permissions: string[]`
- `suggested_risk_category: string`

---

### 3. Fix plan generation

```
POST /api/security/plan
```

Request:

```json
{
  "issue_id": "issue_001"
}
```

Response:

```json
{
  "issue_id": "issue_001",
  "recommended_fix": "Disable external email tool until approval policy is attached",
  "required_permissions": ["agent_workflow_write", "policy_update"],
  "required_resources": ["engineering_time", "test_environment"],
  "backend_action": "POST /api/security/fix",
  "rollback_plan": "Re-enable previous workflow version if fix fails",
  "risk_after_fix": "low",
  "approval_required": true,
  "estimated_time": "30 minutes"
}
```

---

### 4. Fix execution

```
POST /api/security/fix
```

Request:

```json
{
  "issue_id": "issue_001",
  "approved_by": "manager@example.com",
  "resources": ["engineering_time", "test_environment"],
  "action_plan": "Disable external email tool and attach approval policy"
}
```

Response:

```json
{
  "execution_id": "exec_001",
  "status": "fixed",
  "message": "Security policy attached and risky tool disabled",
  "logs": [
    "Policy check created",
    "External email tool restricted",
    "Approval rule attached",
    "Audit record generated"
  ]
}
```

Status values: `fixed`, `pending`, `failed`, `needs_manual_review`

---

### 5. Execution status

```
GET /api/security/executions/:id
```

Response:

```json
{
  "execution_id": "exec_001",
  "status": "fixed",
  "logs": ["..."],
  "started_at": "2026-06-27T10:00:00Z",
  "completed_at": "2026-06-27T10:02:00Z",
  "fix_result": "success",
  "rollback_status": null
}
```

---

### 6. Audit event writing

```
POST /api/security/audit
```

The frontend sends audit events for:

- `issue_selected`
- `approval_requested`
- `manager_approved`
- `manager_rejected`
- `resource_allocated`
- `fix_triggered`
- `backend_response`
- `attio_updated`
- `n8n_triggered`

Request shape:

```json
{
  "event_type": "manager_approved",
  "description": "Manager approved fix for: Prompt injection risk in customer support agent",
  "actor": "manager@example.com",
  "issue_id": "issue_001",
  "metadata": {
    "manager": "manager@example.com"
  }
}
```

Response: `{ "success": true, "audit_id": "audit_xyz" }`

---

### 7. Deployment preparation

```
POST /api/deployment/prepare
```

Request:

```json
{
  "company": "Acme AI Ops",
  "agent_workflow_url": "https://example.com/agent.json",
  "api_access_type": "REST",
  "database_type": "PostgreSQL",
  "tool_list": ["email_tool", "crm_write"],
  "approval_manager_email": "manager@example.com",
  "allowed_actions": ["crm_read", "send_internal_email"],
  "blocked_actions": ["export_contacts", "send_external_email_without_approval"],
  "test_environment_url": "https://staging.example.com",
  "deployment_mode": "shadow_monitoring"
}
```

Response:

```json
{
  "deployment_id": "deploy_001",
  "company": "Acme AI Ops",
  "mode": "shadow_monitoring",
  "required_permissions": [
    "read_agent_workflow",
    "read_api_schema",
    "read_database_schema",
    "create_policy_hook"
  ],
  "blocked_actions": [
    "export_contacts",
    "send_external_email_without_approval",
    "database_write_without_policy"
  ],
  "approval_required": true,
  "manager_email": "manager@example.com",
  "status": "ready_for_manager_approval"
}
```

---

### 8. Deployment registration

```
POST /api/deployment/register
```

Request:

```json
{
  "deployment_id": "deploy_001"
}
```

Response: `{ "success": true, "message": "Deployment registered in shadow monitoring mode." }`

---

## Schema stability request

Even if backend logic is incomplete, please keep the response schema stable so the frontend can switch from mock mode to live mode without frontend changes.

The frontend client (`frontend/src/lib/backendClient.ts`) already uses `process.env.NEXT_PUBLIC_BACKEND_API_URL` and falls back to mock data when it is not set.

---

## Optional enhancements

If time allows, these would improve the live demo:

- Streaming logs from `/api/security/fix` (Server-Sent Events or WebSocket)
- Real-time issue push (WebSocket or polling)
- Attio record URLs in fix execution response
- n8n execution URL in audit response
