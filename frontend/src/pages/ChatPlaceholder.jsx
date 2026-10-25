import { ArrowLeft, MessageCircle, Paperclip, Send } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Spinner } from "../components/ui";
import { useApi } from "../lib/hooks";

/**
 * Screens 4–5 (group and direct chat). Real-time messaging was deferred to the next
 * phase following the proposal feedback, so this page shows the layout without
 * pretending messages exist.
 */
export default function ChatPlaceholder() {
  const { id } = useParams();
  const { data: g, loading } = useApi(id ? `/groups/${id}/` : null);
  if (loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <div className="card flex h-[70vh] flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
          <Link to={id ? `/groups/${id}` : "/groups"} className="btn-ghost p-2" aria-label="Back"><ArrowLeft size={18} /></Link>
          <span><span className="block font-bold text-navy-900">{g ? g.name : "Messages"}</span>
            {g && <span className="text-xs text-ink/55">{g.member_count} members</span>}</span>
        </header>
        <div className="flex flex-1 flex-col items-center justify-center bg-mist px-8 text-center">
          <MessageCircle size={40} className="text-forest-600" />
          <p className="mt-3 font-bold text-navy-900">Group chat is coming in the next phase</p>
          <p className="mt-1 max-w-sm text-sm text-ink/65">For now, coordinate using the trip page: the meeting point, equipment list and updates are shared with everyone who joins.</p>
        </div>
        <footer className="flex items-center gap-2 border-t border-slate-200 p-3">
          <Paperclip size={18} className="text-ink/30" />
          <input className="input" disabled placeholder="Type a message…" aria-label="Message (not available yet)" />
          <button className="btn-primary p-2.5" disabled aria-label="Send"><Send size={18} /></button>
        </footer>
      </div>
    </div>
  );
}
