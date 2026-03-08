"use client";

import { useEffect, useState, useRef, use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { streamSessionEvents } from "@/lib/api";

interface SessionEvent {
  event_type: string;
  data?: Record<string, unknown>;
  timestamp?: string;
  [key: string]: unknown;
}

interface Hypothesis {
  id?: string;
  title?: string;
  novelty_score?: number;
  a_term?: string;
  b_term?: string;
  c_term?: string;
  experiment_verdict?: string;
}

function formatEventMessage(ev: SessionEvent): string {
  const data = ev.data || {};
  switch (ev.event_type) {
    case "stage_start":
      return `Starting ${data.stage || "unknown"} stage${data.entity ? ` for ${data.entity}` : ""}`;
    case "stage_complete": {
      const stage = data.stage || "unknown";
      if (stage === "literature")
        return `Literature complete: ${data.papers || 0} papers, ${data.triples || 0} triples`;
      if (stage === "graph")
        return `Graph complete: ${data.hypotheses || 0} hypotheses found, ${data.scored || 0} scored`;
      return `${stage} stage complete`;
    }
    case "triples_merged":
      return `Merged ${data.count || 0} triples into knowledge graph`;
    case "pivot":
      return `Pivoted to ${data.entity || "new entity"}: ${data.reason || ""}`;
    case "branch":
      return `Branched to explore ${data.entity || "new entity"}: ${data.reason || ""}`;
    case "pipeline_complete":
      return `Pipeline complete: ${data.hypotheses || 0} hypotheses, ${data.pivots || 0} pivots`;
    case "experiment_complete":
      return `Experiment complete for "${data.hypothesis_title || "hypothesis"}": ${data.verdict || data.status || "done"}`;
    case "experiment_retry":
      return `Experiment retry for "${data.hypothesis_title || "hypothesis"}": ${data.verdict || data.status || "retried"} — ${data.reason || ""}`;
    case "session_created":
      return "Research session started";
    case "session_completed":
      return `Session complete: ${data.hypotheses_count || 0} hypotheses, ${data.pivot_count || 0} pivots`;
    case "keepalive":
      return "";
    default:
      return ev.event_type;
  }
}

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [status, setStatus] = useState("connecting");
  const [stepCount, setStepCount] = useState(0);
  const [pivotCount, setPivotCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = streamSessionEvents(
      id,
      (raw: Record<string, unknown>) => {
        const ev: SessionEvent = {
          event_type: (raw.event_type as string) || "",
          data: (raw.data as Record<string, unknown>) || {},
        };

        // Skip keepalive events from timeline
        if (ev.event_type === "keepalive") return;

        setEvents((prev) => [...prev, ev]);
        setStepCount((prev) => prev + 1);

        if (ev.event_type === "session_created" || ev.event_type === "stage_start") {
          setStatus("running");
        }
        if (ev.event_type === "stage_complete" && ev.data?.stage === "graph") {
          const count = (ev.data.hypotheses as number) || 0;
          if (count > 0) {
            const scored = (ev.data.scored as number) || 0;
            setHypotheses((prev) => {
              if (prev.length < scored) {
                const newHyps: Hypothesis[] = [];
                for (let i = prev.length; i < scored; i++) {
                  newHyps.push({ title: `Hypothesis ${i + 1}` });
                }
                return [...prev, ...newHyps];
              }
              return prev;
            });
          }
        }
        if (ev.event_type === "pivot") {
          setPivotCount((prev) => prev + 1);
        }
        if (ev.event_type === "experiment_complete") {
          const title = ev.data?.hypothesis_title as string;
          const verdict = ev.data?.verdict as string;
          if (title && verdict) {
            setHypotheses((prev) =>
              prev.map((h) =>
                h.title === title ? { ...h, experiment_verdict: verdict } : h,
              ),
            );
          }
        }
        if (ev.event_type === "pipeline_complete") {
          setStatus("complete");
          const hypCount = (ev.data?.hypotheses as number) || 0;
          if (hypCount > 0) {
            setHypotheses((prev) => {
              if (prev.length < hypCount) {
                const newHyps: Hypothesis[] = [];
                for (let i = prev.length; i < hypCount; i++) {
                  newHyps.push({ title: `Hypothesis ${i + 1}` });
                }
                return [...prev, ...newHyps];
              }
              return prev;
            });
          }
        }
        if (ev.event_type === "session_completed") {
          setStatus("complete");
        }
      },
      () => {
        if (status !== "complete") {
          setError("Connection to event stream lost. The session may still be running on the server.");
        }
      },
    );

    setStatus("running");

    return () => {
      source.close();
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Session Monitor</h1>
          <p className="font-mono text-sm text-slate-400">{id}</p>
        </div>
        <Badge
          className={
            status === "complete"
              ? "bg-emerald-100 text-emerald-700"
              : status === "running"
                ? "bg-teal-100 text-teal-700"
                : "bg-slate-100 text-slate-600"
          }
        >
          {status}
        </Badge>
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Event Timeline */}
        <div className="lg:col-span-2">
          <Card className="h-[600px] overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Event Timeline</CardTitle>
            </CardHeader>
            <CardContent className="h-[calc(100%-4rem)] overflow-y-auto">
              <div className="space-y-2">
                {events.length === 0 && (
                  <p className="text-sm text-slate-400">
                    Waiting for events...
                  </p>
                )}
                {events.map((ev, i) => {
                  const message = formatEventMessage(ev);
                  return (
                    <div
                      key={i}
                      className="flex items-start gap-3 rounded-md border border-slate-100 px-3 py-2"
                    >
                      <Badge variant="outline" className="shrink-0 text-xs">
                        {ev.event_type}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <span className="text-sm text-slate-600">
                          {message || JSON.stringify(ev.data).slice(0, 120)}
                        </span>
                      </div>
                    </div>
                  );
                })}
                <div ref={eventsEndRef} />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Hypotheses Panel */}
        <div>
          <Card className="h-[600px] overflow-hidden">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                Hypotheses ({hypotheses.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[calc(100%-4rem)] overflow-y-auto">
              <div className="space-y-3">
                {hypotheses.length === 0 && (
                  <p className="text-sm text-slate-400">
                    No hypotheses generated yet...
                  </p>
                )}
                {hypotheses.map((h, i) => (
                  <div
                    key={h.id || i}
                    className="rounded-md border border-slate-100 p-3"
                  >
                    <p className="text-sm font-medium text-slate-700">
                      {h.title || `Hypothesis ${i + 1}`}
                    </p>
                    {h.a_term && h.b_term && h.c_term && (
                      <p className="mt-1 font-mono text-xs text-slate-400">
                        {h.a_term} → {h.b_term} → {h.c_term}
                      </p>
                    )}
                    {h.novelty_score !== undefined && (
                      <span className="mt-1 inline-block text-xs text-emerald-600">
                        Novelty: {(h.novelty_score * 100).toFixed(0)}%
                      </span>
                    )}
                    {h.experiment_verdict && (
                      <Badge
                        className={`mt-1 ml-2 text-xs ${
                          h.experiment_verdict === "validated"
                            ? "bg-emerald-100 text-emerald-700"
                            : h.experiment_verdict === "refuted"
                              ? "bg-red-100 text-red-700"
                              : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {h.experiment_verdict}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom Metrics Bar */}
      <Separator className="my-6" />
      <div className="flex items-center gap-8">
        <div>
          <span className="text-xs text-slate-400">Status</span>
          <p className="text-sm font-medium text-slate-700">{status}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">Steps</span>
          <p className="text-sm font-medium text-slate-700">{stepCount}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">Pivots</span>
          <p className="text-sm font-medium text-slate-700">{pivotCount}</p>
        </div>
        <div>
          <span className="text-xs text-slate-400">Hypotheses</span>
          <p className="text-sm font-medium text-slate-700">
            {hypotheses.length}
          </p>
        </div>
      </div>
    </div>
  );
}
