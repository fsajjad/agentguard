"use client";

import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, ArrowRight, Ban, Zap, FileText } from "lucide-react";

export interface LogEntry {
  timestamp: string;
  action: string;
  tool: string;
  params: string;
  outcome: "allowed" | "blocked" | "failed";
  reason?: string;
  risk_score?: number;
}

const outcomeConfig = {
  allowed: {
    icon: ShieldCheck,
    label: "ALLOWED",
    bg: "bg-emerald-950/40",
    border: "border-emerald-800/50",
    badge: "bg-emerald-900/60 text-emerald-300",
    text: "text-emerald-400",
  },
  blocked: {
    icon: ShieldAlert,
    label: "BLOCKED",
    bg: "bg-red-950/40",
    border: "border-red-800/50",
    badge: "bg-red-900/60 text-red-300",
    text: "text-red-400",
  },
  failed: {
    icon: Ban,
    label: "FAILED",
    bg: "bg-amber-950/40",
    border: "border-amber-800/50",
    badge: "bg-amber-900/60 text-amber-300",
    text: "text-amber-400",
  },
};

export default function ActivityLog({ logs }: { logs: LogEntry[] }) {
  if (logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        <div className="text-center">
          <FileText size={28} className="mx-auto mb-2 text-gray-700" />
          <p>Activity log will appear here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
      {logs.map((log, i) => {
        const config = outcomeConfig[log.outcome];
        const Icon = config.icon;

        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.25 }}
            className={`p-3 rounded-lg border ${config.bg} ${config.border}`}
          >
            {/* Header row */}
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-2">
                <Icon size={14} className={config.text} />
                <span className="text-xs font-mono text-gray-500">{log.timestamp}</span>
              </div>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.badge}`}>
                {config.label}
              </span>
            </div>

            {/* Tool call details */}
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs text-gray-400">Agent called</span>
              <code className="text-xs font-mono font-semibold text-white bg-gray-800 px-1.5 py-0.5 rounded">
                {log.tool}
              </code>
              {log.risk_score !== undefined && (
                <span className={`text-[10px] px-1 py-0.5 rounded ${
                  log.risk_score >= 0.7 ? "bg-red-900/50 text-red-300" :
                  log.risk_score >= 0.4 ? "bg-amber-900/50 text-amber-300" :
                  "bg-gray-800 text-gray-400"
                }`}>
                  risk: {log.risk_score.toFixed(1)}
                </span>
              )}
            </div>

            {/* Parameters */}
            <div className="text-[11px] text-gray-500 font-mono pl-4 mb-1 truncate">
              <ArrowRight size={10} className="inline mr-1" />
              {log.params}
            </div>

            {/* Outcome with reason */}
            {log.outcome === "blocked" && log.reason && (
              <div className="flex items-start gap-1.5 mt-2 pt-2 border-t border-red-900/30">
                <Zap size={11} className="text-red-400 mt-0.5 flex-shrink-0" />
                <span className="text-[11px] text-red-300/80">
                  <span className="font-semibold">Guard:</span> {log.reason}
                </span>
              </div>
            )}

            {log.outcome === "allowed" && (
              <div className="flex items-start gap-1.5 mt-2 pt-2 border-t border-emerald-900/30">
                <Zap size={11} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                <span className="text-[11px] text-emerald-300/80">
                  <span className="font-semibold">Executed:</span> Tool ran successfully through circuit breaker
                </span>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
