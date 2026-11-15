import { Calendar, ChevronRight, MapPin, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { dateRange, label } from "../lib/format";
import CampsiteImage from "./CampsiteImage";
import { NotVerifiedBadge, StatusBadge, Stars, isUnverified } from "./ui";

export function TripCard({ trip }) {
  const full = trip.spots_left === 0;
  return (
    <article className="card group flex flex-col overflow-hidden transition duration-300 ease-out hover:-translate-y-1 hover:scale-[1.02] hover:border-forest-200 hover:shadow-xl focus-within:-translate-y-1 focus-within:scale-[1.02] focus-within:shadow-xl">
      <Link to={`/trips/${trip.id}`} className="relative block overflow-hidden" tabIndex={-1} aria-hidden="true">
        <CampsiteImage src={trip.location.cover_image} seed={trip.location.id * 31 + trip.id} className="h-36 w-full transition-transform duration-500 ease-out group-hover:scale-105" />
        {trip.status !== "published" && <StatusBadge status={trip.status} className="absolute left-3 top-3" />}
      </Link>
      <div className="flex flex-1 flex-col p-4">
        <h3 className="font-bold leading-snug"><Link to={`/trips/${trip.id}`} className="hover:text-forest-800">{trip.title}</Link></h3>
        {trip.organizer && <p className="mt-0.5 text-xs text-ink/60">by <span className="font-semibold text-ink/75">{trip.organizer.display_name}</span></p>}
        <p className="mt-2 flex items-center gap-2 text-sm text-ink/70"><Calendar size={15} className="text-forest-700" /> {dateRange(trip.start_datetime, trip.end_datetime)}</p>
        <p className="mt-1 flex items-center gap-2 text-sm text-ink/70"><MapPin size={15} className="text-forest-700" /> {trip.location.name}</p>
        <p className="mt-2 text-xs text-ink/60">{label(trip.difficulty)} · from {trip.min_experience_level}</p>
        <div className="mt-auto pt-4">
          <div className="mb-3 flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 text-ink/70"><Users size={15} /> {trip.confirmed_count} / {trip.participant_capacity} going</span>
            {trip.my_status && <StatusBadge status={trip.my_status} />}
            {!trip.my_status && full && <span className="text-xs font-semibold text-sunrise-600">Waitlist open</span>}
          </div>
          <Link to={`/trips/${trip.id}`} className="btn-outline w-full">View trip</Link>
        </div>
      </div>
    </article>
  );
}

/**
 * An organizer's record. Only trips that are hard to fake count: completed, not flagged,
 * at least 2 attendees and at least half of them checked in. No average until 3 people rated.
 */
export function OrganizerRecord({ stats, className = "" }) {
  if (!stats) return null;
  const parts = [];
  if (stats.trips_run === 0) parts.push("New organizer: no counted trips yet");
  else {
    parts.push(`${stats.trips_run} trip${stats.trips_run === 1 ? "" : "s"} run`);
    parts.push(`${stats.campers} camper${stats.campers === 1 ? "" : "s"}`);
  }
  if (stats.cancelled) parts.push(`${stats.cancelled} cancelled`);
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink/70 ${className}`}
          title="Counts only completed trips with at least 2 attendees, at least half of them checked in with the trip code. Trips flagged as suspicious don't count.">
      {stats.rating != null
        ? <span className="flex items-center gap-1 font-semibold text-navy-900"><Stars value={stats.rating} size={13} /> {stats.rating.toFixed(1)} as organizer ({stats.rating_count})</span>
        : stats.trips_run > 0 && <span className="text-ink/55">Not enough organizer ratings yet ({stats.rating_count} of {stats.min_ratings})</span>}
      <span>{parts.join(" · ")}</span>
    </span>
  );
}

export function CampsiteRow({ c }) {
  return (
    <Link to={`/campsites/${c.id}`} className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-forest-50">
      <CampsiteImage src={c.cover_image} seed={c.id} tent={false} className="h-14 w-20 shrink-0 rounded-lg" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-navy-900">{c.name}</span>
        <span className="flex flex-wrap items-center gap-2 text-xs text-ink/60">{c.province}{isUnverified(c) && <NotVerifiedBadge />}</span>
        <span className="mt-0.5 flex items-center gap-1 text-xs text-ink/60">
          {c.avg_rating ? <><Stars value={c.avg_rating} size={12} /> {Number(c.avg_rating).toFixed(1)} ({c.review_count})</> : "No reviews yet"}
        </span>
      </span>
      <ChevronRight size={18} className="text-ink/40" />
    </Link>
  );
}
