import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchRecommendations } from './api';

const personalized = {
  request_id: '8341de8b-c1fe-49b0-b8b0-be9e24d1ca51', model_version: 'retrieval-bundle-v001',
  method: 'two_tower', fallback_reason: null,
  items: [{ channel_id: '12321', channel_name: 'ninja', retrieval_score: 21.48 },
    { channel_id: '17025', channel_name: 'tfue', retrieval_score: 19.14 }],
};
function respond(body: unknown, status = 200) {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
describe('recommendation API boundary', () => {
  it('posts the exact Java request and preserves channel order and scores', async () => {
    const fetch = respond(personalized);
    expect(await fetchRecommendations('1')).toEqual(personalized);
    expect(fetch).toHaveBeenCalledWith('/api/recommendations', expect.objectContaining({
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: '{"user_id":"1","k":10}', signal: expect.any(AbortSignal),
    }));
  });
  it('accepts both popularity fallback reasons with null scores', async () => {
    for (const reason of ['unknown_user', 'retrieval_error']) {
      const result = { ...personalized, method: 'popular', fallback_reason: reason,
        items: [{ channel_id: '12321', channel_name: 'ninja', retrieval_score: null }] };
      respond(result);
      expect(await fetchRecommendations('new-user')).toEqual(result);
    }
  });
  it('accepts an empty result so the page can explain it', async () => {
    respond({ ...personalized, items: [] });
    expect((await fetchRecommendations('1')).items).toEqual([]);
  });
  it.each([400, 503, 500])('turns HTTP %i into a readable error without leaking the server body', async status => {
    respond({ error: 'private-internal-detail' }, status);
    await expect(fetchRecommendations('1')).rejects.toThrow(status === 400 ? /user ID/i : /unavailable/i);
  });
  it.each([
    null, {}, { ...personalized, items: 'bad' },
    { ...personalized, items: [{ channel_id: '1', channel_name: '', retrieval_score: 2 }] },
    { ...personalized, items: [{ channel_id: '1', channel_name: 'name', retrieval_score: null }] },
    { ...personalized, method: 'popular', fallback_reason: 'unknown_user' },
    { ...personalized, items: [personalized.items[0], personalized.items[0]] },
    { ...personalized, items: [...personalized.items].reverse() },
    { ...personalized, request_id: '' },
  ])('rejects malformed successful response %#', async body => {
    respond(body);
    await expect(fetchRecommendations('1')).rejects.toThrow(/invalid response/i);
  });
  it('handles invalid JSON and network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json')));
    await expect(fetchRecommendations('1')).rejects.toThrow(/invalid response/i);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network details')));
    await expect(fetchRecommendations('1')).rejects.toThrow(/connect/i);
  });
  it('bounds waiting to ten seconds and aborts the request', async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => {
      signal = options.signal;
      signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    })));
    const result = fetchRecommendations('1');
    const assertion = expect(result).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(10_000);
    await assertion;
    expect(signal?.aborted).toBe(true);
  });
});
