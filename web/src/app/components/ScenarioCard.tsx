"use client";

import { motion } from "framer-motion";
import { Play, ShieldCheck, ShieldAlert } from "lucide-react";

export interface Scenario {
  id: string;
  title: string;
  description: string;
  prompt: string;
  type: "safe" | "dangerous";
}

export default function ScenarioCard({
  scenario,
  onRun,
  isRunning,
  isActive,
}: {
  scenario: Scenario;
  onRun: (scenario: Scenario) => void;
  isRunning: boolean;
  isActive: boolean;
}) {
  const isSafe = scenario.type === "safe";

  return (
    <div
      className={`relative p-3 rounded-lg border cursor-pointer transition-all overflow-hidden ${
        isActive
          ? isSafe
            ? "border-emerald-500 bg-emerald-950/30"
            : "border-red-500 bg-red-950/30"
          : "border-gray-800 bg-gray-900/50 hover:border-gray-700"
      }`}
      onClick={() => !isRunning && onRun(scenario)}
    >
      <div className="flex items-center gap-2 mb-1.5">
        {isSafe ? (
          <ShieldCheck size={14} className="text-emerald-400 flex-shrink-0" />
        ) : (
          <ShieldAlert size={14} className="text-red-400 flex-shrink-0" />
        )}
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
            isSafe
              ? "bg-emerald-900/50 text-emerald-300"
              : "bg-red-900/50 text-red-300"
          }`}
        >
          {isSafe ? "SAFE" : "DANGEROUS"}
        </span>
        <button
          disabled={isRunning}
          className={`ml-auto flex-shrink-0 p-1.5 rounded transition-colors ${
            isRunning
              ? "bg-gray-800 text-gray-600 cursor-not-allowed"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white"
          }`}
        >
          <Play size={12} />
        </button>
      </div>
      <h3 className="text-xs font-semibold text-white">{scenario.title}</h3>
      <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{scenario.description}</p>
      <code className="block text-[10px] text-gray-600 mt-1.5 p-1.5 bg-gray-900/80 rounded border border-gray-800/50 truncate">
        {scenario.prompt}
      </code>
    </div>
  );
}
