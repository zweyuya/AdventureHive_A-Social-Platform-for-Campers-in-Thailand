import { useState } from "react";
import LandscapeArt from "./LandscapeArt";

/**
 * The campsite's uploaded cover photo, or — if there is none (or it fails to
 * load) — the generated landscape illustration for that campsite.
 */
export default function CampsiteImage({ src, seed, alt = "", className = "", tent = true }) {
  const [broken, setBroken] = useState(false);
  if (src && !broken)
    return <img src={src} alt={alt} loading="lazy" onError={() => setBroken(true)} className={`object-cover ${className}`} />;
  return <LandscapeArt seed={seed} tent={tent} className={className} label={alt || undefined} />;
}
