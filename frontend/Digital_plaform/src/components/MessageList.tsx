import { Bot, Check, Copy, Paperclip, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { UIMessage } from 'ai'
import { useState } from 'react'
import type { ContextAnalysis, ContextAnalysisMetadata } from '../services/aiService'

type MessageListProps = {
  messages: UIMessage[]
  copiedMessageId: string | null
  onCopy: (id: string, text: string) => void
  isStreaming: boolean
}

function isContextAnalysis(metadata: unknown): metadata is ContextAnalysisMetadata {
  return typeof metadata === 'object' && metadata !== null && 'type' in metadata && metadata.type === 'context-analysis'
}

function analysisToText(analysis: ContextAnalysis) {
  return [
    `Problem statement\n${analysis.problem_statement}`,
    `Business goal\n${analysis.business_goal}`,
    `Evidence\n${analysis.evidence.join('\n')}`,
    `Users\n${analysis.users.join('\n')}`,
    `Assumptions\n${analysis.assumptions.join('\n')}`,
    `Constraints\n${analysis.constraints.join('\n')}`,
  ].join('\n\n')
}

function AnalysisSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="analysis-empty">No items identified</p>
      )}
    </section>
  )
}

function ContextAnalysisResult({ analysis }: { analysis: ContextAnalysis }) {
  return (
    <div className="context-analysis">
      <div className="analysis-heading">
        <span>Context analysis</span>
        <span className="analysis-status">Complete</span>
      </div>
      <AnalysisSection title="Problem statement" items={[analysis.problem_statement]} />
      <AnalysisSection title="Business goal" items={[analysis.business_goal]} />
      <AnalysisSection title="Evidence" items={analysis.evidence} />
      <AnalysisSection title="Users" items={analysis.users} />
      <AnalysisSection title="Assumptions" items={analysis.assumptions} />
      <AnalysisSection title="Constraints" items={analysis.constraints} />
    </div>
  )
}

export function MessageList({ messages, copiedMessageId, onCopy, isStreaming }: MessageListProps) {
  const [openAttachment, setOpenAttachment] = useState<{ messageId: string; filename: string } | null>(null)

  return (
    <div className="messages">
      {messages.length === 0
        ? null
        : messages.map((message) => {
            const text = message.parts
              .filter((part) => part.type === 'text')
              .map((part) => part.text)
              .join('')
            const analysis = isContextAnalysis(message.metadata) ? message.metadata : null
            const files = message.parts.flatMap((part) => (part.type === 'file' && part.filename ? [part] : []))

            return (
              <div className={`message-row ${message.role === 'user' ? 'user-row' : ''}`} key={message.id}>
                {message.role !== 'user' && (
                  <div className="message-avatar">
                    <Bot size={19} />
                  </div>
                )}
                <div className="message-content">
                  <div className="message-bubble">
                    {files.length > 0 && (
                      <div className="message-files">
                        {files.map((file, index) => {
                          const filename = file.filename ?? 'Attached file'
                          const isOpen =
                            openAttachment?.messageId === message.id && openAttachment.filename === filename
                          return (
                            <div key={`${filename}-${index}`}>
                              <button
                                className="message-file"
                                type="button"
                                title={`${isOpen ? 'Close' : 'Open'} ${filename}`}
                                onClick={() =>
                                  setOpenAttachment(isOpen ? null : { messageId: message.id, filename })
                                }
                              >
                                <Paperclip size={14} />
                                <span>{filename}</span>
                              </button>
                              {isOpen &&
                                (file.mediaType.startsWith('image/') ? (
                                  <img className="inline-attachment" src={file.url} alt={filename} />
                                ) : (
                                  <iframe className="inline-attachment" src={file.url} title={filename} />
                                ))}
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {analysis ? <ContextAnalysisResult analysis={analysis} /> : text}
                  </div>
                  {message.role === 'assistant' && text && (
                    <div className="message-actions">
                      <button
                        title="Copy"
                        type="button"
                        onClick={() => onCopy(message.id, analysis ? analysisToText(analysis) : text)}
                      >
                        {copiedMessageId === message.id ? <Check size={16} /> : <Copy size={16} />}
                      </button>
                      <button title="Helpful" type="button">
                        <ThumbsUp size={16} />
                      </button>
                      <button title="Not helpful" type="button">
                        <ThumbsDown size={16} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
      {isStreaming && (
        <div className="typing">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  )
}