import { Menu, Plus, ShieldCheck } from 'lucide-react'
import { PAGE_CONTENT } from '../constants/page'

type ChatSidebarProps = {
  onNewChat: () => void
  recentChats: string[]
  onSelectChat: (sessionId: string) => void
  recentSessionIds: string[]
}

export function ChatSidebar({ onNewChat, recentChats, onSelectChat, recentSessionIds }: ChatSidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <ShieldCheck size={19} />
        </span>
        <span>{PAGE_CONTENT.brand}</span>
      </div>
      <button className="new-chat" type="button" onClick={onNewChat}>
        <Plus size={18} /> New chat
      </button>
      <div className="history-label">Recent</div>
      {recentChats.map((chat, index) => (
        <button
          className={`history-item ${index === 0 ? 'active' : ''}`}
          key={`${chat}-${index}`}
          type="button"
          onClick={() => recentSessionIds[index] && onSelectChat(recentSessionIds[index])}
          title={chat}
        >
          {chat}
        </button>
      ))}
      <div className="sidebar-footer">
        <div>
          <span>{PAGE_CONTENT.plan}</span>
        </div>
        <Menu size={18} />
      </div>
    </aside>
  )
}