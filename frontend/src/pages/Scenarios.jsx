import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from '../router'
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuth } from '../context/AuthContext'
import './Scenarios.css'

function Scenarios() {
  const { userRole } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeModal, setActiveModal] = useState(null)
  const [activeScenario, setActiveScenario] = useState(null)
  const [editingCampaign, setEditingCampaign] = useState(null)
  const [deletionTarget, setDeletionTarget] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [collapsedCampaignIds, setCollapsedCampaignIds] = useState([])
  const [campaignResults, setCampaignResults] = useState(null)
  const [isResultsLoading, setIsResultsLoading] = useState(false)
  const [resultsError, setResultsError] = useState('')
  const [toastMessage, setToastMessage] = useState('')
  const [campaigns, setCampaigns] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [totalCount, setTotalCount] = useState(0)
  const [lifecycleCounts, setLifecycleCounts] = useState({ Draft: 0, Scheduled: 0, Active: 0, Completed: 0 })
  const [templates, setTemplates] = useState([])
  const [scenarioOptions, setScenarioOptions] = useState([])
  const [adaptiveCampaigns, setAdaptiveCampaigns] = useState([])
  const [adaptiveCampaignId, setAdaptiveCampaignId] = useState('')
  const [adaptiveConfig, setAdaptiveConfig] = useState({
    baselineScenarioId: '',
    sourceScenarioIds: '',
    easierScenarioId: '',
    sameScenarioId: '',
    harderScenarioId: '',
    targetedScenarioId: '',
    slightEasierScenarioId: '',
    finalScenarioId: '',
    stageLabel: 'adaptive_round_2',
  })
  const [adaptiveLoading, setAdaptiveLoading] = useState(false)
  const [adaptiveError, setAdaptiveError] = useState('')
  const [adaptiveBaselineResult, setAdaptiveBaselineResult] = useState(null)
  const [adaptiveDispatchResult, setAdaptiveDispatchResult] = useState(null)
  const [adaptiveFinalResult, setAdaptiveFinalResult] = useState(null)
  const [adaptivePrograms, setAdaptivePrograms] = useState([])
  const [adaptiveProgramId, setAdaptiveProgramId] = useState('')
  const [adaptiveProgramName, setAdaptiveProgramName] = useState('Quarterly phishing adaptive program')
  const [adaptiveProgramRunResult, setAdaptiveProgramRunResult] = useState(null)
  const [quickDemoResult, setQuickDemoResult] = useState(null)
  const [adaptiveDifficulties, setAdaptiveDifficulties] = useState({
    baseline: 'medium',
    targeted: 'easy',
    easier: 'easy',
    same: 'medium',
    harder: 'hard',
    final: 'medium',
  })
  const [adaptiveSchedule, setAdaptiveSchedule] = useState({
    baseline: '',
    adaptive: '',
    final: '',
  })
  const [createStep, setCreateStep] = useState(1)
  const [formData, setFormData] = useState({
    campaignId: '',
    campaignName: '',
    campaignDescription: '',
    scenarioName: '',
    template: '',
    emailTemplateKey: '',
    emailSubject: '',
    emailBodyText: '',
    emailBodyHtml: '',
    audience: 'All Staff',
    schedule: '',
  })

  const showToast = (message) => {
    setToastMessage(message)
    window.setTimeout(() => setToastMessage(''), 2000)
  }

  const apiBase = API_BASE_URL
  const normalizedUserRole = String(userRole || '').toLowerCase() === 'manager'
    ? 'analyst'
    : String(userRole || '').toLowerCase()
  const canManageScenarios = normalizedUserRole === 'admin' || normalizedUserRole === 'analyst'
  const canDeleteCampaigns = normalizedUserRole === 'admin'
  const adaptiveUsers = adaptiveDispatchResult?.users || adaptiveBaselineResult?.users || []
  const adaptiveGroupDefinitions = [
    {
      key: 'targeted',
      label: 'High-risk recipients',
      shortLabel: 'High risk',
      difficulty: 'Easy',
      configKey: 'targetedScenarioId',
      actions: ['targeted_repetition'],
      reason: 'Repeated click behavior. Repeat focused training and micro-learning.',
    },
    {
      key: 'easier',
      label: 'Needs reinforcement',
      shortLabel: 'Reinforcement',
      difficulty: 'Easy',
      configKey: 'easierScenarioId',
      actions: ['easier', 'same_or_slightly_easier'],
      reason: 'Clicked or reported after clicking. Reinforce the phishing fundamentals.',
    },
    {
      key: 'same',
      label: 'Aware recipients',
      shortLabel: 'Aware',
      difficulty: 'Medium',
      configKey: 'sameScenarioId',
      actions: ['same'],
      reason: 'Avoided the click but did not report. Continue at the current level.',
    },
    {
      key: 'harder',
      label: 'Advanced recipients',
      shortLabel: 'Advanced',
      difficulty: 'Hard',
      configKey: 'harderScenarioId',
      actions: ['harder'],
      reason: 'Reported correctly without clicking. Move to a more challenging scenario.',
    },
  ]
  const selectedAdaptiveCampaign = adaptiveCampaigns.find(
    (campaign) => String(campaign.id) === String(adaptiveCampaignId)
  ) || null
  const adaptiveScenarioOptions = selectedAdaptiveCampaign?.scenarios || []
  const pageSize = 20
  const templateFormValues = (templateKey = '', availableTemplates = templates) => {
    const template = availableTemplates.find((item) => item.key === templateKey) || availableTemplates[0]
    return {
      campaignId: '',
      campaignName: '',
      campaignDescription: '',
      scenarioName: '',
      template: template?.name || '',
      emailTemplateKey: template?.key || '',
      emailSubject: template?.subject || '',
      emailBodyText: template?.body_text || '',
      emailBodyHtml: template?.body_html || '',
      audience: 'All Staff',
      schedule: '',
    }
  }

  const applyTemplate = (templateKey) => {
    const template = templates.find((item) => item.key === templateKey)
    if (!template) return
    setFormData((current) => ({
      ...current,
      template: template.name,
      emailTemplateKey: template.key,
      emailSubject: template.subject || '',
      emailBodyText: template.body_text || '',
      emailBodyHtml: template.body_html || '',
    }))
  }

  const normalizeScenario = (scenario) => ({
    id: scenario.id,
    name: scenario.title || 'Untitled Scenario',
    template: scenario.indicators?.email_template_name || scenario.indicators?.template || 'Mock phishing',
    emailTemplateKey: scenario.indicators?.email_template_key || 'mock_phishing',
    emailSubject: scenario.indicators?.email_subject || '',
    emailBodyText: scenario.indicators?.email_body_text || '',
    emailBodyHtml: scenario.indicators?.email_body_html || '',
    senderName: scenario.indicators?.sender_name || 'IT Support Team',
    senderEmail: scenario.indicators?.sender_email || 'it-security@company-support.example',
    audience: scenario.indicators?.audience || 'All Staff',
    status: scenario.indicators?.status || 'Draft',
    lastRun: scenario.indicators?.last_run || '—',
    scheduledFor: scenario.indicators?.scheduled_for || '',
    clickRate: scenario.indicators?.click_rate || '0%',
    reportRate: scenario.indicators?.report_rate || '0%',
    difficulty: scenario.difficulty || 'medium',
    campaignId: scenario.campaign_id || null,
  })

  const normalizeCampaign = (campaign) => ({
    id: campaign.id,
    name: campaign.name || 'Untitled campaign',
    description: campaign.description || '',
    status: campaign.status || 'Draft',
    scenarios: (campaign.scenarios || []).map(normalizeScenario),
  })

  const buildFeedbackPreviewUrl = (scenarioId) => {
    const normalizedBase = apiBase.replace(/\/$/, '')
    return `${normalizedBase}/simulate/phishing-link?scenario_id=${encodeURIComponent(scenarioId)}&preview=1`
  }

  const formatTimestamp = (value) => {
    if (!value) return '—'
    const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(String(value)) ? value : `${value}Z`
    const parsed = new Date(normalized)
    return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString()
  }

  const formatScheduleInput = (value) => {
    if (!value) return ''
    const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(String(value)) ? value : `${value}Z`
    const parsed = new Date(normalized)
    if (Number.isNaN(parsed.getTime())) return ''
    const localTime = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
    return localTime.toISOString().slice(0, 16)
  }

  const schedulePayloadValue = (value) => (value ? new Date(value).toISOString() : null)

  const openFeedbackPreview = (scenarioId) => {
    const url = buildFeedbackPreviewUrl(scenarioId)
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const handleViewAdaptiveScenario = (scenarioId) => {
    const scenario = scenarioOptions.find((item) => String(item.id) === String(scenarioId))
    if (!scenario) {
      setAdaptiveError('The selected scenario could not be loaded.')
      return
    }
    openScenarioModal('view', scenario)
  }

  const totalScenarios = campaigns.reduce((sum, campaign) => sum + campaign.scenarios.length, 0)
  const activeCount = lifecycleCounts.Active
  const draftCount = lifecycleCounts.Draft
  const scheduledCount = lifecycleCounts.Scheduled
  const completedCount = lifecycleCounts.Completed
  const campaignGroups = campaigns
  const fetchCampaigns = async (options = {}) => {
    setIsLoading(true)
    setErrorMessage('')
    try {
      const response = await axios.get(`${apiBase}/campaigns/`, {
        params: { ...options, include_scenarios: true },
      })
      setCampaigns((response.data.items || []).map(normalizeCampaign))
      setTotalCount(response.data.total || 0)
      setHasNextPage(Boolean(response.data.has_more))
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || 'Failed to load campaigns.')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchAdaptiveCampaigns = async () => {
    try {
      const response = await axios.get(`${apiBase}/campaigns/`, {
        params: { limit: 1000, offset: 0, include_scenarios: true },
      })
      setAdaptiveCampaigns((response.data.items || []).map(normalizeCampaign))
    } catch (error) {
      setAdaptiveCampaigns([])
    }
  }

  const fetchLifecycleCounts = async () => {
    try {
      const statuses = ['Draft', 'Scheduled', 'Active', 'Completed']
      const responses = await Promise.all(
        statuses.map((status) => axios.get(`${apiBase}/campaigns/`, { params: { status, limit: 1, include_scenarios: false } }))
      )
      setLifecycleCounts(
        statuses.reduce((counts, status, index) => ({ ...counts, [status]: responses[index].data.total || 0 }), {})
      )
    } catch (error) {
      setLifecycleCounts({ Draft: 0, Scheduled: 0, Active: 0, Completed: 0 })
    }
  }

  const fetchScenarioOptions = async () => {
    try {
      const response = await axios.get(`${apiBase}/scenarios/`, { params: { limit: 1000, offset: 0 } })
      const options = (response.data.items || []).map(normalizeScenario)
      setScenarioOptions(options)
    } catch (error) {
      setScenarioOptions([])
    }
  }

  const fetchAdaptivePrograms = async () => {
    try {
      const response = await axios.get(`${apiBase}/users/adaptive-programs`)
      const programs = response.data || []
      setAdaptivePrograms(programs)
    } catch (error) {
      setAdaptivePrograms([])
    }
  }

  const toScenarioId = (value) => {
    const parsed = Number.parseInt(String(value), 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null
  }

  const parseScenarioIdList = (value) => {
    const uniqueIds = []
    const seen = new Set()
    String(value || '')
      .split(',')
      .map((item) => Number.parseInt(item.trim(), 10))
      .filter((item) => Number.isFinite(item) && item > 0)
      .forEach((item) => {
        if (seen.has(item)) return
        seen.add(item)
        uniqueIds.push(item)
      })
    return uniqueIds
  }

  const nextDispatchLabel = (value) => {
    const match = /^(.*_round_)(\d+)$/.exec(value || '')
    if (!match) return 'adaptive_round_3'
    return `${match[1]}${Number.parseInt(match[2], 10) + 1}`
  }

  const getAdaptiveSourceScenarioIds = () => {
    const parsed = parseScenarioIdList(adaptiveConfig.sourceScenarioIds)
    if (parsed.length) return parsed
    const baselineScenarioId = toScenarioId(adaptiveConfig.baselineScenarioId)
    return baselineScenarioId ? [baselineScenarioId] : []
  }

  const applyDefaultAdaptiveConfig = (options) => {
    if (!options.length) {
      setAdaptiveConfig((current) => ({
        ...current,
        baselineScenarioId: '',
        sourceScenarioIds: '',
        targetedScenarioId: '',
        easierScenarioId: '',
        sameScenarioId: '',
        harderScenarioId: '',
        slightEasierScenarioId: '',
        finalScenarioId: '',
      }))
      return
    }
    const easyOptions = options.filter((scenario) => scenario.difficulty === 'easy')
    const mediumOptions = options.filter((scenario) => scenario.difficulty === 'medium')
    const hardOptions = options.filter((scenario) => scenario.difficulty === 'hard')
    const baseline = mediumOptions[0] || options[0]
    const easy = easyOptions[0] || options[0]
    const secondEasy = easyOptions[1] || easy
    const medium = mediumOptions[1] || mediumOptions[0] || options[0]
    const hard = hardOptions[0] || options[0]
    const final = mediumOptions[2] || mediumOptions[0] || options[options.length - 1]
    setAdaptiveDifficulties({
      baseline: baseline.difficulty || 'medium',
      targeted: easy.difficulty || 'easy',
      easier: secondEasy.difficulty || 'easy',
      same: medium.difficulty || 'medium',
      harder: hard.difficulty || 'hard',
      final: final.difficulty || 'medium',
    })
    setAdaptiveConfig((current) => ({
      ...current,
      baselineScenarioId: String(baseline.id),
      sourceScenarioIds: String(baseline.id),
      sameScenarioId: String(medium.id),
      easierScenarioId: String(secondEasy.id),
      harderScenarioId: String(hard.id),
      targetedScenarioId: String(easy.id),
      slightEasierScenarioId: '',
      finalScenarioId: String(final.id),
    }))
  }

  const handleAdaptiveConfigChange = (key, value) => {
    setAdaptiveConfig((current) => ({ ...current, [key]: value }))
  }

  const scenariosForDifficulty = (difficulty) => (
    adaptiveScenarioOptions.filter((scenario) => !difficulty || scenario.difficulty === difficulty)
  )

  const handleAdaptiveCampaignChange = (value) => {
    setAdaptiveCampaignId(value)
    setAdaptiveError('')
    const campaign = adaptiveCampaigns.find((item) => String(item.id) === String(value))
    applyDefaultAdaptiveConfig(campaign?.scenarios || [])
  }

  const handleAdaptiveDifficultyChange = (laneKey, configKey, difficulty) => {
    const matchingScenarios = scenariosForDifficulty(difficulty)
    setAdaptiveDifficulties((current) => ({ ...current, [laneKey]: difficulty }))
    setAdaptiveConfig((current) => ({
      ...current,
      [configKey]: matchingScenarios.some((scenario) => String(scenario.id) === String(current[configKey]))
        ? current[configKey]
        : String(matchingScenarios[0]?.id || ''),
    }))
  }

  const handleAdaptiveProgramSelection = (value) => {
    setAdaptiveProgramId(value)
    setAdaptiveError('')
    setAdaptiveBaselineResult(null)
    setAdaptiveDispatchResult(null)
    setAdaptiveFinalResult(null)
    setAdaptiveProgramRunResult(null)
    if (!value) {
      setAdaptiveCampaignId('')
      applyDefaultAdaptiveConfig([])
      setAdaptiveSchedule({ baseline: '', adaptive: '', final: '' })
      return
    }

    const selected = adaptivePrograms.find((program) => String(program.id) === String(value))
    if (!selected) return
    const selectedCampaignId = selected.campaign_id || scenarioOptions.find(
      (scenario) => String(scenario.id) === String(selected.baseline_scenario_id)
    )?.campaignId || ''
    setAdaptiveCampaignId(String(selectedCampaignId))
    setAdaptiveProgramName(selected.name || 'Adaptive phishing program')
    setAdaptiveConfig((current) => ({
      ...current,
      baselineScenarioId: String(selected.baseline_scenario_id || ''),
      sourceScenarioIds: (selected.source_scenario_ids || []).join(', '),
      easierScenarioId: String(selected.easier_scenario_id || ''),
      sameScenarioId: String(selected.same_scenario_id || ''),
      harderScenarioId: String(selected.harder_scenario_id || ''),
      targetedScenarioId: String(selected.targeted_repetition_scenario_id || selected.easier_scenario_id || ''),
      slightEasierScenarioId: String(selected.slight_easier_scenario_id || ''),
      finalScenarioId: String(selected.final_scenario_id || ''),
    }))
    const difficultyFor = (scenarioId, fallback) => (
      scenarioOptions.find((scenario) => String(scenario.id) === String(scenarioId))?.difficulty || fallback
    )
    setAdaptiveDifficulties({
      baseline: difficultyFor(selected.baseline_scenario_id, 'medium'),
      targeted: difficultyFor(selected.targeted_repetition_scenario_id || selected.easier_scenario_id, 'easy'),
      easier: difficultyFor(selected.easier_scenario_id, 'easy'),
      same: difficultyFor(selected.same_scenario_id, 'medium'),
      harder: difficultyFor(selected.harder_scenario_id, 'hard'),
      final: difficultyFor(selected.final_scenario_id, 'medium'),
    })
    setAdaptiveSchedule({
      baseline: formatScheduleInput(selected.baseline_scheduled_at),
      adaptive: formatScheduleInput(selected.adaptive_scheduled_at),
      final: formatScheduleInput(selected.final_scheduled_at),
    })
    setAdaptiveProgramRunResult({ stage: 'selected', program: selected, payload: {} })
    if (selected.latest_summary) {
      setAdaptiveBaselineResult({ summary: selected.latest_summary })
    }
    if ((selected.latest_campaigns || []).length && selected.status === 'adaptive_running') {
      setAdaptiveDispatchResult({
        stage_label: `adaptive_round_${selected.adaptive_round_index}`,
        source_scenario_ids: selected.source_scenario_ids || [],
        summary: selected.latest_summary,
        sent_campaigns: selected.latest_campaigns,
        users: [],
      })
    }
    if (selected.final_evaluation) {
      setAdaptiveFinalResult(selected.final_evaluation)
    }
  }

  const handleNewAdaptiveProgram = () => {
    setAdaptiveProgramId('')
    setAdaptiveCampaignId('')
    setAdaptiveProgramName('Quarterly phishing adaptive program')
    setAdaptiveProgramRunResult(null)
    setAdaptiveBaselineResult(null)
    setAdaptiveDispatchResult(null)
    setAdaptiveFinalResult(null)
    setAdaptiveError('')
    setAdaptiveSchedule({ baseline: '', adaptive: '', final: '' })
    setAdaptiveConfig((current) => ({
      ...current,
      baselineScenarioId: '',
      sourceScenarioIds: '',
      targetedScenarioId: '',
      easierScenarioId: '',
      sameScenarioId: '',
      harderScenarioId: '',
      slightEasierScenarioId: '',
      finalScenarioId: '',
      stageLabel: 'adaptive_round_2',
    }))
  }

  const handleCreateAdaptiveProgram = async ({ announce = true } = {}) => {
    const campaignId = toScenarioId(adaptiveCampaignId)
    const baselineScenarioId = toScenarioId(adaptiveConfig.baselineScenarioId)
    const finalScenarioId = toScenarioId(adaptiveConfig.finalScenarioId)
    const easierScenarioId = toScenarioId(adaptiveConfig.easierScenarioId)
    const sameScenarioId = toScenarioId(adaptiveConfig.sameScenarioId)
    const harderScenarioId = toScenarioId(adaptiveConfig.harderScenarioId)
    const targetedScenarioId = toScenarioId(adaptiveConfig.targetedScenarioId)
    if (!campaignId) {
      setAdaptiveError('Select the campaign that owns this adaptive program.')
      return null
    }
    if (!baselineScenarioId || !finalScenarioId || !targetedScenarioId || !easierScenarioId || !sameScenarioId || !harderScenarioId) {
      setAdaptiveError('Select one scenario from the chosen campaign for Stage 1, every Stage 3 path, and Stage 4.')
      return null
    }
    const scheduledValues = [adaptiveSchedule.baseline, adaptiveSchedule.adaptive, adaptiveSchedule.final]
      .filter(Boolean)
      .map((value) => new Date(value).getTime())
    if (scheduledValues.some((value, index) => index > 0 && value < scheduledValues[index - 1])) {
      setAdaptiveError('Scheduled dates must follow Stage 1, Stage 2/3, then Stage 4.')
      return null
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const payload = {
        name: adaptiveProgramName || 'Adaptive phishing program',
        campaign_id: campaignId,
        baseline_scenario_id: baselineScenarioId,
        final_scenario_id: finalScenarioId,
        easier_scenario_id: easierScenarioId,
        same_scenario_id: sameScenarioId,
        harder_scenario_id: harderScenarioId,
        targeted_repetition_scenario_id: targetedScenarioId,
        adaptive_rounds: 1,
        baseline_scheduled_at: schedulePayloadValue(adaptiveSchedule.baseline),
        adaptive_scheduled_at: schedulePayloadValue(adaptiveSchedule.adaptive),
        final_scheduled_at: schedulePayloadValue(adaptiveSchedule.final),
      }

      const response = await axios.post(`${apiBase}/users/adaptive-programs`, payload)
      setAdaptiveProgramId(String(response.data.id))
      setAdaptiveProgramRunResult({ stage: 'created', program: response.data, payload: {} })
      if (announce) showToast('Adaptive program configuration saved.')
      fetchAdaptivePrograms()
      return response.data
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to create adaptive program.')
      return null
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleAdvanceAdaptiveProgram = async (programIdOverride = null) => {
    const programId = toScenarioId(programIdOverride || adaptiveProgramId)
    if (!programId) {
      setAdaptiveError('Create or select an adaptive program first.')
      return
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const response = await axios.post(`${apiBase}/users/adaptive-programs/${programId}/advance`)
      setAdaptiveProgramRunResult(response.data)
      setAdaptiveBaselineResult(response.data.stage === 'adaptive_round_dispatched' ? {
        summary: response.data.payload?.summary,
      } : adaptiveBaselineResult)
      setAdaptiveDispatchResult(response.data.stage === 'adaptive_round_dispatched' ? response.data.payload : adaptiveDispatchResult)
      setAdaptiveFinalResult(response.data.stage === 'completed' ? response.data.payload : adaptiveFinalResult)
      showToast(`Program advanced: ${response.data.stage.replaceAll('_', ' ')}`)
      fetchAdaptivePrograms()
      fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to advance adaptive program.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleStartAdaptiveProgram = async () => {
    if (activeAdaptiveProgram) {
      if (adaptiveProgramStatus !== 'created') return
      await handleAdvanceAdaptiveProgram(activeAdaptiveProgram.id)
      return
    }

    const createdProgram = await handleCreateAdaptiveProgram({ announce: false })
    if (!createdProgram) return

    const baselineScheduleValue = createdProgram.baseline_scheduled_at
    const baselineStart = baselineScheduleValue
      ? new Date(
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(String(baselineScheduleValue))
          ? baselineScheduleValue
          : `${baselineScheduleValue}Z`
      ).getTime()
      : null
    if (Number.isFinite(baselineStart) && baselineStart > Date.now()) {
      showToast(`Adaptive program started. Stage 1 is scheduled for ${formatTimestamp(createdProgram.baseline_scheduled_at)}.`)
      return
    }

    await handleAdvanceAdaptiveProgram(createdProgram.id)
  }

  const handleRunFullAdaptiveDemo = async () => {
    const baselineScenarioId = toScenarioId(adaptiveConfig.baselineScenarioId)
    const finalScenarioId = toScenarioId(adaptiveConfig.finalScenarioId)
    const easierScenarioId = toScenarioId(adaptiveConfig.easierScenarioId)
    const sameScenarioId = toScenarioId(adaptiveConfig.sameScenarioId)
    const harderScenarioId = toScenarioId(adaptiveConfig.harderScenarioId)
    if (!baselineScenarioId || !finalScenarioId || !easierScenarioId || !sameScenarioId || !harderScenarioId) {
      setAdaptiveError('Για one-click demo, επέλεξε baseline/final και easier/same/harder scenarios.')
      return
    }

    setAdaptiveLoading(true)
    setAdaptiveError('')
    setQuickDemoResult(null)
    try {
      const createPayload = {
        name: `${adaptiveProgramName || 'Adaptive demo'} (one-click)`,
        campaign_id: toScenarioId(adaptiveCampaignId),
        baseline_scenario_id: baselineScenarioId,
        final_scenario_id: finalScenarioId,
        easier_scenario_id: easierScenarioId,
        same_scenario_id: sameScenarioId,
        harder_scenario_id: harderScenarioId,
        adaptive_rounds: 2,
      }
      const targetedScenarioId = toScenarioId(adaptiveConfig.targetedScenarioId)
      const slightEasierScenarioId = toScenarioId(adaptiveConfig.slightEasierScenarioId)
      if (targetedScenarioId) createPayload.targeted_repetition_scenario_id = targetedScenarioId
      if (slightEasierScenarioId) createPayload.slight_easier_scenario_id = slightEasierScenarioId

      const created = await axios.post(`${apiBase}/users/adaptive-programs`, createPayload)
      let currentProgram = created.data
      const programId = currentProgram.id
      setAdaptiveProgramId(String(programId))

      const transitions = []
      const maxSteps = Number(currentProgram.adaptive_rounds || 2) + 5
      for (let step = 0; step < maxSteps; step += 1) {
        const advanced = await axios.post(`${apiBase}/users/adaptive-programs/${programId}/advance`)
        const stage = advanced?.data?.stage || 'unknown'
        currentProgram = advanced?.data?.program || currentProgram
        transitions.push({
          stage,
          status: currentProgram.status,
          round: `${currentProgram.adaptive_round_index}/${currentProgram.adaptive_rounds}`,
        })
        if (currentProgram.status === 'completed') {
          setAdaptiveProgramRunResult(advanced.data)
          break
        }
      }

      if (currentProgram.final_evaluation) {
        setAdaptiveFinalResult(currentProgram.final_evaluation)
      }

      setQuickDemoResult({
        programId,
        status: currentProgram.status,
        transitions,
        baselinePreviewUrl: buildFeedbackPreviewUrl(baselineScenarioId),
      })

      fetchAdaptivePrograms()
      fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
      showToast('One-click adaptive demo ολοκληρώθηκε.')
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to run one-click adaptive demo.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleRunAdaptiveBaseline = async () => {
    const baselineScenarioId = toScenarioId(adaptiveConfig.baselineScenarioId)
    if (!baselineScenarioId) {
      setAdaptiveError('Select a baseline scenario first.')
      return
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const response = await axios.post(`${apiBase}/users/adaptive-programs/baseline`, {
        source_scenario_ids: [baselineScenarioId],
      })
      setAdaptiveBaselineResult(response.data)
      showToast('Baseline evaluation completed.')
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to run baseline evaluation.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleRunAdaptiveDispatch = async () => {
    const sourceScenarioIds = getAdaptiveSourceScenarioIds()
    const easierScenarioId = toScenarioId(adaptiveConfig.easierScenarioId)
    const sameScenarioId = toScenarioId(adaptiveConfig.sameScenarioId)
    const harderScenarioId = toScenarioId(adaptiveConfig.harderScenarioId)
    if (!sourceScenarioIds.length || !easierScenarioId || !sameScenarioId || !harderScenarioId) {
      setAdaptiveError('Choose source, easier, same, and harder scenarios before dispatch.')
      return
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const payload = {
        source_scenario_ids: sourceScenarioIds,
        easier_scenario_id: easierScenarioId,
        same_scenario_id: sameScenarioId,
        harder_scenario_id: harderScenarioId,
        stage_label: adaptiveConfig.stageLabel || 'adaptive_round_2',
        assign_training_for_low_readiness: true,
      }
      const targetedScenarioId = toScenarioId(adaptiveConfig.targetedScenarioId)
      const slightEasierScenarioId = toScenarioId(adaptiveConfig.slightEasierScenarioId)
      if (targetedScenarioId) payload.targeted_repetition_scenario_id = targetedScenarioId
      if (slightEasierScenarioId) payload.slight_easier_scenario_id = slightEasierScenarioId

      const response = await axios.post(`${apiBase}/users/adaptive-programs/dispatch`, payload)
      setAdaptiveDispatchResult(response.data)
      const nextSourceScenarioIds = [...new Set((response.data?.sent_campaigns || []).map((campaign) => campaign.scenario_id).filter(Boolean))]
      if (nextSourceScenarioIds.length) {
        setAdaptiveConfig((current) => ({
          ...current,
          sourceScenarioIds: nextSourceScenarioIds.join(', '),
          stageLabel: nextDispatchLabel(current.stageLabel || 'adaptive_round_2'),
        }))
      }
      showToast('Adaptive dispatch completed.')
      fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to run adaptive dispatch.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleRunAdaptiveFinalEvaluation = async () => {
    const baselineScenarioId = toScenarioId(adaptiveConfig.baselineScenarioId)
    const finalScenarioId = toScenarioId(adaptiveConfig.finalScenarioId)
    if (!baselineScenarioId || !finalScenarioId) {
      setAdaptiveError('Select baseline and final common scenarios first.')
      return
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const response = await axios.post(`${apiBase}/users/adaptive-programs/final-evaluation`, {
        baseline_scenario_id: baselineScenarioId,
        final_scenario_id: finalScenarioId,
      })
      setAdaptiveFinalResult(response.data)
      showToast('Final before-after evaluation completed.')
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || 'Failed to run final evaluation.')
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleSendAdaptiveScenario = async (scenarioId, label) => {
    if (!scenarioId) {
      setAdaptiveError(`Select a ${label} scenario first.`)
      return
    }
    setAdaptiveLoading(true)
    setAdaptiveError('')
    try {
      const response = await axios.post(`${apiBase}/scenarios/${scenarioId}/send-mock`)
      if (label === 'baseline') {
        setAdaptiveConfig((current) => ({
          ...current,
          sourceScenarioIds: String(scenarioId),
          stageLabel: 'adaptive_round_2',
        }))
      }
      fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
      showToast(response.data?.message || `${label} campaign sent.`)
    } catch (error) {
      setAdaptiveError(error?.response?.data?.detail || `Failed to send ${label} campaign.`)
    } finally {
      setAdaptiveLoading(false)
    }
  }

  const handleRecipientSimulationAction = async (recipient, actionType) => {
    const url = recipient?.interaction_urls?.[actionType]
    if (!url) {
      showToast('Interaction link is not available for this recipient snapshot.')
      return
    }

    if (actionType === 'open') {
      try {
        await axios.get(url)
        if (activeScenario?.id) {
          fetchCampaignResults(activeScenario.id)
        }
        showToast('Open event recorded.')
      } catch (error) {
        showToast('Failed to record open event.')
      }
      return
    }

    window.open(url, '_blank', 'noopener,noreferrer')
    if (activeScenario?.id) {
      window.setTimeout(() => fetchCampaignResults(activeScenario.id), 250)
    }
    showToast(actionType === 'click' ? 'Click simulation opened.' : 'Report confirmation opened.')
  }

  useEffect(() => {
    fetchCampaigns({ limit: pageSize, offset: 0 })
    fetchLifecycleCounts()
    fetchScenarioOptions()
    fetchAdaptiveCampaigns()
    fetchAdaptivePrograms()
  }, [])

  useEffect(() => {
    const timer = window.setInterval(fetchAdaptivePrograms, 30000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!canManageScenarios) return
    axios.get(`${apiBase}/email-templates/`, { params: { approval_status: 'approved' } })
      .then((response) => setTemplates((response.data || []).filter((template) => template.key !== 'password_reset')))
      .catch(() => setTemplates([]))
  }, [apiBase, canManageScenarios])

  useEffect(() => {
    const selectedTemplate = searchParams.get('template')
    if (!selectedTemplate || !templates.length) return
    if (templates.some((template) => template.key === selectedTemplate)) {
      setFormData(templateFormValues(selectedTemplate))
      setCreateStep(1)
      setIsModalOpen(true)
    }
    setSearchParams({}, { replace: true })
  }, [templates, searchParams, setSearchParams])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = {}
      if (searchTerm.trim()) params.search = searchTerm.trim()
      if (statusFilter !== 'all') params.status = statusFilter
      params.limit = pageSize
      params.offset = page * pageSize
      fetchCampaigns(params)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchTerm, statusFilter, page])

  const openScenarioModal = (type, scenario) => {
    setActiveModal(type)
    setActiveScenario(scenario)
    if (type === 'report' && scenario) {
      fetchCampaignResults(scenario.id)
    }
    if (type === 'edit' && scenario) {
      setFormData({
        campaignId: scenario.campaignId || '',
        campaignName: '',
        campaignDescription: '',
        scenarioName: scenario.name,
        template: scenario.template,
        emailTemplateKey: scenario.emailTemplateKey,
        emailSubject: scenario.emailSubject,
        emailBodyText: scenario.emailBodyText,
        emailBodyHtml: scenario.emailBodyHtml,
        audience: scenario.audience,
        schedule: scenario.scheduledFor,
      })
    }
  }

  const closeScenarioModal = () => {
    setActiveModal(null)
    setActiveScenario(null)
    setCampaignResults(null)
    setResultsError('')
  }

  const openNewCampaign = async () => {
    if (!canManageScenarios) {
      showToast('You do not have permission to create or edit campaigns.')
      return
    }

    let availableTemplates = templates
    if (!availableTemplates.length) {
      try {
        const response = await axios.get(`${apiBase}/email-templates/`, {
          params: { approval_status: 'approved' },
        })
        availableTemplates = (response.data || []).filter(
          (template) => template.key !== 'password_reset'
        )
        setTemplates(availableTemplates)
      } catch (error) {
        showToast(error?.response?.data?.detail || 'Failed to load campaign templates.')
        return
      }
    }

    if (!availableTemplates.length) {
      showToast('No approved templates are available for campaign creation.')
      return
    }

    setFormData(templateFormValues('', availableTemplates))
    setCreateStep(1)
    setIsModalOpen(true)
  }

  const fetchCampaignResults = async (scenarioId) => {
    setIsResultsLoading(true)
    setResultsError('')
    setCampaignResults(null)
    try {
      const response = await axios.get(`${apiBase}/scenarios/${scenarioId}/results`)
      setCampaignResults(response.data)
    } catch (error) {
      setResultsError(error?.response?.data?.detail || 'Failed to load campaign results.')
    } finally {
      setIsResultsLoading(false)
    }
  }

  const handleCreateCampaign = async () => {
    if (!canManageScenarios) {
      showToast('You do not have permission to create or edit campaigns.')
      return
    }
    try {
      let campaignId = Number.parseInt(String(formData.campaignId), 10)
      if (!Number.isFinite(campaignId)) {
        const campaignResponse = await axios.post(`${apiBase}/campaigns/`, {
          name: formData.campaignName,
          description: formData.campaignDescription || null,
          status: formData.schedule ? 'Scheduled' : 'Draft',
          scenario_ids: [],
        })
        campaignId = campaignResponse.data.id
      }

      const payload = {
        title: formData.scenarioName,
        difficulty: 'medium',
        campaign_id: campaignId,
        indicators: {
          template: formData.template,
          email_template_key: formData.emailTemplateKey,
          email_template_name: formData.template,
          email_subject: formData.emailSubject,
          email_body_text: formData.emailBodyText,
          email_body_html: formData.emailBodyHtml,
          audience: formData.audience,
          status: formData.schedule ? 'Scheduled' : 'Draft',
          scheduled_for: formData.schedule || null,
          last_run: '—',
          click_rate: '0%',
          report_rate: '0%',
        },
      }
      await axios.post(`${apiBase}/scenarios/`, payload)
      await fetchCampaigns({
        limit: pageSize,
        offset: page * pageSize,
        ...(searchTerm.trim() ? { search: searchTerm.trim() } : {}),
        ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
      })
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
      fetchLifecycleCounts()
      setIsModalOpen(false)
      showToast(formData.campaignId ? 'Scenario added to campaign.' : 'Campaign created.')
    } catch (error) {
      showToast(error?.response?.data?.detail || 'Failed to create campaign.')
    }
  }

  const handleUpdateScenario = async () => {
    if (!activeScenario) return
    try {
      const payload = {
        title: formData.scenarioName,
        indicators: {
          template: formData.template,
          email_template_key: formData.emailTemplateKey,
          email_template_name: formData.template,
          email_subject: formData.emailSubject,
          email_body_text: formData.emailBodyText,
          email_body_html: formData.emailBodyHtml,
          audience: formData.audience,
          status: activeScenario.status,
          scheduled_for: formData.schedule || null,
          last_run: activeScenario.lastRun,
          click_rate: activeScenario.clickRate,
          report_rate: activeScenario.reportRate,
        },
      }
      await axios.patch(`${apiBase}/scenarios/${activeScenario.id}`, payload)
      await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchScenarioOptions()
      fetchAdaptiveCampaigns()
      showToast('Changes saved.')
    } catch (error) {
      showToast('Failed to update scenario.')
    }
  }

  const handleStatusChange = async (scenario, status) => {
    try {
      await axios.patch(`${apiBase}/scenarios/${scenario.id}`, {
        indicators: {
          template: scenario.template,
          email_template_key: scenario.emailTemplateKey,
          email_template_name: scenario.template,
          email_subject: scenario.emailSubject,
          email_body_text: scenario.emailBodyText,
          email_body_html: scenario.emailBodyHtml,
          audience: scenario.audience,
          status,
          last_run: scenario.lastRun,
          scheduled_for: scenario.scheduledFor || null,
          click_rate: scenario.clickRate,
          report_rate: scenario.reportRate,
        },
      })
      await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      showToast(`${scenario.name} moved to ${status}.`)
    } catch (error) {
      showToast('Failed to update campaign status.')
    }
  }

  const confirmResourceDeletion = async () => {
    if (!deletionTarget || isDeleting) return
    const { type, resource } = deletionTarget
    setIsDeleting(true)
    try {
      if (type === 'campaign') {
        const response = await axios.delete(`${apiBase}/campaigns/${resource.id}`)
        const nextPage = campaigns.length === 1 && page > 0 ? page - 1 : page
        if (nextPage !== page) setPage(nextPage)
        await fetchCampaigns({ limit: pageSize, offset: nextPage * pageSize })
        fetchScenarioOptions()
        fetchAdaptiveCampaigns()
        fetchAdaptivePrograms()
        fetchLifecycleCounts()
        const scenariosDeleted = Number(response.data?.scenarios_deleted || 0)
        showToast(`Campaign deleted with ${scenariosDeleted} scenario${scenariosDeleted === 1 ? '' : 's'}.`)
      } else {
        const response = await axios.delete(`${apiBase}/scenarios/${resource.id}`)
        await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
        fetchScenarioOptions()
        fetchAdaptiveCampaigns()
        fetchAdaptivePrograms()
        fetchLifecycleCounts()
        const removedPrograms = Number(response.data?.adaptive_programs_deleted || 0)
        showToast(
          removedPrograms
            ? `Scenario deleted with ${removedPrograms} dependent adaptive program${removedPrograms === 1 ? '' : 's'}.`
            : 'Scenario deleted.'
        )
      }
      setDeletionTarget(null)
    } catch (error) {
      showToast(
        error?.response?.data?.detail
        || `Failed to delete ${type === 'campaign' ? 'campaign' : 'scenario'}.`
      )
    } finally {
      setIsDeleting(false)
    }
  }

  const requestScenarioDeletion = (scenario) => {
    setDeletionTarget({ type: 'scenario', resource: scenario })
  }

  const requestCampaignDeletion = (campaign) => {
    if (!canDeleteCampaigns) {
      showToast('Only administrators can delete campaigns.')
      return
    }
    setDeletionTarget({ type: 'campaign', resource: campaign })
  }

  const handleCampaignStatusChange = async (campaign, status) => {
    try {
      await axios.patch(`${apiBase}/campaigns/${campaign.id}`, { status })
      await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      showToast(`${campaign.name} moved to ${status}.`)
    } catch (error) {
      showToast(error?.response?.data?.detail || 'Failed to update campaign status.')
    }
  }

  const openCampaignEditor = (campaign) => {
    setEditingCampaign({
      id: campaign.id,
      name: campaign.name,
      description: campaign.description || '',
      status: campaign.status,
    })
  }

  const handleUpdateCampaignDetails = async () => {
    if (!editingCampaign?.id || !editingCampaign.name.trim()) return
    try {
      await axios.patch(`${apiBase}/campaigns/${editingCampaign.id}`, {
        name: editingCampaign.name.trim(),
        description: editingCampaign.description.trim() || null,
        status: editingCampaign.status,
      })
      await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchAdaptiveCampaigns()
      setEditingCampaign(null)
      showToast('Campaign details updated.')
    } catch (error) {
      showToast(error?.response?.data?.detail || 'Failed to update campaign details.')
    }
  }

  const toggleCampaignScenarios = (campaignId) => {
    setCollapsedCampaignIds((current) => (
      current.includes(campaignId)
        ? current.filter((id) => id !== campaignId)
        : [...current, campaignId]
    ))
  }

  const handleDownloadReport = async (scenario) => {
    try {
      const response = await axios.post(
        `${apiBase}/stats/export`,
        {
          format: 'csv',
          include_scenarios: true,
          include_users: false,
          include_events: false,
          scenario_id: String(scenario.id),
        },
        { responseType: 'blob' }
      )
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `dark-signal-scenario-${scenario.id}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      showToast('Report downloaded.')
    } catch (error) {
      showToast('Failed to download report.')
    }
  }

  const handleSendMock = async (scenario) => {
    if (!window.confirm(`Send mock phishing email for ${scenario.name}?`)) return
    try {
      const response = await axios.post(`${apiBase}/scenarios/${scenario.id}/send-mock`)
      await fetchCampaigns({ limit: pageSize, offset: page * pageSize })
      fetchLifecycleCounts()
      const message =
        response.data?.message || `Mock phishing campaign completed for ${response.data?.recipients || 0} users.`
      showToast(message)
    } catch (error) {
      showToast('Failed to send mock phishing emails.')
    }
  }

  const activeAdaptiveProgram =
    adaptivePrograms.find((program) => String(program.id) === String(adaptiveProgramId))
    || adaptiveProgramRunResult?.program
    || null
  const adaptiveProgramStatus = activeAdaptiveProgram?.status || 'configuration'
  const adaptiveRoundIndex = Number(activeAdaptiveProgram?.adaptive_round_index || 0)
  const adaptiveRoundTotal = Number(activeAdaptiveProgram?.adaptive_rounds || 2)
  const adaptiveConfigurationComplete = Boolean(
    adaptiveCampaignId
    && toScenarioId(adaptiveConfig.baselineScenarioId)
    && toScenarioId(adaptiveConfig.targetedScenarioId)
    && toScenarioId(adaptiveConfig.easierScenarioId)
    && toScenarioId(adaptiveConfig.sameScenarioId)
    && toScenarioId(adaptiveConfig.harderScenarioId)
    && toScenarioId(adaptiveConfig.finalScenarioId)
  )
  const stageStates = {
    baseline: ['baseline_sent', 'adaptive_running', 'final_sent', 'completed'].includes(adaptiveProgramStatus)
      ? 'completed'
      : adaptiveProgramStatus === 'created' ? 'ready' : 'configuration',
    segmentation: ['adaptive_running', 'final_sent', 'completed'].includes(adaptiveProgramStatus)
      ? 'completed'
      : adaptiveProgramStatus === 'baseline_sent' ? 'active' : 'pending',
    adaptive: ['final_sent', 'completed'].includes(adaptiveProgramStatus)
      || (adaptiveProgramStatus === 'adaptive_running' && adaptiveRoundIndex >= adaptiveRoundTotal)
      ? 'completed'
      : adaptiveProgramStatus === 'adaptive_running' ? 'active' : 'pending',
    final: adaptiveProgramStatus === 'completed'
      ? 'completed'
      : adaptiveProgramStatus === 'final_sent' ? 'active' : 'pending',
  }
  const stageStateLabel = {
    configuration: 'Configure',
    pending: 'Waiting',
    ready: 'Ready',
    active: 'In progress',
    completed: 'Completed',
  }
  const nextStageLabel = (() => {
    if (!activeAdaptiveProgram) return 'Save the program first'
    if (adaptiveProgramStatus === 'created') return 'Start Adaptive Program'
    if (adaptiveProgramStatus === 'baseline_sent') return 'Run Stage 2 & Start Stage 3'
    if (adaptiveProgramStatus === 'adaptive_running' && adaptiveRoundIndex < adaptiveRoundTotal) {
      return `Run Adaptive Round ${adaptiveRoundIndex + 1}`
    }
    if (adaptiveProgramStatus === 'adaptive_running') return 'Start Stage 4'
    if (adaptiveProgramStatus === 'final_sent') return 'Complete Final Comparison'
    if (adaptiveProgramStatus === 'completed') return 'Program Completed'
    return 'Run Next Stage'
  })()
  const nextScheduledAt = (() => {
    if (!activeAdaptiveProgram) return null
    if (adaptiveProgramStatus === 'created') return activeAdaptiveProgram.baseline_scheduled_at
    if (
      ['baseline_sent', 'adaptive_running'].includes(adaptiveProgramStatus)
      && adaptiveRoundIndex < adaptiveRoundTotal
    ) return activeAdaptiveProgram.adaptive_scheduled_at
    if (adaptiveProgramStatus === 'adaptive_running') return activeAdaptiveProgram.final_scheduled_at
    return null
  })()
  const nextScheduleTimestamp = nextScheduledAt
    ? new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(String(nextScheduledAt)) ? nextScheduledAt : `${nextScheduledAt}Z`).getTime()
    : null
  const waitingForScheduledStage = Number.isFinite(nextScheduleTimestamp) && nextScheduleTimestamp > Date.now()
  const adaptiveStartLabel = (() => {
    if (adaptiveLoading) return 'Starting...'
    if (!activeAdaptiveProgram) return 'Start Adaptive Program'
    if (adaptiveProgramStatus === 'created' && waitingForScheduledStage) {
      return `Stage 1 Scheduled · ${formatTimestamp(nextScheduledAt)}`
    }
    if (adaptiveProgramStatus === 'created') return 'Start Adaptive Program'
    if (adaptiveProgramStatus === 'completed') return 'Adaptive Program Completed'
    return 'Adaptive Program Running'
  })()
  const adaptiveStartDisabled = adaptiveLoading
    || (!activeAdaptiveProgram && !adaptiveConfigurationComplete)
    || (Boolean(activeAdaptiveProgram) && adaptiveProgramStatus !== 'created')
    || waitingForScheduledStage
  const countRecipientsForActions = (actions) => {
    const classifiedUsers = adaptiveUsers.filter((item) => actions.includes(item.recommended_action))
    if (classifiedUsers.length) return classifiedUsers.length
    return (activeAdaptiveProgram?.latest_campaigns || adaptiveDispatchResult?.sent_campaigns || [])
      .filter((item) => actions.includes(item.recommended_action))
      .reduce((sum, item) => sum + Number(item.recipients || 0), 0)
  }
  const scenarioNameById = (scenarioId) => (
    scenarioOptions.find((scenario) => String(scenario.id) === String(scenarioId))?.name || 'Scenario not selected'
  )
  const scenarioPreviewHtml = (scenario) => {
    const escapedText = String(scenario?.emailBodyText || 'No email body has been configured for this scenario.')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
    const messageBody = scenario?.emailBodyHtml || `<pre>${escapedText}</pre>`
    return `
      <!doctype html>
      <html lang="en">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width,initial-scale=1" />
          <style>
            * { box-sizing: border-box; }
            html, body { margin: 0; min-height: 100%; }
            body {
              padding: 28px 30px;
              background: #f8fafc;
              color: #172033;
              font-family: Inter, "Segoe UI", Arial, sans-serif;
              font-size: 15px;
              line-height: 1.65;
            }
            main { max-width: 680px; margin: 0 auto; }
            h1, h2, h3 { color: #0f172a; line-height: 1.25; }
            p { margin: 0 0 16px; }
            a { color: #0369a1; font-weight: 700; }
            button, .button, [role="button"] {
              display: inline-block;
              padding: 11px 18px;
              border: 0;
              border-radius: 7px;
              background: #0369a1;
              color: white;
              font-weight: 700;
              text-decoration: none;
            }
            img { max-width: 100%; }
            pre {
              margin: 0;
              color: #172033;
              font: 14px/1.65 Inter, "Segoe UI", Arial, sans-serif;
              white-space: pre-wrap;
            }
            .training-footer {
              margin-top: 30px;
              padding-top: 14px;
              border-top: 1px solid #e2e8f0;
              color: #64748b;
              font-size: 12px;
            }
          </style>
        </head>
        <body>
          <main>
            ${messageBody}
            <div class="training-footer">Dark Signal · Controlled security-awareness simulation</div>
          </main>
        </body>
      </html>
    `
  }

  if (isLoading) {
    return (
      <div className="container loading">
        <div className="spinner"></div>
      </div>
    )
  }

  if (errorMessage) {
    return (
      <div className="container error">
        Error: {errorMessage}
        <div style={{ marginTop: '1rem' }}>
          <button className="action-btn secondary-btn" onClick={() => fetchCampaigns({ limit: pageSize, offset: page * pageSize })}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container campaigns-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Campaigns</h1>
          <p className="page-subtitle">Create, schedule, and monitor phishing simulation campaigns.</p>
        </div>
        <button
          className="action-btn primary-btn"
          title={!canManageScenarios ? 'Viewer access: campaign creation requires Admin or Analyst permissions' : undefined}
          onClick={openNewCampaign}
        >
          + New Campaign
        </button>
      </div>

      <section className="campaign-control" aria-labelledby="campaign-control-title">
        <div className="campaign-control-header">
          <div>
            <span className="campaign-control-eyebrow">Campaign control center</span>
            <h2 id="campaign-control-title">Simulation operations</h2>
          </div>
          <span className="campaign-control-summary">
            {totalCount ? `${totalCount} campaign${totalCount === 1 ? '' : 's'} tracked` : 'Ready for your first campaign'}
          </span>
        </div>
        <div className="campaign-status-overview">
          <button className={`campaign-status-card ${statusFilter === 'all' ? 'selected' : ''}`} onClick={() => setStatusFilter('all')}>
            <div>
              <span>All campaigns</span>
              <strong>{totalCount}</strong>
            </div>
          </button>
          <button className={`campaign-status-card draft ${statusFilter === 'Draft' ? 'selected' : ''}`} onClick={() => setStatusFilter('Draft')}>
            <div>
              <span>Draft</span>
              <strong>{draftCount}</strong>
            </div>
          </button>
          <button className={`campaign-status-card scheduled ${statusFilter === 'Scheduled' ? 'selected' : ''}`} onClick={() => setStatusFilter('Scheduled')}>
            <div>
              <span>Scheduled</span>
              <strong>{scheduledCount}</strong>
            </div>
          </button>
          <button className={`campaign-status-card active ${statusFilter === 'Active' ? 'selected' : ''}`} onClick={() => setStatusFilter('Active')}>
            <div>
              <span>Active</span>
              <strong>{activeCount}</strong>
            </div>
          </button>
          <button className={`campaign-status-card completed ${statusFilter === 'Completed' ? 'selected' : ''}`} onClick={() => setStatusFilter('Completed')}>
            <div>
              <span>Completed</span>
              <strong>{completedCount}</strong>
            </div>
          </button>
        </div>
      </section>

      {canManageScenarios && (
        <section className="adaptive-program" aria-labelledby="adaptive-program-title">
          <div className="adaptive-program-header">
            <div>
              <span className="campaign-control-eyebrow">Continuous training</span>
              <h2 id="adaptive-program-title">Adaptive Program Lab</h2>
              <p className="muted adaptive-subtitle">Run the 4-stage workflow: common baseline, segmentation, adaptive dispatch, and common final comparison.</p>
            </div>
            <span className="adaptive-status-pill">
              {adaptiveLoading ? 'Running...' : adaptiveProgramStatus.replaceAll('_', ' ')}
            </span>
          </div>

          <div className="adaptive-program-setup">
            <label className="field">
              Program name
              <input
                value={adaptiveProgramName}
                disabled={Boolean(adaptiveProgramId)}
                onChange={(event) => setAdaptiveProgramName(event.target.value)}
                placeholder="Adaptive training program"
              />
            </label>

            <label className="field">
              Campaign
              <select
                value={adaptiveCampaignId}
                disabled={Boolean(adaptiveProgramId)}
                onChange={(event) => handleAdaptiveCampaignChange(event.target.value)}
              >
                <option value="">Select campaign first</option>
                {adaptiveCampaigns.map((campaign) => (
                  <option key={`adaptive-campaign-${campaign.id}`} value={campaign.id}>
                    {campaign.name} · {campaign.scenarios.length} scenario{campaign.scenarios.length === 1 ? '' : 's'}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              Existing program
              <select value={adaptiveProgramId} onChange={(event) => handleAdaptiveProgramSelection(event.target.value)}>
                <option value="">New program configuration</option>
                {adaptivePrograms.map((program) => (
                  <option key={`program-${program.id}`} value={program.id}>
                    #{program.id} · {program.name} · {program.status.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!adaptiveCampaignId && (
            <div className="adaptive-campaign-guidance">
              <strong>Select a campaign to configure the adaptive workflow.</strong>
              <span>Only scenarios belonging to that campaign will become available in Stages 1, 3, and 4.</span>
            </div>
          )}
          {selectedAdaptiveCampaign && (
            <div className="adaptive-campaign-guidance selected">
              <strong>{selectedAdaptiveCampaign.name}</strong>
              <span>{selectedAdaptiveCampaign.scenarios.length} linked scenario{selectedAdaptiveCampaign.scenarios.length === 1 ? '' : 's'} available for this program.</span>
            </div>
          )}

          <div className={`adaptive-launch-panel ${adaptiveConfigurationComplete || activeAdaptiveProgram ? 'ready' : ''}`}>
            <div>
              <span className="campaign-control-eyebrow">Program launch</span>
              <strong>
                {activeAdaptiveProgram
                  ? `Program #${activeAdaptiveProgram.id} · ${activeAdaptiveProgram.name}`
                  : adaptiveConfigurationComplete
                    ? 'Configuration complete — ready to launch'
                    : 'Complete all required scenario selections to enable launch'}
              </strong>
              <small>
                {adaptiveSchedule.baseline
                  ? 'Starting activates the workflow and respects the Stage 1 scheduled date.'
                  : 'Starting saves the configuration and immediately sends the common Stage 1 scenario.'}
              </small>
            </div>
            <button
              className="action-btn primary-btn adaptive-start-button"
              disabled={adaptiveStartDisabled}
              onClick={handleStartAdaptiveProgram}
            >
              {adaptiveStartLabel}
            </button>
          </div>

          <div className="adaptive-workflow" aria-label="Four-stage adaptive training workflow">
            <article className={`adaptive-stage-card adaptive-baseline-card state-${stageStates.baseline}`}>
              <div className="adaptive-stage-heading">
                <span className="adaptive-stage-number">1</span>
                <div>
                  <span className="adaptive-stage-kicker">Stage 1</span>
                  <h3>Baseline assessment</h3>
                </div>
                <span className={`adaptive-stage-state state-${stageStates.baseline}`}>{stageStateLabel[stageStates.baseline]}</span>
              </div>
              <p>One common scenario establishes the starting awareness level for every email recipient.</p>
              <label className="field">
                Difficulty
                <select
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveDifficulties.baseline}
                  onChange={(event) => handleAdaptiveDifficultyChange('baseline', 'baselineScenarioId', event.target.value)}
                >
                  <option value="">All levels</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
              <label className="field">
                Common baseline scenario
                <select
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveConfig.baselineScenarioId}
                  onChange={(event) => handleAdaptiveConfigChange('baselineScenarioId', event.target.value)}
                >
                  <option value="">Select scenario</option>
                  {scenariosForDifficulty(adaptiveDifficulties.baseline).map((scenario) => (
                    <option key={`baseline-${scenario.id}`} value={scenario.id}>{scenario.name}</option>
                  ))}
                </select>
              </label>
              <label className="field adaptive-date-field">
                Stage 1 date and time
                <input
                  type="datetime-local"
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveSchedule.baseline}
                  onChange={(event) => setAdaptiveSchedule((current) => ({ ...current, baseline: event.target.value }))}
                />
                <small>{adaptiveSchedule.baseline ? 'Runs automatically at this time.' : 'Optional — leave empty to run manually.'}</small>
              </label>
              {activeAdaptiveProgram?.baseline_executed_at && (
                <div className="adaptive-executed-date">
                  <span>Executed</span>
                  <strong>{formatTimestamp(activeAdaptiveProgram.baseline_executed_at)}</strong>
                </div>
              )}
              <button
                className="adaptive-inline-link"
                disabled={!toScenarioId(adaptiveConfig.baselineScenarioId)}
                onClick={() => handleViewAdaptiveScenario(toScenarioId(adaptiveConfig.baselineScenarioId))}
              >
                View selected scenario
              </button>
            </article>

            <div className={`adaptive-split state-${stageStates.segmentation}`} aria-label="Stage 2 automatic user segmentation">
              <div className="adaptive-split-label">
                <span>Stage 2</span>
                <strong>Automatic segmentation</strong>
                <small>{stageStateLabel[stageStates.segmentation]}</small>
              </div>
              <svg viewBox="0 0 120 680" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                  <marker id="adaptive-arrow-split" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M0,0 L8,4 L0,8 Z" />
                  </marker>
                </defs>
                <path d="M0 340 C48 340, 52 170, 116 170" />
                <path d="M0 340 C48 340, 52 300, 116 300" />
                <path d="M0 340 C48 340, 52 430, 116 430" />
                <path d="M0 340 C48 340, 52 560, 116 560" />
              </svg>
            </div>

            <div className="adaptive-stage-three">
              <div className="adaptive-stage-three-title">
                <span className="adaptive-stage-number">3</span>
                <div>
                  <span className="adaptive-stage-kicker">Stage 3</span>
                  <h3>Adaptive training paths</h3>
                </div>
                <span className={`adaptive-stage-state state-${stageStates.adaptive}`}>{stageStateLabel[stageStates.adaptive]}</span>
              </div>
              <label className="field adaptive-date-field adaptive-stage-three-date">
                Stage 2 segmentation and Stage 3 start
                <input
                  type="datetime-local"
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveSchedule.adaptive}
                  onChange={(event) => setAdaptiveSchedule((current) => ({ ...current, adaptive: event.target.value }))}
                />
                <small>{adaptiveSchedule.adaptive ? 'Segmentation and adaptive dispatch run automatically.' : 'Optional — leave empty to run manually.'}</small>
              </label>
              {activeAdaptiveProgram?.adaptive_executed_at && (
                <div className="adaptive-executed-date adaptive-stage-three-executed">
                  <span>Segmentation completed and training started</span>
                  <strong>{formatTimestamp(activeAdaptiveProgram.adaptive_executed_at)}</strong>
                </div>
              )}

              <div className="adaptive-lane-list">
                {adaptiveGroupDefinitions.map((definition) => {
                  const recipients = countRecipientsForActions(definition.actions)
                  return (
                    <article className={`adaptive-lane-card lane-${definition.key} state-${stageStates.adaptive}`} key={definition.key}>
                      <div className="adaptive-lane-heading">
                        <div>
                          <span>{definition.shortLabel}</span>
                          <h4>{definition.label}</h4>
                        </div>
                        <strong>{recipients} recipient{recipients === 1 ? '' : 's'}</strong>
                      </div>
                      <p>{definition.reason}</p>
                      <div className="adaptive-lane-fields">
                        <label className="field">
                          Difficulty
                          <select
                            disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                            value={adaptiveDifficulties[definition.key]}
                            onChange={(event) => handleAdaptiveDifficultyChange(definition.key, definition.configKey, event.target.value)}
                          >
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                          </select>
                        </label>
                        <label className="field">
                          Assigned scenario
                          <select
                            disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                            value={adaptiveConfig[definition.configKey]}
                            onChange={(event) => handleAdaptiveConfigChange(definition.configKey, event.target.value)}
                          >
                            <option value="">Select scenario</option>
                            {scenariosForDifficulty(adaptiveDifficulties[definition.key]).map((scenario) => (
                              <option key={`${definition.key}-${scenario.id}`} value={scenario.id}>{scenario.name}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {['targeted', 'easier'].includes(definition.key) && (
                        <span className="adaptive-training-note">Includes phishing signal micro-learning</span>
                      )}
                    </article>
                  )
                })}
              </div>
            </div>

            <div className={`adaptive-merge state-${stageStates.final}`} aria-hidden="true">
              <svg viewBox="0 0 120 680" preserveAspectRatio="none">
                <defs>
                  <marker id="adaptive-arrow-merge" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M0,0 L8,4 L0,8 Z" />
                  </marker>
                </defs>
                <path d="M0 170 C66 170, 70 340, 116 340" />
                <path d="M0 300 C66 300, 70 340, 116 340" />
                <path d="M0 430 C66 430, 70 340, 116 340" />
                <path d="M0 560 C66 560, 70 340, 116 340" />
              </svg>
            </div>

            <article className={`adaptive-stage-card adaptive-final-card state-${stageStates.final}`}>
              <div className="adaptive-stage-heading">
                <span className="adaptive-stage-number">4</span>
                <div>
                  <span className="adaptive-stage-kicker">Stage 4</span>
                  <h3>Final assessment</h3>
                </div>
                <span className={`adaptive-stage-state state-${stageStates.final}`}>{stageStateLabel[stageStates.final]}</span>
              </div>
              <p>All groups receive the same final scenario, followed by a before-and-after comparison.</p>
              <label className="field">
                Difficulty
                <select
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveDifficulties.final}
                  onChange={(event) => handleAdaptiveDifficultyChange('final', 'finalScenarioId', event.target.value)}
                >
                  <option value="">All levels</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
              <label className="field">
                Common final scenario
                <select
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveConfig.finalScenarioId}
                  onChange={(event) => handleAdaptiveConfigChange('finalScenarioId', event.target.value)}
                >
                  <option value="">Select scenario</option>
                  {scenariosForDifficulty(adaptiveDifficulties.final).map((scenario) => (
                    <option key={`final-${scenario.id}`} value={scenario.id}>{scenario.name}</option>
                  ))}
                </select>
              </label>
              <label className="field adaptive-date-field">
                Stage 4 date and time
                <input
                  type="datetime-local"
                  disabled={Boolean(adaptiveProgramId) || !adaptiveCampaignId}
                  value={adaptiveSchedule.final}
                  onChange={(event) => setAdaptiveSchedule((current) => ({ ...current, final: event.target.value }))}
                />
                <small>{adaptiveSchedule.final ? 'Runs automatically at this time.' : 'Optional — leave empty to run manually.'}</small>
              </label>
              {activeAdaptiveProgram?.final_executed_at && (
                <div className="adaptive-executed-date">
                  <span>Executed</span>
                  <strong>{formatTimestamp(activeAdaptiveProgram.final_executed_at)}</strong>
                </div>
              )}
              <div className="adaptive-final-summary">
                <span>Comparison</span>
                <strong>Baseline vs final click and report rates</strong>
              </div>
            </article>
          </div>

          <div className="adaptive-actions adaptive-workflow-actions">
            <button className="action-btn secondary-btn" disabled={adaptiveLoading} onClick={handleNewAdaptiveProgram}>
              New Program
            </button>
            <button
              className="action-btn secondary-btn"
              disabled={adaptiveLoading || Boolean(adaptiveProgramId) || !adaptiveConfigurationComplete || !adaptiveScenarioOptions.length}
              onClick={() => handleCreateAdaptiveProgram()}
              title={!adaptiveConfigurationComplete ? 'Complete the campaign and every required scenario selection first.' : undefined}
            >
              Save Without Starting
            </button>
            {activeAdaptiveProgram && !['created', 'completed'].includes(adaptiveProgramStatus) && (
              <button
                className="action-btn primary-btn"
                disabled={adaptiveLoading || waitingForScheduledStage}
                onClick={() => handleAdvanceAdaptiveProgram()}
              >
                {adaptiveLoading
                  ? 'Running...'
                  : waitingForScheduledStage
                    ? `Scheduled · ${formatTimestamp(nextScheduledAt)}`
                    : nextStageLabel}
              </button>
            )}
            <button
              className="action-btn secondary-btn"
              disabled={!activeAdaptiveProgram}
              onClick={() => document.getElementById('adaptive-program-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              View Program Results
            </button>
            <button className="action-btn secondary-btn" onClick={() => navigate('/templates')}>
              Open Templates
            </button>
          </div>

          <p className="muted adaptive-subtitle">
            Start Adaptive Program saves and launches the workflow in one step. Use Save Without Starting only when you want to preserve the setup as a draft.
          </p>

          {activeAdaptiveProgram && (
            <div className="adaptive-result-card" style={{ marginTop: '12px' }}>
              <h3>Automatic program status</h3>
              <p className="muted">Program #{activeAdaptiveProgram.id}: {activeAdaptiveProgram.name}</p>
              <p className="muted">Current status: {activeAdaptiveProgram.status}</p>
              <p className="muted">Adaptive rounds completed: {activeAdaptiveProgram.adaptive_round_index}/{activeAdaptiveProgram.adaptive_rounds}</p>
              <p className="muted">Last transition: {adaptiveProgramRunResult?.stage || 'Scheduled program loaded'}</p>
              <div className="adaptive-program-dates">
                <div><span>Stage 1</span><strong>{formatTimestamp(activeAdaptiveProgram.baseline_executed_at || activeAdaptiveProgram.baseline_scheduled_at)}</strong></div>
                <div><span>Stage 2/3</span><strong>{formatTimestamp(activeAdaptiveProgram.adaptive_executed_at || activeAdaptiveProgram.adaptive_scheduled_at)}</strong></div>
                <div><span>Stage 4</span><strong>{formatTimestamp(activeAdaptiveProgram.final_executed_at || activeAdaptiveProgram.final_scheduled_at)}</strong></div>
              </div>
            </div>
          )}

          {quickDemoResult && (
            <div className="adaptive-result-card" style={{ marginTop: '12px' }}>
              <h3>One-click demo summary</h3>
              <p className="muted">Program #{quickDemoResult.programId} status: {quickDemoResult.status}</p>
              <p className="muted">Baseline feedback preview: <a href={quickDemoResult.baselinePreviewUrl} target="_blank" rel="noreferrer">open</a></p>
              <div className="adaptive-dispatch-list">
                {(quickDemoResult.transitions || []).map((item, index) => (
                  <div key={`${item.stage}-${index}`}>
                    <span>{item.stage.replaceAll('_', ' ')}</span>
                    <strong>{item.status} · round {item.round}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          {adaptiveError && <p className="error-text">{adaptiveError}</p>}

          {(adaptiveBaselineResult || adaptiveDispatchResult || adaptiveFinalResult) && (
            <div className="adaptive-results" id="adaptive-program-results">
              {adaptiveBaselineResult?.summary && (
                <div className="adaptive-result-card">
                  <h3>Baseline summary</h3>
                  <div className="adaptive-kpis">
                    <div><span>Users</span><strong>{adaptiveBaselineResult.summary.users}</strong></div>
                    <div><span>Opened</span><strong>{adaptiveBaselineResult.summary.opened}</strong></div>
                    <div><span>Clicked</span><strong>{adaptiveBaselineResult.summary.clicked}</strong></div>
                    <div><span>Reported</span><strong>{adaptiveBaselineResult.summary.reported}</strong></div>
                  </div>
                </div>
              )}

              {adaptiveDispatchResult && (
                <div className="adaptive-result-card">
                  <h3>Dispatch summary</h3>
                  <p className="muted">Stage label: {adaptiveDispatchResult.stage_label}</p>
                  <p className="muted">Source scenario IDs: {(adaptiveDispatchResult.source_scenario_ids || []).join(', ') || '—'}</p>
                  <p className="muted">Training assignments created: {adaptiveDispatchResult.training_assignments_created || 0}</p>
                  <div className="adaptive-dispatch-list">
                    {(adaptiveDispatchResult.sent_campaigns || []).map((campaign, index) => (
                      <div key={`${campaign.scenario_id}-${index}`}>
                        <span>{campaign.recommended_action.replaceAll('_', ' ')}</span>
                        <strong>Scenario #{campaign.scenario_id} · {campaign.recipients} recipients</strong>
                      </div>
                    ))}
                  </div>
                  <p className="muted">Next source IDs: {[...new Set((adaptiveDispatchResult.sent_campaigns || []).map((campaign) => campaign.scenario_id))].join(', ') || '—'}</p>
                </div>
              )}

              {adaptiveUsers.length > 0 && (
                <div className="adaptive-result-card adaptive-groups-card">
                  <h3>Stage 2 — User segmentation</h3>
                  <p className="muted">Every recipient is routed from Stage 1 behavior to the next suitable scenario.</p>
                  <div className="table-wrap">
                    <table className="activity-table adaptive-groups-table">
                      <thead>
                        <tr>
                          <th>Group</th>
                          <th>Why</th>
                          <th>Users</th>
                          <th>Next scenario</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adaptiveGroupDefinitions.map((definition) => {
                          const groupUsers = adaptiveUsers.filter((item) => definition.actions.includes(item.recommended_action))
                          const dispatched = (adaptiveDispatchResult?.sent_campaigns || []).filter((item) => definition.actions.includes(item.recommended_action))
                          return (
                            <tr key={definition.key}>
                              <td><strong>{definition.label}</strong></td>
                              <td>{definition.reason}</td>
                              <td>
                                <strong>{groupUsers.length}</strong>
                                <div className="muted">{groupUsers.map((item) => item.user_email).join(', ') || 'No users'}</div>
                              </td>
                              <td>
                                {dispatched.length
                                  ? [...new Set(dispatched.map((item) => scenarioNameById(item.scenario_id)))].join(', ')
                                  : scenarioNameById(adaptiveConfig[definition.configKey])}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {adaptiveFinalResult?.delta && (
                <div className="adaptive-result-card">
                  <h3>Before-after comparison</h3>
                  <div className="adaptive-kpis">
                    <div><span>Baseline click rate</span><strong>{adaptiveFinalResult.baseline?.click_rate ?? 0}%</strong></div>
                    <div><span>Final click rate</span><strong>{adaptiveFinalResult.final?.click_rate ?? 0}%</strong></div>
                    <div><span>Click rate change</span><strong>{adaptiveFinalResult.delta?.click_rate_change ?? 0}%</strong></div>
                    <div><span>Report rate change</span><strong>{adaptiveFinalResult.delta?.report_rate_change ?? 0}%</strong></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="campaign-list" aria-labelledby="campaign-list-title">
        <div className="campaign-list-header">
          <div>
            <span className="campaign-control-eyebrow">Campaign inventory</span>
            <h2 id="campaign-list-title">Campaigns</h2>
            <p className="campaign-control-summary">
              {campaignGroups.length} campaign{campaignGroups.length === 1 ? '' : 's'} containing {totalScenarios} scenario{totalScenarios === 1 ? '' : 's'}. Lifecycle mix: {draftCount} draft{draftCount === 1 ? '' : 's'}, {scheduledCount} scheduled, {activeCount} active, {completedCount} completed.
            </p>
          </div>
          <div className="table-actions">
            <input
              className="table-input"
              placeholder="Search campaigns..."
              value={searchTerm}
              onChange={(event) => {
                setSearchTerm(event.target.value)
                setPage(0)
              }}
            />
          </div>
        </div>
        {campaigns.length === 0 ? (
          <div className="campaign-empty-state">
            <strong>No campaigns match this view</strong>
            <span>Create a draft, schedule a mock run, or choose another lifecycle filter.</span>
            <button
              className="action-btn primary-btn"
              title={!canManageScenarios ? 'Viewer access: campaign creation requires Admin or Analyst permissions' : undefined}
              onClick={openNewCampaign}
            >
              Create campaign
            </button>
          </div>
        ) : (
          <div className="campaign-card-list">
            {campaignGroups.map((campaign) => {
              const scenariosCollapsed = collapsedCampaignIds.includes(campaign.id)
              return (
                <article className="campaign-card campaign-group-card" key={campaign.id}>
                <div className="campaign-card-heading">
                  <div>
                    <span className="campaign-card-template">Campaign</span>
                    <h3>{campaign.name}</h3>
                    {campaign.description && <p className="muted">{campaign.description}</p>}
                    <span className="campaign-card-audience">{campaign.scenarios.length} scenario{campaign.scenarios.length === 1 ? '' : 's'} inside</span>
                  </div>
                  <div className="campaign-inventory-actions">
                    {canManageScenarios ? (
                      <label className="campaign-status-control">
                        <span>Status</span>
                        <select
                          value={campaign.status}
                          onChange={(event) => handleCampaignStatusChange(campaign, event.target.value)}
                        >
                          <option>Draft</option>
                          <option>Scheduled</option>
                          <option>Active</option>
                          <option>Completed</option>
                        </select>
                      </label>
                    ) : (
                      <span className={`badge ${campaign.status === 'Active' ? 'success' : campaign.status === 'Scheduled' ? 'warning' : campaign.status === 'Completed' ? 'danger' : 'neutral'}`}>
                        {campaign.status}
                      </span>
                    )}
                    {canManageScenarios && (
                      <button className="inventory-action-btn edit" onClick={() => openCampaignEditor(campaign)}>
                        <span aria-hidden="true">✎</span>
                        Edit details
                      </button>
                    )}
                    {canManageScenarios && (
                      <button
                        className="inventory-action-btn add"
                        onClick={() => {
                          setFormData({
                            ...templateFormValues(),
                            campaignId: campaign.id,
                            campaignName: campaign.name,
                            scenarioName: '',
                          })
                          setCreateStep(1)
                          setIsModalOpen(true)
                        }}
                      >
                        <span aria-hidden="true">＋</span>
                        Add scenario
                      </button>
                    )}
                    <button className="inventory-action-btn view" onClick={() => toggleCampaignScenarios(campaign.id)}>
                      <span aria-hidden="true">{scenariosCollapsed ? '▾' : '▴'}</span>
                      {scenariosCollapsed ? 'View scenarios' : 'Hide scenarios'}
                    </button>
                    {canDeleteCampaigns && (
                      <button
                        className="inventory-action-btn delete"
                        type="button"
                        onClick={() => requestCampaignDeletion(campaign)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                          <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />
                        </svg>
                        Delete campaign
                      </button>
                    )}
                  </div>
                </div>
                {!scenariosCollapsed && <div className="campaign-group-scenarios">
                  {campaign.scenarios.map((scenario) => (
                    <div className="campaign-group-scenario" key={scenario.id}>
                      <div className="campaign-group-scenario-heading">
                        <strong>{scenario.name}</strong>
                        {canManageScenarios ? (
                          <select
                            className="table-input"
                            value={scenario.status}
                            onChange={(event) => handleStatusChange(scenario, event.target.value)}
                          >
                            <option>Draft</option>
                            <option>Scheduled</option>
                            <option>Active</option>
                            <option>Completed</option>
                          </select>
                        ) : (
                          <span className={`badge ${scenario.status === 'Active' ? 'success' : scenario.status === 'Scheduled' ? 'warning' : scenario.status === 'Completed' ? 'danger' : 'neutral'}`}>
                            {scenario.status}
                          </span>
                        )}
                      </div>
                      <div className="campaign-card-details">
                        <div><span>Audience</span><strong>{scenario.audience}</strong></div>
                        <div><span>Schedule</span><strong>{scenario.scheduledFor || 'Not scheduled'}</strong></div>
                        <div><span>Last run</span><strong>{scenario.lastRun}</strong></div>
                        <div><span>Click rate</span><strong>{scenario.clickRate}</strong></div>
                      </div>
                      <div className="scenario-inventory-actions">
                        <button className="scenario-action-btn" onClick={() => openScenarioModal('view', scenario)}>View details</button>
                        {canManageScenarios && <button className="scenario-action-btn" onClick={() => openScenarioModal('edit', scenario)}>Edit</button>}
                        <button className="scenario-action-btn results" onClick={() => openScenarioModal('report', scenario)}>Results</button>
                        {canManageScenarios && <button className="scenario-action-btn send" onClick={() => handleSendMock(scenario)}>Send mock</button>}
                        {canManageScenarios && <button className="scenario-action-btn danger" onClick={() => requestScenarioDeletion(scenario)}>Delete</button>}
                      </div>
                    </div>
                  ))}
                </div>}
                </article>
              )
            })}
          </div>
        )}
        <div className="table-footer">
          <span className="pagination-info">
            Page {Math.min(page + 1, Math.max(1, Math.ceil(totalCount / pageSize)))} of{' '}
            {Math.max(1, Math.ceil(totalCount / pageSize))}
          </span>
          <div className="pagination-actions">
            <button
              className="action-btn secondary-btn"
              disabled={page === 0}
              onClick={() => setPage((prev) => Math.max(0, prev - 1))}
            >
              Previous
            </button>
            <button
              className="action-btn secondary-btn"
              disabled={!hasNextPage}
              onClick={() => setPage((prev) => prev + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {editingCampaign && (
        <div className="modal-backdrop" onClick={() => setEditingCampaign(null)}>
          <div className="modal campaign-details-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="campaign-control-eyebrow">Campaign inventory</span>
                <h3>Edit campaign details</h3>
              </div>
              <button className="icon-btn" onClick={() => setEditingCampaign(null)} aria-label="Close campaign editor">✕</button>
            </div>
            <div className="modal-body">
              <label className="field">
                Campaign name
                <input
                  type="text"
                  value={editingCampaign.name}
                  onChange={(event) => setEditingCampaign((current) => ({ ...current, name: event.target.value }))}
                />
              </label>
              <label className="field">
                Description
                <textarea
                  rows="4"
                  value={editingCampaign.description}
                  onChange={(event) => setEditingCampaign((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Describe the purpose and audience of this campaign."
                />
              </label>
              <label className="field">
                Campaign status
                <select
                  value={editingCampaign.status}
                  onChange={(event) => setEditingCampaign((current) => ({ ...current, status: event.target.value }))}
                >
                  <option>Draft</option>
                  <option>Scheduled</option>
                  <option>Active</option>
                  <option>Completed</option>
                </select>
              </label>
            </div>
            <div className="modal-footer">
              <button className="action-btn secondary-btn" onClick={() => setEditingCampaign(null)}>Cancel</button>
              <button
                className="action-btn primary-btn"
                disabled={!editingCampaign.name.trim()}
                onClick={handleUpdateCampaignDetails}
              >
                Save campaign
              </button>
            </div>
          </div>
        </div>
      )}

      {deletionTarget && (
        <div className="modal-backdrop" onClick={() => !isDeleting && setDeletionTarget(null)}>
          <div
            className="modal destructive-confirm-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-resource-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="destructive-confirm-header">
              <span className="destructive-confirm-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M12 3 21 20H3L12 3Z" />
                  <path d="M12 9v5m0 3h.01" />
                </svg>
              </span>
              <div>
                <span className="campaign-control-eyebrow">Permanent action</span>
                <h3 id="delete-resource-title">
                  Delete {deletionTarget.type === 'campaign' ? 'campaign' : 'scenario'}?
                </h3>
              </div>
            </div>
            <div className="modal-body destructive-confirm-body">
              <strong>{deletionTarget.resource.name}</strong>
              {deletionTarget.type === 'campaign' ? (
                <p>
                  The campaign and all {deletionTarget.resource.scenarios.length} scenario{deletionTarget.resource.scenarios.length === 1 ? '' : 's'} inside it will be removed permanently, together with recipient snapshots and dependent adaptive programs. Historical audit entries will be preserved.
                </p>
              ) : (
                <p>
                  The scenario and its recipient snapshots will be removed permanently. Historical audit entries will be preserved. Any saved adaptive program that depends on this scenario will also be removed to prevent an invalid workflow.
                </p>
              )}
            </div>
            <div className="modal-footer">
              <button
                className="action-btn secondary-btn"
                type="button"
                disabled={isDeleting}
                onClick={() => setDeletionTarget(null)}
              >
                Cancel
              </button>
              <button
                className="destructive-confirm-btn"
                type="button"
                disabled={isDeleting}
                onClick={confirmResourceDeletion}
              >
                {isDeleting ? 'Deleting…' : `Delete ${deletionTarget.type}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {isModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div className="modal campaign-wizard" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="campaign-control-eyebrow">{formData.campaignId ? 'Existing campaign' : 'New campaign'}</span>
                <h3>{formData.campaignId ? `Add scenario to ${formData.campaignName}` : 'Build simulation'}</h3>
              </div>
              <button className="icon-btn" onClick={() => setIsModalOpen(false)}>✕</button>
            </div>
            <div className="wizard-progress" aria-label={`Step ${createStep} of 3`}>
              <span className={createStep >= 1 ? 'current' : ''}>1 Details</span>
              <span className={createStep >= 2 ? 'current' : ''}>2 Audience</span>
              <span className={createStep >= 3 ? 'current' : ''}>3 Schedule</span>
            </div>
            <div className="modal-body">
              {createStep === 1 && (
                <>
                  {!formData.campaignId && (
                    <>
                      <label className="field">
                        Campaign name
                        <input
                          type="text"
                          placeholder="Quarterly Security Training"
                          value={formData.campaignName}
                          onChange={(event) => setFormData({ ...formData, campaignName: event.target.value })}
                        />
                      </label>
                      <label className="field">
                        Campaign description
                        <textarea
                          rows="3"
                          placeholder="Purpose and scope of this campaign"
                          value={formData.campaignDescription}
                          onChange={(event) => setFormData({ ...formData, campaignDescription: event.target.value })}
                        />
                      </label>
                    </>
                  )}
                  <label className="field">
                    Scenario name
                    <input
                      type="text"
                      placeholder="Payroll verification email"
                      value={formData.scenarioName}
                      onChange={(event) => setFormData({ ...formData, scenarioName: event.target.value })}
                    />
                  </label>
                  <label className="field">
                    Email template
                    <select
                      value={formData.emailTemplateKey}
                      onChange={(event) => applyTemplate(event.target.value)}
                      disabled={!templates.length}
                    >
                      {!templates.length && <option>Loading templates...</option>}
                      {templates.map((template) => (
                        <option key={template.key} value={template.key}>{template.name}</option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              {createStep === 2 && (
                <label className="field">
                  Target audience
                  <select value={formData.audience} onChange={(event) => setFormData({ ...formData, audience: event.target.value })}>
                    <option>All Staff</option>
                    <option>Engineering</option>
                    <option>Finance</option>
                    <option>HR</option>
                  </select>
                </label>
              )}
              {createStep === 3 && (
                <>
                  <label className="field">
                    Schedule date
                    <input type="date" value={formData.schedule} onChange={(event) => setFormData({ ...formData, schedule: event.target.value })} />
                  </label>
                  <div className="wizard-review">
                    <span>Campaign</span><strong>{formData.campaignName || 'Untitled campaign'}</strong>
                    <span>Scenario</span><strong>{formData.scenarioName || 'Untitled scenario'}</strong>
                    <span>Template</span><strong>{formData.template}</strong>
                    <span>Audience</span><strong>{formData.audience}</strong>
                    <span>Lifecycle</span><strong>{formData.schedule ? `Scheduled for ${formData.schedule}` : 'Draft'}</strong>
                  </div>
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="action-btn secondary-btn" onClick={() => setIsModalOpen(false)}>
                Cancel
              </button>
              {createStep > 1 && <button className="action-btn secondary-btn" onClick={() => setCreateStep((step) => step - 1)}>Back</button>}
              {createStep < 3 && (
                <button
                  className="action-btn primary-btn"
                  disabled={createStep === 1 && (!formData.scenarioName.trim() || (!formData.campaignId && !formData.campaignName.trim()))}
                  onClick={() => setCreateStep((step) => step + 1)}
                >
                  Continue
                </button>
              )}
              {createStep === 3 && (
              <button
                className="action-btn primary-btn"
                disabled={!canManageScenarios || !formData.emailTemplateKey}
                title={!canManageScenarios ? 'Admin or Analyst access required' : undefined}
                onClick={handleCreateCampaign}
              >
                {formData.campaignId ? 'Add scenario' : 'Create campaign'}
              </button>
              )}
            </div>
          </div>
        </div>
      )}

      {activeModal && activeScenario && (
        <div className="modal-backdrop" onClick={closeScenarioModal}>
          <aside className={`campaign-drawer ${activeModal === 'view' ? 'campaign-drawer-wide' : ''}`} onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {activeModal === 'view' && 'Scenario Details'}
                {activeModal === 'edit' && 'Edit Scenario'}
                {activeModal === 'report' && 'Scenario Report'}
              </h3>
              <button className="icon-btn" onClick={closeScenarioModal}>✕</button>
            </div>
            <div className="modal-body">
              {activeModal === 'view' && (
                <>
                  <div className="detail-grid campaign-detail-grid">
                    <div>
                      <span className="detail-label">Name</span>
                      <strong>{activeScenario.name}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Template</span>
                      <strong>{activeScenario.template}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Email subject</span>
                      <strong>{activeScenario.emailSubject || 'Uses the selected template default'}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Audience</span>
                      <strong>{activeScenario.audience}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Status</span>
                      <strong>{activeScenario.status}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Last run</span>
                      <strong>{activeScenario.lastRun}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Scheduled for</span>
                      <strong>{activeScenario.scheduledFor || 'Not scheduled'}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Click rate</span>
                      <strong>{activeScenario.clickRate}</strong>
                    </div>
                    <div>
                      <span className="detail-label">Report rate</span>
                      <strong>{activeScenario.reportRate}</strong>
                    </div>
                  </div>
                  <section className="scenario-email-preview" aria-label="Selected phishing email preview">
                    <div className="scenario-email-preview-header">
                      <span className="campaign-control-eyebrow">Selected scenario email</span>
                      <h4>{activeScenario.emailSubject || activeScenario.name}</h4>
                      <p className="muted">This is the simulated email recipients receive during the scenario.</p>
                    </div>
                    <div className="scenario-mail-client">
                      <div className="scenario-mail-toolbar">
                        <div className="scenario-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
                        <strong>Dark Signal Mail Preview</strong>
                        <span>Training safe</span>
                      </div>
                      <div className="scenario-mail-meta">
                        <div className="scenario-sender-avatar">{(activeScenario.senderName || 'DS').slice(0, 2).toUpperCase()}</div>
                        <div>
                          <strong>{activeScenario.senderName}</strong>
                          <span>&lt;{activeScenario.senderEmail}&gt;</span>
                          <small>to Campaign recipients</small>
                        </div>
                        <time>Simulation preview</time>
                      </div>
                      <div className="scenario-mail-subject">
                        <span>Subject</span>
                        <strong>{activeScenario.emailSubject || activeScenario.name}</strong>
                      </div>
                      <iframe
                        title={`Email preview for ${activeScenario.name}`}
                        sandbox=""
                        srcDoc={scenarioPreviewHtml(activeScenario)}
                      />
                      <div className="scenario-mail-footer">
                        <span>◆</span>
                        No real credentials, external links, or account actions are used in this simulation.
                      </div>
                    </div>
                  </section>
                  <section className="feedback-preview-card" aria-label="Learner feedback preview">
                    <div>
                      <span className="campaign-control-eyebrow">Learning Experience</span>
                      <h4>Preview learner feedback page</h4>
                      <p className="muted">Open the exact page users see after clicking a simulated phishing link.</p>
                    </div>
                    <button className="action-btn primary-btn" onClick={() => openFeedbackPreview(activeScenario.id)}>
                      Preview learner feedback
                    </button>
                  </section>
                </>
              )}
              {activeModal === 'edit' && (
                <>
                  <label className="field">
                    Scenario name
                    <input
                      value={formData.scenarioName}
                      onChange={(event) => setFormData({ ...formData, scenarioName: event.target.value })}
                    />
                  </label>
                  <label className="field">
                    Email template
                    <select
                      value={formData.emailTemplateKey}
                      onChange={(event) => applyTemplate(event.target.value)}
                    >
                      {templates.map((template) => (
                        <option key={template.key} value={template.key}>{template.name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    Audience
                    <select
                      value={formData.audience}
                      onChange={(event) => setFormData({ ...formData, audience: event.target.value })}
                    >
                      <option>All Staff</option>
                      <option>Engineering</option>
                      <option>Finance</option>
                      <option>HR</option>
                    </select>
                  </label>
                  <section className="campaign-email-editor" aria-labelledby="campaign-email-editor-title">
                    <div>
                      <span className="campaign-control-eyebrow">Campaign email</span>
                      <h4 id="campaign-email-editor-title">Customize this campaign only</h4>
                      <p className="muted">Changing these fields does not alter the library template or any other campaign.</p>
                    </div>
                    <label className="field">
                      Subject
                      <input
                        value={formData.emailSubject}
                        onChange={(event) => setFormData({ ...formData, emailSubject: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      Plain text
                      <textarea
                        rows="6"
                        value={formData.emailBodyText}
                        onChange={(event) => setFormData({ ...formData, emailBodyText: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      HTML
                      <textarea
                        rows="8"
                        value={formData.emailBodyHtml}
                        onChange={(event) => setFormData({ ...formData, emailBodyHtml: event.target.value })}
                      />
                    </label>
                    <p className="muted">Placeholders: {'{{app_name}}'}, {'{{scenario_title}}'}, {'{{audience}}'}</p>
                  </section>
                </>
              )}
              {activeModal === 'report' && (
                <>
                  {isResultsLoading && <p className="muted">Loading results...</p>}
                  {resultsError && <p className="error-text">{resultsError}</p>}
                  {campaignResults && (
                    <>
                      <div className="campaign-results-summary">
                        <div><span>Deliveries</span><strong>{campaignResults.deliveries}</strong></div>
                        <div><span>Recipients</span><strong>{campaignResults.unique_recipients}</strong></div>
                        <div><span>Opened</span><strong>{campaignResults.opens}</strong><small>{campaignResults.open_rate}% rate</small></div>
                        <div><span>Clicked</span><strong>{campaignResults.clicks}</strong><small>{campaignResults.click_rate}% rate</small></div>
                        <div><span>Reported</span><strong>{campaignResults.reports}</strong><small>{campaignResults.report_rate}% rate</small></div>
                      </div>
                      <section className="campaign-response-list">
                        <h4>Simulation activity</h4>
                        {campaignResults.recent_responses.length ? (
                          <ul>
                            {campaignResults.recent_responses.map((response) => (
                              <li key={response.id}>
                                <div>
                                  <strong>{response.user_email || 'Unknown user'}</strong>
                                  <span>{response.action.replaceAll('.', ' ')}</span>
                                </div>
                                <time>{formatTimestamp(response.created_at)}</time>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted">No simulation events have been recorded for this campaign.</p>
                        )}
                      </section>
                      <section className="campaign-response-list recipient-snapshot-list">
                        <h4>Recipient snapshot</h4>
                        {campaignResults.latest_run_recipients.length ? (
                          <ul>
                            {campaignResults.latest_run_recipients.map((recipient) => (
                              <li key={recipient.id}>
                                <div className="recipient-snapshot-content">
                                  <strong>{recipient.full_name || recipient.email}</strong>
                                  <span>{recipient.email} · {recipient.department || 'No department'}</span>
                                  <div className="recipient-actions">
                                    <button className="link-btn" onClick={() => handleRecipientSimulationAction(recipient, 'open')}>Open</button>
                                    <button className="link-btn" onClick={() => handleRecipientSimulationAction(recipient, 'click')}>Click</button>
                                    <button className="link-btn" onClick={() => handleRecipientSimulationAction(recipient, 'report')}>Report</button>
                                  </div>
                                </div>
                                <time>{formatTimestamp(recipient.executed_at)}</time>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted">Recipient snapshots are available for mock runs created after this update.</p>
                        )}
                      </section>
                    </>
                  )}
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="action-btn secondary-btn" onClick={closeScenarioModal}>
                Close
              </button>
              {activeModal === 'edit' && (
                <button
                  className="action-btn primary-btn"
                  disabled={!canManageScenarios}
                  title={!canManageScenarios ? 'Admin or Analyst access required' : undefined}
                  onClick={handleUpdateScenario}
                >
                  Save
                </button>
              )}
              {activeModal === 'report' && (
                <button className="action-btn primary-btn" onClick={() => handleDownloadReport(activeScenario)}>
                  Download
                </button>
              )}
            </div>
          </aside>
        </div>
      )}

      {toastMessage && <div className="toast">{toastMessage}</div>}
    </div>
  )
}

export default Scenarios
