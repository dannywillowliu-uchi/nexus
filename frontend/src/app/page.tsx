import Link from "next/link";

const stats = [
	{ value: "129K+", label: "Knowledge Graph", sublabel: "nodes" },
	{ value: "8.1M+", label: "PrimeKG Relationships", sublabel: "edges" },
	{ value: "10/10", label: "Benchmark Recovery", sublabel: "score" },
];

const stages = [
	"Literature",
	"Graph",
	"Reasoning",
	"Validation",
	"Experiment",
	"Protocol",
	"Cloud Lab",
];

export default function Home() {
	return (
		<div className="px-8 py-20">
			{/* Hero */}
			<section className="text-center">
				<h1 className="font-mono text-6xl font-bold text-teal-600 tracking-tight">
					NEXUS
				</h1>
				<p className="mt-4 text-lg font-sans text-slate-500">
					Autonomous Biological Discovery Platform
				</p>
				<Link href="/query">
					<button className="glow-button mt-10 rounded-xl bg-teal-600 px-10 py-3.5 text-base font-semibold text-white transition-colors hover:bg-teal-700">
						Try a Discovery
					</button>
				</Link>
			</section>

			{/* Stats */}
			<section className="mx-auto mt-20 max-w-3xl">
				<div className="grid grid-cols-3 gap-6">
					{stats.map((stat) => (
						<div
							key={stat.label}
							className="rounded-xl bg-white px-6 py-8 text-center shadow-sm"
						>
							<p className="font-mono text-3xl font-bold text-teal-600">
								{stat.value}
							</p>
							<p className="mt-1 text-xs text-slate-400 font-mono">
								{stat.sublabel}
							</p>
							<p className="mt-2 text-sm text-slate-500">
								{stat.label}
							</p>
						</div>
					))}
				</div>
			</section>

			{/* Pipeline Diagram */}
			<section className="mx-auto mt-24 max-w-4xl">
				<p className="mb-8 text-center text-sm font-mono text-slate-400 uppercase tracking-widest">
					Discovery Pipeline
				</p>
				<div className="flex items-center justify-center">
					{stages.map((stage, i) => (
						<div key={stage} className="flex items-center">
							<div className="flex flex-col items-center">
								<div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-600 text-white font-mono text-sm font-semibold">
									{i + 1}
								</div>
								<span className="mt-2 text-xs font-mono text-slate-500">
									{stage}
								</span>
							</div>
							{i < stages.length - 1 && (
								<div className="mx-2 h-px w-10 bg-slate-300" />
							)}
						</div>
					))}
				</div>
			</section>
		</div>
	);
}
