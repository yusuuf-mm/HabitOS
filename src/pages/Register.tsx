import { AuthForm } from "@/components/AuthForm";
import { useAuth } from "@/hooks/useAuth";
import { Sparkles } from "lucide-react";
import { Navigate } from "react-router-dom";

export default function Register() {
  const { register, isAuthenticated, isLoading } = useAuth();

  if (isAuthenticated && !isLoading) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex min-h-screen">
      {/* Left Panel - Branding */}
      <div className="hidden w-1/2 bg-sidebar lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sidebar-primary">
            <Sparkles className="h-5 w-5 text-sidebar-primary-foreground" />
          </div>
          <span className="text-xl font-semibold text-sidebar-foreground">
            HabitOS
          </span>
        </div>

        <div className="space-y-6">
          <h2 className="text-4xl font-semibold leading-tight text-sidebar-foreground">
            Start your journey
            <br />
            <span className="gradient-text">to optimization.</span>
          </h2>
          <p className="text-lg text-sidebar-foreground/70">
            Join thousands of high-performers who have transformed their habits
            into a systematic approach to daily excellence.
          </p>
        </div>

        <p className="text-sm text-sidebar-foreground/50">
          © 2024 HabitOS. All rights reserved.
        </p>
      </div>

      {/* Right Panel - Form */}
      <div className="flex flex-1 items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-sm">
          {/* Mobile Logo */}
          <div className="mb-8 flex items-center justify-center gap-2 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent">
              <Sparkles className="h-4 w-4 text-accent-foreground" />
            </div>
            <span className="text-lg font-semibold text-foreground">HabitOS</span>
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
    </div>
  );
}
