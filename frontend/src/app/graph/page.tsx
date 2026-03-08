"use client";

import { useState } from "react";
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

interface GraphData {
  nodes?: Array<{ id: string; name: string; type: string }>;
  edges?: Array<{ source: string; target: string; type: string }>;
}

export default function GraphPage() {
  const [entityName, setEntityName] = useState("");
  const [entityType, setEntityType] = useState("Disease");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleExplore() {
    if (!entityName) return;
    setLoading(true);
    try {
      const data = await exploreGraph({
        entity_name: entityName,
        entity_type: entityType,
        depth: 1,
      });
      setGraphData(data);
    } catch {
      setGraphData(null);
    }
    setLoading(false);
  }

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

      {/* Graph Visualization Area */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Knowledge Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[500px] items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50">
            {!graphData && !loading && (
              <p className="text-sm text-slate-400">
                Search for an entity to explore the graph.
              </p>
            )}
            {loading && (
              <p className="text-sm text-slate-400">Loading graph data...</p>
            )}
            {graphData && (
              <div className="text-center">
                <p className="text-sm text-slate-500">
                  Graph visualization - react-force-graph-2d integration pending
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  {graphData.nodes?.length || 0} nodes,{" "}
                  {graphData.edges?.length || 0} edges loaded
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
