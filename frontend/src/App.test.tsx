import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
const response = {
  request_id: '8341de8b-c1fe-49b0-b8b0-be9e24d1ca51', model_version: 'retrieval-bundle-v001',
  method: 'two_tower', fallback_reason: null,
  items: [{ channel_id: '12321', channel_name: 'ninja', retrieval_score: 21.48 },
    { channel_id: '17025', channel_name: 'tfue', retrieval_score: 19.14 }],
};
function body(value: unknown = response, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
afterEach(() => vi.unstubAllGlobals());
async function submit(id = '1') {
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: /user id/i }), id);
  await user.click(screen.getByRole('button', { name: /get recommendations/i }));
  return user;
}
it('submits by keyboard, trims ID and displays the server order', async () => {
  const fetch = vi.fn().mockResolvedValue(body()); vi.stubGlobal('fetch', fetch);
  render(<App />);
  const user = userEvent.setup();
  await user.type(screen.getByRole('textbox', { name: /user id/i }), ' 1 {Enter}');
  expect(await screen.findByText('ninja')).toBeVisible();
  const cards = screen.getAllByRole('listitem');
  expect(within(cards[0]).getByText('ninja')).toBeVisible();
  expect(within(cards[1]).getByText('tfue')).toBeVisible();
  expect(screen.getByText(/personalized/i)).toBeVisible();
  expect(fetch.mock.calls[0][1].body).toBe('{"user_id":"1","k":10}');
});
it.each(['   ', 'a'.repeat(129)])('rejects invalid user ID before contacting Java', async id => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<App />); await submit(id);
  expect(screen.getByRole('alert')).toHaveTextContent(/1.*128/);
  expect(fetch).not.toHaveBeenCalled();
});
it('accepts 128 Unicode code points rather than counting UTF-16 units', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body()));
  render(<App />); await submit('😀'.repeat(128));
  expect(await screen.findByText('ninja')).toBeVisible();
});
it('disables repeat submission while loading', async () => {
  let resolve!: (response: Response) => void;
  const fetch = vi.fn().mockImplementation(() => new Promise<Response>(r => { resolve = r; }));
  vi.stubGlobal('fetch', fetch);
  render(<App />); const user = await submit();
  expect(screen.getByRole('button', { name: /finding/i })).toBeDisabled();
  await user.click(screen.getByRole('button'));
  expect(fetch).toHaveBeenCalledTimes(1);
  resolve(body());
  expect(await screen.findByText('ninja')).toBeVisible();
});
it('explains unknown-user fallback and does not display null as a score', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body({ ...response, method: 'popular',
    fallback_reason: 'unknown_user', items: [{ ...response.items[0], retrieval_score: null }] })));
  render(<App />); await submit('new-user');
  expect(await screen.findByText('ninja')).toBeVisible();
  expect(screen.getByText(/not in the trained model/i)).toBeVisible();
  expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
});
it('explains retrieval-error fallback separately', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body({ ...response, method: 'popular',
    fallback_reason: 'retrieval_error', items: [{ ...response.items[0], retrieval_score: null }] })));
  render(<App />); await submit();
  expect(await screen.findByText(/personalized retrieval is temporarily unavailable/i)).toBeVisible();
});
it('clears previous results on resubmit and allows retry after failure', async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(body())
    .mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }))
    .mockImplementation(() => Promise.resolve(body())));
  render(<App />); const user = await submit();
  expect(await screen.findByText('ninja')).toBeVisible();
  await user.click(screen.getByRole('button', { name: /get recommendations/i }));
  expect(screen.queryByText('ninja')).not.toBeInTheDocument();
  resolve(body({}, 503));
  expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable/i);
  await user.click(screen.getByRole('button', { name: /get recommendations/i }));
  expect(await screen.findByText('ninja')).toBeVisible();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
it('shows an explicit empty state', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body({ ...response, items: [] })));
  render(<App />); await submit();
  expect(await screen.findByText(/no channels were returned/i)).toBeVisible();
});
it('renders HTML-like channel names as text', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(body({ ...response,
    items: [{ ...response.items[0], channel_name: '<img src=x onerror=alert(1)>' }] })));
  render(<App />); await submit();
  expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeVisible();
  expect(document.querySelector('img')).toBeNull();
});
