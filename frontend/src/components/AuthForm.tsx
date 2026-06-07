import { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, Loader2, AlertCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface AuthFormProps {
  mode: "login" | "register";
  onSubmit: (data: { email: string; password: string; name?: string }) => Promise<{ success: boolean; error?: string }>;
  isLoading?: boolean;
}

export function AuthForm({ mode, onSubmit, isLoading = false }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const result = await onSubmit({
      email,
      password,
      ...(mode === "register" ? { name } : {}),
    });

    if (!result.success && result.error) {
      setError(result.error);
    }
  };

  const isLogin = mode === "login";

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-white/90 tracking-tight mb-2">
          {isLogin ? "Welcome back" : "Create your account"}
        </h1>
        <p className="text-sm text-white/30">
          {isLogin
            ? "Sign in to continue to HabitOS"
            : "Start optimizing your behaviors today"}
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 flex items-center gap-2.5 rounded-xl border border-red-500/20 bg-red-500/[0.06] px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        {mode === "register" && (
          <div className="space-y-2">
            <Label htmlFor="name" className="text-xs uppercase tracking-widest text-white/30 font-medium">
              Full Name
            </Label>
            <Input
              id="name"
              type="text"
              placeholder="Alex Chen"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={isLoading}
              className="input-glow h-12 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-white/20 rounded-xl focus:bg-white/[0.06]"
            />
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="email" className="text-xs uppercase tracking-widest text-white/30 font-medium">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isLoading}
            className="input-glow h-12 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-white/20 rounded-xl focus:bg-white/[0.06]"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password" className="text-xs uppercase tracking-widest text-white/30 font-medium">
            Password
          </Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              className="input-glow h-12 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-white/20 rounded-xl pr-11 focus:bg-white/[0.06]"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/25 hover:text-white/60 transition-colors"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <Button
          type="submit"
          className={cn(
            "w-full h-12 rounded-xl font-semibold text-sm",
            "bg-white text-[#050505] hover:bg-white/90",
            "transition-all duration-300 hover:shadow-[0_0_30px_rgba(255,255,255,0.08)]",
            "active:scale-[0.98]"
          )}
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {isLogin ? "Signing in..." : "Creating account..."}
            </>
          ) : (
            <span className="flex items-center justify-center gap-2">
              {isLogin ? "Sign in" : "Create account"}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </span>
          )}
        </Button>
      </form>

      {/* Demo hint */}
      {isLogin && (
        <div className="mt-5 rounded-xl border border-white/[0.05] bg-white/[0.02] p-3 text-center text-xs text-white/25">
          <span className="font-medium text-white/35">Demo:</span> demo@habitos.io / demo123
        </div>
      )}

      {/* Footer link */}
      <p className="mt-8 text-center text-sm text-white/25">
        {isLogin ? (
          <>
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              className="font-medium text-white/60 hover:text-white transition-colors"
            >
              Sign up
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-white/60 hover:text-white transition-colors"
            >
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
