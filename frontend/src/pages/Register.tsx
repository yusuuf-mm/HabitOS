import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/hooks/useAuth";
import { Navigate, Link } from "react-router-dom";
import { useEffect, useState } from "react";

export default function Register() {
  const { register, isAuthenticated, isLoading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 80);
    return () => clearTimeout(t);
  }, []);

  if (isAuthenticated && !isLoading) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="relative min-h-[100dvh] bg-[#050505] flex items-center justify-center overflow-hidden grain">
      {/* Ambient spatial backdrop */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(170,180,160,0.05) 0%, transparent 60%)",
            filter: "blur(60px)",
          }}
        />
        <div
          className="absolute inset-0 spatial-grid opacity-30"
          style={{
            transform: "perspective(1000px) rotateX(40deg)",
            transformOrigin: "center 100%",
          }}
        />
      </div>

      {/* Floating pill nav */}
      <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
        <div className="glass-card rounded-full px-6 py-2.5 flex items-center gap-4">
          <Link to="/" className="font-serif text-lg text-white/90 tracking-tight hover:text-white transition-colors">
            HabitOS
          </Link>
        </div>
      </nav>

      {/* Glassmorphic register card */}
      <div
        className={`relative z-10 w-full max-w-md mx-4 transition-all duration-700 ${
          mounted ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-6 scale-[0.98]"
        }`}
      >
        <div className="rounded-[1.5rem] p-[1px] bg-gradient-to-b from-white/10 via-white/[0.04] to-transparent">
          <div className="glass-card-strong rounded-[calc(1.5rem-1px)] p-8 md:p-10">
            <div className="flex items-center gap-2.5 mb-8">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.06] border border-white/[0.06]">
                <svg className="h-4.5 w-4.5 text-white/70" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <span className="font-serif text-xl text-white/90">HabitOS</span>
            </div>

            <AuthForm
              mode="register"
              onSubmit={async ({ email, password, name }) => {
                return await register({ email, password, name: name || "" });
              }}
              isLoading={isLoading}
            />
          </div>
        </div>

        <div
          className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-3/4 h-16 rounded-full opacity-30"
          style={{
            background: "radial-gradient(ellipse, rgba(170,180,160,0.15), transparent 70%)",
            filter: "blur(20px)",
          }}
        />
      </div>
    </div>
  );
}
