import { randomUUID } from 'crypto'
import store from './traceStore'
import { writeAudit } from './auditService'
import type { CustomerLead } from './traceTypes'

export function discoverCustomers(_query?: string): CustomerLead[] {
  // In demo mode, return all mock leads seeded in the store
  // When Tavily + Superlinked are live, this would call those adapters and merge results
  return store.getLeads()
}

export function createOpportunity(
  leadId: string,
  requestedBy = 'trace_system'
): { success: boolean; attio_record_id?: string; message: string; lead?: CustomerLead } {
  const leads = store.getLeads()
  const lead = leads.find(l => l.id === leadId)

  if (!lead) {
    return { success: false, message: `Lead ${leadId} not found.` }
  }

  const attioRecordId = `attio_${randomUUID().slice(0, 12)}`
  const updated: CustomerLead = { ...lead, status: 'created_in_attio' }

  // Update in store
  const idx = store.customerLeads.findIndex(l => l.id === leadId)
  if (idx !== -1) store.customerLeads[idx] = updated

  writeAudit(
    'opportunity_created',
    `Customer opportunity created for ${lead.company} (Attio record: ${attioRecordId})`,
    requestedBy,
    { metadata: { company: lead.company, attio_record_id: attioRecordId } }
  )

  return {
    success: true,
    attio_record_id: attioRecordId,
    message: `[DEMO] Attio company and opportunity payload generated for ${lead.company}. CRM record: ${attioRecordId}`,
    lead: updated,
  }
}
