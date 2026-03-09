"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { createSession, startDemo, streamSessionEvents } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

// -- Types --

type PipelineStage = "Literature" | "Graph" | "Reasoning" | "Validation" | "Experiment" | "Complete";

const STAGES: PipelineStage[] = ["Literature", "Graph", "Reasoning", "Validation", "Experiment", "Complete"];

const STAGE_COLORS: Record<string, string> = {
  Literature: "#F59E0B",
  Graph: "#8B5CF6",
  Reasoning: "#3B82F6",
  Validation: "#10B981",
  Experiment: "#EC4899",
  Checkpoint: "#F97316",
  Complete: "#10B981",
};

interface StreamEvent {
  id: number;
  type: string;
  stage?: string;
  timestamp: string;
  message?: string;
  // checkpoint fields
  decision?: string;
  reason?: string;
  // pivot fields
  from_entity?: string;
  to_entity?: string;
  // hypothesis_scored fields
  title?: string;
  score?: number;
  hypothesis_id?: string;
  // stage_complete fields
  papers_found?: number;
  triples_extracted?: number;
  hypotheses_generated?: number;
  // triples_merged
  count?: number;
  // generic
  [key: string]: unknown;
}

interface LiveStats {
  papers: number;
  triples: number;
  hypotheses: number;
  pivots: number;
}

// -- Helpers --

function relativeTime(ts: string): string {
  try {
    const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 5) return "just now";
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  } catch {
    return "";
  }
}

function stageForEvent(ev: StreamEvent): string {
  if (ev.stage) return ev.stage;
  if (ev.type === "checkpoint" || ev.decision) return "Checkpoint";
  return "Reasoning";
}

function stageBadgeStyle(stage: string): React.CSSProperties {
  const color = STAGE_COLORS[stage] || "#64748B";
  return { backgroundColor: `${color}18`, color, borderColor: `${color}40` };
}

// -- Components --

const DEMOS = [
  { id: 1, label: "ADMET Validation", desc: "Riluzole for melanoma (fast)", query: "drug properties of riluzole for melanoma treatment" },
  { id: 2, label: "Multi-Tool Discovery", desc: "Glioblastoma repurposing (complex)", query: "novel therapeutic approaches for glioblastoma using repurposed compounds" },
  { id: 3, label: "Cloud Lab Failure", desc: "Metformin + Strateos error recovery", query: "experimental validation of metformin for pancreatic cancer" },
];

function PromptMode({ onSubmit, onDemo }: { onSubmit: (query: string) => void; onDemo: (demoId: number, query: string) => void }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) onSubmit(query.trim());
  }

  const DEMO_BORDER_COLORS = ["border-l-teal-500", "border-l-violet-500", "border-l-amber-500"];

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-2xl text-center"
      >
        <h1 className="mb-2 font-mono text-4xl font-bold tracking-tight text-teal-600">
          NEXUS
        </h1>
        <p className="mb-10 text-sm text-slate-500">
          Autonomous biological hypothesis generation powered by Swanson ABC traversal.
        </p>
        <form onSubmit={handleSubmit} className="relative">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask Nexus anything..."
            className="w-full rounded-2xl border border-slate-200 bg-white px-6 py-5 text-lg text-slate-800 shadow-md outline-none transition-all placeholder:text-slate-400 focus:border-teal-400 focus:shadow-lg focus:ring-4 focus:ring-teal-100"
          />
          <Button
            type="submit"
            disabled={!query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-teal-600 px-6 hover:bg-teal-700"
          >
            Discover
          </Button>
        </form>
        <p className="mt-4 text-sm text-slate-400">
          Try: &quot;ways to treat melanoma similar to riluzole&quot; or &quot;novel gene targets for Parkinson&apos;s Disease&quot;
        </p>

        <div className="mt-12">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Demo Scenarios
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            {DEMOS.map((demo, i) => (
              <button
                key={demo.id}
                onClick={() => onDemo(demo.id, demo.query)}
                className={`rounded-xl border border-slate-200 border-l-4 ${DEMO_BORDER_COLORS[i]} bg-white px-5 py-4 text-left shadow-sm transition-all hover:shadow-md`}
              >
                <span className="text-sm font-medium text-slate-700">{demo.label}</span>
                <span className="mt-1 block text-xs text-slate-400">{demo.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function EventCard({ event, index }: { event: StreamEvent; index: number }) {
  const stage = stageForEvent(event);
  const isCheckpoint = event.type === "checkpoint" || !!event.decision;
  const isPivot = event.type === "pivot";
  const isHypothesis = event.type === "hypothesis_scored";
  const isError = event.type === "experiment_error";
  const isProgress = event.type === "progress" || event.type === "status_update";
  const stageColor = STAGE_COLORS[stage] || "#64748B";

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.02, 0.1) }}
      className={`rounded-xl border-l-4 bg-white p-4 shadow-sm ${isError ? "border-l-red-500 bg-red-50/30" : ""} ${isProgress ? "opacity-60" : ""}`}
      style={!isError ? { borderLeftColor: stageColor } : undefined}
    >
      <div className="mb-2 flex items-center justify-between">
        <Badge
          variant="outline"
          className="text-xs font-medium"
          style={stageBadgeStyle(stage)}
        >
          {stage}
        </Badge>
        <span className="text-xs text-slate-400">{relativeTime(event.timestamp)}</span>
      </div>

      <p className="text-sm text-slate-700">
        {event.message || event.type.replace(/_/g, " ")}
      </p>

      {isCheckpoint && event.decision && (
        <div className="mt-3 rounded-md border px-3 py-2" style={{
          borderColor: event.decision === "CONTINUE" ? "#10B98140" : event.decision === "PIVOT" ? "#F9731640" : "#8B5CF640",
          backgroundColor: event.decision === "CONTINUE" ? "#10B98108" : event.decision === "PIVOT" ? "#F9731608" : "#8B5CF608",
        }}>
          <span className="text-xs font-semibold uppercase tracking-wide" style={{
            color: event.decision === "CONTINUE" ? "#10B981" : event.decision === "PIVOT" ? "#F97316" : "#8B5CF6",
          }}>
            {event.decision}
          </span>
          {event.reason && (
            <p className="mt-1 text-xs text-slate-500">{event.reason}</p>
          )}
        </div>
      )}

      {isPivot && event.from_entity && event.to_entity && (
        <div className="mt-3 flex items-center gap-2 text-sm">
          <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
            {event.from_entity}
          </span>
          <span className="text-slate-400">&rarr;</span>
          <span className="rounded bg-orange-50 px-2 py-0.5 font-mono text-xs text-orange-700">
            {event.to_entity}
          </span>
        </div>
      )}

      {isError && (
        <div className="mt-3 rounded-md border border-red-300 bg-red-50 px-3 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-red-600">
            Error
          </span>
          <p className="mt-1 text-xs text-red-700">{event.message}</p>
        </div>
      )}

      {isHypothesis && (
        <div className="mt-3 flex items-center justify-between rounded-md bg-emerald-50 px-3 py-2">
          <span className="text-xs font-medium text-slate-700">
            {event.title || "Hypothesis"}
          </span>
          {event.score !== undefined && (
            <Badge className="bg-emerald-100 text-emerald-700">
              {typeof event.score === "number" ? `${(event.score * 100).toFixed(0)}%` : event.score}
            </Badge>
          )}
        </div>
      )}
    </motion.div>
  );
}

function PipelineStepper({ currentStage, completed }: { currentStage: PipelineStage; completed: boolean }) {
  const currentIndex = completed ? STAGES.length - 1 : STAGES.indexOf(currentStage);

  return (
    <div className="space-y-1">
      {STAGES.map((stage, i) => {
        const isDone = i < currentIndex || completed;
        const isCurrent = i === currentIndex && !completed;
        const color = STAGE_COLORS[stage];

        return (
          <div key={stage} className="flex items-center gap-3 py-2">
            <div
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all"
              style={{
                backgroundColor: isDone || isCurrent ? color : "#F1F5F9",
                color: isDone || isCurrent ? "#fff" : "#94A3B8",
              }}
            >
              {isDone ? (
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                i + 1
              )}
            </div>
            <span
              className="text-sm font-medium transition-colors"
              style={{ color: isDone || isCurrent ? "#1E293B" : "#94A3B8" }}
            >
              {stage}
            </span>
            {isCurrent && (
              <motion.div
                className="ml-auto h-2 w-2 rounded-full"
                style={{ backgroundColor: color }}
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-mono text-2xl font-bold" style={{ color }}>{value}</p>
    </div>
  );
}

function StreamMode({
  events,
  stats,
  currentStage,
  completed,
  topHypothesisId,
  query,
  isReplicated,
}: {
  events: StreamEvent[];
  stats: LiveStats;
  currentStage: PipelineStage;
  completed: boolean;
  topHypothesisId: string | null;
  query: string;
  isReplicated: boolean;
}) {
  const feedRef = useRef<HTMLDivElement>(null);
  const [relativeNow, setRelativeNow] = useState(0);

  // Auto-scroll to latest event
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);

  // Tick for relative timestamps
  useEffect(() => {
    const interval = setInterval(() => setRelativeNow((n) => n + 1), 5000);
    return () => clearInterval(interval);
  }, []);

  // Suppress unused warning -- relativeNow drives re-renders for timestamp freshness
  void relativeNow;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="px-6 py-8"
    >
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-800">Agent Reasoning</h1>
          {completed ? (
            <Badge className="bg-emerald-100 text-emerald-700">Complete</Badge>
          ) : isReplicated ? (
            <Badge variant="outline" className="border-slate-300 text-slate-500 font-mono">Replicated</Badge>
          ) : (
            <Badge className="bg-teal-100 text-teal-700">Live</Badge>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-500">{query}</p>
      </div>

      {/* Two-panel layout */}
      <div className="flex gap-6" style={{ height: "calc(100vh - 12rem)" }}>
        {/* Left panel: Event stream */}
        <div className="flex w-[65%] flex-col">
          <Card className="flex flex-1 flex-col overflow-hidden rounded-xl shadow-sm">
            <CardHeader className="shrink-0 pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <span>Agent Reasoning Stream</span>
                <span className="text-xs font-normal text-slate-400">
                  {events.length} events
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden px-0">
              <div
                ref={feedRef}
                className="h-full space-y-3 overflow-y-auto px-4 pb-4"
              >
                <AnimatePresence initial={false}>
                  {events.length === 0 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex h-full items-center justify-center"
                    >
                      <div className="text-center">
                        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-teal-200 border-t-teal-600" />
                        <p className="text-sm text-slate-400">Initializing pipeline...</p>
                      </div>
                    </motion.div>
                  )}
                  {events.map((ev, i) => (
                    <EventCard key={ev.id} event={ev} index={i} />
                  ))}
                </AnimatePresence>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right panel: Summary sidebar */}
        <div className="flex w-[35%] flex-col gap-4">
          {/* Pipeline progress */}
          <Card className="rounded-xl shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Pipeline Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <PipelineStepper currentStage={currentStage} completed={completed} />
            </CardContent>
          </Card>

          {/* Live stats */}
          <Card className="rounded-xl shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Live Stats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="Papers Found" value={stats.papers} color="#F59E0B" />
                <StatCard label="Triples Extracted" value={stats.triples} color="#8B5CF6" />
                <StatCard label="Hypotheses" value={stats.hypotheses} color="#3B82F6" />
                <StatCard label="Pivots Taken" value={stats.pivots} color="#F97316" />
              </div>
            </CardContent>
          </Card>

          {/* Completion actions */}
          {completed && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <Card className="rounded-xl border-emerald-200 bg-emerald-50/50 shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base text-emerald-800">
                    Pipeline Complete
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-emerald-700">
                    Generated {stats.hypotheses} hypotheses from {stats.papers} papers.
                  </p>
                  <Separator />
                  <div className="flex flex-col gap-2">
                    {topHypothesisId && (
                      <Link href={`/hypothesis/${topHypothesisId}`}>
                        <Button className="w-full bg-emerald-600 hover:bg-emerald-700">
                          View Results
                        </Button>
                      </Link>
                    )}
                    <Link href="/graph">
                      <Button variant="outline" className="w-full">
                        View Graph
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// -- Main Page --

export default function DashboardPage() {
  const [mode, setMode] = useState<"prompt" | "stream">("prompt");
  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [stats, setStats] = useState<LiveStats>({ papers: 0, triples: 0, hypotheses: 0, pivots: 0 });
  const [currentStage, setCurrentStage] = useState<PipelineStage>("Literature");
  const [completed, setCompleted] = useState(false);
  const [topHypothesisId, setTopHypothesisId] = useState<string | null>(null);
  const eventCounter = useRef(0);

  const addEvent = useCallback((raw: Record<string, unknown>) => {
    const ev: StreamEvent = {
      ...raw,
      id: eventCounter.current++,
      type: String(raw.type || "unknown"),
      timestamp: String(raw.timestamp || new Date().toISOString()),
    } as StreamEvent;

    setEvents((prev) => [...prev, ev]);

    // Update state based on event type
    switch (ev.type) {
      case "stage_start":
        if (ev.stage) {
          const mapped = ev.stage.charAt(0).toUpperCase() + ev.stage.slice(1);
          if (STAGES.includes(mapped as PipelineStage)) {
            setCurrentStage(mapped as PipelineStage);
          }
        }
        break;

      case "stage_complete":
        if (ev.papers_found) setStats((s) => ({ ...s, papers: s.papers + ev.papers_found! }));
        if (ev.triples_extracted) setStats((s) => ({ ...s, triples: s.triples + ev.triples_extracted! }));
        if (ev.hypotheses_generated) setStats((s) => ({ ...s, hypotheses: s.hypotheses + ev.hypotheses_generated! }));
        break;

      case "triples_merged":
        if (ev.count) setStats((s) => ({ ...s, triples: s.triples + ev.count! }));
        break;

      case "pivot":
        setStats((s) => ({ ...s, pivots: s.pivots + 1 }));
        break;

      case "hypothesis_scored":
        setStats((s) => ({ ...s, hypotheses: s.hypotheses + 1 }));
        if (ev.hypothesis_id && !topHypothesisId) {
          setTopHypothesisId(ev.hypothesis_id);
        }
        break;

      case "pipeline_complete":
      case "session_complete":
        setCompleted(true);
        setCurrentStage("Complete");
        if (ev.hypothesis_id) setTopHypothesisId(ev.hypothesis_id);
        break;
    }
  }, [topHypothesisId]);

  // Start SSE stream when session is created
  useEffect(() => {
    if (!sessionId) return;

    const source = streamSessionEvents(sessionId, addEvent);

    return () => {
      source.close();
    };
  }, [sessionId, addEvent]);

  async function handleQuerySubmit(queryText: string) {
    setQuery(queryText);
    setMode("stream");

    try {
      const result = await createSession({
        query: queryText,
        disease_area: queryText,
        start_entity: queryText,
        start_type: "Disease",
        target_types: ["Gene", "Drug"],
      });
      if (result.session_id) {
        setSessionId(result.session_id);
      }
    } catch {
      // If session creation fails, add an error event
      setEvents([{
        id: eventCounter.current++,
        type: "error",
        stage: "Literature",
        timestamp: new Date().toISOString(),
        message: "Failed to start session. Check that the backend is running at localhost:8000.",
      }]);
    }
  }

  async function handleDemoLaunch(demoId: number, demoQuery: string) {
    setQuery(demoQuery);
    setMode("stream");

    try {
      const result = await startDemo(demoId);
      if (result.session_id) {
        setSessionId(result.session_id);
      }
    } catch {
      setEvents([{
        id: eventCounter.current++,
        type: "error",
        stage: "Literature",
        timestamp: new Date().toISOString(),
        message: "Failed to start demo. Check that the backend is running at localhost:8000.",
      }]);
    }
  }

  if (mode === "prompt") {
    return <PromptMode onSubmit={handleQuerySubmit} onDemo={handleDemoLaunch} />;
  }

  const isReplicated = sessionId?.startsWith("demo-") ?? false;

  return (
    <StreamMode
      events={events}
      stats={stats}
      currentStage={currentStage}
      completed={completed}
      topHypothesisId={topHypothesisId}
      query={query}
      isReplicated={isReplicated}
    />
  );
}
