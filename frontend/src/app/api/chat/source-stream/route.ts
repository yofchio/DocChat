import { NextRequest } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:5055";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const token = request.headers.get("authorization");

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
