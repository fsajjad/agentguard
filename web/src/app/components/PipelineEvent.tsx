"use client";

import { motion } from "framer-motion";
import { Shield, ShieldAlert, ShieldCheck, Zap, Clock, AlertTriangle } from "lucide-react";

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

export default function PipelineEvent({
  event,
  index,
}: {
  event: PipelineEventData;
  index: number;
}) {
  const config = statusConfig[event.status];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1, duration: 0.2 }}
      className={`flex items-center gap-2 px-2.5 py-2 rounded-md border ${config.bg} ${config.border}`}
    >
      <div className={`flex-shrink-0 ${config.text}`}>
        <Icon size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-xs font-medium ${config.text}`}>{event.type}</div>
        <div className="text-[11px] text-gray-500 truncate">{event.detail}</div>
      </div>
      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${config.dot}`} />
    </motion.div>
  );
}
