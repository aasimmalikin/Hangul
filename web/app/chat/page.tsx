"use client"

import { useState } from "react"
import { useChat } from "@ai-sdk/react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent } from "@/components/ai-elements/message"

type Approval = { runId: string; tool: string; arguments: Record<string, unknown> }
type ChoiceOption = { label: string; description: string }
type Choice = { runId: string; question: string; options: ChoiceOption[] }

function AnswerText({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 underline"
          >
            {children}
          </a>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  )
}

export default function Chat() {
  const { messages, sendMessage, status } = useChat()
  const [input, setInput] = useState("")
  const [resolved, setResolved] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)

  const submit = () => {
    if (!input.trim()) return
    sendMessage({ text: input })
    setInput("")
  }

  const decide = async (runId: string, decision: "approve" | "reject") => {
    setBusy(runId)
    try {
      const res = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: runId, decision }),
      })
      const data = await res.json()
      setResolved((r) => ({ ...r, [runId]: data.answer || "Done." }))
    } catch {
      setResolved((r) => ({ ...r, [runId]: "Something went wrong resuming the run." }))
    } finally {
      setBusy(null)
    }
  }

  const answer = async (runId: string, choice: string) => {
    setBusy(runId)
    try {
      const res = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: runId, decision: "approve", choice }),
      })
      const data = await res.json()
      setResolved((r) => ({ ...r, [runId]: data.answer || "Done." }))
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
              const approval = m.parts.find(
                (p) => p.type === "data-approval"
              ) as unknown as { data: Approval } | undefined

              const choice = m.parts.find(
                (p) => p.type === "data-choice"
              ) as unknown as { data: Choice } | undefined

              return (
                <Message from={m.role} key={m.id}>
                  <MessageContent>
                    {choice ? (
                      resolved[choice.data.runId] !== undefined ? (
                        <AnswerText text={resolved[choice.data.runId]} />
                      ) : (
                        <div className="rounded-lg border border-blue-300 bg-blue-50 p-3">
                          <p className="text-sm mb-2">{choice.data.question}</p>
                          <div className="flex flex-col gap-2">
                            {choice.data.options.map((opt) => (
                              <button
                                key={opt.label}
                                onClick={() => answer(choice.data.runId, opt.label)}
                                disabled={busy === choice.data.runId}
                                className="rounded border bg-white px-3 py-2 text-left text-sm hover:border-blue-400 disabled:opacity-50"
                              >
                                <span className="block font-medium">{opt.label}</span>
                                {opt.description ? (
                                  <span className="mt-0.5 block text-xs text-gray-600">
                                    {opt.description}
                                  </span>
                                ) : null}
                              </button>
                            ))}
                          </div>
                        </div>
                      )
                    ) : approval ? (
                      resolved[approval.data.runId] !== undefined ? (
                        <AnswerText text={resolved[approval.data.runId]} />
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
                        p.type === "text" ? <AnswerText key={i} text={p.text} /> : null
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
