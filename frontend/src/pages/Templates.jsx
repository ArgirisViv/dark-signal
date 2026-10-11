import React, { useEffect, useState } from 'react'
import { useNavigate } from '../router'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuth } from '../context/AuthContext'
import './Templates.css'

const TEMPLATE_METADATA = {
  account_notice: { category: 'Security', description: 'Verify account access with a clear notice' },
  invoice_review: { category: 'Finance', description: 'Request a review of pending invoice activity' },
  shared_document: { category: 'Collaboration', description: 'Prompt review of a shared document' },
  delivery_notice: { category: 'Operations', description: 'Confirm a shipment or delivery update' },
  payroll_update: { category: 'Finance', description: 'Highlight payroll details that need review' },
  security_policy_reminder: { category: 'IT', description: 'Remind staff to review security guidance' },
  cloud_storage_alert: { category: 'IT', description: 'Surface a cloud storage usage warning' },
  benefits_enrollment: { category: 'HR', description: 'Encourage benefits enrollment before a deadline' },
  travel_reimbursement: { category: 'Finance', description: 'Ask for a quick reimbursement review' },
  shared_drive_access: { category: 'Collaboration', description: 'Request confirmation of shared drive access' },
  mock_phishing: { category: 'Training', description: 'Classic phishing awareness example' },
}

const TEMPLATE_CATEGORIES = [
  'Security',
  'Finance',
  'Collaboration',
  'Operations',
  'IT',
  'HR',
  'Training',
  'General',
]

const TEMPLATE_TOPICS = [
  'Account verification',
  'Invoice fraud',
  'Shared documents',
  'Delivery notification',
  'Payroll change',
  'Security policy',
  'Cloud storage',
  'Benefits enrollment',
  'Expense reimbursement',
  'Shared drive access',
  'Phishing fundamentals',
  'Password reset',
  'Security awareness',
]

const TEMPLATE_SENDERS = {
  Security: { name: 'Security Operations', email: 'security@company-support.example', initials: 'SO' },
  Finance: { name: 'Finance Operations', email: 'finance@company-support.example', initials: 'FO' },
  Collaboration: { name: 'Collaboration Services', email: 'collaboration@company-support.example', initials: 'CS' },
  Operations: { name: 'Operations Desk', email: 'operations@company-support.example', initials: 'OD' },
  IT: { name: 'IT Support Team', email: 'it-security@company-support.example', initials: 'IT' },
  HR: { name: 'People Operations', email: 'hr-services@company-support.example', initials: 'HR' },
  Training: { name: 'Security Awareness Team', email: 'training@company-support.example', initials: 'SA' },
  General: { name: 'Company Support Team', email: 'support@company-support.example', initials: 'CS' },
}

function Templates() {
  const { userRole } = useAuth()
  const canManageTemplates = userRole === 'admin'
  const canUseTemplates = userRole === 'admin' || userRole === 'analyst'
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [filters, setFilters] = useState({ difficulty: '', category: '', topic: '', technique: '', origin: '', approval: '' })
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formState, setFormState] = useState({
    key: '',
    name: '',
    subject: '',
    body_text: '',
    body_html: '',
    difficulty: 'medium',
    category: 'General',
    topic: 'Security awareness',
    psychological_technique: 'urgency',
  })
  const [createError, setCreateError] = useState('')
  const [creating, setCreating] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editTemplateKey, setEditTemplateKey] = useState('')
  const [editFormState, setEditFormState] = useState({
    name: '',
    subject: '',
    body_text: '',
    body_html: '',
  })
  const [editError, setEditError] = useState('')
  const [editing, setEditing] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [copyState, setCopyState] = useState('')
  const [showAssistantModal, setShowAssistantModal] = useState(false)
  const [assistantState, setAssistantState] = useState({
    language: 'English',
    organization_category: 'Finance',
    recipient_role: 'Employee',
    topic: 'Account verification',
    difficulty: 'medium',
    psychological_technique: 'urgency',
    template_name: '',
  })
  const [assistantResult, setAssistantResult] = useState(null)
  const [assistantError, setAssistantError] = useState('')
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [assistantStatus, setAssistantStatus] = useState(null)
  const [assistantStatusLoading, setAssistantStatusLoading] = useState(false)
  const [approveLoadingKey, setApproveLoadingKey] = useState('')
  const navigate = useNavigate()

  const loadTemplates = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/email-templates/`)
      setTemplates((response.data || []).filter((template) => template.key !== 'password_reset'))
    } catch (loadError) {
      setError(loadError?.response?.data?.detail || 'Failed to load the template library.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTemplates()
  }, [])

  const getTemplateMetadata = (template) => {
    const key = template?.key || ''
    return TEMPLATE_METADATA[key] || { category: 'General', description: 'Training-ready phishing scenario' }
  }

  const filteredTemplates = templates.filter((template) => {
    const metadata = getTemplateMetadata(template)
    const category = template.category || metadata.category
    const haystack = [template.name, template.subject, template.key, category, template.topic, template.psychological_technique, metadata.description]
      .join(' ')
      .toLowerCase()

    return haystack.includes(searchTerm.trim().toLowerCase())
      && (!filters.difficulty || template.difficulty === filters.difficulty)
      && (!filters.category || category === filters.category)
      && (!filters.topic || template.topic === filters.topic)
      && (!filters.technique || template.psychological_technique === filters.technique)
      && (!filters.origin || template.origin === filters.origin)
      && (!filters.approval || template.approval_status === filters.approval)
  })

  const buildPreviewDocument = (template) => {
    const previewText = template.body_text || 'No preview content available.'
    if (template.body_html) {
      if (/<html[\s>]/i.test(template.body_html)) return template.body_html
      return `<!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <style>
              * { box-sizing: border-box; }
              body { margin: 0; padding: 30px; background: #f8fafc; color: #0f172a; font: 15px/1.65 "Segoe UI", Arial, sans-serif; }
              h1, h2, h3, h4 { color: #0f172a; line-height: 1.25; }
              a { color: #2563eb; }
              table { max-width: 100%; }
            </style>
          </head>
          <body>${template.body_html}</body>
        </html>`
    }

    const escapedText = previewText
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;')

    return `<!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <style>
            body { margin: 0; padding: 30px; background: #f8fafc; color: #0f172a; font: 15px/1.65 "Segoe UI", Arial, sans-serif; }
            pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }
          </style>
        </head>
        <body><pre>${escapedText}</pre></body>
      </html>`
  }

  const getTemplateSender = (template) => {
    const category = template.category || getTemplateMetadata(template).category || 'General'
    return TEMPLATE_SENDERS[category] || TEMPLATE_SENDERS.General
  }

  const parseAssistantMetadata = (template) => {
    if (!template?.assistant_metadata) return null
    try {
      return JSON.parse(template.assistant_metadata)
    } catch {
      return null
    }
  }

  const approveTemplate = async (templateKey) => {
    setApproveLoadingKey(templateKey)
    try {
      const response = await axios.post(`${API_BASE_URL}/email-templates/${templateKey}/approve`)
      setTemplates((current) =>
        current.map((template) => (template.key === templateKey ? response.data : template))
      )
      if (selectedTemplate?.key === templateKey) {
        setSelectedTemplate(response.data)
      }
    } catch (approveError) {
      setAssistantError(approveError?.response?.data?.detail || 'Failed to approve template.')
    } finally {
      setApproveLoadingKey('')
    }
  }

  const handleGenerateAssistantDraft = async (event) => {
    event.preventDefault()
    setAssistantLoading(true)
    setAssistantError('')
    try {
      const response = await axios.post(`${API_BASE_URL}/email-templates/assistant/generate-draft`, assistantState)
      setAssistantResult(response.data)
      setTemplates((current) => [response.data.template, ...current])
      setSelectedTemplate(response.data.template)
    } catch (generationError) {
      setAssistantError(generationError?.response?.data?.detail || 'Failed to generate assistant draft.')
    } finally {
      setAssistantLoading(false)
    }
  }

  const openAssistantModal = async () => {
    setShowAssistantModal(true)
    setAssistantError('')
    setAssistantStatusLoading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/email-templates/assistant/status`)
      setAssistantStatus(response.data)
    } catch (statusError) {
      setAssistantStatus(null)
      setAssistantError(statusError?.response?.data?.detail || 'Could not verify the OpenAI assistant status.')
    } finally {
      setAssistantStatusLoading(false)
    }
  }

  const handleCopyPreview = async (template) => {
    const content = `${template.subject}\n\n${template.body_text || ''}`
    try {
      await navigator.clipboard.writeText(content)
      setCopyState('Copied to clipboard')
      window.setTimeout(() => setCopyState(''), 1800)
    } catch (clipboardError) {
      setCopyState('Copy failed')
      window.setTimeout(() => setCopyState(''), 1800)
    }
  }

  const handleCreateTemplate = async (event) => {
    event.preventDefault()
    setCreating(true)
    setCreateError('')

    try {
      const response = await axios.post(`${API_BASE_URL}/email-templates/`, {
        key: formState.key,
        name: formState.name,
        subject: formState.subject,
        body_text: formState.body_text,
        body_html: formState.body_html,
        difficulty: formState.difficulty,
        category: formState.category,
        topic: formState.topic,
        psychological_technique: formState.psychological_technique,
      })

      setTemplates((currentTemplates) => [response.data, ...currentTemplates])
      setShowCreateModal(false)
      setFormState({ key: '', name: '', subject: '', body_text: '', body_html: '', difficulty: 'medium', category: 'General', topic: 'Security awareness', psychological_technique: 'urgency' })
    } catch (createError) {
      setCreateError(createError?.response?.data?.detail || 'Failed to create the custom template.')
    } finally {
      setCreating(false)
    }
  }

  const openEditModal = (template) => {
    setEditTemplateKey(template.key)
    setEditFormState({
      name: template.name || '',
      subject: template.subject || '',
      body_text: template.body_text || '',
      body_html: template.body_html || '',
    })
    setEditError('')
    setShowEditModal(true)
  }

  const handleEditTemplate = async (event) => {
    event.preventDefault()
    if (!editTemplateKey) return

    setEditing(true)
    setEditError('')

    try {
      const response = await axios.put(`${API_BASE_URL}/email-templates/${encodeURIComponent(editTemplateKey)}`, {
        name: editFormState.name,
        subject: editFormState.subject,
        body_text: editFormState.body_text,
        body_html: editFormState.body_html,
      })

      setTemplates((currentTemplates) =>
        currentTemplates.map((template) => (template.key === editTemplateKey ? response.data : template))
      )
      if (selectedTemplate?.key === editTemplateKey) {
        setSelectedTemplate(response.data)
      }
      setShowEditModal(false)
      setEditTemplateKey('')
      setEditFormState({ name: '', subject: '', body_text: '', body_html: '' })
    } catch (editError) {
      setEditError(editError?.response?.data?.detail || 'Failed to update the template.')
    } finally {
      setEditing(false)
    }
  }

  if (loading) {
    return <div className="container loading"><div className="spinner" /></div>
  }

  if (error) {
    return <div className="container error">{error}</div>
  }

  return (
    <div className="container templates-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Templates</h1>
          <p className="page-subtitle">Choose a training email pattern, then tailor its content to each campaign.</p>
        </div>
      </div>

      <section className="template-library" aria-labelledby="template-library-title">
        <div className="template-library-heading">
          <div>
            <span className="campaign-control-eyebrow">Campaign email library</span>
            <h2 id="template-library-title">Mock phishing templates</h2>
          </div>
          <div className="template-toolbar">
            <label className="template-search" htmlFor="template-search">
              <span className="sr-only">Search templates</span>
              <input
                id="template-search"
                type="search"
                placeholder="Search templates"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </label>
            {canManageTemplates && <button className="action-btn primary-btn" onClick={() => setShowCreateModal(true)}>Create custom template</button>}
            {canManageTemplates && <button className="action-btn secondary-btn" onClick={openAssistantModal}>LLM assistant draft</button>}
          </div>
        </div>

        <div className="template-filters" aria-label="Template filters">
          <select value={filters.difficulty} onChange={(event) => setFilters({ ...filters, difficulty: event.target.value })}>
            <option value="">All difficulties</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </select>
          <select value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value })}>
            <option value="">All categories</option>{[...new Set(templates.map((item) => item.category || getTemplateMetadata(item).category))].sort().map((value) => <option key={value}>{value}</option>)}
          </select>
          <select value={filters.topic} onChange={(event) => setFilters({ ...filters, topic: event.target.value })}>
            <option value="">All topics</option>{[...new Set(templates.map((item) => item.topic).filter(Boolean))].sort().map((value) => <option key={value}>{value}</option>)}
          </select>
          <select value={filters.technique} onChange={(event) => setFilters({ ...filters, technique: event.target.value })}>
            <option value="">All techniques</option><option value="urgency">Urgency</option><option value="authority">Authority</option><option value="curiosity">Curiosity</option><option value="fear">Fear</option><option value="reward">Reward</option>
          </select>
          <select value={filters.origin} onChange={(event) => setFilters({ ...filters, origin: event.target.value })}>
            <option value="">All origins</option><option value="system">System</option><option value="manual">Manual</option><option value="llm_assistant">LLM assistant</option>
          </select>
          <select value={filters.approval} onChange={(event) => setFilters({ ...filters, approval: event.target.value })}>
            <option value="">All approval states</option><option value="approved">Approved</option><option value="draft">Draft</option>
          </select>
        </div>

        <div className="template-library-summary">
          <span>{filteredTemplates.length} ready-to-use templates</span>
          <span>Campaign edits create an independent copy.</span>
        </div>

        <div className="template-results-viewport">
          {filteredTemplates.length === 0 ? (
            <div className="template-empty-state">
              <h3>No templates match that search.</h3>
              <p>Try another keyword such as finance, security, hr, or collaboration.</p>
            </div>
          ) : (
            <div className="template-library-grid">
              {filteredTemplates.map((template) => {
                const metadata = getTemplateMetadata(template)
                return (
                  <article className="template-library-item" key={template.key}>
                  <div className="template-card-content">
                    <div className="template-card-top">
                      <span className="template-library-key">{template.category || metadata.category}</span>
                      <span className="template-library-pill">{(template.difficulty || 'medium').replace(/^./, (letter) => letter.toUpperCase())}</span>
                    </div>
                    <h3>{template.name}</h3>
                    <p className="template-library-subject">{template.subject}</p>
                    <div className="template-status-row">
                      <span className={`template-status ${template.approval_status === 'approved' ? 'approved' : 'draft'}`}>
                        {template.approval_status === 'approved' ? 'Approved' : 'Draft pending approval'}
                      </span>
                      <span className="template-origin">{template.origin === 'llm_assistant' ? 'LLM assistant' : 'Manual/System'}</span>
                    </div>
                    <p className="template-library-preview">{template.body_text}</p>
                  </div>
                  <div className="template-actions">
                    {canManageTemplates && <button
                      type="button"
                      className="action-btn secondary-btn"
                      onClick={() => openEditModal(template)}
                    >
                      Edit
                    </button>}
                    <button
                      type="button"
                      className="action-btn secondary-btn"
                      onClick={() => setSelectedTemplate(template)}
                    >
                      Preview
                    </button>
                    {canUseTemplates && <button
                      className="action-btn primary-btn"
                      disabled={template.approval_status !== 'approved'}
                      title={template.approval_status !== 'approved' ? 'Approve draft first' : undefined}
                      onClick={() => navigate(`/scenarios?template=${encodeURIComponent(template.key)}`)}
                    >
                      Use in campaign
                    </button>}
                  </div>
                  </article>
                )
              })}
            </div>
          )}
        </div>
      </section>

      {selectedTemplate && (
        <div className="template-modal-overlay" onClick={() => setSelectedTemplate(null)}>
          <div className="template-modal preview-modal" onClick={(event) => event.stopPropagation()}>
            <div className="template-modal-header">
              <div>
                <span className="campaign-control-eyebrow">Selected template email</span>
                <h3>{selectedTemplate.subject}</h3>
                <p>This is the simulated email recipients receive when this template is used in a campaign.</p>
              </div>
              <button className="icon-btn" onClick={() => setSelectedTemplate(null)} aria-label="Close preview">
                ×
              </button>
            </div>

            <div className="template-preview-body">
              <div className="template-mail-client">
                <div className="template-mail-toolbar">
                  <div className="template-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
                  <strong>Dark Signal Mail Preview</strong>
                  <span>Training safe</span>
                </div>
                <div className="template-mail-meta">
                  <div className="template-sender-avatar">{getTemplateSender(selectedTemplate).initials}</div>
                  <div>
                    <strong>{getTemplateSender(selectedTemplate).name}</strong>
                    <span>&lt;{getTemplateSender(selectedTemplate).email}&gt;</span>
                    <small>to Campaign recipients</small>
                  </div>
                  <time>Simulation preview</time>
                </div>
                <div className="template-mail-subject">
                  <span>Subject</span>
                  <strong>{selectedTemplate.subject}</strong>
                </div>
                <iframe
                  className="template-html-preview"
                  title={`Email preview for ${selectedTemplate.name}`}
                  sandbox=""
                  srcDoc={buildPreviewDocument(selectedTemplate)}
                />
                <div className="template-mail-footer">
                  <span>◆</span>
                  No real credentials, external links, or account actions are used in this simulation.
                </div>
              </div>

              {canManageTemplates && selectedTemplate.approval_status !== 'approved' && (
                <div className="template-draft-warning">
                  This template is draft and cannot be used in campaigns until approved by an admin.
                </div>
              )}

              {parseAssistantMetadata(selectedTemplate)?.suspicious_points?.length > 0 && (
                <div className="assistant-points">
                  <h4>Why this message is suspicious</h4>
                  <p>
                    Generator: {parseAssistantMetadata(selectedTemplate)?.generator || 'rule_based_fallback'}
                  </p>
                  <ul>
                    {parseAssistantMetadata(selectedTemplate).suspicious_points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="template-modal-actions">
              <span className="template-copy-status">{copyState}</span>
              <button type="button" className="action-btn secondary-btn" onClick={() => handleCopyPreview(selectedTemplate)}>
                Copy preview
              </button>
              <button type="button" className="action-btn secondary-btn" onClick={() => setSelectedTemplate(null)}>
                Close
              </button>
              {canManageTemplates && selectedTemplate.approval_status !== 'approved' && (
                <button
                  className="action-btn secondary-btn"
                  disabled={approveLoadingKey === selectedTemplate.key}
                  onClick={() => approveTemplate(selectedTemplate.key)}
                >
                  {approveLoadingKey === selectedTemplate.key ? 'Approving...' : 'Approve draft'}
                </button>
              )}
              {canUseTemplates && <button
                className="action-btn primary-btn"
                disabled={selectedTemplate.approval_status !== 'approved'}
                title={selectedTemplate.approval_status !== 'approved' ? 'Approve draft first' : undefined}
                onClick={() => {
                  setSelectedTemplate(null)
                  navigate(`/scenarios?template=${encodeURIComponent(selectedTemplate.key)}`)
                }}
              >
                Use in campaign
              </button>}
            </div>
          </div>
        </div>
      )}

      {showEditModal && (
        <div className="template-modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="template-modal" onClick={(event) => event.stopPropagation()}>
            <div className="template-modal-header">
              <div>
                <h3>Edit template</h3>
                <p>Update the visible content for this template.</p>
              </div>
              <button className="icon-btn" onClick={() => setShowEditModal(false)} aria-label="Close modal">
                ×
              </button>
            </div>

            <form className="template-form" onSubmit={handleEditTemplate}>
              <label>
                Template name
                <input
                  required
                  value={editFormState.name}
                  onChange={(event) => setEditFormState({ ...editFormState, name: event.target.value })}
                  placeholder="Template name"
                />
              </label>
              <label>
                Subject
                <input
                  required
                  value={editFormState.subject}
                  onChange={(event) => setEditFormState({ ...editFormState, subject: event.target.value })}
                  placeholder="Email subject"
                />
              </label>
              <label>
                Plain text body
                <textarea
                  rows="4"
                  value={editFormState.body_text}
                  onChange={(event) => setEditFormState({ ...editFormState, body_text: event.target.value })}
                  placeholder="Write the updated body"
                />
              </label>
              <label>
                HTML body
                <textarea
                  rows="4"
                  value={editFormState.body_html}
                  onChange={(event) => setEditFormState({ ...editFormState, body_html: event.target.value })}
                  placeholder="Optional HTML content"
                />
              </label>

              {editError && <p className="template-form-error">{editError}</p>}

              <div className="template-modal-actions">
                <button type="button" className="action-btn secondary-btn" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="action-btn primary-btn" disabled={editing}>
                  {editing ? 'Saving...' : 'Save changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="template-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="template-modal" onClick={(event) => event.stopPropagation()}>
            <div className="template-modal-header">
              <div>
                <h3>Create custom template</h3>
                <p>Build your own phishing-style email and save it to your library.</p>
              </div>
              <button className="icon-btn" onClick={() => setShowCreateModal(false)} aria-label="Close modal">
                ×
              </button>
            </div>

            <form className="template-form" onSubmit={handleCreateTemplate}>
              <div className="assistant-grid">
                <label>Difficulty<select value={formState.difficulty} onChange={(event) => setFormState({ ...formState, difficulty: event.target.value })}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
                <label>
                  Category
                  <select value={formState.category} onChange={(event) => setFormState({ ...formState, category: event.target.value })}>
                    {TEMPLATE_CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}
                  </select>
                </label>
                <label>
                  Topic
                  <select value={formState.topic} onChange={(event) => setFormState({ ...formState, topic: event.target.value })}>
                    {TEMPLATE_TOPICS.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
                  </select>
                </label>
                <label>Psychological technique<select value={formState.psychological_technique} onChange={(event) => setFormState({ ...formState, psychological_technique: event.target.value })}><option value="urgency">Urgency</option><option value="authority">Authority</option><option value="curiosity">Curiosity</option><option value="fear">Fear</option><option value="reward">Reward</option></select></label>
              </div>
              <label>
                Template key
                <input
                  required
                  value={formState.key}
                  onChange={(event) => setFormState({ ...formState, key: event.target.value })}
                  placeholder="e.g. quarterly_bonus"
                />
              </label>
              <label>
                Template name
                <input
                  required
                  value={formState.name}
                  onChange={(event) => setFormState({ ...formState, name: event.target.value })}
                  placeholder="Quarterly bonus notice"
                />
              </label>
              <label>
                Subject
                <input
                  required
                  value={formState.subject}
                  onChange={(event) => setFormState({ ...formState, subject: event.target.value })}
                  placeholder="Action required: review your bonus"
                />
              </label>
              <label>
                Plain text body
                <textarea
                  rows="4"
                  value={formState.body_text}
                  onChange={(event) => setFormState({ ...formState, body_text: event.target.value })}
                  placeholder="Write the body of your custom email"
                />
              </label>
              <label>
                HTML body
                <textarea
                  rows="4"
                  value={formState.body_html}
                  onChange={(event) => setFormState({ ...formState, body_html: event.target.value })}
                  placeholder="Optional HTML content"
                />
              </label>

              {createError && <p className="template-form-error">{createError}</p>}

              <div className="template-modal-actions">
                <button type="button" className="action-btn secondary-btn" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="action-btn primary-btn" disabled={creating}>
                  {creating ? 'Creating...' : 'Save template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAssistantModal && (
        <div className="template-modal-overlay" onClick={() => setShowAssistantModal(false)}>
          <div className="template-modal assistant-modal" onClick={(event) => event.stopPropagation()}>
            <div className="template-modal-header">
              <div>
                <h3>LLM phishing template assistant</h3>
                <p>Generate a safe draft with fictional entities, educational links, and structured suspicious indicators.</p>
              </div>
              <button className="icon-btn" onClick={() => setShowAssistantModal(false)} aria-label="Close modal">
                ×
              </button>
            </div>

            <div className={`assistant-connection ${assistantStatus?.configured ? 'is-ready' : 'is-unavailable'}`}>
              <span className="assistant-connection-dot" aria-hidden="true" />
              <div>
                <strong>
                  {assistantStatusLoading
                    ? 'Checking OpenAI configuration...'
                    : assistantStatus?.configured
                      ? 'OpenAI API key configured'
                      : 'OpenAI API key not configured'}
                </strong>
                <p>
                  {assistantStatus?.configured
                    ? `Responses API · ${assistantStatus.model} · verified when a draft is generated`
                    : 'Add OPENAI_API_KEY to the local .env file and rebuild the backend. The key is never sent to the browser.'}
                </p>
              </div>
            </div>

            <form className="template-form" onSubmit={handleGenerateAssistantDraft}>
              <div className="assistant-grid">
                <label>
                  Language
                  <input value={assistantState.language} onChange={(event) => setAssistantState({ ...assistantState, language: event.target.value })} required />
                </label>
                <label>
                  Organization category
                  <select value={assistantState.organization_category} onChange={(event) => setAssistantState({ ...assistantState, organization_category: event.target.value })}>
                    {TEMPLATE_CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}
                  </select>
                </label>
                <label>
                  Recipient role
                  <input value={assistantState.recipient_role} onChange={(event) => setAssistantState({ ...assistantState, recipient_role: event.target.value })} required />
                </label>
                <label>
                  Topic
                  <select value={assistantState.topic} onChange={(event) => setAssistantState({ ...assistantState, topic: event.target.value })}>
                    {TEMPLATE_TOPICS.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
                  </select>
                </label>
                <label>
                  Difficulty
                  <select value={assistantState.difficulty} onChange={(event) => setAssistantState({ ...assistantState, difficulty: event.target.value })}>
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </label>
                <label>
                  Psychological technique
                  <select value={assistantState.psychological_technique} onChange={(event) => setAssistantState({ ...assistantState, psychological_technique: event.target.value })}>
                    <option value="urgency">Urgency</option>
                    <option value="authority">Authority</option>
                    <option value="curiosity">Curiosity</option>
                    <option value="fear">Fear</option>
                    <option value="reward">Reward</option>
                  </select>
                </label>
              </div>

              <label>
                Draft template name (optional)
                <input
                  value={assistantState.template_name}
                  onChange={(event) => setAssistantState({ ...assistantState, template_name: event.target.value })}
                  placeholder="Example: Payroll refresh assistant draft"
                />
              </label>

              {assistantError && <p className="template-form-error">{assistantError}</p>}

              <div className="template-modal-actions">
                <button type="button" className="action-btn secondary-btn" onClick={() => setShowAssistantModal(false)}>
                  Close
                </button>
                <button
                  type="submit"
                  className="action-btn primary-btn"
                  disabled={assistantLoading || assistantStatusLoading || !assistantStatus?.configured}
                >
                  {assistantLoading ? 'Generating...' : 'Generate draft'}
                </button>
              </div>
            </form>

            {assistantResult && (
              <section className="assistant-result">
                <h4>Assistant output</h4>
                <p><strong>Generator:</strong> OpenAI Responses API</p>
                <p><strong>Model:</strong> {assistantResult.model}</p>
                {assistantResult.request_id && <p><strong>Request:</strong> {assistantResult.request_id}</p>}
                <p><strong>Draft key:</strong> {assistantResult.template.key}</p>
                <p><strong>Suggested subject:</strong> {assistantResult.template.subject}</p>
                <div className="assistant-result-block">
                  <span>Suspicious points</span>
                  <ul>
                    {(assistantResult.suspicious_points || []).map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </div>
                <div className="assistant-result-block">
                  <span>Alternative variant ({assistantResult.alternative_variant?.difficulty})</span>
                  <p>{assistantResult.alternative_variant?.subject}</p>
                </div>
                <div className="assistant-result-block">
                  <span>Safety notes</span>
                  <ul>
                    {(assistantResult.safety_notes || []).map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Templates
