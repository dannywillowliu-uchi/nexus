"use client";

import { useEffect, useState, use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { getHypothesis } from "@/lib/api";

interface HypothesisData {
  id: string;
  title: string;
  disease_area: string;
  a_term: string;
  a_type: string;
  b_term: string;
  b_type: string;
  c_term: string;
  c_type: string;
  confidence_scores: {
    graph: number;
    literature: number;
    plausibility: number;
    novelty: number;
  };
  evidence_chain: Array<{
    source: string;
    claim: string;
    confidence: number;
  }>;
  research_brief: string;
  experiment_status?: string;
  experiment?: {
    status?: string;
    interpretation?: {
      verdict?: string;
      confidence?: number;
      concerns?: string[];
      next_steps?: string[];
    };
  };
}

export default function HypothesisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<HypothesisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const result = await getHypothesis(id);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load hypothesis");
        setData(null);
      }
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-sm text-slate-400">Loading hypothesis...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-12">
        {error && (
          <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <p className="text-sm text-slate-400">Hypothesis not found.</p>
      </div>
    );
  }

  const scores = data.confidence_scores || {
    graph: 0,
    literature: 0,
    plausibility: 0,
    novelty: 0,
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      {/* Header */}
      <div className="mb-8">
        <Badge className="mb-3 bg-teal-50 text-teal-700">
          {data.disease_area}
        </Badge>
        <h1 className="text-3xl font-bold text-slate-800">{data.title}</h1>
      </div>

      {/* ABC Path Visualization */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">ABC Path</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center gap-4 py-4">
            <div className="rounded-lg border-2 border-teal-200 bg-teal-50 px-6 py-3 text-center">
              <p className="text-xs text-slate-400">{data.a_type || "A"}</p>
              <p className="font-semibold text-teal-700">{data.a_term}</p>
            </div>
            <div className="flex items-center">
              <div className="h-px w-8 bg-slate-300" />
              <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            <div className="rounded-lg border-2 border-amber-200 bg-amber-50 px-6 py-3 text-center">
              <p className="text-xs text-slate-400">{data.b_type || "B"}</p>
              <p className="font-semibold text-amber-700">{data.b_term}</p>
            </div>
            <div className="flex items-center">
              <div className="h-px w-8 bg-slate-300" />
              <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            <div className="rounded-lg border-2 border-emerald-200 bg-emerald-50 px-6 py-3 text-center">
              <p className="text-xs text-slate-400">{data.c_type || "C"}</p>
              <p className="font-semibold text-emerald-700">{data.c_term}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confidence Breakdown */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Confidence Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            { label: "Graph Evidence", value: scores.graph, color: "bg-teal-500" },
            { label: "Literature Support", value: scores.literature, color: "bg-blue-500" },
            { label: "Biological Plausibility", value: scores.plausibility, color: "bg-amber-500" },
            { label: "Novelty", value: scores.novelty, color: "bg-emerald-500" },
          ].map((score) => (
            <div key={score.label} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">{score.label}</span>
                <span className="font-medium text-slate-800">
                  {((score.value || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <Progress value={(score.value || 0) * 100} className="h-2" />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Evidence Chain */}
      {data.evidence_chain && data.evidence_chain.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Evidence Chain</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.evidence_chain.map((ev, i) => (
                <div key={i} className="rounded-md border border-slate-100 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-teal-600">
                      {ev.source}
                    </span>
                    <span className="text-xs text-slate-400">
                      {((ev.confidence || 0) * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{ev.claim}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Research Brief */}
      {data.research_brief && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Research Brief</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-slate-600">
              {data.research_brief}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Experiment Results */}
      {(data.experiment_status || data.experiment) && (
        <>
          <Separator className="my-6" />
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Experiment Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <Badge
                  className={
                    (data.experiment?.interpretation?.verdict || data.experiment_status) === "validated"
                      ? "bg-emerald-100 text-emerald-700"
                      : (data.experiment?.interpretation?.verdict || data.experiment_status) === "refuted"
                        ? "bg-red-100 text-red-700"
                        : data.experiment_status === "completed"
                          ? "bg-emerald-100 text-emerald-700"
                          : data.experiment_status === "in_progress"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                  }
                >
                  {data.experiment?.interpretation?.verdict || data.experiment_status || "pending"}
                </Badge>
                {data.experiment?.interpretation?.confidence !== undefined && (
                  <span className="text-sm text-slate-600">
                    Confidence: {(data.experiment.interpretation.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {data.experiment?.interpretation?.concerns && data.experiment.interpretation.concerns.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-slate-500">Concerns</p>
                  <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
                    {data.experiment.interpretation.concerns.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {data.experiment?.interpretation?.next_steps && data.experiment.interpretation.next_steps.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-slate-500">Next Steps</p>
                  <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
                    {data.experiment.interpretation.next_steps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
