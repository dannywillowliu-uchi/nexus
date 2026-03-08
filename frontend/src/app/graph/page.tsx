"use client";

import { useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { exploreGraph } from "@/lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

const entityTypes = [
  "Disease",
  "Gene",
  "Compound",
  "BiologicalProcess",
  "Anatomy",
  "Symptom",
  "Pathway",
  "MolecularFunction",
  "CellularComponent",
  "PharmacologicClass",
];

const typeColors: Record<string, string> = {
  Disease: "#ef4444",
  Gene: "#3b82f6",
  Compound: "#22c55e",
  BiologicalProcess: "#f59e0b",
  Anatomy: "#ec4899",
  Symptom: "#a855f7",
  Pathway: "#06b6d4",
  MolecularFunction: "#f97316",
  CellularComponent: "#6366f1",
  PharmacologicClass: "#14b8a6",
  Entity: "#94a3b8",
};

interface GraphNode {
  id: string;
  name: string;
  type: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface GraphData {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
}

export default function GraphPage() {
  const [entityName, setEntityName] = useState("");
  const [entityType, setEntityType] = useState("Disease");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExplore() {
    if (!entityName) return;
    setLoading(true);
    setError(null);
    try {
      const data = await exploreGraph({
        entity_name: entityName,
        entity_type: entityType,
        depth: 1,
      });
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph data");
      setGraphData(null);
    }
    setLoading(false);
  }

  const forceGraphData = useMemo(() => {
    if (!graphData?.nodes?.length) return null;
    return {
      nodes: graphData.nodes.map((n) => ({ ...n })),
      links: (graphData.edges || []).map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
      })),
    };
  }, [graphData]);

  const nodeCanvasObject = useCallback(
    (node: Record<string, unknown>, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = (node.name as string) || (node.id as string) || "";
      const type = (node.type as string) || "Entity";
      const x = node.x as number;
      const y = node.y as number;
      const fontSize = 12 / globalScale;
      const radius = 5;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = typeColors[type] || typeColors.Entity;
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5 / globalScale;
      ctx.stroke();

      // Draw label
      ctx.font = `${fontSize}px Sans-Serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#334155";
      ctx.fillText(label, x, y + radius + 2);
    },
    [],
  );

  // Build legend entries from current graph data
  const legendTypes = useMemo(() => {
    if (!graphData?.nodes?.length) return [];
    const types = new Set(graphData.nodes.map((n) => n.type));
    return Array.from(types).sort();
  }, [graphData]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <h1 className="mb-2 text-3xl font-bold text-slate-800">Graph Explorer</h1>
      <p className="mb-8 text-slate-500">
        Explore the biomedical knowledge graph interactively.
      </p>

      {/* Search Controls */}
      <div className="mb-6 flex items-end gap-4">
        <div className="flex-1 space-y-2">
          <Label htmlFor="entityName">Entity Name</Label>
          <Input
            id="entityName"
            placeholder="e.g. Alzheimer's Disease"
            value={entityName}
            onChange={(e) => setEntityName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleExplore()}
          />
        </div>
        <div className="w-48 space-y-2">
          <Label>Entity Type</Label>
          <Select value={entityType} onValueChange={(v) => v && setEntityType(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {entityTypes.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={handleExplore}
          disabled={loading || !entityName}
          className="bg-teal-600 hover:bg-teal-700"
        >
          {loading ? "Exploring..." : "Explore"}
        </Button>
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Graph Visualization Area */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Knowledge Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative h-[500px] overflow-hidden rounded-lg border-2 border-dashed border-slate-200 bg-slate-50">
            {!graphData && !loading && (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-slate-400">
                  Search for an entity to explore the graph.
                </p>
              </div>
            )}
            {loading && (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-slate-400">Loading graph data...</p>
              </div>
            )}
            {graphData && !loading && graphData.nodes?.length === 0 && (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-slate-400">
                  No graph data found for this entity. Try seeding the knowledge graph first.
                </p>
              </div>
            )}
            {forceGraphData && !loading && (
              <ForceGraph2D
                graphData={forceGraphData}
                nodeCanvasObject={nodeCanvasObject}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={1}
                linkColor={() => "#cbd5e1"}
                linkWidth={1.5}
                width={undefined}
                height={500}
              />
            )}
          </div>

          {/* Legend */}
          {legendTypes.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-4">
              {legendTypes.map((t) => (
                <div key={t} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-3 w-3 rounded-full"
                    style={{ backgroundColor: typeColors[t] || typeColors.Entity }}
                  />
                  <span className="text-xs text-slate-600">{t}</span>
                </div>
              ))}
            </div>
          )}

          {/* Stats */}
          {graphData && (graphData.nodes?.length || 0) > 0 && (
            <p className="mt-2 text-xs text-slate-400">
              {graphData.nodes?.length || 0} nodes, {graphData.edges?.length || 0} edges
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
