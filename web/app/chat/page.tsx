"use client"

import { useState } from "react"
import { useChat } from "@ai-sdk/react"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent } from "@/components/ai-elements/message"

type Approval = { runId: string; tool: string; arguments: Record<string, unknown> }

export default function Chat() {
  const { messages, sendMessage, status } = useChat()
  const [input, setInput] = useState("")
  // resolved approvals: runId -> the answer that came back after deciding
  const [resolved, setResolved] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)

  const submit = () => {
    if (!input.trim()) return
    sendMessage({ text: input })
    setInput("")
  }

  const decide = async (runId: string, decision: "approve" | "reject") => {
    console.log("DECIDING:", runId, decision)
    setBusy(runId)
    try {
      const res = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: runId, decision }),
      })
      const data = await res.json()
      setResolved((r) => ({ ...r, [runId]: data.answer ?? "(no answer)" }))
    } catch {
      setResolved((r) => ({ ...r, [runId]: "Something went wrong resuming the run." }))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto p-4">
      <Conversation className="flex-1">
        <ConversationContent>
          {messages.length === 0 ? (
            <ConversationEmptyState
              title="Ask anything"
              description="Your documents, the web, and your connected tools."
            />
          ) : (
            messages.map((m) => {
              // find an approval part, if any, on this message
              const approval = m.parts.find(
                (p) => p.type === "data-approval"
              ) as unknown as { data: Approval } | undefined

              return (
                <Message from={m.role} key={m.id}>
                  <MessageContent>
                    {approval ? (
                      resolved[approval.data.runId] !== undefined ? (
                        <span>{resolved[approval.data.runId]}</span>
                      ) : (
                        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                          <p className="text-sm mb-2">
                            The assistant wants to run{" "}
                            <code className="text-xs">{approval.data.tool}</code>.
                            Allow it?
                          </p>
                          <div className="flex gap-2">
                            <button
                              onClick={() => decide(approval.data.runId, "approve")}
                              disabled={busy === approval.data.runId}
                              className="rounded border px-3 py-1 text-sm disabled:opacity-50"
                            >
                              {busy === approval.data.runId ? "..." : "Approve"}
                            </button>
                            <button
                              onClick={() => decide(approval.data.runId, "reject")}
                              disabled={busy === approval.data.runId}
                              className="rounded border px-3 py-1 text-sm disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      )
                    ) : (
                      m.parts.map((p, i) =>
                        p.type === "text" ? <span key={i}>{p.text}</span> : null
                      )
                    )}
                  </MessageContent>
                </Message>
              )
            })
          )}
        </ConversationContent>
      </Conversation>

      <form onSubmit={(e) => { e.preventDefault(); submit() }} className="mt-4 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() }
          }}
          placeholder="Ask a question"
          rows={1}
          className="flex-1 resize-none rounded-lg border p-3 text-sm"
        />
        <button type="submit" disabled={status === "streaming"}
          className="rounded-lg border px-4 text-sm disabled:opacity-50">
          {status === "streaming" ? "..." : "Send"}
        </button>
      </form>
    </div>
  )
}
