import { ArrowUp } from 'lucide-react'
import { CHAT_SUGGESTIONS, PAGE_CONTENT } from '../constants/page'

type WelcomeStateProps = {
  onSuggestion: (suggestion: string) => void
}

export function WelcomeState({ onSuggestion }: WelcomeStateProps) {
  return <div className="welcome"><h2>{PAGE_CONTENT.welcomeTitle}</h2><p className="welcome-copy">{PAGE_CONTENT.welcomeCopy}</p><div className="suggestions">{CHAT_SUGGESTIONS.map((suggestion) => <button type="button" key={suggestion} onClick={() => onSuggestion(suggestion)}>{suggestion} <ArrowUp size={15} /></button>)}</div></div>
}