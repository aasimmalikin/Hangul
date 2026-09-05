import { auth } from "@/auth"
import { mintServiceToken } from "@/lib/service-token"

// Node runtime, not Edge: Edge caps streaming at ~25s and agent runs exceed that.
export const runtime = "nodejs"
export const maxDuration = 300

/**
 * Backend-for-frontend chat route.
 *
 * Verifies the Auth.js session, mints a short-lived JWT the FastAPI backend
 * trusts, proxies the question to the agent's SSE endpoint, and translates
 * the agent's event stream into the AI SDK's UI message stream protocol.
 *
 * Tool events are deliberately NOT forwarded to the browser: the end user sees
 * only the answer. Tool activity remains available to the admin console, which
 * reads it from the backend's trace store rather than from this stream.
 */
export async function POST(req: Request) {
  const session = await auth()
  if (!session?.user?.email) {
    return new Response("Unauthorized", { status: 401 })
  }

  const token = await mintServiceToken(session.user.email, "user")

  const body = await req.json()
  const question =
    body.messages?.[body.messages.length - 1]?.parts?.[0]?.text ??
    body.messages?.[body.messages.length - 1]?.content ??
    ""

  const upstream = await fetch(`${process.env.FASTAPI_URL}/ask/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  })

  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      const send = (obj: unknown) =>
        controller.enqueue(
          new TextEncoder().encode(`data: ${JSON.stringify(obj)}\n\n`)
        )

      try {
        send({ type: "start" })
        send({ type: "text-start", id: "0" })

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          // Normalise CRLF: the upstream sends \r\n, but SSE events are split
          // on a blank line, so mixed endings break the delimiter.
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n")

          const events = buffer.split("\n\n")
          // The final piece may be a partial event; keep it for the next chunk.
          buffer = events.pop() ?? ""

          for (const evt of events) {
            let eventType = ""
            let dataStr = ""
            for (const line of evt.split("\n")) {
              if (line.startsWith("event:")) eventType = line.slice(6).trim()
              else if (line.startsWith("data:")) dataStr = line.slice(5).trim()
            }
            if (!dataStr) continue
            const data = JSON.parse(dataStr)

            if (eventType === "token") {
              send({ type: "text-delta", id: "0", delta: data.text })
            } else if (eventType === "done") {
              send({ type: "text-end", id: "0" })
              send({ type: "finish" })
            } else if (eventType === "error") {
              send({ type: "error", errorText: data.message })
            }
            // tool_call / tool_used events are intentionally not forwarded.
          }
        }
      } catch (e) {
        send({ type: "error", errorText: String(e) })
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "x-vercel-ai-ui-message-stream": "v1",
    },
  })
}
