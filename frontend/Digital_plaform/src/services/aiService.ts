import { DefaultChatTransport } from 'ai'

export const AI_CHAT_ENDPOINT = '/api/chat'
export const CONTEXT_ANALYZE_ENDPOINT = 'http://127.0.0.1:8000/context/analyze'

export type ContextAnalysis = {
	problem_statement: string
	business_goal: string
	evidence: string[]
	users: string[]
	assumptions: string[]
	constraints: string[]
}

export type ContextAnalysisMetadata = ContextAnalysis & { type: 'context-analysis' }

export async function analyzeAttachedFile(file: File): Promise<ContextAnalysis> {
	const formData = new FormData()
	formData.append('file', file)

	const response = await fetch(CONTEXT_ANALYZE_ENDPOINT, {
		method: 'POST',
		body: formData,
	})

	if (!response.ok) {
		let message = `Context analysis failed (${response.status})`
		try {
			const error = await response.json() as { detail?: string; error?: string }
			message = error.detail ?? error.error ?? message
		} catch {
			// Keep the status-based message when the backend does not return JSON.
		}
		throw new Error(message)
	}

	return response.json() as Promise<ContextAnalysis>
}

export const aiChatTransport = new DefaultChatTransport({
	api: AI_CHAT_ENDPOINT,
})

export async function analyzeFile(file: File): Promise<ContextAnalysis> {
	const formData = new FormData()
	formData.append('file', file, file.name)

	const response = await fetch(CONTEXT_ANALYZE_ENDPOINT, {
		method: 'POST',
		body: formData,
	})

	if (!response.ok) {
		const errorBody = await response.json().catch(() => null) as { detail?: string; error?: string } | null
		throw new Error(errorBody?.detail ?? errorBody?.error ?? `Context analysis failed (${response.status})`)
	}

	return response.json() as Promise<ContextAnalysis>
}