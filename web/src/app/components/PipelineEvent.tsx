"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, ShieldAlert, ShieldCheck, AlertTriangle, ChevronDown } from "lucide-react";

export interface PipelineEventData {
  type: string;
  detail: string;
  status: "success" | "blocked" | "info" | "warning";
  timestamp?: string;
}

const statusConfig = {
  success: {
    icon: ShieldCheck,
    bg: "bg-emerald-950/50",
    border: "border-emerald-700/50",
    text: "text-emerald-400",
    dot: "bg-emerald-400",
  },
  blocked: {
    icon: ShieldAlert,
    bg: "bg-red-950/50",
    border: "border-red-700/50",
    text: "text-red-400",
    dot: "bg-red-400",
  },
  info: {
    icon: Shield,
    bg: "bg-blue-950/50",
    border: "border-blue-700/50",
    text: "text-blue-400",
    dot: "bg-blue-400",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-amber-950/50",
    border: "border-amber-700/50",
    text: "text-amber-400",
    dot: "bg-amber-400",
  },
};

function formatJson(str: string): string {
  try {
    const parsed = JSON.parse(str);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return str;
  }
}

export default function PipelineEvent({
  event,
  index,
}: {
  event: PipelineEventData;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const config = statusConfig[event.status];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1, duration: 0.2 }}
      className={`rounded-md border cursor-pointer transition-colors hover:brightness-110 ${config.bg} ${config.border}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2 px-2.5 py-2">
        <div className={`flex-shrink-0 ${config.text}`}>
          <Icon size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-xs font-medium ${config.text}`}>{event.type}</div>
          {!expanded && (
            <div className="text-[11px] text-gray-500 truncate">{event.detail}</div>
          )}
        </div>
        <ChevronDown
          size={12}
          className={`flex-shrink-0 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <pre className="text-[11px] text-gray-300 px-3 pb-2.5 pt-0.5 whitespace-pre-wrap break-all font-mono leading-relaxed border-t border-gray-700/30 mt-0.5">
              {formatJson(event.detail)}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
