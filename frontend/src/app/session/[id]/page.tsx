"use client";

import { useEffect, useState, useRef, use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { streamSessionEvents } from "@/lib/api";

interface SessionEvent {
  type: string;
  timestamp?: string;
  tool_name?: string;
  message?: string;
  hypothesis?: Record<string, unknown>;
  [key: string]: unknown;
}

interface Hypothesis {
  id?: string;
  title?: string;
  novelty_score?: number;
  a_term?: string;
  b_term?: string;
  c_term?: string;
}

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [status, setStatus] = useState("connecting");
  const [stepCount, setStepCount] = useState(0);
  const [pivotCount, setPivotCount] = useState(0);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = streamSessionEvents(id, (event: Record<string, unknown>) => {
      const ev = event as SessionEvent;
      setEvents((prev) => [...prev, ev]);
      setStepCount((prev) => prev + 1);

      if (ev.type === "hypothesis_generated" && ev.hypothesis) {
        setHypotheses((prev) => [...prev, ev.hypothesis as Hypothesis]);
      }
      if (ev.type === "pivot") {
        setPivotCount((prev) => prev + 1);
      }
      if (ev.type === "status_change") {
        setStatus(String(ev.status || ev.message || "running"));
      }
      if (ev.type === "session_started") {
        setStatus("running");
      }
      if (ev.type === "session_complete") {
        setStatus("complete");
      }
    });

    setStatus("running");

    return () => {
      source.close();
    };
  }, [id]);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  function formatTime(ts?: string) {
    if (!ts) return "";
    try {
      return new Date(ts).toLocaleTimeString();
    } catch {
      return ts;
    }
  }

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
                {events.map((ev, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-md border border-slate-100 px-3 py-2"
                  >
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {ev.type}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      {ev.tool_name && (
                        <span className="mr-2 font-mono text-xs text-teal-600">
                          {ev.tool_name}
                        </span>
                      )}
                      <span className="text-sm text-slate-600">
                        {ev.message || JSON.stringify(ev).slice(0, 120)}
                      </span>
                    </div>
                    <span className="shrink-0 text-xs text-slate-400">
                      {formatTime(ev.timestamp)}
                    </span>
                  </div>
                ))}
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
