export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  const body = await req.json();
  const apiBase = process.env.API_BASE_URL;
  if (!apiBase) {
    return new Response('Missing API_BASE_URL', { status: 500 });
  }

  // Forward Authorization header if the client sent one
  const auth = req.headers.get('authorization') || undefined;

  // Forward to FastAPI streaming endpoint
  const upstream = await fetch(`${apiBase}/chat/stream`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(auth ? { authorization: auth } : {}),
    },
    body: JSON.stringify(body),
  });

  // Pipe the upstream SSE/stream back to the client
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      'content-type': upstream.headers.get('content-type') || 'text/event-stream',
      'cache-control': 'no-cache',
    },
  });
}
