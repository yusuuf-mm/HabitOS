import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";

const BLOCK_ROWS = 24;
const BLOCK_COLS = 4;
const TOTAL = BLOCK_ROWS * BLOCK_COLS;

function SpatialGrid() {
  const blocks = useMemo(() => {
    return Array.from({ length: TOTAL }, (_, i) => {
      const row = Math.floor(i / BLOCK_COLS);
      const col = i % BLOCK_COLS;
      const delay = (row * 0.08 + col * 0.15).toFixed(2);
      const duration = (4 + Math.random() * 3).toFixed(2);
      const isActive = Math.random() > 0.6;
      return { row, col, delay, duration, isActive };
    });
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ perspective: "1200px" }}>
      {/* Perspective grid floor */}
      <div
        className="absolute inset-0 spatial-grid"
        style={{
          transform: "rotateX(60deg) translateZ(-100px)",
          transformOrigin: "center 120%",
          opacity: 0.4,
        }}
      />

      {/* Floating blocks */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div
          className="relative"
          style={{
            width: `${BLOCK_COLS * 52}px`,
            height: `${BLOCK_ROWS * 52}px`,
            transformStyle: "preserve-3d",
            transform: "rotateX(8deg) rotateY(-4deg)",
          }}
        >
          {blocks.map((b, i) => (
            <div
              key={i}
              className="absolute rounded-[3px] transition-all"
              style={{
                width: "44px",
                height: "44px",
                left: `${b.col * 52}px`,
                top: `${b.row * 52}px`,
                background: b.isActive
                  ? "linear-gradient(135deg, rgba(170,130,90,0.15), rgba(170,180,160,0.08))"
                  : "rgba(255,255,255,0.015)",
                border: b.isActive
                  ? "1px solid rgba(170,130,90,0.2)"
                  : "1px solid rgba(255,255,255,0.03)",
                animation: `glow-pulse ${b.duration}s ease-in-out ${b.delay}s infinite`,
                boxShadow: b.isActive
                  ? "0 0 20px rgba(170,130,90,0.06)"
                  : "none",
              }}
            />
          ))}
        </div>
      </div>

      {/* Radial ambient glow */}
      <div
        className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(170,130,90,0.06) 0%, transparent 60%)",
          filter: "blur(80px)",
        }}
      />
    </div>
  );
}

function MomentumCurve() {
  return (
    <svg
      className="absolute bottom-0 left-0 w-full h-48 opacity-[0.08]"
      viewBox="0 0 1200 200"
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="curve-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgb(170,130,90)" stopOpacity="0" />
          <stop offset="30%" stopColor="rgb(170,130,90)" stopOpacity="0.6" />
          <stop offset="70%" stopColor="rgb(170,180,160)" stopOpacity="0.4" />
          <stop offset="100%" stopColor="rgb(170,180,160)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0,180 C200,160 300,40 500,80 C700,120 800,20 1000,60 C1100,80 1150,50 1200,40"
        fill="none"
        stroke="url(#curve-gradient)"
        strokeWidth="2"
      />
      <path
        d="M0,180 C200,160 300,40 500,80 C700,120 800,20 1000,60 C1100,80 1150,50 1200,40 L1200,200 L0,200 Z"
        fill="url(#curve-gradient)"
        opacity="0.15"
      />
    </svg>
  );
}

export default function Landing() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="relative min-h-[100dvh] bg-[#050505] overflow-hidden grain">
      {/* Spatial grid backdrop */}
      <SpatialGrid />

      {/* Content layer */}
      <div className="relative z-10 flex min-h-[100dvh] flex-col items-center justify-center px-6">
        {/* Top nav bar — floating pill */}
        <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
          <div className="glass-card rounded-full px-6 py-2.5 flex items-center gap-6">
            <span className="font-serif text-lg text-white/90 tracking-tight">HabitOS</span>
            <div className="h-4 w-px bg-white/10" />
            <Link
              to="/login"
              className="text-sm text-white/50 hover:text-white/90 transition-colors duration-300"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="text-sm text-[#050505] bg-white/90 hover:bg-white rounded-full px-4 py-1.5 font-medium transition-all duration-300 hover:scale-[1.02]"
            >
              Get started
            </Link>
          </div>
        </nav>

        {/* Hero content */}
        <div
          className={`text-center max-w-4xl transition-all duration-1000 ${
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          {/* Eyebrow tag */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-1.5 mb-8">
            <div className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-subtle" />
            <span className="text-[11px] uppercase tracking-[0.2em] text-white/40 font-medium">
              96 discrete blocks. One optimized day.
            </span>
          </div>

          {/* Main headline */}
          <h1 className="font-serif text-display md:text-[5.5rem] leading-[1.02] tracking-[-0.03em] text-white mb-6">
            Your day, mathematically
            <br />
            <span className="gradient-text-chrome">aligned to your purpose.</span>
          </h1>

          {/* Subheadline */}
          <p
            className={`text-lg md:text-xl text-white/35 max-w-2xl mx-auto mb-12 leading-relaxed transition-all duration-1000 delay-200 ${
              mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            HabitOS decomposes your 24 hours into 15-minute blocks and solves a
            combinatorial optimization — placing every behavior where it
            creates the most impact.
          </p>

          {/* CTA buttons */}
          <div
            className={`flex flex-col sm:flex-row items-center justify-center gap-4 transition-all duration-1000 delay-300 ${
              mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            <Link
              to="/register"
              className="group relative inline-flex items-center gap-3 rounded-full bg-white px-8 py-4 text-[#050505] font-semibold text-base transition-all duration-500 hover:scale-[1.03] hover:shadow-[0_0_40px_rgba(255,255,255,0.1)]"
            >
              Start optimizing
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[#050505]/5 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
                </svg>
              </span>
            </Link>

            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-8 py-4 text-white/60 hover:text-white/90 hover:border-white/20 transition-all duration-300 text-base"
            >
              Sign in to your workspace
            </Link>
          </div>
        </div>

        {/* Momentum curve — decorative */}
        <MomentumCurve />

        {/* Bottom gradient fade */}
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#050505] to-transparent" />
      </div>
    </div>
  );
}
