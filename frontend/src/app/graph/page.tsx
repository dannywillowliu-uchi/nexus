"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { exploreGraph } from "@/lib/api";
import type { ForceGraphMethods } from "react-force-graph-2d";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyNode = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyLink = any;

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

const entityTypes = [
  "Disease",
  "Drug",
  "Gene",
  "Pathway",
  "Compound",
  "Anatomy",
  "BiologicalProcess",
  "Symptom",
  "MolecularFunction",
  "CellularComponent",
  "PharmacologicClass",
];

const NODE_COLORS: Record<string, string> = {
  Disease: "#EF4444",
  Drug: "#3B82F6",
  Gene: "#10B981",
  Pathway: "#8B5CF6",
  Compound: "#3B82F6",
  Anatomy: "#6B7280",
};
const DEFAULT_NODE_COLOR = "#9CA3AF";

interface GraphNode {
  id: string;
  name: string;
  type: string;
}

interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

interface ApiResponse {
  entity_name: string;
  entity_type: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface ForceNode {
  id: string;
  name: string;
  type: string;
  isRoot: boolean;
}

interface ForceLink {
  source: string;
  target: string;
  label: string;
}

interface ForceGraphData {
  nodes: ForceNode[];
  links: ForceLink[];
}

export default function GraphPage() {
  const [entityName, setEntityName] = useState("");
  const [entityType, setEntityType] = useState("Disease");
  const [depth, setDepth] = useState(1);
  const [graphData, setGraphData] = useState<ForceGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<ForceNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<ForceNode | null>(null);
  const [feed, setFeed] = useState<ForceNode[]>([]);
  const [graphDimensions, setGraphDimensions] = useState({ width: 800, height: 600 });

  const graphContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<ForceGraphMethods<any, any>>(undefined);

  useEffect(() => {
    function updateDimensions() {
      if (graphContainerRef.current) {
        const rect = graphContainerRef.current.getBoundingClientRect();
        setGraphDimensions({ width: rect.width, height: rect.height });
      }
    }
    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  async function handleExplore() {
    if (!entityName) return;
    setLoading(true);
    setSelectedNode(null);
    setFeed([]);
    try {
      const data: ApiResponse = await exploreGraph({
        entity_name: entityName,
        entity_type: entityType,
        depth,
      });

      const nodes: ForceNode[] = (data.nodes || []).map((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        isRoot: n.name.toLowerCase() === entityName.toLowerCase(),
      }));

      const links: ForceLink[] = (data.edges || []).map((e) => ({
        source: e.source,
        target: e.target,
        label: e.relationship,
      }));

      setGraphData({ nodes, links });
      setFeed(nodes);

      // Zoom to fit after data loads
      setTimeout(() => {
        fgRef.current?.zoomToFit(400, 60);
      }, 500);
    } catch {
      setGraphData(null);
    }
    setLoading(false);
  }

  const getNodeColor = useCallback((node: AnyNode) => {
    return NODE_COLORS[node.type ?? ""] ?? DEFAULT_NODE_COLOR;
  }, []);

  const getNodeSize = useCallback((node: AnyNode) => {
    return node.isRoot ? 12 : 8;
  }, []);

  const paintNode = useCallback(
    (node: AnyNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const size = node.isRoot ? 12 : 8;
      const color = NODE_COLORS[node.type ?? ""] ?? DEFAULT_NODE_COLOR;
      const isHighlighted =
        hoveredNode?.id === node.id ||
        selectedNode?.id === node.id;

      // Glow on highlight
      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(x, y, size + 3, 0, 2 * Math.PI);
        ctx.fillStyle = color + "33";
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(x, y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = isHighlighted ? "#1E293B" : "#FFFFFF";
      ctx.lineWidth = isHighlighted ? 2 : 1.2;
      ctx.stroke();

      // Label below node
      const fontSize = Math.max(10 / globalScale, 3);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#334155";
      ctx.fillText(node.name ?? "", x, y + size + 2);
    },
    [hoveredNode, selectedNode]
  );

  const paintLink = useCallback(
    (link: AnyLink, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const sx = link.source.x ?? 0;
      const sy = link.source.y ?? 0;
      const tx = link.target.x ?? 0;
      const ty = link.target.y ?? 0;

      const isHighlighted =
        hoveredNode &&
        (link.source.id === hoveredNode.id || link.target.id === hoveredNode.id);

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.strokeStyle = isHighlighted ? "#64748B" : "#D1D5DB";
      ctx.lineWidth = isHighlighted ? 1.5 : 0.8;
      ctx.stroke();

      // Show label on hover or when zoomed in
      if ((isHighlighted || globalScale > 1.5) && link.label) {
        const mx = (sx + tx) / 2;
        const my = (sy + ty) / 2;
        const fontSize = Math.max(8 / globalScale, 2.5);
        ctx.font = `${fontSize}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = isHighlighted ? "#1E293B" : "#94A3B8";
        ctx.fillText(link.label, mx, my);
      }
    },
    [hoveredNode]
  );

  const handleNodeClick = useCallback((node: AnyNode) => {
    setSelectedNode({
      id: node.id as string,
      name: node.name ?? "",
      type: node.type ?? "",
      isRoot: node.isRoot ?? false,
    });
  }, []);

  const handleNodeHover = useCallback((node: AnyNode | null) => {
    setHoveredNode(
      node
        ? {
            id: node.id as string,
            name: node.name ?? "",
            type: node.type ?? "",
            isRoot: node.isRoot ?? false,
          }
        : null
    );
  }, []);

  const connectionCount = useCallback(
    (nodeId: string) => {
      if (!graphData) return 0;
      return graphData.links.filter((l) => {
        const src = typeof l.source === "object" ? (l.source as ForceNode).id : l.source;
        const tgt = typeof l.target === "object" ? (l.target as ForceNode).id : l.target;
        return src === nodeId || tgt === nodeId;
      }).length;
    },
    [graphData]
  );

  // Unique types present in current graph for legend
  const activeTypes = graphData
    ? [...new Set(graphData.nodes.map((n) => n.type))].sort()
    : [];

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col px-6 py-4">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-slate-800">Graph Explorer</h1>
        <p className="text-sm text-slate-500">
          Explore the biomedical knowledge graph interactively.
        </p>
      </div>

      {/* Search Controls */}
      <div className="mb-4 flex items-end gap-3">
        <div className="flex-1 space-y-1">
          <Label htmlFor="entityName">Entity Name</Label>
          <Input
            id="entityName"
            placeholder="e.g. Alzheimer's Disease"
            value={entityName}
            onChange={(e) => setEntityName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleExplore()}
          />
        </div>
        <div className="w-44 space-y-1">
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
        <div className="w-32 space-y-1">
          <Label>Depth: {depth}</Label>
          <input
            type="range"
            min={1}
            max={3}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="h-8 w-full cursor-pointer accent-teal-600"
          />
        </div>
        <Button
          onClick={handleExplore}
          disabled={loading || !entityName}
          className="bg-teal-600 hover:bg-teal-700"
        >
          {loading ? "Exploring..." : "Explore"}
        </Button>
      </div>

      {/* Main Content: Graph + Sidebar */}
      <div className="flex min-h-0 flex-1 gap-4">
        {/* Graph Canvas */}
        <div className="flex-[3]">
          <Card className="h-full">
            <CardContent className="relative h-full p-0">
              <div
                ref={graphContainerRef}
                className="h-full w-full overflow-hidden rounded-lg"
                style={{
                  background:
                    "radial-gradient(circle, #e2e8f0 1px, transparent 1px)",
                  backgroundSize: "20px 20px",
                  backgroundColor: "#f8fafc",
                }}
              >
                {!graphData && !loading && (
                  <div className="flex h-full items-center justify-center">
                    <p className="text-sm text-slate-400">
                      Search for an entity to explore the graph.
                    </p>
                  </div>
                )}
                {loading && (
                  <div className="flex h-full items-center justify-center">
                    <div className="flex items-center gap-2">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
                      <p className="text-sm text-slate-500">Loading graph data...</p>
                    </div>
                  </div>
                )}
                {graphData && !loading && (
                  <ForceGraph2D
                    ref={fgRef}
                    graphData={graphData}
                    width={graphDimensions.width}
                    height={graphDimensions.height}
                    backgroundColor="transparent"
                    nodeCanvasObject={paintNode}
                    nodeCanvasObjectMode={() => "replace"}
                    nodeVal={getNodeSize}
                    nodeColor={getNodeColor}
                    linkCanvasObject={paintLink}
                    linkCanvasObjectMode={() => "replace"}
                    onNodeClick={handleNodeClick}
                    onNodeHover={handleNodeHover}
                    enableZoomInteraction={true}
                    enablePanInteraction={true}
                    enableNodeDrag={true}
                    cooldownTicks={100}
                    d3AlphaDecay={0.02}
                    d3VelocityDecay={0.3}
                    minZoom={0.5}
                    maxZoom={8}
                  />
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar */}
        <div className="flex w-72 flex-col gap-4">
          {/* Legend */}
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-slate-700">Legend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {(activeTypes.length > 0 ? activeTypes : Object.keys(NODE_COLORS)).map(
                  (type) => (
                    <div key={type} className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-3 w-3 rounded-full"
                        style={{ backgroundColor: NODE_COLORS[type] ?? DEFAULT_NODE_COLOR }}
                      />
                      <span className="text-xs text-slate-600">{type}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>

          {/* Node Detail */}
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-slate-700">
                Node Detail
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedNode ? (
                <div className="space-y-2">
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {selectedNode.name}
                    </p>
                    <Badge
                      className="mt-1"
                      style={{
                        backgroundColor: NODE_COLORS[selectedNode.type] ?? DEFAULT_NODE_COLOR,
                        color: "#fff",
                      }}
                    >
                      {selectedNode.type}
                    </Badge>
                  </div>
                  <div className="text-xs text-slate-500">
                    <span className="font-medium text-slate-600">
                      {connectionCount(selectedNode.id)}
                    </span>{" "}
                    connection{connectionCount(selectedNode.id) !== 1 ? "s" : ""}
                  </div>
                  {selectedNode.isRoot && (
                    <p className="text-xs italic text-teal-600">Search entity</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-slate-400">
                  Click a node to see details.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Live Feed */}
          <Card size="sm" className="flex min-h-0 flex-1 flex-col">
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-slate-700">
                Live Feed
                {feed.length > 0 && (
                  <span className="ml-2 text-xs font-normal text-slate-400">
                    {feed.length} nodes
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="min-h-0 flex-1 overflow-y-auto">
              {feed.length === 0 ? (
                <p className="text-xs text-slate-400">
                  Nodes will appear here as the graph loads.
                </p>
              ) : (
                <ul className="space-y-1">
                  {feed.map((node) => (
                    <li
                      key={node.id}
                      className="flex items-center gap-2 rounded px-1.5 py-0.5 text-xs transition-colors hover:bg-slate-100 cursor-pointer"
                      onClick={() => setSelectedNode(node)}
                    >
                      <span
                        className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                        style={{
                          backgroundColor:
                            NODE_COLORS[node.type] ?? DEFAULT_NODE_COLOR,
                        }}
                      />
                      <span className="truncate text-slate-700">{node.name}</span>
                      <span className="ml-auto flex-shrink-0 text-slate-400">
                        {node.type}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
