import { PAGE_CONTENT } from '../constants/page'

export function ChatHeader() {
  return <header className="chat-header"><div><h1>{PAGE_CONTENT.title}</h1><p className="eyebrow">{PAGE_CONTENT.eyebrow}</p></div><a className="architecture-link" href="/architecture" title="Open architecture flow">Architecture flow</a></header>
}