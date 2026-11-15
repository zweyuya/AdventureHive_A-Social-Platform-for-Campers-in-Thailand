import { AlertTriangle, Calendar, MapPin, Pencil, Plus, Repeat, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { OrganizerRecord } from "../components/cards";
import { Empty, ErrorNote, Spinner, StatusBadge } from "../components/ui";
import { useApi } from "../lib/hooks";
import { dateRange, fmtDate } from "../lib/format";

/** Things the organizer should do now, as short labels. */
function todo(t) {
  const items = [];
  if (t.status === "draft") items.push("Draft: not published yet");
  if (t.needs_attendance) items.push(`Record attendance by ${fmtDate(t.attendance_due)}`);
  if (t.open_appeals) items.push(`${t.open_appeals} no-show appeal${t.open_appeals === 1 ? "" : "s"} waiting for an admin`);
  if (t.flag_status === "needs_review") items.push("Flagged for admin review");
  return items;
}

function Row({ t }) {
  const upcoming = ["draft", "published", "full"].includes(t.status);
  const actions = todo(t);
  return (
    <li className="card p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="mr-auto min-w-0">
          <Link to={`/trips/${t.id}`} className="font-semibold text-navy-900 hover:text-forest-800">{t.title}</Link>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink/65">
            <span className="flex items-center gap-1"><Calendar size={14} /> {dateRange(t.start_datetime, t.end_datetime)}</span>
            <span className="flex items-center gap-1"><MapPin size={14} /> {t.location.name}</span>
            <span className="flex items-center gap-1"><Users size={14} /> {t.confirmed_count} / {t.participant_capacity}
              {t.waitlist_count > 0 && ` · ${t.waitlist_count} waitlisted`}</span>
          </p>
        </div>
        <StatusBadge status={t.status} />
      </div>
      {actions.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {actions.map((a) => (
            <li key={a} className="flex items-center gap-1 rounded-full bg-sunrise-100/60 px-2.5 py-0.5 text-xs font-semibold text-navy-900">
              <AlertTriangle size={12} className="text-sunrise-600" /> {a}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Link to={`/trips/${t.id}`} className="btn-outline btn-sm">Open</Link>
        {upcoming && <Link to={`/trips/${t.id}/edit`} className="btn-outline btn-sm"><Pencil size={13} /> Edit</Link>}
        {t.status === "completed" && <Link to={`/trips/new?repeat=${t.id}`} className="btn-outline btn-sm"><Repeat size={13} /> Repeat this trip</Link>}
      </div>
    </li>
  );
}

function Section({ title, trips, empty }) {
  return (
    <section className="mt-6">
      <h2 className="mb-3 text-lg font-bold">{title} <span className="text-sm font-normal text-ink/55">({trips.length})</span></h2>
      {trips.length === 0 ? <p className="text-sm text-ink/60">{empty}</p>
        : <ul className="space-y-3">{trips.map((t) => <Row key={t.id} t={t} />)}</ul>}
    </section>
  );
}

/** Organizer dashboard: my record, what needs doing, and every trip I organise. */
export default function OrganisedTrips() {
  const me = useApi("/users/me/");
  const { data, loading, error } = useApi("/trips/organised/");
  const trips = data || [];
  const attention = trips.filter((t) => todo(t).length > 0);
  // Published trips stay here until the scheduled job marks them completed after they end.
  const upcoming = trips.filter((t) => ["published", "full"].includes(t.status) && !todo(t).length)
    .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));
  const past = trips.filter((t) => ["completed", "cancelled"].includes(t.status) && !todo(t).length);
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">Trips organised</h1>
        <Link to="/trips/new" className="btn-primary"><Plus size={16} /> Create a trip</Link>
      </div>
      <OrganizerRecord stats={me.data?.organizer} />
      <ErrorNote error={error} className="mt-4" />
      {loading && <Spinner />}
      {!loading && trips.length === 0 && (
        <div className="mt-6"><Empty title="You haven't organised a trip yet" action={<Link to="/trips/new" className="btn-primary">Create your first trip</Link>} /></div>
      )}
      {trips.length > 0 && <>
        <Section title="Needs your attention" trips={attention} empty="Nothing to do right now." />
        <Section title="Upcoming" trips={upcoming} empty="No upcoming trips." />
        <Section title="Past" trips={past} empty="No past trips yet." />
      </>}
    </div>
  );
}
