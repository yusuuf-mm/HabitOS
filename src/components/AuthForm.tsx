import { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
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
    <div className="w-full max-w-sm">
      {/* Header */}
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {isLogin ? "Welcome back" : "Create your account"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {isLogin
            ? "Sign in to continue to HabitOS"
            : "Start optimizing your behaviors today"}
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "register" && (
          <div className="space-y-2">
            <Label htmlFor="name">Full Name</Label>
            <Input
              id="name"
              type="text"
              placeholder="Alex Chen"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={isLoading}
              className="input-focus"
            />
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isLoading}
            className="input-focus"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              className="input-focus pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              tabIndex={-1}
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        <Button
          type="submit"
          className={cn(
            "w-full",
            "bg-accent text-accent-foreground hover:bg-accent/90"
          )}
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {isLogin ? "Signing in..." : "Creating account..."}
            </>
          ) : (
            <>{isLogin ? "Sign in" : "Create account"}</>
          )}
        </Button>
      </form>

      {/* Demo credentials hint for login */}
      {isLogin && (
        <div className="mt-4 rounded-lg border border-border bg-muted/50 p-3 text-center text-xs text-muted-foreground">
          <span className="font-medium">Demo:</span> demo@habitos.io / demo123
        </div>
      )}

      {/* Footer link */}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {isLogin ? (
          <>
            Don't have an account?{" "}
            <Link
              to="/register"
              className="font-medium text-accent hover:underline"
            >
              Sign up
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-accent hover:underline"
            >
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
