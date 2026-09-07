import { auth } from "@/auth"
import { mintServiceToken } from "@/lib/service-token"

export const runtime = "nodejs"
export const maxDuration = 300

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
      let pendingApproval = false

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

            if (eventType === "approval_required") {
              // Suppress the placeholder answer text so the card stands alone.
              pendingApproval = true
              if (data.name === "ask_user") {
                // A clarification question, not an action approval. Options are
                // {label, description} objects; tolerate plain strings too, so a
                // checkpoint written before that schema change still renders.
                const options = (data.arguments.options ?? []).map(
                  (o: unknown) =>
                    typeof o === "string"
                      ? { label: o, description: "" }
                      : {
                          label: String((o as { label?: unknown }).label ?? ""),
                          description: String(
                            (o as { description?: unknown }).description ?? ""
                          ),
                        }
                )
                send({
                  type: "data-choice",
                  data: {
                    runId: data.run_id,
                    question: data.arguments.question,
                    options,
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
            } else if (eventType === "token") {
              if (!pendingApproval) {
                send({ type: "text-delta", id: "0", delta: data.text })
              }
            } else if (eventType === "done") {
              send({ type: "text-end", id: "0" })
              send({ type: "finish" })
            } else if (eventType === "error") {
              send({ type: "error", errorText: data.message })
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
