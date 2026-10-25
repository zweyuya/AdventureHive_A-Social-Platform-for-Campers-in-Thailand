import { Check, EyeOff, Hourglass, ImagePlus, Lock, MessageCircle, MoreHorizontal, Pencil, RotateCcw, Send, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload } from "../lib/api";
import { useAuth } from "../lib/auth";
import { timeAgo } from "../lib/format";
import { Avatar, Empty, ErrorNote, Modal, Spinner } from "./ui";

export const REACTIONS = [
  ["like", "👍", "Like"], ["love", "❤️", "Love"], ["haha", "😂", "Haha"], ["wow", "😮", "Wow"], ["sad", "😢", "Sad"],
];
const EMOJI = Object.fromEntries(REACTIONS.map(([k, e]) => [k, e]));
const WORD = Object.fromEntries(REACTIONS.map(([k, , w]) => [k, w]));

/* ------------------------------------------------------------------ composer */

export function PostComposer({ groupId, tripId, needsApproval, onPosted, placeholder }) {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [sentForReview, setSentForReview] = useState(false);
  const input = useRef(null);

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pick = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) return setError("Photos can be up to 5 MB.");
    setError(null); setFile(f);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!text.trim() && !file) return;
    setBusy(true); setError(null); setSentForReview(false);
    try {
      const fd = new FormData();
      fd.append("content_text", text.trim());
      if (groupId) fd.append("group_id", groupId);
      if (tripId) fd.append("trip_id", tripId);
      if (file) fd.append("image", file);
      const post = await apiUpload("/posts/", fd, { method: "POST" });
      setText(""); setFile(null);
      if (post.status === "pending_review") setSentForReview(true);
      onPosted?.(post);
    } catch (err) { setError(err); }
    setBusy(false);
  };

  if (!user) return null;
  return (
    <form onSubmit={submit} className="card p-4">
      <div className="flex gap-3">
        <Avatar name={user.display_name} id={user.id} src={user.avatar} />
        <textarea className="input min-h-[72px] resize-y" maxLength={5000} value={text} onChange={(e) => setText(e.target.value)}
                  placeholder={placeholder || "Share an update, a photo or a question…"} aria-label="Write a post" />
      </div>
      {preview && (
        <div className="relative ml-12 mt-3 inline-block">
          <img src={preview} alt="Selected photo" className="max-h-56 rounded-lg object-cover" />
          <button type="button" onClick={() => setFile(null)} className="absolute right-1.5 top-1.5 rounded-full bg-navy-900/70 p-1 text-white" aria-label="Remove photo"><X size={14} /></button>
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 pl-12">
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick} />
        <button type="button" className="btn-ghost btn-sm" onClick={() => input.current?.click()}><ImagePlus size={16} /> Photo</button>
        {needsApproval && <span className="flex items-center gap-1 text-xs text-ink/60"><Lock size={12} /> An admin approves posts in this private group</span>}
        <button className="btn-primary btn-sm ml-auto" disabled={busy || (!text.trim() && !file)}>{busy ? "Posting…" : "Post"}</button>
      </div>
      {sentForReview && (
        <p className="ml-12 mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
          <Hourglass size={15} /> Sent to the group admins. Your post appears once it's approved.
        </p>
      )}
      <ErrorNote error={error} className="ml-12 mt-3" />
    </form>
  );
}

/* ------------------------------------------------------------------ reactions */

function ReactionBar({ post, onChange }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const live = post.status === "published";

  const send = async (type) => {
    setOpen(false); setError(null);
    try {
      const same = post.my_reaction === type;
      onChange(await api(`/posts/${post.id}/react/`, same ? { method: "DELETE" } : { method: "PUT", body: { type } }));
    } catch (err) { setError(err); }
  };
  const top = Object.entries(post.reactions || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="relative" onMouseEnter={() => { clearTimeout(timer.current); live && setOpen(true); }}
           onMouseLeave={() => { timer.current = setTimeout(() => setOpen(false), 250); }}>
        <button disabled={!live} onClick={() => send(post.my_reaction || "like")}
                className={`btn-ghost btn-sm ${post.my_reaction ? "font-bold text-forest-800" : ""}`}
                aria-label={post.my_reaction ? `Remove your ${WORD[post.my_reaction]} reaction` : "Like"}>
          <span className="text-base leading-none">{post.my_reaction ? EMOJI[post.my_reaction] : "👍"}</span>
          {post.my_reaction ? WORD[post.my_reaction] : "Like"}
        </button>
        {open && (
          <div className="absolute bottom-full left-0 z-20 mb-1 flex gap-0.5 rounded-full border border-slate-200 bg-white p-1 shadow-lg" role="menu" aria-label="Choose a reaction">
            {REACTIONS.map(([k, e, w]) => (
              <button key={k} role="menuitem" title={w} aria-label={w} onClick={() => send(k)}
                      className={`rounded-full px-1.5 py-1 text-xl leading-none transition-transform hover:scale-125 ${post.my_reaction === k ? "bg-forest-100" : ""}`}>{e}</button>
            ))}
          </div>
        )}
      </div>
      {post.reaction_count > 0 && (
        <span className="flex items-center gap-1 text-sm text-ink/65" title={top.map(([k, n]) => `${WORD[k]} ${n}`).join(" · ")}>
          <span className="tracking-tighter">{top.map(([k]) => EMOJI[k]).join("")}</span> {post.reaction_count}
        </span>
      )}
      <ErrorNote error={error} className="w-full" />
    </div>
  );
}

/* ------------------------------------------------------------------ comments */

function CommentItem({ c, onReply, onRemove, canModerate, reply, children }) {
  return (
    <li className={reply ? "mt-3" : ""}>
      <div className="flex gap-2.5">
        <Avatar name={c.author.display_name} id={c.author.id} src={c.author.avatar} size={reply ? "h-7 w-7 text-[10px]" : "h-8 w-8 text-xs"} />
        <div className="min-w-0 flex-1">
          <div className={`inline-block max-w-full rounded-2xl px-3 py-2 ${c.status === "hidden" ? "bg-red-50" : "bg-slate-100"}`}>
            <p className="text-sm font-semibold text-navy-900">{c.author.display_name}</p>
            <p className="whitespace-pre-line break-words text-sm text-ink/85">{c.content_text}</p>
          </div>
          <div className="mt-0.5 flex gap-3 pl-3 text-xs text-ink/55">
            <span>{timeAgo(c.created_at)}</span>
            {c.status === "hidden" && <span className="font-semibold text-red-700">Hidden</span>}
            {onReply && <button className="font-semibold hover:text-forest-800" onClick={onReply}>Reply</button>}
            {canModerate && <button className="font-semibold hover:text-forest-800" onClick={() => onRemove(c, c.status === "hidden" ? "restore" : "hide")}>{c.status === "hidden" ? "Restore" : "Hide"}</button>}
            {c.can_delete && <button className="font-semibold hover:text-red-700" onClick={() => onRemove(c, "delete")}>Delete</button>}
          </div>
        </div>
      </div>
      {children}
    </li>
  );
}

function Comments({ post, onCount }) {
  const [list, setList] = useState(null);
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState(null);
  const [error, setError] = useState(null);
  const field = useRef(null);
  const live = post.status === "published";

  const load = useCallback(() => api(`/posts/${post.id}/comments/`).then(setList).catch(setError), [post.id]);
  useEffect(() => { load(); }, [load]);

  const count = (l) => l.flatMap((c) => [c, ...c.replies]).filter((c) => c.status === "published").length;
  const submit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setError(null);
    try {
      await api(`/posts/${post.id}/comments/`, { method: "POST", body: { content_text: text.trim(), parent_comment_id: replyTo?.id ?? null } });
      setText(""); setReplyTo(null);
      const fresh = await api(`/posts/${post.id}/comments/`);
      setList(fresh); onCount(count(fresh));
    } catch (err) { setError(err); }
  };
  const remove = async (c, action) => {
    setError(null);
    try {
      if (action === "delete") await api(`/comments/${c.id}/`, { method: "DELETE" });
      else await api(`/comments/${c.id}/${action}/`, { method: "POST" });
      const fresh = await api(`/posts/${post.id}/comments/`);
      setList(fresh); onCount(count(fresh));
    } catch (err) { setError(err); }
  };
  const startReply = (c) => { setReplyTo(c); setTimeout(() => field.current?.focus(), 0); };

  if (!list) return error ? <ErrorNote error={error} /> : <p className="py-2 text-sm text-ink/55">Loading comments…</p>;
  return (
    <div className="space-y-3">
      <ul className="space-y-3">
        {list.map((c) => (
          <CommentItem key={c.id} c={c} canModerate={post.can_moderate} onRemove={remove} onReply={live ? () => startReply(c) : null}>
            {c.replies.length > 0 && (
              <ul className="ml-10">
                {c.replies.map((r) => <CommentItem key={r.id} c={r} reply canModerate={post.can_moderate} onRemove={remove} onReply={live ? () => startReply(c) : null} />)}
              </ul>
            )}
          </CommentItem>
        ))}
      </ul>
      {live && (
        <form onSubmit={submit}>
          {replyTo && <p className="mb-1 flex items-center gap-2 text-xs text-ink/60">Replying to {replyTo.author.display_name}
            <button type="button" onClick={() => setReplyTo(null)} className="hover:text-red-700" aria-label="Cancel reply"><X size={12} /></button></p>}
          <div className="flex gap-2">
            <input ref={field} className="input rounded-full py-2" maxLength={2000} value={text} onChange={(e) => setText(e.target.value)}
                   placeholder={replyTo ? "Write a reply…" : "Write a comment…"} aria-label={replyTo ? "Write a reply" : "Write a comment"} />
            <button className="btn-primary btn-sm rounded-full" disabled={!text.trim()} aria-label="Send"><Send size={15} /></button>
          </div>
        </form>
      )}
      <ErrorNote error={error} />
    </div>
  );
}

/* ------------------------------------------------------------------ post card */

function RejectModal({ post, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    try { onDone(await api(`/posts/${post.id}/reject/`, { method: "POST", body: { note } })); }
    catch (err) { setError(err); }
  };
  return (
    <Modal title="Don't approve this post" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-ink/70">{post.author.display_name} will see your note, so they know what to change.</p>
        <textarea className="input min-h-[90px]" required maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. Please don't share exact locations of the river spot here." aria-label="Note to the author" autoFocus />
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-danger" disabled={!note.trim()}>Reject post</button></div>
      </form>
    </Modal>
  );
}

function EditModal({ post, onClose, onDone, needsApproval }) {
  const [text, setText] = useState(post.content_text);
  const [error, setError] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    try { onDone(await api(`/posts/${post.id}/`, { method: "PUT", body: { content_text: text } })); }
    catch (err) { setError(err); }
  };
  return (
    <Modal title="Edit post" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <textarea className="input min-h-[120px]" required maxLength={5000} value={text} onChange={(e) => setText(e.target.value)} aria-label="Post text" autoFocus />
        {needsApproval && <p className="text-xs text-ink/60">Edited posts in a private group go back to the admins for approval.</p>}
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary">Save</button></div>
      </form>
    </Modal>
  );
}

export function PostCard({ post: initial, onRemoved, onModerated, showPlace = true, openComments = false }) {
  const [post, setPost] = useState(initial);
  const [comments, setComments] = useState(openComments);
  const [menu, setMenu] = useState(false);
  const [modal, setModal] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => setPost(initial), [initial]);

  const isPrivate = post.group?.privacy_type === "private";
  const run = async (fn) => {
    setMenu(false); setError(null);
    try { await fn(); } catch (err) { setError(err); }
  };
  const update = (p) => { setPost(p); onModerated?.(p); };
  const moderate = (action) => run(async () => update(await api(`/posts/${post.id}/${action}/`, { method: "POST" })));
  const remove = () => run(async () => {
    if (!window.confirm("Delete this post? This can't be undone.")) return;
    await api(`/posts/${post.id}/`, { method: "DELETE" });
    onRemoved?.(post);
  });
  const reviewed = (p) => { setModal(null); update(p); };
  const place = post.group ? { to: `/groups/${post.group.id}`, name: post.group.name } : post.trip ? { to: `/trips/${post.trip.id}`, name: post.trip.title } : null;

  return (
    <article className={`card ${post.status === "hidden" ? "opacity-70" : ""}`} aria-label={`Post by ${post.author.display_name}`}>
      {post.status === "pending_review" && (
        <div className="flex items-center gap-2 rounded-t-xl border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <Hourglass size={15} /> {post.is_mine ? "Waiting for an admin to approve your post. Only you and the admins can see it." : "Waiting for approval"}
        </div>
      )}
      {post.status === "rejected" && (
        <div className="rounded-t-xl border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
          <p className="font-semibold">Not approved</p>
          {post.moderation_note && <p className="mt-0.5">Note from the admin: “{post.moderation_note}”</p>}
          {post.is_mine && <p className="mt-0.5 text-xs">Edit the post to send it for approval again.</p>}
        </div>
      )}
      {post.status === "hidden" && (
        <div className="flex items-center gap-2 rounded-t-xl border-b border-slate-200 bg-slate-50 px-4 py-2 text-sm text-ink/70"><EyeOff size={15} /> Hidden by a moderator</div>
      )}

      <div className="p-4">
        <header className="flex items-start gap-3">
          <Avatar name={post.author.display_name} id={post.author.id} src={post.author.avatar} size="h-10 w-10 text-sm" />
          <div className="min-w-0 flex-1">
            <p className="text-sm">
              <span className="font-semibold text-navy-900">{post.author.display_name}</span>
              {showPlace && place && <> <span className="text-ink/45">▸</span> <Link to={place.to} className="font-semibold text-forest-800 hover:underline">{place.name}</Link></>}
            </p>
            <p className="flex items-center gap-1 text-xs text-ink/55">
              <Link to={`/posts/${post.id}`} className="hover:underline">{timeAgo(post.created_at)}</Link>
              {post.edited_at && <span>· edited</span>}
              {isPrivate && <Lock size={11} aria-label="Private group" />}
            </p>
          </div>
          {(post.is_mine || post.can_moderate) && (
            <div className="relative">
              <button className="btn-ghost p-1.5" onClick={() => setMenu((m) => !m)} aria-label="Post options" aria-expanded={menu}><MoreHorizontal size={18} /></button>
              {menu && (
                <div className="card absolute right-0 z-20 mt-1 w-44 overflow-hidden py-1 text-sm" onMouseLeave={() => setMenu(false)}>
                  {post.is_mine && <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-forest-50" onClick={() => { setMenu(false); setModal("edit"); }}><Pencil size={14} /> Edit</button>}
                  {post.can_moderate && post.status === "published" && <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-forest-50" onClick={() => moderate("hide")}><EyeOff size={14} /> Hide</button>}
                  {post.can_moderate && post.status === "hidden" && <button className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-forest-50" onClick={() => moderate("restore")}><RotateCcw size={14} /> Restore</button>}
                  <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-700 hover:bg-red-50" onClick={remove}><Trash2 size={14} /> Delete</button>
                </div>
              )}
            </div>
          )}
        </header>

        {post.content_text && <p className="mt-3 whitespace-pre-line break-words text-[15px] leading-relaxed text-ink/90">{post.content_text}</p>}
      </div>
      {post.image && <img src={post.image} alt={`Photo shared by ${post.author.display_name}`} className="max-h-[520px] w-full bg-slate-100 object-cover" loading="lazy" />}

      {post.status === "pending_review" && post.can_moderate && !post.is_mine && (
        <div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-3">
          <button className="btn-primary btn-sm" onClick={() => moderate("approve")}><Check size={15} /> Approve</button>
          <button className="btn-danger btn-sm" onClick={() => setModal("reject")}><X size={15} /> Reject…</button>
        </div>
      )}

      {post.status === "published" && (
        <div className="border-t border-slate-100 px-4 py-2">
          <div className="flex items-center gap-2">
            <ReactionBar post={post} onChange={setPost} />
            <button className="btn-ghost btn-sm ml-auto" onClick={() => setComments((c) => !c)} aria-expanded={comments}>
              <MessageCircle size={16} /> {post.comment_count > 0 ? `${post.comment_count} comment${post.comment_count === 1 ? "" : "s"}` : "Comment"}
            </button>
          </div>
          {comments && <div className="mt-3 border-t border-slate-100 pt-3"><Comments post={post} onCount={(n) => setPost((p) => ({ ...p, comment_count: n }))} /></div>}
        </div>
      )}
      <ErrorNote error={error} className="mx-4 mb-4" />
      {modal === "reject" && <RejectModal post={post} onClose={() => setModal(null)} onDone={reviewed} />}
      {modal === "edit" && <EditModal post={post} needsApproval={isPrivate && !post.can_moderate} onClose={() => setModal(null)} onDone={reviewed} />}
    </article>
  );
}

/* ------------------------------------------------------------------ lists */

/** Loads a paginated /posts/ query; `refreshKey` reloads it. */
export function PostList({ query = "", refreshKey = 0, showPlace = true, empty }) {
  const [state, setState] = useState({ items: [], page: 1, hasMore: false, loading: true, error: null });

  const load = useCallback(async (page) => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const sep = query ? "&" : "?";
      const data = await api(`/posts/${query}${sep}page=${page}`);
      setState((s) => ({ items: page === 1 ? data.results : [...s.items, ...data.results], page, hasMore: !!data.next, loading: false, error: null }));
    } catch (error) { setState((s) => ({ ...s, loading: false, error })); }
  }, [query]);
  useEffect(() => { load(1); }, [load, refreshKey]);

  if (state.error) return <ErrorNote error={state.error} />;
  if (state.loading && state.items.length === 0) return <Spinner text="Loading posts…" />;
  if (state.items.length === 0) return empty || <Empty title="No posts yet">Be the first to share something.</Empty>;
  return (
    <div className="space-y-4">
      {state.items.map((p) => (
        <PostCard key={p.id} post={p} showPlace={showPlace}
                  onRemoved={() => setState((s) => ({ ...s, items: s.items.filter((x) => x.id !== p.id) }))} />
      ))}
      {state.hasMore && (
        <div className="text-center"><button className="btn-outline" disabled={state.loading} onClick={() => load(state.page + 1)}>{state.loading ? "Loading…" : "Show older posts"}</button></div>
      )}
    </div>
  );
}

/** Group moderators: posts waiting for approval. */
export function PendingQueue({ groupId, refreshKey, onChange }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    api(`/posts/?group=${groupId}&status=pending_review`).then((d) => setItems(d.results)).catch(() => setItems([]));
  }, [groupId, refreshKey]);
  if (!items || items.length === 0) return null;
  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
      <h3 className="mb-3 flex items-center gap-2 font-bold text-amber-900"><Hourglass size={17} /> Waiting for your approval ({items.length})</h3>
      <div className="space-y-4">
        {items.map((p) => {
          const done = () => { setItems((l) => l.filter((x) => x.id !== p.id)); onChange?.(); };
          return <PostCard key={p.id} post={p} showPlace={false} onRemoved={done}
                           onModerated={(np) => np.status !== "pending_review" && done()} />;
        })}
      </div>
    </section>
  );
}
