import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Behaviors from "@/pages/Behaviors";
import Optimization from "@/pages/Optimization";
import Schedule from "@/pages/Schedule";
import History from "@/pages/History";
import NotFound from "@/pages/NotFound";

export function AppRouter() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected Routes */}
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/behaviors" element={<Behaviors />} />
        <Route path="/optimization" element={<Optimization />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/history" element={<History />} />
      </Route>

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
