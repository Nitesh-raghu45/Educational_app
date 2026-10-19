import type { Section, User } from "../types";

interface Props {
  sections: Section[];
  activeId: string | null;
  user: User;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
}

export default function Sidebar({ sections, activeId, user, onSelect, onNewChat, onDelete, onLogout }: Props) {
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNewChat}>
        <span>＋</span> New chat
      </button>
      <div className="sidebar-label">Chats</div>
      <nav className="section-list">
        {sections.length === 0 && <div className="muted small pad">No chats yet</div>}
        {sections.map((s) => (
          <div
            key={s.id}
            className={`section-item ${s.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(s.id)}
            title={s.title ?? "New chat"}
          >
            <span className="section-title">{s.title ?? "New chat"}</span>
            <span className={`count ${s.status === "limit_reached" ? "full" : ""}`}>
              {s.question_count}/{s.max_questions}
            </span>
            <button
              className="delete"
              aria-label="Delete chat"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm("Delete this chat and its history?")) onDelete(s.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="small muted ellipsis">{user.email}</span>
        <button className="link small" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
