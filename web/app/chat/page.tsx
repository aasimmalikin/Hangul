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
import { ToolRow, type ToolActivity } from "@/components/agent-activity"

type Approval = { runId: string; tool: string; arguments: Record<string, unknown> }
type ChoiceOption = { label: string; description: string }
type Choice = { runId: string; question: string; options: ChoiceOption[] }

type Part = {
  type: string
  text?: string
  id?: string
  data?: unknown
}

function LinkRenderer(props: { href?: string; children?: React.ReactNode }) {
  return (
    <a href={props.href} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
      {props.children}
    </a>
  )
}

function AnswerText({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: LinkRenderer }}>
      {text}
    </ReactMarkdown>
  )
}

function Thinking() {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-gray-500">
      <span className="inline-flex gap-1">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gray-400" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gray-400 [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gray-400 [animation-delay:300ms]" />
      </span>
      <span>Thinking…</span>
    </div>
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

  // Nothing has come back yet for the run in flight.
  const last = messages[messages.length - 1]
  const showThinking =
    (status === "submitted" || status === "streaming") &&
    (!last || last.role === "user" || last.parts.length === 0)

  const renderPart = (part: Part, key: string) => {
    if (part.type === "text") {
      return part.text ? <AnswerText key={key} text={part.text} /> : null
    }

    if (part.type === "data-tool") {
      return <ToolRow key={key} activity={part.data as ToolActivity} />
    }

    if (part.type === "data-choice") {
      const choice = part.data as Choice
      if (resolved[choice.runId] !== undefined) {
        return <AnswerText key={key} text={resolved[choice.runId]} />
      }
      return (
        <div key={key} className="rounded-lg border border-blue-300 bg-blue-50 p-3">
          <p className="mb-2 text-sm">{choice.question}</p>
          <div className="flex flex-col gap-2">
            {choice.options.map((opt) => (
              <button
                key={opt.label}
                onClick={() => answer(choice.runId, opt.label)}
                disabled={busy === choice.runId}
                className="rounded border bg-white px-3 py-2 text-left text-sm hover:border-blue-400 disabled:opacity-50"
              >
                <span className="block font-medium">{opt.label}</span>
                {opt.description ? (
                  <span className="mt-0.5 block text-xs text-gray-600">{opt.description}</span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      )
    }

    if (part.type === "data-approval") {
      const approval = part.data as Approval
      if (resolved[approval.runId] !== undefined) {
        return <AnswerText key={key} text={resolved[approval.runId]} />
      }
      return (
        <div key={key} className="rounded-lg border border-amber-300 bg-amber-50 p-3">
          <p className="mb-2 text-sm">
            The assistant wants to run <code className="text-xs">{approval.tool}</code>. Allow it?
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => decide(approval.runId, "approve")}
              disabled={busy === approval.runId}
              className="rounded border px-3 py-1 text-sm disabled:opacity-50"
            >
              {busy === approval.runId ? "..." : "Approve"}
            </button>
            <button
              onClick={() => decide(approval.runId, "reject")}
              disabled={busy === approval.runId}
              className="rounded border px-3 py-1 text-sm disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      )
    }

    return null
  }

  return (
    <div className="mx-auto flex h-screen max-w-3xl flex-col p-4">
      <Conversation className="flex-1">
        <ConversationContent>
          {messages.length === 0 ? (
            <ConversationEmptyState
              title="Ask anything"
              description="Your documents, the web, and your connected tools."
            />
          ) : (
            messages.map((m) => (
              <Message from={m.role} key={m.id}>
                {/* Parts arrive in the order the agent produced them, so the
                    narration, the tool it ran, and the answer read as one
                    running commentary. */}
                <MessageContent>
                  {(m.parts as Part[]).map((p, i) => renderPart(p, `${m.id}-${i}`))}
                </MessageContent>
              </Message>
            ))
          )}
          {showThinking && <Thinking />}
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
