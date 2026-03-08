const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function assertOk(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }
  return res;
}

export async function createSession(request: {
  query: string;
  disease_area: string;
  start_entity: string;
  start_type: string;
  target_types: string[];
  max_hypotheses?: number;
  reasoning_depth?: string;
  max_pivots?: number;
}) {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  await assertOk(res);
  return res.json();
}

export function streamSessionEvents(
  sessionId: string,
  onEvent: (event: Record<string, unknown>) => void,
  onError?: (error: Event) => void,
) {
  const source = new EventSource(`${API_BASE}/sessions/${sessionId}/stream`);
  source.onmessage = (e) => onEvent(JSON.parse(e.data));
  source.onerror = (e) => {
    if (onError) onError(e);
  };
  return source;
}

export async function getSessionReport(sessionId: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/report`);
  await assertOk(res);
  return res.json();
}

export async function getFeed(params?: { disease_area?: string; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.disease_area) query.set("disease_area", params.disease_area);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const res = await fetch(`${API_BASE}/feed?${query}`);
  await assertOk(res);
  return res.json();
}

export async function getHypothesis(id: string) {
  const res = await fetch(`${API_BASE}/hypotheses/${id}`);
  await assertOk(res);
  return res.json();
}

export async function submitExperiment(hypothesisId: string, provider?: string) {
  const res = await fetch(`${API_BASE}/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hypothesis_id: hypothesisId, provider: provider || "simulator" }),
  });
  await assertOk(res);
  return res.json();
}

export async function getExperiment(experimentId: string) {
  const res = await fetch(`${API_BASE}/experiments/${experimentId}`);
  await assertOk(res);
  return res.json();
}

export async function exploreGraph(params: { entity_name: string; entity_type: string; depth?: number }) {
  const query = new URLSearchParams({
    entity_name: params.entity_name,
    entity_type: params.entity_type,
    depth: String(params.depth || 1),
  });
  const res = await fetch(`${API_BASE}/graph/explore?${query}`);
  await assertOk(res);
  return res.json();
}
