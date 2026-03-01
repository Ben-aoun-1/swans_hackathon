"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getClioStatus } from "@/lib/api";

export function ClioStatusBadge() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    getClioStatus()
      .then((s) => setConnected(s.has_access_token))
      .catch(() => setConnected(false));
  }, []);

  // Don't render until we know the status
  if (connected === null) return null;

  return (
    <Link href="/settings" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
      <div
        className={`h-2 w-2 rounded-full ${
          connected
            ? "bg-emerald-400 animate-pulse-slow"
            : "bg-red-400"
        }`}
      />
      <span className="text-xs text-slate-400">
        {connected ? "Clio Connected" : "Clio Disconnected"}
      </span>
    </Link>
  );
}
