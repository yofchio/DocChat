import { NextRequest } from "next/server";

// =============================================================================
// Next.js API Route — SSE Proxy for Notebook Chat Streaming
// =============================================================================
// Why do we need this proxy?
//   The browser (port 3000) cannot directly call the backend (port 5055)
//   without CORS issues.  This server-side API route acts as a transparent
//   pass-through: it receives the browser's POST request, forwards it to the
//   FastAPI backend, and pipes the SSE ReadableStream straight back to the
//   browser.  The browser sees a same-origin request to /api/chat/stream,
//   so no CORS headers are needed.
//
// The response is a text/event-stream with lines like:
//   data: {"references": [...]}
//   data: {"content": "partial text"}
//   data: [DONE]
// =============================================================================

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:5055";

export async function POST(request: NextRequest) {
  // 1. Read the JSON body and JWT token from the incoming browser request
  const body = await request.json();
  const token = request.headers.get("authorization");

  // 2. Forward the request to the FastAPI backend's streaming endpoint
  const upstream = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: token } : {}),
    },
    body: JSON.stringify(body),
  });

  // 3. Propagate any upstream errors (401, 403, 500, etc.)
  if (!upstream.ok) {
    return new Response(upstream.statusText, { status: upstream.status });
  }

  // 4. Grab the ReadableStream from the upstream response — this is the
  //    raw byte stream of SSE events that FastAPI's StreamingResponse
  //    is producing.  We do NOT buffer it; we pipe it directly.
  const readable = upstream.body;
  if (!readable) {
    return new Response("No stream body", { status: 500 });
  }

  // 5. Return the stream to the browser with SSE-appropriate headers.
  //    "no-cache, no-transform" prevents any intermediate proxy from
  //    buffering the chunks (which would defeat the purpose of streaming).
  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
