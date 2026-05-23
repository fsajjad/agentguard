"use client";

import { motion } from "framer-motion";
import { Activity, Shield, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

export interface ResultData {
  session_state: string;
  actions_executed: number;
  actions_blocked: number;
  violations: string[];
  trust_score: number;
  audit_entries: number;
  audit_valid: boolean;
}

export default function ResultPanel({ result }: { result: ResultData | null }) {
  if (!result) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        <div className="text-center">
          <Shield size={32} className="mx-auto mb-2 text-gray-700" />
          <p>Run a scenario to see results</p>
        </div>
      </div>
    );
  }

  const trustColor =
    result.trust_score >= 0.9
      ? "text-emerald-400"
      : result.trust_score >= 0.7
      ? "text-amber-400"
      : "text-red-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-lg bg-gray-900 border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Trust Score</div>
          <div className={`text-2xl font-bold ${trustColor}`}>
            {(result.trust_score * 100).toFixed(0)}%
          </div>
        </div>
        <div className="p-3 rounded-lg bg-gray-900 border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">Session State</div>
          <div className="text-sm font-semibold text-white capitalize mt-1">
            {result.session_state}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-gray-900 border border-gray-800">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 size={14} className="text-emerald-400" />
            <span className="text-xs text-gray-500">Executed</span>
          </div>
          <div className="text-xl font-bold text-emerald-400 mt-1">
            {result.actions_executed}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-gray-900 border border-gray-800">
          <div className="flex items-center gap-1.5">
            <XCircle size={14} className="text-red-400" />
            <span className="text-xs text-gray-500">Blocked</span>
          </div>
          <div className="text-xl font-bold text-red-400 mt-1">
            {result.actions_blocked}
          </div>
        </div>
      </div>

      {result.violations.length > 0 && (
        <div className="p-3 rounded-lg bg-red-950/30 border border-red-900/50">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle size={14} className="text-red-400" />
            <span className="text-xs font-medium text-red-400">
              Violations ({result.violations.length})
            </span>
          </div>
          <div className="space-y-1">
            {result.violations.map((v, i) => (
              <div key={i} className="text-xs text-red-300/80 pl-5">
                • {v}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="p-3 rounded-lg bg-gray-900 border border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Activity size={14} className="text-blue-400" />
            <span className="text-xs text-gray-500">Audit Log</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">
              {result.audit_entries} entries
            </span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${
                result.audit_valid
                  ? "bg-emerald-900/50 text-emerald-400"
                  : "bg-red-900/50 text-red-400"
              }`}
            >
              {result.audit_valid ? "VALID" : "TAMPERED"}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
