import LandscapeArt from "../components/LandscapeArt";

/** Split layout: illustration on the left (desktop), form card on the right. */
export default function AuthLayout({ children }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden lg:block">
        <LandscapeArt seed={3} mood="dawn" className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-navy-900/70 to-transparent p-12 text-white">
          <p className="max-w-md text-3xl font-extrabold leading-tight">Explore Thailand's campsites with people who love them too.</p>
          <p className="mt-3 max-w-md text-white/85">Find a campsite, join a trip, and read reviews written only by people who were actually there.</p>
        </div>
      </aside>
      <main className="flex items-center justify-center bg-white px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">{children}</div>
      </main>
    </div>
  );
}
