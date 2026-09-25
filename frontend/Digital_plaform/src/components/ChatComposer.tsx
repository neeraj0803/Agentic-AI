import { ArrowUp, CircleStop, Paperclip, X } from 'lucide-react'
import { PAGE_CONTENT } from '../constants/page'

type ChatComposerProps = {
  input: string
  files: File[]
  fileLabels: string[]
  isStreaming: boolean
  onChange: (value: string) => void
  onFilesChange: (files: File[]) => void
  onFileLabelsChange: (labels: string[]) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onStop: () => void
}

export function ChatComposer({
  input,
  files,
  fileLabels,
  isStreaming,
  onChange,
  onFilesChange,
  onFileLabelsChange,
  onSubmit,
  onStop,
}: ChatComposerProps) {
  const hasContent = input.trim().length > 0 || files.length > 0 || fileLabels.length > 0

  return (
    <form className="composer-wrap" onSubmit={onSubmit}>
      <div className="composer">
        {(files.length > 0 || fileLabels.length > 0) && (
          <div className="file-list" aria-label="Selected files">
            {files.map((file, index) => (
              <div className="file-chip" key={`${file.name}-${file.lastModified}`}>
                <span title={file.name}>{file.name}</span>
                <button
                  type="button"
                  title={`Remove ${file.name}`}
                  aria-label={`Remove ${file.name}`}
                  onClick={() => onFilesChange(files.filter((_, fileIndex) => fileIndex !== index))}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            {fileLabels.map((label, index) => (
              <div className="file-chip" key={`label-${label}`}>
                <span title={label}>{label}</span>
                <button
                  type="button"
                  title={`Remove ${label}`}
                  aria-label={`Remove ${label}`}
                  onClick={() => onFileLabelsChange(fileLabels.filter((_, labelIndex) => labelIndex !== index))}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="composer-controls">
          <label className="icon-button" title="Attach files">
            <Paperclip size={20} />
            <input
              className="file-input"
              type="file"
              multiple
              onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            />
          </label>
          <input
            value={input}
            onChange={(event) => onChange(event.target.value)}
            placeholder={PAGE_CONTENT.composerPlaceholder}
            aria-label={PAGE_CONTENT.composerPlaceholder}
          />
          <button
            className="send-button"
            title={isStreaming ? 'Stop generating' : 'Send message'}
            type={isStreaming ? 'button' : 'submit'}
            onClick={isStreaming ? onStop : undefined}
            disabled={!isStreaming && !hasContent}
            style={{ opacity: !isStreaming && !hasContent ? 0.45 : 1 }}
          >
            {isStreaming ? <CircleStop size={20} /> : <ArrowUp size={20} />}
          </button>
        </div>
      </div>
      <p className="disclaimer">{PAGE_CONTENT.disclaimer}</p>
    </form>
  )
}