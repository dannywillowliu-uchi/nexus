"use client";

import { useEffect, useState, useRef, use, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { streamSessionEvents } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import {
	Check,
	BookOpen,
	GitFork,
	Brain,
	ShieldCheck,
	FlaskConical,
	CircleDot,
	AlertTriangle,
	ChevronDown,
	ChevronRight,
	FileText,
	Triangle,
	Waypoints,
	Lightbulb,
	Repeat,
} from "lucide-react";

// --- Types ---

interface SessionEvent {
	type: string;
	stage?: string;
	message?: string;
	title?: string;
	score?: number;
	hypothesis_id?: string;
	decision?: string;
	reason?: string;
	from_entity?: string;
	to_entity?: string;
	entity_type?: string;
	count?: number;
	papers_found?: number;
	triples_extracted?: number;
	hypotheses_generated?: number;
	research_brief?: string;
	[key: string]: unknown;
}

interface TrackedHypothesis {
	hypothesis_id: string;
	title: string;
	score: number;
	research_brief?: string;
}

// --- Constants ---

const PIPELINE_STAGES = [
	"literature",
	"checkpoint",
	"graph",
	"checkpoint",
	"reasoning",
	"validation",
	"experiment",
	"complete",
] as const;

const STAGE_LABELS: Record<string, string> = {
	literature: "Literature",
	checkpoint: "Checkpoint",
	graph: "Graph",
	reasoning: "Reasoning",
	validation: "Validation",
	experiment: "Experiment",
	complete: "Complete",
};

const STAGE_ICONS: Record<string, React.ReactNode> = {
	literature: <BookOpen size={14} />,
	checkpoint: <ShieldCheck size={14} />,
	graph: <GitFork size={14} />,
	reasoning: <Brain size={14} />,
	validation: <ShieldCheck size={14} />,
	experiment: <FlaskConical size={14} />,
	complete: <Check size={14} />,
};

const STAGE_COLORS: Record<string, string> = {
	literature: "#F59E0B",
	graph: "#8B5CF6",
	reasoning: "#3B82F6",
	validation: "#10B981",
	experiment: "#EC4899",
};

const STAGE_BORDER_COLOR: Record<string, string> = {
	literature: "border-l-amber-500",
	graph: "border-l-violet-500",
	reasoning: "border-l-blue-500",
	validation: "border-l-emerald-500",
	experiment: "border-l-pink-500",
};

const STAGE_BADGE_STYLES: Record<string, string> = {
	literature: "bg-amber-100 text-amber-700 border-amber-200",
	graph: "bg-violet-100 text-violet-700 border-violet-200",
	reasoning: "bg-blue-100 text-blue-700 border-blue-200",
	validation: "bg-emerald-100 text-emerald-700 border-emerald-200",
	experiment: "bg-pink-100 text-pink-700 border-pink-200",
};

const DECISION_STYLES: Record<string, { bg: string; text: string }> = {
	CONTINUE: { bg: "bg-emerald-100", text: "text-emerald-700" },
	PIVOT: { bg: "bg-amber-100", text: "text-amber-700" },
	BRANCH: { bg: "bg-violet-100", text: "text-violet-700" },
};

function getStageBorderClass(stage?: string): string {
	if (!stage) return "border-l-slate-400";
	return STAGE_BORDER_COLOR[stage] || "border-l-slate-400";
}

function getStageBadgeClass(stage?: string): string {
	if (!stage) return "bg-slate-100 text-slate-600 border-slate-200";
	return STAGE_BADGE_STYLES[stage] || "bg-slate-100 text-slate-600 border-slate-200";
}

function getStageLabel(stage?: string): string {
	if (!stage) return "UNKNOWN";
	return (STAGE_LABELS[stage] || stage).toUpperCase();
}

// --- Pipeline Stepper ---

function PipelineStepper({ currentStage, completedStages }: { currentStage: string; completedStages: Set<string> }) {
	// Build unique step keys with index to handle duplicate "checkpoint"
	const steps = PIPELINE_STAGES.map((stage, i) => {
		const stageIndex = PIPELINE_STAGES.indexOf(stage);
		const currentIndex = PIPELINE_STAGES.indexOf(currentStage as typeof PIPELINE_STAGES[number]);
		const isCompleted = completedStages.has(`${stage}-${i}`) || (currentIndex > i);
		const isCurrent = currentStage === stage && !isCompleted && (
			// For duplicate stages like checkpoint, match the first uncompleted one
			i === PIPELINE_STAGES.findIndex((s, idx) => s === stage && !completedStages.has(`${s}-${idx}`) && !(currentIndex > idx))
		);

		return { stage, index: i, isCompleted, isCurrent };
	});

	return (
		<div className="flex items-center justify-between w-full px-4">
			{steps.map((step, i) => (
				<div key={i} className="flex items-center flex-1 last:flex-none">
					{/* Step circle */}
					<div className="flex flex-col items-center gap-1.5">
						<div className="relative">
							{step.isCurrent && (
								<div className="absolute inset-0 rounded-full bg-teal-400 animate-ping opacity-40" />
							)}
							<div
								className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-medium transition-all duration-300 ${
									step.isCompleted
										? "bg-teal-600"
										: step.isCurrent
											? "bg-teal-600 ring-4 ring-teal-200"
											: "bg-slate-300"
								}`}
							>
								{step.isCompleted ? (
									<Check size={14} strokeWidth={3} />
								) : (
									STAGE_ICONS[step.stage] || <CircleDot size={14} />
								)}
							</div>
						</div>
						<span
							className={`text-[10px] font-medium whitespace-nowrap ${
								step.isCompleted || step.isCurrent ? "text-teal-700" : "text-slate-400"
							}`}
						>
							{STAGE_LABELS[step.stage]}
						</span>
					</div>

					{/* Connector line */}
					{i < steps.length - 1 && (
						<div className="flex-1 mx-2 mt-[-18px]">
							<div
								className={`h-0.5 w-full transition-colors duration-500 ${
									step.isCompleted ? "bg-teal-600" : "bg-slate-300"
								}`}
							/>
						</div>
					)}
				</div>
			))}
		</div>
	);
}

// --- Event Card ---

function EventCard({ event, index }: { event: SessionEvent; index: number }) {
	const isStageStart = event.type === "stage_start";
	const isError = event.type === "experiment_error";
	const isCheckpoint = event.type === "checkpoint";
	const isPivot = event.type === "pivot";

	const borderClass = isError ? "border-l-red-500" : getStageBorderClass(event.stage);

	return (
		<motion.div
			initial={{ opacity: 0, y: 12 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3, delay: Math.min(index * 0.02, 0.2) }}
		>
			{isStageStart ? (
				/* Stage transition cards are larger */
				<div
					className={`rounded-xl border-l-4 ${borderClass} bg-white shadow-sm p-4`}
				>
					<Badge className={`${getStageBadgeClass(event.stage)} text-xs font-semibold tracking-wide border`}>
						{getStageLabel(event.stage)} AGENT
					</Badge>
					{event.message && (
						<p className="mt-2 text-sm text-slate-600">{event.message}</p>
					)}
				</div>
			) : isError ? (
				<div className="rounded-xl border-l-4 border-l-red-500 bg-red-50/50 shadow-sm p-3">
					<div className="flex items-center gap-2">
						<AlertTriangle size={14} className="text-red-500 shrink-0" />
						<Badge className="bg-red-100 text-red-700 border border-red-200 text-xs">ERROR</Badge>
						{event.stage && (
							<span className="text-xs text-red-400 font-mono">{event.stage}</span>
						)}
					</div>
					{event.message && (
						<p className="mt-1.5 text-sm text-red-600">{event.message}</p>
					)}
				</div>
			) : isCheckpoint ? (
				<div className={`rounded-xl border-l-4 ${borderClass} bg-white shadow-sm p-3`}>
					<div className="flex items-center gap-2">
						{event.decision && (
							<Badge
								className={`text-xs font-semibold border ${
									DECISION_STYLES[event.decision]
										? `${DECISION_STYLES[event.decision].bg} ${DECISION_STYLES[event.decision].text}`
										: "bg-slate-100 text-slate-600"
								}`}
							>
								{event.decision}
							</Badge>
						)}
						{event.reason && (
							<span className="text-sm text-slate-600">{event.reason}</span>
						)}
					</div>
				</div>
			) : isPivot ? (
				<div className="rounded-xl border-l-4 border-l-amber-400 bg-amber-50/30 shadow-sm p-3">
					<div className="flex items-center gap-2">
						<Repeat size={14} className="text-amber-600 shrink-0" />
						<span className="text-sm text-slate-600">
							<span className="font-mono text-xs text-amber-700">{event.from_entity}</span>
							{" -> "}
							<span className="font-mono text-xs text-amber-700">{event.to_entity}</span>
						</span>
					</div>
				</div>
			) : (
				/* Regular events */
				<div className={`rounded-xl border-l-4 ${borderClass} bg-white shadow-sm p-3`}>
					<div className="flex items-start gap-2">
						<Badge variant="outline" className="shrink-0 text-[10px] font-mono">
							{event.type}
						</Badge>
						<p className="text-sm text-slate-600 min-w-0">
							{event.message || JSON.stringify(event).slice(0, 150)}
						</p>
					</div>
				</div>
			)}
		</motion.div>
	);
}

// --- Hypothesis Card ---

function HypothesisCard({ hypothesis, isTop }: { hypothesis: TrackedHypothesis; isTop: boolean }) {
	const [expanded, setExpanded] = useState(false);

	return (
		<motion.div
			initial={{ opacity: 0, scale: 0.95 }}
			animate={{ opacity: 1, scale: 1 }}
			transition={{ duration: 0.3 }}
		>
			<Card
				className={`rounded-xl shadow-sm cursor-pointer transition-all hover:shadow-md ${
					isTop ? "border-2 border-amber-400 bg-amber-50/30" : ""
				}`}
				onClick={() => setExpanded(!expanded)}
			>
				<CardContent className="p-4">
					<div className="flex items-start justify-between gap-2">
						<div className="flex-1 min-w-0">
							{isTop && (
								<Badge className="mb-2 bg-amber-100 text-amber-700 border border-amber-300 text-[10px] font-semibold">
									TOP DISCOVERY
								</Badge>
							)}
							<p className="text-sm font-bold text-slate-800 leading-snug">
								{hypothesis.title}
							</p>
							<p className="font-mono text-[10px] text-slate-400 mt-1">
								{hypothesis.hypothesis_id}
							</p>
						</div>
						<div className="shrink-0 pt-1">
							{expanded ? (
								<ChevronDown size={14} className="text-slate-400" />
							) : (
								<ChevronRight size={14} className="text-slate-400" />
							)}
						</div>
					</div>

					{/* Score bar */}
					<div className="mt-3 flex items-center gap-3">
						<div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
							<motion.div
								className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400"
								initial={{ width: 0 }}
								animate={{ width: `${(hypothesis.score * 100).toFixed(0)}%` }}
								transition={{ duration: 0.6, ease: "easeOut" }}
							/>
						</div>
						<span className="font-mono text-xs font-semibold text-teal-700 w-8 text-right">
							{hypothesis.score.toFixed(2)}
						</span>
					</div>

					{/* Expandable research brief */}
					<AnimatePresence>
						{expanded && hypothesis.research_brief && (
							<motion.div
								initial={{ height: 0, opacity: 0 }}
								animate={{ height: "auto", opacity: 1 }}
								exit={{ height: 0, opacity: 0 }}
								transition={{ duration: 0.2 }}
								className="overflow-hidden"
							>
								<p className="mt-3 text-xs text-slate-500 leading-relaxed border-t border-slate-100 pt-3">
									{hypothesis.research_brief}
								</p>
							</motion.div>
						)}
					</AnimatePresence>
				</CardContent>
			</Card>
		</motion.div>
	);
}

// --- Metric Card ---

function MetricCard({ value, label, icon }: { value: number; label: string; icon: React.ReactNode }) {
	const [flash, setFlash] = useState(false);
	const prevValue = useRef(value);

	useEffect(() => {
		if (value !== prevValue.current) {
			setFlash(true);
			prevValue.current = value;
			const timer = setTimeout(() => setFlash(false), 600);
			return () => clearTimeout(timer);
		}
	}, [value]);

	return (
		<div
			className={`flex-1 rounded-xl bg-white shadow-sm px-4 py-3 text-center transition-colors duration-300 ${
				flash ? "bg-teal-50 ring-1 ring-teal-300" : ""
			}`}
		>
			<div className="flex items-center justify-center gap-1.5 mb-1 text-slate-400">
				{icon}
			</div>
			<p
				className={`font-mono text-2xl font-bold transition-colors duration-300 ${
					flash ? "text-teal-600" : "text-slate-800"
				}`}
			>
				{value}
			</p>
			<p className="text-xs text-slate-500 mt-0.5">{label}</p>
		</div>
	);
}

// --- Main Page ---

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
	const { id } = use(params);
	const [events, setEvents] = useState<SessionEvent[]>([]);
	const [hypotheses, setHypotheses] = useState<Map<string, TrackedHypothesis>>(new Map());
	const [currentStage, setCurrentStage] = useState("");
	const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
	const [connected, setConnected] = useState(false);
	const [metrics, setMetrics] = useState({ papers: 0, triples: 0, edges: 0, hypotheses: 0, pivots: 0 });

	const eventsEndRef = useRef<HTMLDivElement>(null);
	const timelineRef = useRef<HTMLDivElement>(null);

	const handleEvent = useCallback((event: Record<string, unknown>) => {
		const ev = event as SessionEvent;
		setEvents((prev) => [...prev, ev]);

		switch (ev.type) {
			case "stage_start":
				if (ev.stage) setCurrentStage(ev.stage);
				break;

			case "stage_complete":
				if (ev.stage) {
					setCompletedStages((prev) => {
						const next = new Set(prev);
						// Find the index of this stage in PIPELINE_STAGES and mark it
						const idx = PIPELINE_STAGES.findIndex((s, i) => s === ev.stage && !prev.has(`${s}-${i}`));
						if (idx !== -1) next.add(`${ev.stage}-${idx}`);
						return next;
					});
				}
				if (ev.papers_found) {
					setMetrics((m) => ({ ...m, papers: m.papers + ev.papers_found! }));
				}
				if (ev.triples_extracted) {
					setMetrics((m) => ({ ...m, triples: m.triples + ev.triples_extracted! }));
				}
				if (ev.hypotheses_generated) {
					setMetrics((m) => ({ ...m, hypotheses: m.hypotheses + ev.hypotheses_generated! }));
				}
				break;

			case "hypothesis_scored":
				if (ev.hypothesis_id && ev.title) {
					setHypotheses((prev) => {
						const next = new Map(prev);
						const isNew = !prev.has(ev.hypothesis_id!);
						next.set(ev.hypothesis_id!, {
							hypothesis_id: ev.hypothesis_id!,
							title: ev.title!,
							score: ev.score ?? 0,
							research_brief: ev.research_brief || prev.get(ev.hypothesis_id!)?.research_brief,
						});
						if (isNew) {
							setMetrics((m) => ({ ...m, hypotheses: m.hypotheses + 1 }));
						}
						return next;
					});
				}
				break;

			case "pivot":
				setMetrics((m) => ({ ...m, pivots: m.pivots + 1 }));
				break;

			case "triples_merged":
				if (ev.count) {
					setMetrics((m) => ({ ...m, edges: m.edges + ev.count! }));
				}
				break;

			case "entity_resolved":
				setMetrics((m) => ({ ...m, edges: m.edges + 1 }));
				break;

			case "session_complete":
			case "pipeline_complete":
				setCurrentStage("complete");
				break;
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	useEffect(() => {
		const source = streamSessionEvents(id, (event) => {
			setConnected(true);
			handleEvent(event);
		});

		source.onopen = () => setConnected(true);
		source.onerror = () => {
			// Only set disconnected if source wasn't intentionally closed
			if (source.readyState === EventSource.CLOSED) {
				setConnected(false);
			}
		};

		setConnected(true);

		return () => {
			source.close();
			setConnected(false);
		};
	}, [id, handleEvent]);

	// Auto-scroll timeline
	useEffect(() => {
		eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [events]);

	const sortedHypotheses = Array.from(hypotheses.values()).sort((a, b) => b.score - a.score);
	const isReplicated = id.startsWith("demo-");

	return (
		<div className="flex flex-col h-screen">
			{/* Header */}
			<div className="px-6 pt-6 pb-4 flex items-center justify-between">
				<div className="flex items-center gap-3">
					<div>
						<h1 className="text-xl font-bold text-slate-800 font-sans">Session Monitor</h1>
						<p className="font-mono text-xs text-slate-400 mt-0.5">{id}</p>
					</div>
					{isReplicated && (
						<Badge variant="outline" className="border-slate-300 text-slate-500 text-[10px] font-mono">
							Replicated
						</Badge>
					)}
				</div>
				<div className="flex items-center gap-2">
					<span
						className={`inline-block w-2 h-2 rounded-full ${
							connected ? "bg-emerald-500 animate-pulse" : "bg-red-500"
						}`}
					/>
					<span className="text-xs text-slate-500">
						{connected ? "Connected" : "Disconnected"}
					</span>
				</div>
			</div>

			{/* Pipeline Stepper */}
			<div className="px-6 pb-4">
				<Card className="rounded-xl shadow-sm">
					<CardContent className="py-4 px-2">
						<PipelineStepper currentStage={currentStage} completedStages={completedStages} />
					</CardContent>
				</Card>
			</div>

			{/* Main Content: Timeline + Hypotheses */}
			<div className="flex-1 min-h-0 px-6 pb-4 flex gap-4">
				{/* Event Timeline - 60% */}
				<div className="w-[60%] min-h-0 flex flex-col">
					<Card className="rounded-xl shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden">
						<div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
							<h2 className="text-sm font-semibold text-slate-700">Event Timeline</h2>
							<span className="font-mono text-[10px] text-slate-400">{events.length} events</span>
						</div>
						<div ref={timelineRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-3">
							<div className="space-y-2">
								{events.length === 0 && (
									<div className="flex flex-col items-center justify-center py-16 text-slate-400">
										<CircleDot size={24} className="mb-2 animate-pulse" />
										<p className="text-sm">Waiting for pipeline events...</p>
									</div>
								)}
								<AnimatePresence>
									{events.map((ev, i) => (
										<EventCard key={i} event={ev} index={i} />
									))}
								</AnimatePresence>
								<div ref={eventsEndRef} />
							</div>
						</div>
					</Card>
				</div>

				{/* Hypotheses Panel - 40% */}
				<div className="w-[40%] min-h-0 flex flex-col">
					<Card className="rounded-xl shadow-sm flex-1 min-h-0 flex flex-col overflow-hidden">
						<div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
							<h2 className="text-sm font-semibold text-slate-700">Hypotheses</h2>
							<Badge variant="outline" className="text-[10px] font-mono">
								{sortedHypotheses.length}
							</Badge>
						</div>
						<div className="flex-1 min-h-0 overflow-y-auto px-4 py-3">
							<div className="space-y-3">
								{sortedHypotheses.length === 0 && (
									<div className="flex flex-col items-center justify-center py-16 text-slate-400">
										<Lightbulb size={24} className="mb-2" />
										<p className="text-sm">No hypotheses yet...</p>
									</div>
								)}
								{sortedHypotheses.map((h, i) => (
									<HypothesisCard
										key={h.hypothesis_id}
										hypothesis={h}
										isTop={i === 0 && sortedHypotheses.length > 1}
									/>
								))}
							</div>
						</div>
					</Card>
				</div>
			</div>

			{/* Sticky Bottom Metrics Bar */}
			<div className="shrink-0 px-6 pb-4">
				<div className="flex gap-3">
					<MetricCard value={metrics.papers} label="Papers" icon={<FileText size={14} />} />
					<MetricCard value={metrics.triples} label="Triples" icon={<Triangle size={14} />} />
					<MetricCard value={metrics.edges} label="Edges" icon={<Waypoints size={14} />} />
					<MetricCard value={metrics.hypotheses} label="Hypotheses" icon={<Lightbulb size={14} />} />
					<MetricCard value={metrics.pivots} label="Pivots" icon={<Repeat size={14} />} />
				</div>
			</div>
		</div>
	);
}
