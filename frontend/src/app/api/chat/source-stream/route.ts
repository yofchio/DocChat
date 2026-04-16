import { NextRequest } from "next/server";

// =============================================================================
// Next.js API Route — SSE Proxy for Source-Scoped Chat Streaming
// =============================================================================
// Same pattern as /api/chat/stream/route.ts, but proxies to the backend's
// source-scoped chat endpoint (POST /api/chat/source/stream).
//
// The difference is that this endpoint only searches for relevant chunks
// within a SINGLE source document, while /chat/stream searches across ALL
// sources in a notebook.
// =============================================================================

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:5055";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const token = request.headers.get("authorization");

  // Forward to the FastAPI source-scoped streaming endpoint
  const upstream = await fetch(`${API_BASE}/api/chat/source/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: token } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    return new Response(upstream.statusText, { status: upstream.status });
  }

  // Pipe the SSE stream directly back to the browser (no buffering)
  const readable = upstream.body;
  if (!readable) {
    return new Response("No stream body", { status: 500 });
  }

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
