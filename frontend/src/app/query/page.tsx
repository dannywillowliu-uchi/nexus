"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
	"Drug",
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

const exampleQueries = [
	{ label: "Riluzole -> melanoma", query: "Riluzole", entity: "Riluzole" },
	{ label: "Thalidomide -> myeloma", query: "Thalidomide", entity: "Thalidomide" },
	{ label: "Auranofin -> ovarian cancer", query: "Auranofin", entity: "Auranofin" },
];

export default function QueryPage() {
	const router = useRouter();
	const [query, setQuery] = useState("Riluzole");
	const [startType, setStartType] = useState("Drug");
	const [targetTypes, setTargetTypes] = useState<string[]>(["Disease"]);
	const [reasoningDepth, setReasoningDepth] = useState("full");
	const [maxHypotheses, setMaxHypotheses] = useState(10);
	const [maxPivots, setMaxPivots] = useState(3);
	const [showAdvanced, setShowAdvanced] = useState(false);
	const [submitting, setSubmitting] = useState(false);

	function toggleTarget(type: string) {
		setTargetTypes((prev) =>
			prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
		);
	}

	function applyExample(example: { query: string; entity: string }) {
		setQuery(example.query);
	}

	async function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		setSubmitting(true);
		try {
			const result = await createSession({
				query,
				disease_area: query,
				start_entity: query,
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
		<div className="flex items-start justify-center px-8 py-16">
			<div className="w-full max-w-2xl">
				<h1 className="mb-1 font-mono text-2xl font-bold text-slate-800">
					New Discovery
				</h1>
				<p className="mb-8 text-sm text-slate-500">
					Define a compound or entity and let Nexus find novel connections.
				</p>

				<form onSubmit={handleSubmit}>
					<div className="gradient-border">
						<div className="rounded-xl bg-white p-8 shadow-sm">
							<div className="space-y-6">
								{/* Query Input */}
								<div className="space-y-2">
									<Label htmlFor="query" className="text-sm font-medium text-slate-700">
										Query Entity
									</Label>
									<Input
										id="query"
										placeholder="e.g. Riluzole, Thalidomide, Auranofin"
										value={query}
										onChange={(e) => setQuery(e.target.value)}
										className="rounded-lg text-base"
										required
									/>
									{/* Example chips */}
									<div className="flex flex-wrap gap-2 pt-1">
										{exampleQueries.map((ex) => (
											<button
												key={ex.label}
												type="button"
												onClick={() => applyExample(ex)}
												className="rounded-full bg-slate-100 px-3 py-1 text-xs font-mono text-slate-500 transition-colors hover:bg-teal-50 hover:text-teal-600"
											>
												{ex.label}
											</button>
										))}
									</div>
								</div>

								{/* Entity Type */}
								<div className="space-y-2">
									<Label className="text-sm font-medium text-slate-700">
										Entity Type
									</Label>
									<Select value={startType} onValueChange={(v) => v && setStartType(v)}>
										<SelectTrigger className="rounded-lg">
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

								{/* Target Types as chips */}
								<div className="space-y-2">
									<Label className="text-sm font-medium text-slate-700">
										Target Types
									</Label>
									<div className="flex flex-wrap gap-2">
										{targetTypeOptions.map((t) => (
											<button
												key={t}
												type="button"
												onClick={() => toggleTarget(t)}
												className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
													targetTypes.includes(t)
														? "bg-teal-600 text-white"
														: "bg-slate-100 text-slate-500 hover:bg-slate-200"
												}`}
											>
												{t}
											</button>
										))}
									</div>
								</div>

								{/* Advanced Toggle */}
								<div>
									<button
										type="button"
										onClick={() => setShowAdvanced(!showAdvanced)}
										className="text-xs font-mono text-slate-400 hover:text-slate-600 transition-colors"
									>
										{showAdvanced ? "- Hide" : "+ Show"} Advanced Options
									</button>

									{showAdvanced && (
										<div className="mt-4 space-y-4 rounded-lg bg-slate-50 p-4">
											{/* Reasoning Depth */}
											<div className="space-y-2">
												<Label className="text-xs text-slate-600">Reasoning Depth</Label>
												<Select value={reasoningDepth} onValueChange={(v) => v && setReasoningDepth(v)}>
													<SelectTrigger className="rounded-lg">
														<SelectValue />
													</SelectTrigger>
													<SelectContent>
														<SelectItem value="quick">Quick</SelectItem>
														<SelectItem value="full">Full</SelectItem>
													</SelectContent>
												</Select>
											</div>

											{/* Max Hypotheses + Max Pivots */}
											<div className="grid grid-cols-2 gap-4">
												<div className="space-y-2">
													<Label htmlFor="maxHypotheses" className="text-xs text-slate-600">
														Max Hypotheses
													</Label>
													<Input
														id="maxHypotheses"
														type="number"
														min={1}
														max={50}
														value={maxHypotheses}
														onChange={(e) => setMaxHypotheses(Number(e.target.value))}
														className="rounded-lg"
													/>
												</div>
												<div className="space-y-2">
													<Label htmlFor="maxPivots" className="text-xs text-slate-600">
														Pivot Budget
													</Label>
													<Input
														id="maxPivots"
														type="number"
														min={0}
														max={10}
														value={maxPivots}
														onChange={(e) => setMaxPivots(Number(e.target.value))}
														className="rounded-lg"
													/>
												</div>
											</div>
										</div>
									)}
								</div>

								{/* Submit */}
								<button
									type="submit"
									disabled={submitting || !query || targetTypes.length === 0}
									className="glow-button w-full rounded-xl bg-teal-600 py-3.5 text-base font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
								>
									{submitting ? "Launching Session..." : "Launch Discovery"}
								</button>
							</div>
						</div>
					</div>
				</form>
			</div>
		</div>
	);
}
