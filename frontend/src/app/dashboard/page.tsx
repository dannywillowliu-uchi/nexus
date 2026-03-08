"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const sessionHistory = [
  { id: "sess_01", query: "Alzheimer's Disease", status: "complete", hypotheses: 12, date: "2026-03-07" },
  { id: "sess_02", query: "Type 2 Diabetes", status: "complete", hypotheses: 8, date: "2026-03-06" },
  { id: "sess_03", query: "Parkinson's Disease", status: "running", hypotheses: 3, date: "2026-03-08" },
];

const subscriptions = [
  { disease: "Alzheimer's Disease", frequency: "Daily", lastNotified: "2026-03-07" },
  { disease: "Breast Cancer", frequency: "Weekly", lastNotified: "2026-03-03" },
];

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <h1 className="mb-2 text-3xl font-bold text-slate-800">Dashboard</h1>
      <p className="mb-8 text-slate-500">
        Manage your sessions, subscriptions, and API access.
      </p>

      {/* Credits Card */}
      <div className="mb-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-500">Credits Remaining</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-teal-600">2,500</p>
            <p className="mt-1 text-xs text-slate-400">of 5,000 monthly</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-500">Sessions This Month</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-slate-800">14</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-500">Hypotheses Generated</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-slate-800">87</p>
          </CardContent>
        </Card>
      </div>

      {/* Session History */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Session History</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session ID</TableHead>
                <TableHead>Query</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hypotheses</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessionHistory.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono text-xs">{s.id}</TableCell>
                  <TableCell>{s.query}</TableCell>
                  <TableCell>
                    <Badge
                      className={
                        s.status === "complete"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-amber-100 text-amber-700"
                      }
                    >
                      {s.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{s.hypotheses}</TableCell>
                  <TableCell className="text-slate-500">{s.date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Subscriptions */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Subscriptions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {subscriptions.map((sub) => (
              <div
                key={sub.disease}
                className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    {sub.disease}
                  </p>
                  <p className="text-xs text-slate-400">
                    {sub.frequency} updates, last: {sub.lastNotified}
                  </p>
                </div>
                <Button variant="outline" size="sm">
                  Manage
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-700">
                  Production Key
                </p>
                <p className="font-mono text-xs text-slate-400">
                  nxs_prod_****...****7f2a
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  Copy
                </Button>
                <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                  Revoke
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-700">
                  Development Key
                </p>
                <p className="font-mono text-xs text-slate-400">
                  nxs_dev_****...****3e1b
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  Copy
                </Button>
                <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                  Revoke
                </Button>
              </div>
            </div>
            <Button className="mt-2 bg-teal-600 hover:bg-teal-700">
              Generate New Key
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
