import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CircleUserRound, Menu, X } from "lucide-react";
import { HabitOSLogo } from "@/components/HabitOSLogo";
import heroDay from "@/data/heroDay.json";
import { useAuth } from "@/hooks/useAuth";

const VIDEO_URL =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260715_082433_69699cf8-444b-4484-93cc-053e57896dfd.mp4";

const TRIANGLE_DOTS: Array<[number, number]> = [
  [8, 0],
  [4, 6],
  [12, 6],
  [0, 12],
  [8, 12],
  [16, 12],
  [0, 18],
  [8, 18],
  [16, 18],
];

export default function Landing() {
  const { isAuthenticated } = useAuth();
  const primaryTarget = isAuthenticated ? "/dashboard" : "/register";
  const accountTarget = isAuthenticated ? "/dashboard" : "/login";

  const [menuOpen, setMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduceMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (reduceMotion) {
      videoRef.current?.pause();
    }
  }, [reduceMotion]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [menuOpen]);

  return (
    <div className="relative flex h-[100dvh] flex-col overflow-hidden bg-[#07090f] text-white">
      <video
        ref={videoRef}
        src={VIDEO_URL}
        autoPlay={!reduceMotion}
        muted
        loop
        playsInline
        poster="/landing-poster.jpg"
        aria-hidden="true"
        tabIndex={-1}
        className="absolute inset-0 h-full w-full object-cover object-[68%_center] max-sm:object-center"
      />

      <div className="absolute inset-0 bg-black/40">
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/25 to-black/40" />
        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-black/55 to-transparent" />
      </div>

      <nav className="relative z-20 flex items-center justify-between px-5 pt-6 sm:px-8 sm:pt-8 md:px-16 lg:px-20">
        <Link to="/" className="flex items-center gap-2.5">
          <HabitOSLogo className="h-8 w-8 text-white md:h-9 md:w-9" />
          <span className="font-semibold tracking-tight">HabitOS</span>
        </Link>

        <div className="liquid-glass hidden rounded-full px-8 py-3 md:flex md:gap-8">
          <Link to="/dashboard" className="text-sm font-medium text-white">
            Dashboard
          </Link>
          <Link
            to="/behaviors"
            className="text-sm font-medium text-white/70 hover:text-white"
          >
            Habits
          </Link>
          <Link
            to="/schedule"
            className="text-sm font-medium text-white/70 hover:text-white"
          >
            Schedule
          </Link>
        </div>

        <div className="flex items-center">
          <Link
            to={accountTarget}
            className="liquid-glass hidden h-10 w-10 place-items-center rounded-full bg-black/20 md:grid"
            aria-label={isAuthenticated ? "Open dashboard" : "Sign in"}
          >
            <CircleUserRound className="h-5 w-5 text-white/80" strokeWidth={1.5} />
          </Link>

          <button
            ref={menuButtonRef}
            type="button"
            className="liquid-glass relative z-50 grid h-10 w-10 place-items-center rounded-full bg-black/20 md:hidden"
            aria-expanded={menuOpen}
            aria-controls="landing-mobile-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Menu
              className={`absolute h-5 w-5 transition duration-300 ${
                menuOpen ? "rotate-90 scale-0 opacity-0" : "rotate-0 scale-100 opacity-100"
              }`}
            />
            <X
              className={`absolute h-5 w-5 transition duration-300 ${
                menuOpen ? "rotate-0 scale-100 opacity-100" : "rotate-90 scale-0 opacity-0"
              }`}
            />
          </button>
        </div>
      </nav>

      <div
        id="landing-mobile-menu"
        className={`fixed inset-0 z-10 bg-black/80 backdrop-blur-xl transition-opacity duration-500 md:hidden ${
          menuOpen ? "visible opacity-100" : "invisible pointer-events-none opacity-0"
        }`}
      >
        <div
          className={`flex h-full flex-col items-center justify-center gap-8 transition duration-500 ${
            menuOpen ? "translate-y-0" : "-translate-y-8"
          }`}
        >
          <Link
            to="/dashboard"
            className="text-2xl font-medium"
            onClick={() => setMenuOpen(false)}
          >
            Dashboard
          </Link>
          <Link
            to="/behaviors"
            className="text-2xl font-medium"
            onClick={() => setMenuOpen(false)}
          >
            Habits
          </Link>
          <Link
            to="/schedule"
            className="text-2xl font-medium"
            onClick={() => setMenuOpen(false)}
          >
            Schedule
          </Link>
          <Link
            to={accountTarget}
            className="flex items-center gap-3"
            onClick={() => setMenuOpen(false)}
          >
            <span className="liquid-glass grid h-10 w-10 place-items-center rounded-full">
              <CircleUserRound className="h-5 w-5 text-white/80" strokeWidth={1.5} />
            </span>
            <span className="text-sm font-light text-white/60">
              {isAuthenticated ? "Open dashboard" : "Sign in to your account"}
            </span>
          </Link>
        </div>
      </div>

      <main
        className={`relative z-10 flex flex-1 flex-col justify-between px-5 pb-8 sm:px-8 sm:pb-10 md:px-16 lg:px-20 ${
          reduceMotion ? "transition-none" : "transition duration-700"
        } ${
          menuOpen
            ? "pointer-events-none opacity-0"
            : mounted
              ? "opacity-100"
              : reduceMotion
                ? "opacity-100"
                : "translate-y-4 opacity-0"
        }`}
      >
        <div className="mt-10 max-w-2xl sm:mt-14 md:mt-20">
          <div className="liquid-glass mb-5 inline-flex items-center gap-2.5 rounded-full px-3 py-1.5 sm:mb-6 sm:gap-3 sm:px-4 sm:py-2">
            <span
              className={`h-1.5 w-1.5 rounded-full bg-emerald-300 ${
                reduceMotion ? "" : "animate-pulse"
              }`}
            />
            <span className="text-xs font-light text-white/80 sm:text-sm">
              One real day · solved in {heroDay.cells.length} blocks
            </span>
          </div>

          <h1
            className="font-display text-4xl font-normal leading-[1.05] text-white sm:text-5xl md:text-6xl lg:text-7xl"
            style={{ letterSpacing: "-0.05em" }}
          >
            Find time for the habits
            <br />
            that matter.
          </h1>

          <p className="mt-4 text-sm font-light text-white/70 sm:mt-5 sm:text-base md:text-lg">
            HabitOS breaks your day into 15-minute blocks and finds the best slot
            for each habit. If the day shifts, the plan shifts with it.
          </p>

          <div className="mt-6 sm:mt-8">
            <Link
              to={primaryTarget}
              className="liquid-glass inline-flex rounded-full px-6 py-3 text-sm font-medium text-white transition duration-300 hover:bg-white/10 sm:px-7 sm:py-3.5"
            >
              {isAuthenticated ? "Go to your day" : "Start planning"}
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-2 items-end gap-6 sm:flex sm:gap-10 md:gap-16">
          <div>
            <div className="relative h-5 w-5" aria-hidden="true">
              {TRIANGLE_DOTS.map(([left, top], index) => (
                <span
                  key={index}
                  className="absolute h-[2.5px] w-[2.5px] bg-white/60"
                  style={{ left, top }}
                />
              ))}
            </div>
            <p className="mt-3 text-xl font-normal text-white sm:text-2xl md:text-3xl">
              {heroDay.cells.length} blocks
            </p>
            <p className="mt-1 text-xs font-light text-white/60 sm:text-sm">
              Fifteen minutes each, one whole day
            </p>
          </div>

          <div>
            <div className="grid w-fit grid-cols-3 gap-[2px]" aria-hidden="true">
              {Array.from({ length: 9 }, (_, index) => (
                <span
                  key={index}
                  className={`h-1 w-1 rounded-[1px] ${
                    index % 2 === 0 ? "bg-white/60" : "bg-white/0"
                  }`}
                />
              ))}
            </div>
            <p className="mt-3 text-xl font-normal text-white sm:text-2xl md:text-3xl">
              {heroDay.sessions.length} sessions
            </p>
            <p className="mt-1 text-xs font-light text-white/60 sm:text-sm">
              Placed by the solver in one real day
            </p>
          </div>

          <ul className="sr-only">
            {heroDay.sessions.map((session) => (
              <li key={`${session.name}-${session.start}`}>
                {session.name} at {session.start}
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
}
