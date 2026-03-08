import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const stats = [
  { label: "Discoveries", value: "2,847" },
  { label: "Hypotheses Validated", value: "412" },
  { label: "Active Sessions", value: "23" },
];

const sampleDiscoveries = [
  {
    title: "VEGFA mediates unexpected link between Diabetes and Retinopathy",
    disease: "Diabetes",
    novelty: 0.89,
    path: "Diabetes -> VEGFA -> Diabetic Retinopathy",
  },
  {
    title: "IL-6 pathway connects Rheumatoid Arthritis to Depression",
    disease: "Rheumatoid Arthritis",
    novelty: 0.76,
    path: "Rheumatoid Arthritis -> IL-6 -> Major Depression",
  },
  {
    title: "BRCA1 repair mechanism reveals Ovarian Cancer drug target",
    disease: "Ovarian Cancer",
    novelty: 0.92,
    path: "Ovarian Cancer -> BRCA1 -> PARP Inhibitor Sensitivity",
  },
];

export default function Home() {
  return (
    <div className="bg-fafafa">
      {/* Hero */}
      <section className="mx-auto max-w-7xl px-6 py-24 text-center">
        <h1 className="text-5xl font-bold tracking-tight text-slate-800">
          Nexus
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-500">
          Autonomous biological discovery through ABC reasoning. Uncover hidden
          connections between diseases, genes, and compounds that no one has
          explored before.
        </p>
        <Link href="/query">
          <Button className="mt-8 bg-teal-600 px-8 py-3 text-base hover:bg-teal-700">
            Start a Discovery Session
          </Button>
        </Link>
      </section>

      {/* Stats */}
      <section className="mx-auto max-w-7xl px-6 pb-16">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {stats.map((stat) => (
            <Card key={stat.label} className="text-center">
              <CardHeader className="pb-2">
                <CardTitle className="text-3xl font-bold text-teal-600">
                  {stat.value}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-500">{stat.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Sample Discoveries */}
      <section className="mx-auto max-w-7xl px-6 pb-24">
        <h2 className="mb-6 text-2xl font-semibold text-slate-800">
          Recent Discoveries
        </h2>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {sampleDiscoveries.map((d) => (
            <Card key={d.title} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="bg-teal-50 text-teal-700">
                    {d.disease}
                  </Badge>
                  <span className="text-sm font-medium text-emerald-600">
                    {(d.novelty * 100).toFixed(0)}% novel
                  </span>
                </div>
                <CardTitle className="mt-2 text-base leading-snug">
                  {d.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-mono text-xs text-slate-400">{d.path}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
