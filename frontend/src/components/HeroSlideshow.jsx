import { ChevronLeft, ChevronRight, MapPin } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { results } from "../lib/api";
import { useApi } from "../lib/hooks";
import LandscapeArt from "./LandscapeArt";

const INTERVAL_MS = 6000;
const MAX_SLIDES = 5;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Background slideshow for the home page hero: up to five campsites that have a
 * cover photo, cross-fading every 6 seconds. Pauses on hover/focus; no autoplay
 * when the visitor has asked for reduced motion. Falls back to an illustration.
 */
export default function HeroSlideshow({ children }) {
  const { data } = useApi(`/campsites/?has_photo=true&ordering=-review_count&page_size=${MAX_SLIDES}`);
  const slides = results(data).slice(0, MAX_SLIDES);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const timer = useRef(null);
  const count = slides.length;

  const go = useCallback((i) => setIndex(((i % count) + count) % count), [count]);

  useEffect(() => {
    if (count < 2 || paused || prefersReducedMotion()) return undefined;
    timer.current = setInterval(() => setIndex((i) => (i + 1) % count), INTERVAL_MS);
    return () => clearInterval(timer.current);
  }, [count, paused]);

  const current = slides[index];
  return (
    <section
      className="relative overflow-hidden rounded-2xl bg-navy-900"
      aria-roledescription="carousel" aria-label="Featured campsites"
      onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}
    >
      {count === 0 && <LandscapeArt seed={12} mood="dawn" className="absolute inset-0 h-full w-full" />}
      {slides.map((s, i) => (
        <img key={s.id} src={s.cover_image} alt="" aria-hidden={i !== index}
             className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ease-in-out ${i === index ? "opacity-100" : "opacity-0"}`} />
      ))}

      <div className="relative bg-gradient-to-r from-navy-900/80 via-navy-900/45 to-transparent px-6 pb-16 pt-12 sm:px-10 sm:pb-20 sm:pt-16">
        {children}
      </div>

      {current && (
        <div className="absolute bottom-3 left-6 right-24 sm:left-10" aria-live={paused ? "polite" : "off"}>
          <Link to={`/campsites/${current.id}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-white hover:underline">
            <MapPin size={15} /> {current.name}, {current.province}
          </Link>
          {current.cover_image_credit && <p className="truncate text-[11px] text-white/70">{current.cover_image_credit}</p>}
        </div>
      )}

      {count > 1 && (
        <div className="absolute bottom-3 right-4 flex items-center gap-1">
          <button onClick={() => go(index - 1)} className="rounded-full bg-black/30 p-1.5 text-white hover:bg-black/50" aria-label="Previous photo">
            <ChevronLeft size={16} />
          </button>
          <div className="flex gap-1.5 px-1" role="group" aria-label="Choose a photo">
            {slides.map((s, i) => (
              <button key={s.id} onClick={() => go(i)} aria-label={`Show ${s.name}`} aria-current={i === index}
                      className={`h-2 rounded-full transition-all ${i === index ? "w-6 bg-white" : "w-2 bg-white/50 hover:bg-white/80"}`} />
            ))}
          </div>
          <button onClick={() => go(index + 1)} className="rounded-full bg-black/30 p-1.5 text-white hover:bg-black/50" aria-label="Next photo">
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </section>
  );
}
