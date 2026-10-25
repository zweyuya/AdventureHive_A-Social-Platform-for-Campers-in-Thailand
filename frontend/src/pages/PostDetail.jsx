import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PostCard } from "../components/feed";
import { ErrorNote, Spinner } from "../components/ui";
import { useApi } from "../lib/hooks";

/** A single post — where notification links land. */
export default function PostDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error } = useApi(`/posts/${id}/`);
  if (loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <button onClick={() => navigate(-1)} className="btn-ghost -ml-3 mb-3 px-3 py-1.5"><ArrowLeft size={16} /> Back</button>
      {error ? <ErrorNote error={error.status === 404 ? "This post was removed, or it's in a group you're not part of." : error} /> : (
        <>
          <PostCard post={data} openComments onRemoved={() => navigate("/feed")} />
          {data.group && <p className="mt-4 text-center text-sm"><Link to={`/groups/${data.group.id}`} className="link">More from {data.group.name}</Link></p>}
          {data.trip && <p className="mt-4 text-center text-sm"><Link to={`/trips/${data.trip.id}`} className="link">Back to {data.trip.title}</Link></p>}
        </>
      )}
    </div>
  );
}
