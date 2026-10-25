import { ArrowLeft, Lock, MessageCircle, MoreVertical, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TripCard } from "../components/cards";
import LandscapeArt from "../components/LandscapeArt";
import { PendingQueue, PostComposer, PostList } from "../components/feed";
import { Avatar, Empty, ErrorNote, Modal, Spinner, Tabs } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { fmtDate, label } from "../lib/format";

const ROLE_TEXT = { admin: "Admin", co_admin: "Co-admin", member: "Member" };

function MemberActions({ groupId, member, myRole, reload }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const run = async (path, body) => {
    setError(null);
    try { await api(`/groups/${groupId}/members/${member.user.id}/${path}/`, { method: "POST", body }); setOpen(false); reload(); }
    catch (err) { setError(err); }
  };
  const isAdmin = myRole === "admin";
  return (
    <>
      <button onClick={() => setOpen(true)} className="btn-ghost p-1.5" aria-label={`Manage ${member.user.display_name}`}><MoreVertical size={16} /></button>
      {open && (
        <Modal title={`Manage ${member.user.display_name}`} onClose={() => setOpen(false)}>
          <div className="space-y-2">
            {isAdmin && ["member", "co_admin", "admin"].filter((r) => r !== member.role_in_group).map((r) => (
              <button key={r} className="btn-outline w-full" onClick={() => run("role", { role: r })}>Make {ROLE_TEXT[r].toLowerCase()}</button>
            ))}
            <button className="btn-danger w-full" onClick={() => run("remove")}>Remove from group</button>
            {isAdmin && <button className="btn-danger w-full" onClick={() => run("ban")}>Ban from group</button>}
          </div>
          <ErrorNote error={error} className="mt-3" />
        </Modal>
      )}
    </>
  );
}

export default function GroupDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: g, loading, error, reload } = useApi(`/groups/${id}/`);
  const members = useApi(`/groups/${id}/members/`, [g?.member_count]);
  const trips = useApi(`/groups/${id}/trips/`);
  const [actionError, setActionError] = useState(null);
  const [addId, setAddId] = useState("");
  const [tab, setTab] = useState("posts");
  const [feedKey, setFeedKey] = useState(0);

  if (loading) return <Spinner />;
  if (error) return <div className="mx-auto max-w-3xl p-6"><ErrorNote error={error} /></div>;
  const act = async (method) => {
    setActionError(null);
    try { await api(`/groups/${id}/join/`, { method }); reload(); members.reload(); trips.reload(); }
    catch (err) { setActionError(err); }
  };
  const addMember = async (e) => {
    e.preventDefault(); setActionError(null);
    try { await api(`/groups/${id}/members/`, { method: "POST", body: { user_id: Number(addId) } }); setAddId(""); reload(); }
    catch (err) { setActionError(err); }
  };
  const remove = async () => { await api(`/groups/${id}/`, { method: "DELETE" }); navigate("/groups"); };
  const canModerate = ["admin", "co_admin"].includes(g.my_role);
  const insideHidden = members.error?.status === 403 || members.error?.status === 401;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <Link to="/groups" className="btn-ghost -ml-3 mb-2 px-3 py-1.5"><ArrowLeft size={16} /> All groups</Link>
      <section className="relative overflow-hidden rounded-2xl">
        <LandscapeArt seed={g.id * 7} className="h-48 w-full" />
        <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-navy-900/80 to-transparent p-6 text-white">
          <h1 className="flex items-center gap-2 text-2xl font-extrabold !text-white sm:text-3xl">{g.name} {g.privacy_type === "private" && <Lock size={20} />}</h1>
          <p className="text-sm text-white/85">{label(g.category)} · {g.member_count} member{g.member_count === 1 ? "" : "s"} · {g.privacy_type === "private" ? "Private group" : "Public group"}</p>
        </div>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-6">
          {g.description && <p className="max-w-prose text-ink/80">{g.description}</p>}
          <Tabs tabs={[["posts", "Posts"], ["trips", "Group trips"]]} active={tab} onChange={setTab} />
          {tab === "posts" && (
            <section className="space-y-4">
              {insideHidden ? <Empty title="This is a private group">Posts are visible to members only.</Empty> : <>
                {canModerate && <PendingQueue groupId={g.id} refreshKey={feedKey} onChange={() => setFeedKey((k) => k + 1)} />}
                {g.my_role && <PostComposer groupId={g.id} needsApproval={g.privacy_type === "private" && !canModerate}
                                            placeholder={`Share something with ${g.name}…`} onPosted={() => setFeedKey((k) => k + 1)} />}
                <PostList query={`?group=${g.id}`} refreshKey={feedKey} showPlace={false}
                          empty={<Empty title="No posts yet">{g.my_role ? "Start the conversation — share a photo or plan." : "Join the group to post."}</Empty>} />
              </>}
            </section>
          )}
          {tab === "trips" && <section>
            {insideHidden ? <Empty title="This is a private group">Trips are visible to members only.</Empty> :
             trips.loading ? <Spinner /> : (trips.data || []).length === 0 ? (
               <Empty title="No trips yet" action={g.my_role && <Link to="/trips/new" className="btn-primary">Plan a group trip</Link>} />
             ) : <div className="grid gap-4 sm:grid-cols-2">{trips.data.map((t) => <TripCard key={t.id} trip={t} />)}</div>}
          </section>}
        </div>
        <aside className="space-y-5">
          <section className="card p-5">
            {!user && <Link to="/login" className="btn-primary w-full">Log in to join</Link>}
            {user && !g.my_role && (g.privacy_type === "public"
              ? <button className="btn-primary w-full" onClick={() => act("POST")}>Join group</button>
              : <p className="text-sm text-ink/70">This group is private. Ask an admin to add you.</p>)}
            {g.my_role && <>
              <p className="text-sm">You're a <span className="font-semibold">{ROLE_TEXT[g.my_role].toLowerCase()}</span> of this group.</p>
              <Link to={`/groups/${g.id}/chat`} className="btn-outline mt-3 w-full"><MessageCircle size={16} /> Group chat</Link>
              <button className="btn-ghost mt-2 w-full text-red-700" onClick={() => act("DELETE")}>Leave group</button>
            </>}
            {g.my_role === "admin" && <button className="btn-danger mt-2 w-full" onClick={remove}>Delete group</button>}
            <ErrorNote error={actionError} className="mt-3" />
          </section>
          <section className="card p-5">
            <h2 className="mb-3 flex items-center gap-2 font-bold"><Users size={18} /> Members</h2>
            {insideHidden && <p className="text-sm text-ink/60">Only members can see who's in a private group.</p>}
            <ul className="space-y-2">
              {(members.data || []).map((m) => (
                <li key={m.user.id} className="flex items-center gap-3">
                  <Avatar name={m.user.display_name} id={m.user.id} src={m.user.avatar} size="h-8 w-8 text-xs" />
                  <span className="flex-1 text-sm"><span className="font-medium">{m.user.display_name}</span>
                    <span className="block text-xs text-ink/55">{ROLE_TEXT[m.role_in_group]} · joined {fmtDate(m.joined_at)}</span></span>
                  {canModerate && user && m.user.id !== user.id && <MemberActions groupId={g.id} member={m} myRole={g.my_role} reload={() => { reload(); members.reload(); }} />}
                </li>
              ))}
            </ul>
            {canModerate && (
              <form onSubmit={addMember} className="mt-4 flex gap-2 border-t border-slate-100 pt-4">
                <input className="input" type="number" min="1" required placeholder="User ID" aria-label="User ID to add" value={addId} onChange={(e) => setAddId(e.target.value)} />
                <button className="btn-outline">Add</button>
              </form>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
