import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api'
import type { LandingDetail } from '../types'
import type { LandingOperation } from './LandingOperationOverlay'
import type { ImageReference } from '../components/ImageReferenceInput'

export function useLandingOperation(api: ApiClient, pagePath: string, onDetail: (detail: LandingDetail) => void, onResult: (result: Record<string, unknown>) => void) {
  const [operation, setOperation] = useState<LandingOperation | null>(null)
  const [phase, setPhase] = useState('')
  const [error, setError] = useState('')
  const [visible, setVisible] = useState(false)
  const epoch = useRef(0)
  const latestDetail = useRef(onDetail); latestDetail.current = onDetail
  const latestResult = useRef(onResult); latestResult.current = onResult
  const requestRef = useRef<{ kind: string; request: Record<string, unknown> } | null>(null)
  const delay = () => new Promise(resolve => window.setTimeout(resolve, 1200))
  const key = `ptw:landing-operation:${pagePath}`
  const remember = (value: string) => { try { sessionStorage.setItem(key, value) } catch { /* Server state remains authoritative. */ } }
  const forget = () => { try { sessionStorage.removeItem(key) } catch { /* Optional browser state. */ } }

  const observe = async (initial: LandingOperation, currentEpoch: number): Promise<Record<string, unknown>> => {
    let value = initial
    let previousCompleted = -1
    while (currentEpoch === epoch.current) {
      if (!value?.operation_id || !Array.isArray(value.jobs)) throw new Error('The server returned an incomplete operation status. Retry will check the original request.')
      setOperation(value); setPhase(''); setVisible(true)
      const completed = value.jobs.filter(job => job.status === 'completed').length
      if (completed !== previousCompleted && completed > 0) {
        const detail = await api.get<LandingDetail>(pagePath)
        if (currentEpoch !== epoch.current) break
        latestDetail.current(detail); previousCompleted = completed
      }
      if (value.status === 'completed') {
        if (value.result?.configuration && value.result.content) latestResult.current(value.result)
        setPhase('preview')
        return { ...value.result, operation_id: value.operation_id }
      }
      if (['failed', 'interrupted'].includes(value.status)) {
        if (value.jobs.length) {
          const detail = await api.get<LandingDetail>(pagePath)
          if (currentEpoch === epoch.current) latestDetail.current(detail)
        }
        throw new Error('Landing operation needs attention')
      }
      await delay()
      if (currentEpoch !== epoch.current) break
      value = await api.get<LandingOperation>(`${pagePath}/operations/${value.operation_id}`)
    }
    throw new Error('Landing page changed')
  }

  useEffect(() => {
    const currentEpoch = ++epoch.current
    setOperation(null); setVisible(false); setError(''); setPhase(''); requestRef.current = null
    if (!pagePath) return
    void api.get<{ operation: LandingOperation | null }>(`${pagePath}/operations`).then(async ({ operation: value }) => {
      if (currentEpoch !== epoch.current || !value) return
      let pending = ''
      try { pending = sessionStorage.getItem(key) || '' } catch { /* Optional browser state. */ }
      if (!['queued', 'running'].includes(value.status) && pending !== value.request_id) return
      try {
        const result = await observe(value, currentEpoch)
        // Field-only Agent results remain unsaved and must survive refresh recovery.
        if (!value.jobs.length && result.configuration && result.content) {
          const detail = await api.get<LandingDetail>(pagePath)
          if (currentEpoch === epoch.current) { latestDetail.current(detail); latestResult.current(result) }
        }
      } catch (cause) {
        if (currentEpoch === epoch.current && !(cause instanceof Error && cause.message === 'Landing operation needs attention')) setError(cause instanceof Error ? cause.message : String(cause))
      }
    }).catch(() => { /* A normal Landing read remains usable; a submitted request reports failures explicitly. */ })
    return () => { epoch.current++ }
  }, [api, pagePath]) // eslint-disable-line react-hooks/exhaustive-deps

  const begin = () => { setVisible(true); setError(''); setOperation(null); setPhase('preparing') }
  const run = async (kind: string, request: Record<string, unknown>) => {
    const currentEpoch = ++epoch.current
    begin(); requestRef.current = { kind, request }; remember(String(request.request_id))
    try {
      const value = await api.post<LandingOperation>(`${pagePath}/operations`, { kind, request }, { deadlineMs: 60_000 })
      if (currentEpoch !== epoch.current) throw new Error('Landing page changed')
      return await observe(value, currentEpoch)
    } catch (cause) {
      if (currentEpoch === epoch.current && !(cause instanceof Error && cause.message === 'Landing operation needs attention')) setError(cause instanceof Error ? cause.message : String(cause))
      throw cause
    }
  }
  const retry = async (reattached?: ImageReference[]) => {
    const currentEpoch = ++epoch.current
    setError(''); setPhase('checking')
    try {
      let value = operation ? await api.get<LandingOperation>(`${pagePath}/operations/${operation.operation_id}`) : null
      if (!value) {
        const latest = await api.get<{ operation: LandingOperation | null }>(`${pagePath}/operations`)
        if (latest.operation?.request_id === requestRef.current?.request.request_id) value = latest.operation
        else if (requestRef.current) value = await api.post<LandingOperation>(`${pagePath}/operations`, requestRef.current, { deadlineMs: 60_000 })
        else throw new Error('Return to the editor and select your saved request.')
      }
      if (value && ['failed', 'interrupted'].includes(value.status)) {
        const request = requestRef.current?.request
        const screenshots = reattached || request?.screenshots || (request?.reference_image ? [request.reference_image] : [])
        value = await api.post<LandingOperation>(`${pagePath}/operations/${value.operation_id}/retry`, { screenshots }, { deadlineMs: 60_000 })
      }
      if (value) {
        const result = await observe(value, currentEpoch)
        if (!value.jobs.length && result.configuration && result.content) {
          const detail = await api.get<LandingDetail>(pagePath)
          if (currentEpoch === epoch.current) { latestDetail.current(detail); latestResult.current(result) }
        }
      }
    } catch (cause) { if (currentEpoch === epoch.current && !(cause instanceof Error && cause.message === 'Landing operation needs attention')) setError(cause instanceof Error ? cause.message : String(cause)) }
  }
  const dismiss = () => { epoch.current++; setVisible(false); setError(''); forget(); requestRef.current = null }
  return { operation, phase, error, visible, run, begin, retry, dismiss,
    preview: () => { setVisible(true); setPhase('preview'); setOperation(null) },
    fail: (message: string) => { setError(message); setVisible(true) },
    ready: () => { forget(); setVisible(false); requestRef.current = null },
  }
}
