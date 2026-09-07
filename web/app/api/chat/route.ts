import { auth } from "@/auth"
import { mintServiceToken } from "@/lib/service-token"

export const runtime = "nodejs"
export const maxDuration = 300

/**
 * Translates the agent's SSE progress stream into an AI SDK UI message stream.
 *
 * The backend emits one event per thing the agent does — a turn's narration
 * tokens, each tool call, each tool result — and they are forwarded in order so
 * the user watches the run unfold instead of waiting on a final answer:
 *
 *   text_start/delta/end  ->  text parts (one block per agent turn)
 *   tool_call             ->  data-tool part, status "running"
 *   tool_result           ->  same data-tool part id, status "done" | "error"
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

      // Arguments arrive on tool_call and are needed again on tool_result, so
      // the finished card can still say what was searched for.
      const callArgs = new Map<string, unknown>()
      const openBlocks = new Set<string>()

      const send = (obj: unknown) =>
        controller.enqueue(
          new TextEncoder().encode(`data: ${JSON.stringify(obj)}\n\n`)
        )

      try {
        send({ type: "start" })

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n")
          const events = buffer.split("\n\n")
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

            switch (eventType) {
              case "text_start":
                openBlocks.add(data.block)
                send({ type: "text-start", id: data.block })
                break

              case "text_delta":
                send({ type: "text-delta", id: data.block, delta: data.text })
                break

              case "text_end":
                openBlocks.delete(data.block)
                send({ type: "text-end", id: data.block })
                break

              case "tool_call":
                callArgs.set(data.id, data.arguments)
                send({
                  type: "data-tool",
                  id: data.id,
                  data: {
                    tool: data.name,
                    arguments: data.arguments,
                    status: "running",
                    step: data.step,
                  },
                })
                break

              case "tool_result":
                // Same id as the tool_call above, so this replaces that part
                // rather than appending a second one.
                send({
                  type: "data-tool",
                  id: data.id,
                  data: {
                    tool: data.name,
                    arguments: callArgs.get(data.id) ?? {},
                    status: data.ok ? "done" : "error",
                    preview: data.preview,
                    ms: data.ms,
                    cached: data.cached,
                  },
                })
                break

              case "approval_required":
                if (data.name === "ask_user") {
                  send({
                    type: "data-choice",
                    data: {
                      runId: data.run_id,
                      question: data.arguments.question,
                      options: data.arguments.options ?? [],
                    },
                  })
                } else {
                  send({
                    type: "data-approval",
                    data: {
                      runId: data.run_id,
                      tool: data.name,
                      arguments: data.arguments,
                    },
                  })
                }
                break

              case "done":
                for (const block of openBlocks) send({ type: "text-end", id: block })
                openBlocks.clear()
                send({ type: "finish" })
                break

              case "error":
                send({ type: "error", errorText: data.message })
                break
            }
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
