"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Settings,
  Plug,
  PlugZap,
  Play,
  Shield,
  Database,
  FileText,
  Layers,
  User,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getClioStatus,
  getClioAuthUrl,
  checkClioSetup,
  runClioSetup,
  disconnectClio,
} from "@/lib/api";
import type { ClioStatus, SetupResult, SetupStep } from "@/lib/types";

const STEP_META: Record<string, { label: string; icon: typeof Settings }> = {
  authenticate: { label: "Authentication", icon: Shield },
  practice_area: { label: "Practice Area", icon: Layers },
  matter_stages: { label: "Matter Stages", icon: Database },
  custom_fields: { label: "Custom Fields", icon: FileText },
  document_template: { label: "Document Template", icon: FileText },
};

function StepStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case "error":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "skipped":
      return <AlertTriangle className="h-4 w-4 text-amber-500" />;
    default:
      return <Loader2 className="h-4 w-4 text-slate-400 animate-spin" />;
  }
}

export default function SettingsPage() {
  const [clioStatus, setClioStatus] = useState<ClioStatus | null>(null);
  const [setupResult, setSetupResult] = useState<SetupResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await getClioStatus();
      setClioStatus(status);
      if (status.has_access_token) {
        setChecking(true);
        const check = await checkClioSetup();
        setSetupResult(check);
        setChecking(false);
      } else {
        setSetupResult(null);
      }
    } catch {
      // Backend not running or not connected
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleConnect = async () => {
    try {
      const url = await getClioAuthUrl();
      window.location.href = url;
    } catch {
      // error
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectClio();
      setClioStatus({ has_access_token: false, has_refresh_token: false, tokens_file_exists: false, access_token_preview: null });
      setSetupResult(null);
    } catch {
      // error
    }
  };

  const handleCheck = async () => {
    setChecking(true);
    try {
      const result = await checkClioSetup();
      setSetupResult(result);
    } catch {
      // error
    } finally {
      setChecking(false);
    }
  };

  const handleRunSetup = async () => {
    setRunning(true);
    try {
      const result = await runClioSetup();
      setSetupResult(result);
    } catch {
      // error
    } finally {
      setRunning(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    setSetupResult(null);
    await fetchStatus();
  };

  const isConnected = clioStatus?.has_access_token ?? false;

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-56px)] flex items-center justify-center">
        <Loader2 className="h-6 w-6 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-56px)] bg-slate-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8 animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-slate-900 flex items-center justify-center">
              <Settings className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <h1 className="font-serif text-2xl text-slate-900">Settings</h1>
              <p className="text-sm text-slate-500">
                Connect your Clio account to get started
              </p>
            </div>
          </div>
        </div>

        {/* Connection Card */}
        <Card className="border-slate-200 shadow-sm overflow-hidden mb-6 animate-fade-in-up">
          <div className="px-6 py-4 bg-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isConnected ? (
                <PlugZap className="h-5 w-5 text-emerald-500" />
              ) : (
                <Plug className="h-5 w-5 text-slate-400" />
              )}
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  Clio Manage
                </p>
                <p className="text-xs text-slate-400">
                  {isConnected
                    ? `Connected (${setupResult?.attorney_name || "loading..."})`
                    : "Not connected - connect your account below"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`h-2.5 w-2.5 rounded-full ${
                  isConnected ? "bg-emerald-400 animate-pulse-slow" : "bg-red-400"
                }`}
              />
              {isConnected ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefresh}
                    className="text-xs"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Refresh
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDisconnect}
                    className="text-xs text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                  >
                    <LogOut className="h-3 w-3 mr-1" />
                    Disconnect
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  onClick={handleConnect}
                  className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold"
                >
                  <ExternalLink className="h-3 w-3 mr-1" />
                  Connect
                </Button>
              )}
            </div>
          </div>
        </Card>

        {/* Setup Status */}
        {isConnected && (
          <div className="animate-fade-in-up">
            {/* Attorney Info */}
            {setupResult?.attorney_name && (
              <Card className="border-slate-200 shadow-sm overflow-hidden mb-6">
                <div className="px-6 py-4 bg-white flex items-center gap-3">
                  <User className="h-5 w-5 text-slate-400" />
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {setupResult.attorney_name}
                    </p>
                    <p className="text-xs text-slate-400">
                      Responsible Attorney (ID: {setupResult.attorney_id})
                    </p>
                  </div>
                </div>
              </Card>
            )}

            {/* Configuration Check */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Account Configuration
                </h2>
                {setupResult?.ready && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-semibold border border-emerald-200">
                    <CheckCircle2 className="h-3 w-3" />
                    Ready
                  </span>
                )}
              </div>
              <div className="h-px flex-1 bg-slate-200 ml-3" />
            </div>

            {checking ? (
              <Card className="border-slate-200 shadow-sm">
                <div className="px-6 py-8 flex flex-col items-center gap-3">
                  <Loader2 className="h-6 w-6 text-amber-500 animate-spin" />
                  <p className="text-sm text-slate-500">
                    Checking Clio configuration...
                  </p>
                </div>
              </Card>
            ) : setupResult ? (
              <>
                <Card className="border-slate-200 shadow-sm overflow-hidden divide-y divide-slate-100">
                  {setupResult.steps.map((step: SetupStep) => {
                    const meta = STEP_META[step.name] || {
                      label: step.name,
                      icon: Settings,
                    };
                    const Icon = meta.icon;
                    return (
                      <div
                        key={step.name}
                        className="px-5 py-3.5 flex items-center gap-3"
                      >
                        <Icon className="h-4 w-4 text-slate-300 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800">
                            {meta.label}
                          </p>
                          {step.detail && (
                            <p className="text-xs text-slate-400 mt-0.5 truncate">
                              {step.detail}
                            </p>
                          )}
                        </div>
                        <StepStatusIcon status={step.status} />
                      </div>
                    );
                  })}
                </Card>

                {/* Missing Items */}
                {setupResult.missing_items.length > 0 && (
                  <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      <p className="text-sm font-semibold text-amber-800">
                        {setupResult.missing_items.length} item
                        {setupResult.missing_items.length > 1 ? "s" : ""} missing
                      </p>
                    </div>
                    <ul className="space-y-1">
                      {setupResult.missing_items.map((item, i) => (
                        <li
                          key={i}
                          className="text-xs text-amber-700 flex items-center gap-1.5"
                        >
                          <span className="h-1 w-1 rounded-full bg-amber-400 shrink-0" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="mt-6 flex items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCheck}
                    disabled={checking}
                    className="text-xs"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Re-check
                  </Button>

                  {!setupResult.ready && (
                    <Button
                      size="sm"
                      onClick={handleRunSetup}
                      disabled={running}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold gap-1.5"
                    >
                      {running ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Configuring...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Auto-Configure Clio
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <Card className="border-slate-200 shadow-sm">
                <div className="px-6 py-8 flex flex-col items-center gap-3">
                  <p className="text-sm text-slate-500">
                    Could not check configuration
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCheck}
                    className="text-xs"
                  >
                    Try Again
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Not Connected State */}
        {!isConnected && (
          <Card className="border-slate-200 shadow-sm animate-fade-in-up">
            <div className="px-6 py-12 flex flex-col items-center gap-4 text-center">
              <div className="h-14 w-14 rounded-2xl bg-slate-100 flex items-center justify-center">
                <Plug className="h-7 w-7 text-slate-400" />
              </div>
              <div>
                <p className="text-base font-semibold text-slate-700">
                  Connect your Clio Account
                </p>
                <p className="text-sm text-slate-400 mt-1 max-w-sm">
                  Sign in with your Clio Manage account to get started.
                  The setup agent will configure everything automatically.
                </p>
              </div>
              <Button
                onClick={handleConnect}
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold gap-2 mt-2"
              >
                <ExternalLink className="h-4 w-4" />
                Connect to Clio
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
