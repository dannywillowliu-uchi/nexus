"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getCapabilities } from "@/lib/api";
import { motion } from "framer-motion";
import {
  FlaskConical,
  Database,
  GitBranch,
  Cloud,
  Wrench,
  BookOpen,
  Atom,
  Dna,
  Microscope,
  Beaker,
  ArrowRight,
  CheckCircle2,
  Clock,
  Zap,
  Network,
  BarChart3,
} from "lucide-react";

// -- Types --

interface Tool {
  name: string;
  category: string;
  provider: string;
  description: string;
}

interface DataSource {
  name: string;
  nodes?: number;
  edges?: number;
  type?: string;
  description: string;
}

interface CloudLab {
  name: string;
  status: string;
  capabilities: string[];
}

interface CapabilitiesData {
  tools: Tool[];
  data_sources: DataSource[];
  pipeline_stages: string[];
  cloud_labs: CloudLab[];
}

// -- Fallback data --

const FALLBACK: CapabilitiesData = {
  tools: [
    { name: "DiffDock", category: "docking", provider: "Tamarind Bio", description: "Protein-ligand docking prediction" },
    { name: "AutoDock Vina", category: "docking", provider: "Tamarind Bio", description: "Classical molecular docking" },
    { name: "AlphaFold", category: "structure", provider: "Tamarind Bio", description: "Protein structure prediction" },
    { name: "ESMFold", category: "structure", provider: "Tamarind Bio", description: "Fast protein folding" },
    { name: "ADMET Prediction", category: "properties", provider: "Tamarind Bio", description: "Drug-likeness and ADMET properties" },
    { name: "DeepFRI", category: "function", provider: "Tamarind Bio", description: "Protein function prediction" },
    { name: "ThermoMPNN", category: "stability", provider: "Tamarind Bio", description: "Protein thermostability prediction" },
    { name: "Literature Validation", category: "literature", provider: "PubMed/Semantic Scholar", description: "Cross-reference against published literature" },
    { name: "Pathway Overlap", category: "pathway", provider: "Internal", description: "Biological pathway intersection analysis" },
    { name: "Expression Correlation", category: "expression", provider: "Internal", description: "Gene expression correlation analysis" },
  ],
  data_sources: [
    { name: "PrimeKG", nodes: 129375, edges: 8100498, description: "Precision Medicine Knowledge Graph" },
    { name: "Hetionet", nodes: 47031, edges: 2250197, description: "Integrative biomedical knowledge graph" },
    { name: "PubMed", type: "literature", description: "Biomedical literature database via NCBI E-utilities" },
    { name: "Semantic Scholar", type: "literature", description: "AI-powered academic search" },
  ],
  pipeline_stages: [
    "Literature Mining",
    "Knowledge Graph Enrichment",
    "Swanson ABC Traversal",
    "Adaptive Checkpoint",
    "Reasoning Agent",
    "Computational Validation",
    "Protocol Generation",
    "Cloud Lab Execution",
  ],
  cloud_labs: [
    { name: "Strateos", status: "integrated", capabilities: ["dose-response", "binding-assay", "cell-viability"] },
    { name: "Ginkgo Bioworks", status: "planned", capabilities: [] },
  ],
};

// -- Helpers --

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  docking: { bg: "bg-violet-50", text: "text-violet-700", border: "border-violet-200" },
  structure: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  properties: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  function: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  stability: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  literature: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  pathway: { bg: "bg-teal-50", text: "text-teal-700", border: "border-teal-200" },
  expression: { bg: "bg-cyan-50", text: "text-cyan-700", border: "border-cyan-200" },
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  docking: <Atom className="h-4 w-4" />,
  structure: <Dna className="h-4 w-4" />,
  properties: <Beaker className="h-4 w-4" />,
  function: <Microscope className="h-4 w-4" />,
  stability: <Zap className="h-4 w-4" />,
  literature: <BookOpen className="h-4 w-4" />,
  pathway: <GitBranch className="h-4 w-4" />,
  expression: <BarChart3 className="h-4 w-4" />,
};

const STAGE_COLORS = [
  "#F59E0B", "#8B5CF6", "#3B82F6", "#F97316",
  "#6366F1", "#10B981", "#EC4899", "#14B8A6",
];

const STAGE_ICONS: React.ReactNode[] = [
  <BookOpen key="s0" className="h-4 w-4" />,
  <Database key="s1" className="h-4 w-4" />,
  <GitBranch key="s2" className="h-4 w-4" />,
  <CheckCircle2 key="s3" className="h-4 w-4" />,
  <Zap key="s4" className="h-4 w-4" />,
  <FlaskConical key="s5" className="h-4 w-4" />,
  <Wrench key="s6" className="h-4 w-4" />,
  <Cloud key="s7" className="h-4 w-4" />,
];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function groupByCategory(tools: Tool[]): Record<string, Tool[]> {
  return tools.reduce<Record<string, Tool[]>>((acc, tool) => {
    if (!acc[tool.category]) acc[tool.category] = [];
    acc[tool.category].push(tool);
    return acc;
  }, {});
}

// -- Animation variants --

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, delay: i * 0.05 },
  }),
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

// -- Page --

export default function CapabilitiesPage() {
  const [data, setData] = useState<CapabilitiesData>(FALLBACK);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getCapabilities()
      .then((res) => {
        if (res) setData(res);
      })
      .catch(() => {
        // Use fallback data
      })
      .finally(() => setLoaded(true));
  }, []);

  const totalNodes = data.data_sources.reduce((sum, ds) => sum + (ds.nodes || 0), 0);
  const totalEdges = data.data_sources.reduce((sum, ds) => sum + (ds.edges || 0), 0);
  const grouped = groupByCategory(data.tools);

  if (!loaded) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-200 border-t-teal-600" />
      </div>
    );
  }

  return (
    <div className="bg-fafafa pb-24">
      {/* Hero */}
      <section className="px-6 py-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="font-mono text-5xl font-bold tracking-tight text-slate-800">
            Platform Capabilities
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-500">
            From literature mining to cloud lab execution -- an autonomous
            pipeline for biological discovery, powered by AI reasoning and
            multi-source validation.
          </p>
        </motion.div>
      </section>

      {/* Stats bar */}
      <section className="px-6 pb-16">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5"
        >
          {[
            { label: "Validation Tools", value: `${data.tools.length}+`, icon: <Wrench className="h-5 w-5" />, color: "#8B5CF6" },
            { label: "Graph Nodes", value: `${formatNumber(totalNodes)}+`, icon: <Network className="h-5 w-5" />, color: "#3B82F6" },
            { label: "Graph Edges", value: `${formatNumber(totalEdges)}+`, icon: <GitBranch className="h-5 w-5" />, color: "#10B981" },
            { label: "Pipeline Stages", value: String(data.pipeline_stages.length), icon: <Zap className="h-5 w-5" />, color: "#F59E0B" },
            { label: "Cloud Labs", value: String(data.cloud_labs.length), icon: <Cloud className="h-5 w-5" />, color: "#F97316" },
          ].map((stat, i) => (
            <motion.div key={stat.label} custom={i} variants={fadeUp}>
              <Card className="rounded-xl text-center shadow-sm transition-shadow hover:shadow-md">
                <CardContent className="pt-6 pb-4">
                  <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: `${stat.color}15`, color: stat.color }}>
                    {stat.icon}
                  </div>
                  <p className="text-3xl font-bold" style={{ color: stat.color }}>
                    {stat.value}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">{stat.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </section>

      <Separator className="mx-6" />

      {/* Validation Tools */}
      <section className="px-6 pt-16 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <div className="mb-2 flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-teal-600" />
            <h2 className="text-2xl font-semibold text-slate-800">
              Validation Tools
            </h2>
          </div>
          <p className="mb-8 text-sm text-slate-500">
            Computational and literature-based tools used to validate hypotheses at each pipeline stage.
          </p>
        </motion.div>

        <div className="space-y-10">
          {Object.entries(grouped).map(([category, tools]) => {
            const colors = CATEGORY_COLORS[category] || { bg: "bg-slate-50", text: "text-slate-700", border: "border-slate-200" };
            const icon = CATEGORY_ICONS[category] || <Wrench className="h-4 w-4" />;

            return (
              <motion.div
                key={category}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: "-50px" }}
                variants={staggerContainer}
              >
                <div className="mb-4 flex items-center gap-2">
                  <span className={`${colors.text}`}>{icon}</span>
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                    {category}
                  </h3>
                  <Badge variant="secondary" className={`${colors.bg} ${colors.text} text-xs`}>
                    {tools.length}
                  </Badge>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {tools.map((tool, i) => (
                    <motion.div key={tool.name} custom={i} variants={fadeUp}>
                      <Card className={`h-full rounded-xl border shadow-sm ${colors.border} transition-all hover:shadow-md`}>
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-base">{tool.name}</CardTitle>
                            <Badge variant="outline" className={`${colors.bg} ${colors.text} text-xs`}>
                              {tool.category}
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm text-slate-600">{tool.description}</p>
                          <p className="mt-2 text-xs text-slate-400">Provider: {tool.provider}</p>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            );
          })}
        </div>
      </section>

      <Separator className="mx-6" />

      {/* Data Sources */}
      <section className="px-6 pt-16 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <div className="mb-2 flex items-center gap-2">
            <Database className="h-5 w-5 text-teal-600" />
            <h2 className="text-2xl font-semibold text-slate-800">
              Data Sources
            </h2>
          </div>
          <p className="mb-8 text-sm text-slate-500">
            Knowledge graphs and literature databases powering hypothesis generation and validation.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2"
        >
          {data.data_sources.map((source, i) => (
            <motion.div key={source.name} custom={i} variants={fadeUp}>
              <Card className="h-full rounded-xl shadow-sm transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{source.name}</CardTitle>
                    {source.nodes ? (
                      <Badge className="bg-blue-50 text-blue-700">Knowledge Graph</Badge>
                    ) : (
                      <Badge className="bg-orange-50 text-orange-700">Literature</Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-600">{source.description}</p>
                  {source.nodes && source.edges && (
                    <div className="mt-4 flex gap-6">
                      <div>
                        <p className="text-2xl font-bold text-blue-600">{formatNumber(source.nodes)}</p>
                        <p className="text-xs text-slate-400">nodes</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-emerald-600">{formatNumber(source.edges)}</p>
                        <p className="text-xs text-slate-400">edges</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      </section>

      <Separator className="mx-6" />

      {/* Pipeline Stages */}
      <section className="px-6 pt-16 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <div className="mb-2 flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-teal-600" />
            <h2 className="text-2xl font-semibold text-slate-800">
              Pipeline Stages
            </h2>
          </div>
          <p className="mb-8 text-sm text-slate-500">
            End-to-end autonomous discovery flow from literature to lab execution.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="relative"
        >
          {/* Connection line (desktop) */}
          <div className="absolute left-0 right-0 top-1/2 hidden h-0.5 -translate-y-1/2 bg-gradient-to-r from-amber-200 via-violet-200 to-teal-200 lg:block" />

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
            {data.pipeline_stages.map((stage, i) => {
              const color = STAGE_COLORS[i % STAGE_COLORS.length];
              return (
                <motion.div
                  key={stage}
                  custom={i}
                  variants={fadeUp}
                  className="relative"
                >
                  <Card className="h-full rounded-xl text-center shadow-sm transition-all hover:shadow-md hover:-translate-y-1">
                    <CardContent className="flex flex-col items-center pt-6 pb-4">
                      <div
                        className="mb-3 flex h-10 w-10 items-center justify-center rounded-full text-white"
                        style={{ backgroundColor: color }}
                      >
                        {STAGE_ICONS[i]}
                      </div>
                      <p className="text-xs font-semibold text-slate-700 leading-tight">
                        {stage}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-slate-400">
                        Stage {i + 1}
                      </p>
                    </CardContent>
                  </Card>
                  {/* Arrow connector (mobile/tablet) */}
                  {i < data.pipeline_stages.length - 1 && (
                    <div className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-slate-300 sm:block lg:hidden">
                      <ArrowRight className="h-4 w-4" />
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </section>

      <Separator className="mx-6" />

      {/* Cloud Lab Integration */}
      <section className="px-6 pt-16 pb-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <div className="mb-2 flex items-center gap-2">
            <Cloud className="h-5 w-5 text-teal-600" />
            <h2 className="text-2xl font-semibold text-slate-800">
              Cloud Lab Integration
            </h2>
          </div>
          <p className="mb-8 text-sm text-slate-500">
            Automated wet-lab experiment execution through cloud laboratory APIs.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={staggerContainer}
          className="grid grid-cols-1 gap-6 sm:grid-cols-2"
        >
          {data.cloud_labs.map((lab, i) => {
            const isIntegrated = lab.status === "integrated";
            return (
              <motion.div key={lab.name} custom={i} variants={fadeUp}>
                <Card className={`h-full rounded-xl shadow-sm transition-shadow hover:shadow-md ${isIntegrated ? "border-emerald-200" : "border-slate-200"}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{lab.name}</CardTitle>
                      {isIntegrated ? (
                        <Badge className="bg-emerald-100 text-emerald-700">
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Integrated
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="bg-slate-100 text-slate-500">
                          <Clock className="mr-1 h-3 w-3" />
                          Planned
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {lab.capabilities.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {lab.capabilities.map((cap) => (
                          <Badge
                            key={cap}
                            variant="outline"
                            className="border-emerald-200 bg-emerald-50 text-emerald-700 text-xs"
                          >
                            {cap}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400 italic">
                        Integration coming soon
                      </p>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </motion.div>
      </section>
    </div>
  );
}
