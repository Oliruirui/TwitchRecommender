export interface Channel {
  channel_id: string;
  channel_name: string;
  retrieval_score: number | null;
}
export interface RecommendationResponse {
  request_id: string;
  model_version: string;
  method: 'two_tower' | 'popular';
  fallback_reason: null | 'unknown_user' | 'retrieval_error';
  items: Channel[];
}
const invalidResponse = () => new Error('The service returned an invalid response. Please try again.');
function isResponse(value: unknown): value is RecommendationResponse {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  if (typeof v.request_id !== 'string' || !/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(v.request_id)
    || typeof v.model_version !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(v.model_version)
    || !Array.isArray(v.items) || v.items.length > 10) return false;
  const personalized = v.method === 'two_tower' && v.fallback_reason === null;
  const popular = v.method === 'popular' && ['unknown_user', 'retrieval_error'].includes(String(v.fallback_reason));
  if (!personalized && !popular) return false;
  const seen = new Set<string>();
  let previous = Infinity;
  return v.items.every((item: unknown) => {
    if (!item || typeof item !== 'object') return false;
    const c = item as Record<string, unknown>;
    if (typeof c.channel_id !== 'string' || !/^(0|[1-9]\d*)$/.test(c.channel_id)
      || seen.has(c.channel_id) || typeof c.channel_name !== 'string' || !c.channel_name.trim()) return false;
    seen.add(c.channel_id);
    if (popular) return c.retrieval_score === null;
    if (typeof c.retrieval_score !== 'number' || !Number.isFinite(c.retrieval_score)
      || c.retrieval_score > previous) return false;
    previous = c.retrieval_score;
    return true;
  });
}
export async function fetchRecommendations(userId: string): Promise<RecommendationResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    let response: Response;
    try {
      response = await fetch('/api/recommendations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, k: 10 }), signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) throw new Error('The request timed out. Please try again.');
      throw new Error('Could not connect to the recommendation service. Please try again.');
    }
    if (!response.ok) throw new Error(response.status === 400
      ? 'Check your user ID and try again.'
      : 'Recommendations are unavailable right now. Please try again.');
    let data: unknown;
    try { data = await response.json(); }
    catch {
      if (controller.signal.aborted) throw new Error('The request timed out. Please try again.');
      throw invalidResponse();
    }
    if (!isResponse(data)) throw invalidResponse();
    return data;
  } finally { clearTimeout(timeout); }
}
