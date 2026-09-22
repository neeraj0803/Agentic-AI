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

export function ChatComposer({ input, files, fileLabels, isStreaming, onChange, onFilesChange, onFileLabelsChange, onSubmit, onStop }: ChatComposerProps) {
  return <form className="composer-wrap" onSubmit={onSubmit}>
    <div className="composer">{(files.length > 0 || fileLabels.length > 0) && <div className="file-list" aria-label="Selected files">{files.map((file, index) => <div className="file-chip" key={`${file.name}-${file.lastModified}`}><span title={file.name}>{file.name}</span><button type="button" title={`Remove ${file.name}`} aria-label={`Remove ${file.name}`} onClick={() => onFilesChange(files.filter((_, fileIndex) => fileIndex !== index))}><X size={13} /></button></div>)}{fileLabels.map((label, index) => <div className="file-chip" key={`label-${label}`}><span title={label}>{label}</span><button type="button" title={`Remove ${label}`} aria-label={`Remove ${label}`} onClick={() => onFileLabelsChange(fileLabels.filter((_, labelIndex) => labelIndex !== index))}><X size={13} /></button></div>)}</div>}<div className="composer-controls"><label className="icon-button" title="Attach files"><Paperclip size={18} /><input className="file-input" type="file" multiple onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))} /></label><input value={input} onChange={(event) => onChange(event.target.value)} placeholder={PAGE_CONTENT.composerPlaceholder} aria-label={PAGE_CONTENT.composerPlaceholder} /><button className="send-button" title={isStreaming ? 'Stop generating' : 'Send message'} type={isStreaming ? 'button' : 'submit'} onClick={isStreaming ? onStop : undefined}>{isStreaming ? <CircleStop size={18} /> : <ArrowUp size={18} />}</button></div></div><p className="disclaimer">{PAGE_CONTENT.disclaimer}</p>
  </form>
}