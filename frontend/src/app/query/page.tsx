"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { createSession } from "@/lib/api";

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

const targetTypeOptions = [
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

export default function QueryPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [startEntity, setStartEntity] = useState("");
  const [startType, setStartType] = useState("Disease");
  const [targetTypes, setTargetTypes] = useState<string[]>(["Gene", "Compound"]);
  const [reasoningDepth, setReasoningDepth] = useState("full");
  const [maxHypotheses, setMaxHypotheses] = useState(10);
  const [maxPivots, setMaxPivots] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  function toggleTarget(type: string) {
    setTargetTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const result = await createSession({
        query,
        disease_area: query,
        start_entity: startEntity,
        start_type: startType,
        target_types: targetTypes,
        max_hypotheses: maxHypotheses,
        reasoning_depth: reasoningDepth,
        max_pivots: maxPivots,
      });
      if (result.session_id) {
        router.push(`/session/${result.session_id}`);
      }
    } catch {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="mb-2 text-3xl font-bold text-slate-800">Query Builder</h1>
      <p className="mb-8 text-slate-500">
        Define your discovery parameters and launch an autonomous research session.
      </p>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Discovery Parameters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Query */}
            <div className="space-y-2">
              <Label htmlFor="query">Disease / Entity Query</Label>
              <Input
                id="query"
                placeholder="e.g. Alzheimer's Disease"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                required
              />
            </div>

            {/* Start Entity */}
            <div className="space-y-2">
              <Label htmlFor="startEntity">Start Entity Name</Label>
              <Input
                id="startEntity"
                placeholder="e.g. Alzheimer's Disease"
                value={startEntity}
                onChange={(e) => setStartEntity(e.target.value)}
                required
              />
            </div>

            {/* Start Type */}
            <div className="space-y-2">
              <Label>Start Entity Type</Label>
              <Select value={startType} onValueChange={(v) => v && setStartType(v)}>
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

            {/* Target Types */}
            <div className="space-y-2">
              <Label>Target Types</Label>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {targetTypeOptions.map((t) => (
                  <label
                    key={t}
                    className="flex items-center gap-2 text-sm text-slate-600"
                  >
                    <Checkbox
                      checked={targetTypes.includes(t)}
                      onCheckedChange={() => toggleTarget(t)}
                    />
                    {t}
                  </label>
                ))}
              </div>
            </div>

            {/* Reasoning Depth */}
            <div className="space-y-2">
              <Label>Reasoning Depth</Label>
              <Select value={reasoningDepth} onValueChange={(v) => v && setReasoningDepth(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="quick">Quick</SelectItem>
                  <SelectItem value="full">Full</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Max Hypotheses */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="maxHypotheses">Max Hypotheses</Label>
                <Input
                  id="maxHypotheses"
                  type="number"
                  min={1}
                  max={50}
                  value={maxHypotheses}
                  onChange={(e) => setMaxHypotheses(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="maxPivots">Pivot Budget</Label>
                <Input
                  id="maxPivots"
                  type="number"
                  min={0}
                  max={10}
                  value={maxPivots}
                  onChange={(e) => setMaxPivots(Number(e.target.value))}
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={submitting || !query || !startEntity || targetTypes.length === 0}
              className="w-full bg-teal-600 hover:bg-teal-700"
            >
              {submitting ? "Launching Session..." : "Launch Discovery Session"}
            </Button>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
