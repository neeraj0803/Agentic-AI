import { useChat } from '@ai-sdk/react'
import type { UIMessage } from 'ai'
import { useEffect, useRef, useState } from 'react'
import { ChatComposer } from './components/ChatComposer'
import { ChatHeader } from './components/ChatHeader'
import { ChatSidebar } from './components/ChatSidebar'
import { MessageList } from './components/MessageList'
import { WelcomeState } from './components/WelcomeState'
<<<<<<< HEAD
import { aiChatTransport, analyzeAttachedFile } from './services/aiService'
=======
import { aiChatTransport, analyzeFile, type ContextAnalysis } from './services/aiService'
>>>>>>> cdda542c48152bb39b0d0bbb988db7f874428d38
import { RECENT_CHATS } from './constants/page'
import './App.css'

const SESSION_STORAGE_KEY = 'catlac-oneid-chat-sessions'
type ChatSession = { id: string; title: string; messages: UIMessage[] }

const loadSessions = (): ChatSession[] => {
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY)
    return stored ? JSON.parse(stored) as ChatSession[] : []
  } catch {
    return []
  }
}

const formatContextAnalysis = (fileName: string, analysis: ContextAnalysis) => {
  const formatList = (label: string, values: string[]) => `${label}:\n${values.map((value) => `- ${value}`).join('\n')}`
  return [
    `Context analysis for ${fileName}`,
    `Problem statement: ${analysis.problem_statement}`,
    `Business goal: ${analysis.business_goal}`,
    formatList('Evidence', analysis.evidence),
    formatList('Users', analysis.users),
    formatList('Assumptions', analysis.assumptions),
    formatList('Constraints', analysis.constraints),
  ].join('\n\n')
}

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const savedSessions = loadSessions()
    return savedSessions.length > 0 ? savedSessions : [{ id: crypto.randomUUID(), title: 'New chat', messages: [] }]
  })
  const initialSession = useRef<ChatSession | null>(null)
  if (!initialSession.current) initialSession.current = sessions[0]
  const [activeSessionId, setActiveSessionId] = useState(initialSession.current.id)
  const [input, setInput] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [fileLabels, setFileLabels] = useState<string[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [recentPromptOverride, setRecentPromptOverride] = useState<string[] | null>(null)
  const [recentPromptSessionId, setRecentPromptSessionId] = useState<string | null>(null)
  const { messages, sendMessage, status, stop, error, setMessages } = useChat({ transport: aiChatTransport, messages: initialSession.current.messages })
  const isStreaming = status === 'streaming' || status === 'submitted' || isAnalyzing
  const activePromptHistory = messages
    .filter((message) => message.role === 'user')
    .map((message) => message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('').trim())
    .filter((prompt) => prompt.length > 0)
    .reverse()
    .slice(0, 5)
  const visibleRecentPrompts = activePromptHistory.length > 0 ? activePromptHistory : recentPromptOverride ?? RECENT_CHATS.slice(0, 5)
  const recentChats = visibleRecentPrompts
  const activeSession = sessions.find((session) => session.id === activeSessionId)
  const visibleRecentSessionId = activePromptHistory.length > 0 ? activeSessionId : recentPromptSessionId ?? activeSession?.id
  const recentSessionIds = visibleRecentSessionId ? visibleRecentPrompts.map(() => visibleRecentSessionId) : []

  useEffect(() => {
    setSessions((currentSessions) => {
      const activeSession = currentSessions.find((session) => session.id === activeSessionId)
      if (!activeSession || JSON.stringify(activeSession.messages) === JSON.stringify(messages)) return currentSessions
      const latestPrompt = messages
        .filter((message) => message.role === 'user')
        .map((message) => message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('').trim())
        .filter((prompt) => prompt.length > 0)
        .pop()
      const nextSessions = [{ ...activeSession, title: latestPrompt || 'New chat', messages }, ...currentSessions.filter((session) => session.id !== activeSessionId)].slice(0, 5)
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSessions))
      return nextSessions
    })
  }, [activeSessionId, messages])

  const handleNewChat = () => {
    stop()
    const previousSessionId = activeSessionId
    setRecentPromptOverride(activePromptHistory)
    setRecentPromptSessionId(previousSessionId)
    const newSession = { id: crypto.randomUUID(), title: 'New chat', messages: [] }
    setSessions((currentSessions) => {
      const currentMessages = messages
      const currentPrompt = currentMessages
        .filter((message) => message.role === 'user')
        .map((message) => message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('').trim())
        .filter((prompt) => prompt.length > 0)
        .pop()
      const preservedSessions = currentSessions.map((session) => session.id === activeSessionId
        ? { ...session, title: currentPrompt || session.title, messages: currentMessages }
        : session)
      const nextSessions = [newSession, ...preservedSessions].slice(0, 5)
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSessions))
      return nextSessions
    })
    setActiveSessionId(newSession.id)
    setMessages([])
    setInput('')
    setFiles([])
    setFileLabels([])
  }

  const handleSelectChat = (sessionId: string) => {
    const session = sessions.find((candidate) => candidate.id === sessionId)
    if (!session) return
    stop()
    setActiveSessionId(session.id)
    setMessages(session.messages)
    setInput('')
    setFiles([])
    setFileLabels([])
    setRecentPromptOverride(null)
    setRecentPromptSessionId(null)
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = input.trim()
    if ((!text && files.length === 0 && fileLabels.length === 0) || isStreaming) return
    const attachedFiles = [...files]
    const fileTransfer = files.length > 0 ? new DataTransfer() : undefined
    files.forEach((file) => fileTransfer?.items.add(file))
    setInput('')
    setFiles([])
    setFileLabels([])
    setRecentPromptOverride(null)
    setRecentPromptSessionId(null)

<<<<<<< HEAD
    if (files.length > 0) {
      setIsAnalyzing(true)
      let nextMessages = [...messages]

      try {
        for (const [index, file] of files.entries()) {
          const userMessage: UIMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            parts: [
              ...(index === 0 && text ? [{ type: 'text' as const, text }] : []),
              { type: 'file', filename: file.name, mediaType: file.type || 'application/octet-stream', url: URL.createObjectURL(file) },
            ],
          }
          nextMessages = [...nextMessages, userMessage]
          setMessages(nextMessages)

          const analysis = await analyzeAttachedFile(file)
          const assistantMessage: UIMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            metadata: { type: 'context-analysis', ...analysis },
            parts: [{ type: 'text', text: analysis.problem_statement || 'Context analysis completed.' }],
          }
          nextMessages = [...nextMessages, assistantMessage]
          setMessages(nextMessages)
        }
      } catch (analysisError) {
        const message = analysisError instanceof Error ? analysisError.message : 'Unable to analyze the attached file.'
        nextMessages = [...nextMessages, {
          id: crypto.randomUUID(),
          role: 'assistant',
          parts: [{ type: 'text', text: message }],
        }]
        setMessages(nextMessages)
      } finally {
        setIsAnalyzing(false)
      }
=======
    if (attachedFiles.length > 0) {
      const promptText = [
        text,
        ...attachedFiles.map((file) => `Attached file: ${file.name}`),
      ].filter(Boolean).join('\n')
      setMessages((currentMessages) => [...currentMessages, {
        id: crypto.randomUUID(),
        role: 'user',
        parts: [{ type: 'text', text: promptText }],
      }])

      const analyses = await Promise.all(attachedFiles.map(async (file) => ({
        fileName: file.name,
        analysis: await analyzeFile(file),
      })))
      const analysisText = analyses.map(({ fileName, analysis }) => formatContextAnalysis(fileName, analysis)).join('\n\n---\n\n')
      setMessages((currentMessages) => [...currentMessages, {
        id: crypto.randomUUID(),
        role: 'assistant',
        parts: [{ type: 'text', text: analysisText }],
      }])
>>>>>>> cdda542c48152bb39b0d0bbb988db7f874428d38
      return
    }

    await sendMessage({ text, files: fileTransfer?.files })
  }

  const copyMessage = async (id: string, text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(id)
    window.setTimeout(() => setCopied(null), 1600)
  }

  return (
    <main className="app-shell">
      <ChatSidebar recentChats={recentChats} recentSessionIds={recentSessionIds} onNewChat={handleNewChat} onSelectChat={handleSelectChat} />

      <section className="chat-panel">
        <ChatHeader />
        {messages.length === 0 && <WelcomeState onSuggestion={setInput} />}
        <MessageList messages={messages} copiedMessageId={copied} onCopy={copyMessage} isStreaming={isStreaming} />
        {error && <p className="chat-error" role="alert">{error.message}</p>}
        <ChatComposer input={input} files={files} fileLabels={fileLabels} isStreaming={isStreaming} onChange={setInput} onFilesChange={setFiles} onFileLabelsChange={setFileLabels} onSubmit={handleSubmit} onStop={stop} />
      </section>
    </main>
  )
}

export default App
