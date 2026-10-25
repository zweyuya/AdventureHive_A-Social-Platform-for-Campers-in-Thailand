import { Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PostComposer, PostList } from "../components/feed";
import { Empty, ErrorNote, Spinner } from "../components/ui";
import { useApi } from "../lib/hooks";

/** Home feed: posts from the groups I belong to and the trips I'm going on. */
export default function Feed() {
  const groups = useApi("/groups/mine/");
  const [target, setTarget] = useState("");
  const [refresh, setRefresh] = useState(0);
  const mine = groups.data?.results ?? groups.data ?? [];
  const selected = mine.find((g) => String(g.id) === target);

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[1fr_300px]">
      <div className="min-w-0 space-y-4">
        <div>
          <h1 className="text-2xl font-extrabold">Your feed</h1>
          <p className="text-sm text-ink/60">Updates from your groups and the trips you're going on. Only members see them.</p>
        </div>
        {groups.loading ? <Spinner /> : groups.error ? <ErrorNote error={groups.error} /> : mine.length > 0 && (
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <span className="font-semibold text-navy-900">Post to</span>
              <select className="input w-auto py-1.5" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Choose a group to post in">
                <option value="">Choose a group…</option>
                {mine.map((g) => <option key={g.id} value={g.id}>{g.name}{g.privacy_type === "private" ? " 🔒" : ""}</option>)}
              </select>
            </label>
            {selected && (
              <PostComposer key={selected.id} groupId={selected.id}
                            needsApproval={selected.privacy_type === "private" && !["admin", "co_admin"].includes(selected.my_role)}
                            placeholder={`Share something with ${selected.name}…`} onPosted={() => setRefresh((r) => r + 1)} />
            )}
          </div>
        )}
        <PostList refreshKey={refresh} empty={
          <Empty title="Nothing here yet" action={<Link to="/groups" className="btn-primary">Find a group</Link>}>
            Join a group or RSVP to a trip and their posts show up here.
          </Empty>} />
      </div>
      <aside className="space-y-4">
        <section className="card p-5">
          <h2 className="mb-3 flex items-center gap-2 font-bold"><Users size={18} /> Your groups</h2>
          {mine.length === 0 ? <p className="text-sm text-ink/60">You haven't joined any groups yet.</p> : (
            <ul className="space-y-2 text-sm">
              {mine.map((g) => <li key={g.id}><Link to={`/groups/${g.id}`} className="font-medium text-forest-800 hover:underline">{g.name}</Link>
                {g.privacy_type === "private" && <span className="text-ink/50"> · private</span>}</li>)}
            </ul>
          )}
        </section>
        <p className="px-1 text-xs text-ink/55">In private groups, posts from members are checked by an admin before others can see them.</p>
      </aside>
    </div>
  );
}
