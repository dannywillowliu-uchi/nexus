"use client";

import { useEffect, useState, use } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { getHypothesis, getResearchOutput } from "@/lib/api";

// --- Type definitions ---

interface ConfidenceScores {
  graph: number;
  literature: number;
  plausibility: number;
  novelty: number;
}

interface ConfidenceAssessment {
  graph_evidence: number;
  graph_reasoning: string;
  literature_support: number;
  literature_reasoning: string;
  biological_plausibility: number;
  plausibility_reasoning: string;
  novelty: number;
  novelty_reasoning: string;
}

interface EvidenceItem {
  paper_id?: string;
  title: string;
  snippet: string;
  confidence: number;
  source?: string;
  claim?: string;
}

interface ResearchBrief {
  hypothesis_title: string;
  connection_explanation: string;
  literature_evidence: EvidenceItem[];
  existing_knowledge_comparison: string;
  confidence: ConfidenceAssessment;
  suggested_validation: string;
  researcher_narrative: string;
}

interface HypothesisData {
  id: string;
  session_id?: string;
  title: string;
  description?: string;
  disease_area: string;
  hypothesis_type?: string;
  novelty_score?: number;
  evidence_score?: number;
  overall_score?: number;
  a_term: string;
  a_type: string;
  b_term: string;
  b_type: string;
  c_term: string;
  c_type: string;
  abc_path?: {
    a: { name: string; type: string };
    b: { name: string; type: string };
    c: { name: string; type: string };
  };
  confidence_scores?: ConfidenceScores;
  evidence_chain?: EvidenceItem[];
  research_brief?: ResearchBrief | string;
  experiment_status?: string;
  experiment_protocol?: string;
}

interface VisualAsset {
  label: string;
  svg: string;
  asset_type: string;
}

interface ResearchOutputData {
  hypothesis_title: string;
  visuals: VisualAsset[];
  discovery_narrative: string;
  pitch_markdown: string;
}

// --- Helpers ---

function overallConfidence(assessment: ConfidenceAssessment): number {
  return (
    (assessment.graph_evidence +
      assessment.literature_support +
      assessment.biological_plausibility +
      assessment.novelty) /
    4
  );
}

function parsePitchSections(markdown: string): { heading: string; body: string }[] {
  const parts = markdown.split(/^## /m).filter(Boolean);
  return parts.map((part) => {
    const newline = part.indexOf("\n");
    if (newline === -1) return { heading: part.trim(), body: "" };
    return {
      heading: part.slice(0, newline).trim(),
      body: part.slice(newline + 1).trim(),
    };
  });
}

/**
 * Minimal markdown-to-HTML for pitch sections.
 * Content comes from our own pipeline (trusted), not user input.
 */
function formatMarkdownBody(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$2</li>')
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br/>");
}

/**
 * Markdown-to-HTML for experiment protocol documents.
 * Content comes from our own pipeline (trusted), not user input.
 */
function formatProtocolMarkdown(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, '<h3 class="mt-4 mb-2 text-base font-semibold">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="mt-6 mb-2 text-lg font-semibold">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="mt-6 mb-3 text-xl font-bold">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, '<code class="rounded bg-slate-100 px-1 py-0.5 text-xs font-mono">$1</code>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-6 list-decimal mb-1">$2</li>')
    .replace(/^- (.+)$/gm, '<li class="ml-6 list-disc mb-1">$1</li>')
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br/>");
}

const SECTION_COLORS: Record<string, string> = {
  pathway: "border-l-teal-500",
  pitch: "border-l-blue-500",
  confidence: "border-l-amber-500",
  evidence: "border-l-emerald-500",
  narrative: "border-l-violet-500",
};

// --- Components ---

function LoadingSpinner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-teal-500" />
      <span className="text-sm text-slate-500">{message}</span>
    </div>
  );
}

function CircularScore({ value, size = 120 }: { value: number; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value);
  const percentage = Math.round(value * 100);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={6}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#0d9488"
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-3xl font-bold text-slate-800">{percentage}</span>
        <span className="text-xs text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

function SectionHeader({
  title,
  colorKey,
}: {
  title: string;
  colorKey: keyof typeof SECTION_COLORS;
}) {
  return (
    <div className={`mb-6 border-l-4 pl-4 ${SECTION_COLORS[colorKey]}`}>
      <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
    </div>
  );
}

function VisualTabs({ visuals }: { visuals: VisualAsset[] }) {
  const [activeTab, setActiveTab] = useState(0);

  if (visuals.length === 0) return null;

  return (
    <div>
      {visuals.length > 1 && (
        <div className="mb-4 flex gap-2">
          {visuals.map((v, i) => (
            <button
              key={i}
              onClick={() => setActiveTab(i)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === i
                  ? "bg-teal-50 text-teal-700"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
      <Card className="overflow-hidden rounded-xl shadow-sm transition-shadow hover:shadow-md">
        <CardContent className="p-6">
          {/* SVG visuals are generated by our own pipeline, not user input */}
          <div
            className="flex justify-center [&>svg]:max-h-[500px] [&>svg]:w-full"
            dangerouslySetInnerHTML={{ __html: visuals[activeTab].svg }}
          />
        </CardContent>
      </Card>
    </div>
  );
}

// --- Main Page ---

export default function HypothesisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const sessionIdParam = searchParams.get("session");

  const [data, setData] = useState<HypothesisData | null>(null);
  const [researchOutput, setResearchOutput] = useState<ResearchOutputData | null>(null);
  const [loading, setLoading] = useState(true);
  const [outputLoading, setOutputLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const result = await getHypothesis(id);
        setData(result);

        // Determine session ID: from query param, or from hypothesis data
        const sessionId = sessionIdParam || result?.session_id;
        if (sessionId) {
          setOutputLoading(true);
          try {
            const output = await getResearchOutput(sessionId);
            setResearchOutput(output);
          } catch {
            // Research output not available -- that's fine
          }
          setOutputLoading(false);
        }
      } catch {
        setData(null);
      }
      setLoading(false);
    }
    load();
  }, [id, sessionIdParam]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-16">
        <LoadingSpinner message="Loading hypothesis..." />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-16">
        <p className="text-sm text-slate-400">Hypothesis not found.</p>
      </div>
    );
  }

  // Normalize data -- handle both flat confidence_scores and nested research_brief.confidence
  const brief: ResearchBrief | null =
    data.research_brief && typeof data.research_brief === "object"
      ? (data.research_brief as ResearchBrief)
      : null;

  const confidenceAssessment: ConfidenceAssessment | null = brief?.confidence ?? null;

  const scores: ConfidenceScores = data.confidence_scores || {
    graph: confidenceAssessment?.graph_evidence ?? 0,
    literature: confidenceAssessment?.literature_support ?? 0,
    plausibility: confidenceAssessment?.biological_plausibility ?? 0,
    novelty: confidenceAssessment?.novelty ?? 0,
  };

  const overall =
    data.overall_score ??
    (confidenceAssessment ? overallConfidence(confidenceAssessment) : null) ??
    (scores.graph + scores.literature + scores.plausibility + scores.novelty) / 4;

  // Determine hypothesis type label
  const hypothesisType = data.hypothesis_type || "Hypothesis";

  // Extract ABC path terms
  const aName = data.a_term || data.abc_path?.a?.name || "";
  const bName = data.b_term || data.abc_path?.b?.name || "";
  const cName = data.c_term || data.abc_path?.c?.name || "";
  const aType = data.a_type || data.abc_path?.a?.type || "A";
  const bType = data.b_type || data.abc_path?.b?.type || "B";
  const cType = data.c_type || data.abc_path?.c?.type || "C";

  // Visuals from research output
  const pathwayVisuals =
    researchOutput?.visuals?.filter((v) => v.asset_type === "pathway") ?? [];
  const mechanismVisuals =
    researchOutput?.visuals?.filter((v) => v.asset_type === "mechanism") ?? [];
  const allVisuals = [...pathwayVisuals, ...mechanismVisuals];

  // Pitch sections
  const pitchSections = researchOutput?.pitch_markdown
    ? parsePitchSections(researchOutput.pitch_markdown)
    : [];

  // Evidence items -- prefer research_brief.literature_evidence, fall back to evidence_chain
  const evidenceItems: EvidenceItem[] =
    brief?.literature_evidence ?? data.evidence_chain ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      {/* Hero Section */}
      <section className="mb-12">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Badge className="bg-teal-50 text-teal-700">{data.disease_area}</Badge>
          <Badge className="bg-slate-100 text-slate-600">{hypothesisType}</Badge>
        </div>

        <h1 className="mb-6 text-4xl font-bold leading-tight text-slate-900">
          {data.title}
        </h1>

        {data.description && (
          <p className="mb-8 max-w-3xl text-lg leading-relaxed text-slate-600">
            {data.description}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-8">
          <CircularScore value={overall} />

          <div className="flex flex-wrap gap-3">
            {[
              { label: "Novelty", value: data.novelty_score ?? scores.novelty },
              { label: "Evidence", value: data.evidence_score ?? scores.literature },
              {
                label: "Path Strength",
                value: scores.graph,
              },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-center shadow-sm"
              >
                <p className="font-mono text-2xl font-semibold text-slate-800">
                  {Math.round((s.value || 0) * 100)}
                </p>
                <p className="text-xs text-slate-500">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ABC Path mini-visualization */}
        {aName && bName && cName && (
          <div className="mt-8 flex items-center gap-3">
            <span className="rounded-md bg-teal-50 px-3 py-1.5 text-sm font-medium text-teal-700">
              {aName}
              <span className="ml-1 text-xs text-teal-400">({aType})</span>
            </span>
            <span className="text-slate-300">&rarr;</span>
            <span className="rounded-md bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700">
              {bName}
              <span className="ml-1 text-xs text-amber-400">({bType})</span>
            </span>
            <span className="text-slate-300">&rarr;</span>
            <span className="rounded-md bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700">
              {cName}
              <span className="ml-1 text-xs text-emerald-400">({cType})</span>
            </span>
          </div>
        )}
      </section>

      <Separator className="mb-12" />

      {/* Section 1: Pathway Visualization */}
      {outputLoading && (
        <section className="mb-12">
          <SectionHeader title="Pathway Visualization" colorKey="pathway" />
          <LoadingSpinner message="Generating research output..." />
        </section>
      )}

      {allVisuals.length > 0 && (
        <section className="mb-12">
          <SectionHeader title="Pathway Visualization" colorKey="pathway" />
          <VisualTabs visuals={allVisuals} />
        </section>
      )}

      {/* Section 2: Research Pitch */}
      {pitchSections.length > 0 && (
        <section className="mb-12">
          <SectionHeader title="Research Pitch" colorKey="pitch" />
          <div className="space-y-6">
            {pitchSections.map((section, i) => (
              <Card key={i} className="rounded-xl shadow-sm transition-shadow hover:shadow-md">
                <CardHeader>
                  <CardTitle className="text-base">{section.heading}</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Pitch markdown is generated by our own pipeline, not user input */}
                  <div
                    className="prose-sm max-w-none leading-relaxed text-slate-600 [&_li]:mb-1 [&_p]:mb-3 [&_strong]:text-slate-800"
                    dangerouslySetInnerHTML={{
                      __html: `<p>${formatMarkdownBody(section.body)}</p>`,
                    }}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* If no research output pitch but we have a string research_brief, show it */}
      {!researchOutput?.pitch_markdown &&
        data.research_brief &&
        typeof data.research_brief === "string" && (
          <section className="mb-12">
            <SectionHeader title="Research Brief" colorKey="pitch" />
            <Card className="rounded-xl shadow-sm transition-shadow hover:shadow-md">
              <CardContent className="pt-6">
                <p className="leading-relaxed text-slate-600">
                  {data.research_brief}
                </p>
              </CardContent>
            </Card>
          </section>
        )}

      {/* Section 3: Confidence Breakdown */}
      <section className="mb-12">
        <SectionHeader title="Confidence Breakdown" colorKey="confidence" />
        <Card className="rounded-xl shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="space-y-5 pt-6">
            {[
              {
                label: "Graph Evidence",
                value: confidenceAssessment?.graph_evidence ?? scores.graph,
                reasoning: confidenceAssessment?.graph_reasoning,
                color: "bg-teal-500",
              },
              {
                label: "Literature Support",
                value:
                  confidenceAssessment?.literature_support ?? scores.literature,
                reasoning: confidenceAssessment?.literature_reasoning,
                color: "bg-blue-500",
              },
              {
                label: "Biological Plausibility",
                value:
                  confidenceAssessment?.biological_plausibility ??
                  scores.plausibility,
                reasoning: confidenceAssessment?.plausibility_reasoning,
                color: "bg-amber-500",
              },
              {
                label: "Novelty",
                value: confidenceAssessment?.novelty ?? scores.novelty,
                reasoning: confidenceAssessment?.novelty_reasoning,
                color: "bg-emerald-500",
              },
            ].map((item) => (
              <div key={item.label} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">{item.label}</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {Math.round((item.value || 0) * 100)}%
                  </span>
                </div>
                <Progress value={(item.value || 0) * 100} className="h-2" />
                {item.reasoning && (
                  <p className="text-xs leading-relaxed text-slate-500">
                    {item.reasoning}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      {/* Section 4: Evidence Chain */}
      {evidenceItems.length > 0 && (
        <section className="mb-12">
          <SectionHeader title="Evidence Chain" colorKey="evidence" />
          <div className="space-y-3">
            {evidenceItems.map((ev, i) => (
              <Card key={i} className="rounded-xl shadow-sm transition-shadow hover:shadow-md">
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-slate-800">
                        {ev.title || ev.source || `Evidence ${i + 1}`}
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">
                        {ev.snippet || ev.claim}
                      </p>
                    </div>
                    <Badge className="shrink-0 bg-emerald-50 text-emerald-700">
                      {Math.round((ev.confidence || 0) * 100)}%
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Section 5: Discovery Narrative */}
      {researchOutput?.discovery_narrative && (
        <section className="mb-12">
          <SectionHeader title="Discovery Narrative" colorKey="narrative" />
          <Card className="rounded-xl border-violet-200 bg-violet-50/30 shadow-sm transition-shadow hover:shadow-md">
            <CardContent className="pt-6">
              <p className="text-sm italic leading-relaxed text-slate-700">
                {researchOutput.discovery_narrative}
              </p>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Fallback: researcher_narrative from brief when no research output */}
      {!researchOutput?.discovery_narrative && brief?.researcher_narrative && (
        <section className="mb-12">
          <SectionHeader title="Discovery Narrative" colorKey="narrative" />
          <Card className="rounded-xl border-violet-200 bg-violet-50/30 shadow-sm transition-shadow hover:shadow-md">
            <CardContent className="pt-6">
              <p className="text-sm italic leading-relaxed text-slate-700">
                {brief.researcher_narrative}
              </p>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Experiment Protocol */}
      {data.experiment_status && (
        <>
          <Separator className="my-8" />
          <section className="mb-12">
            <div className="mb-6 flex items-center justify-between">
              <div className="border-l-4 border-l-cyan-500 pl-4">
                <h2 className="text-xl font-semibold text-slate-800">
                  Experimental Protocol
                </h2>
              </div>
              <div className="flex items-center gap-3">
                <Badge
                  className={
                    data.experiment_status === "completed"
                      ? "bg-emerald-100 text-emerald-700"
                      : data.experiment_status === "in_progress"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                  }
                >
                  {data.experiment_status}
                </Badge>
                {data.experiment_protocol && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const blob = new Blob([data.experiment_protocol!], {
                        type: "text/markdown",
                      });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `protocol-${id}.md`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    Download Protocol
                  </Button>
                )}
              </div>
            </div>
            {data.experiment_protocol ? (
              <Card className="rounded-xl shadow-sm transition-shadow hover:shadow-md">
                <CardContent className="pt-6">
                  <div
                    className="prose prose-sm max-w-none prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-700"
                    dangerouslySetInnerHTML={{
                      __html: formatProtocolMarkdown(data.experiment_protocol),
                    }}
                  />
                </CardContent>
              </Card>
            ) : (
              <Card className="rounded-xl shadow-sm">
                <CardContent className="pt-6">
                  <p className="text-sm text-slate-400">
                    No protocol document available for this experiment.
                  </p>
                </CardContent>
              </Card>
            )}
          </section>
        </>
      )}
    </div>
  );
}
