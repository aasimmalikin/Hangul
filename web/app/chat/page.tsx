"use client"

import { useState } from "react"
import { useChat } from "@ai-sdk/react"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent } from "@/components/ai-elements/message"

export default function Chat() {
  const { messages, sendMessage, status } = useChat()
  const [input, setInput] = useState("")

  const submit = () => {
    if (!input.trim()) return
    sendMessage({ text: input })
    setInput("")
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
            messages.map((m) => (
              <Message from={m.role} key={m.id}>
                <MessageContent>
                  {m.parts.map((p, i) =>
                    p.type === "text" ? <span key={i}>{p.text}</span> : null
                  )}
                </MessageContent>
              </Message>
            ))
          )}
        </ConversationContent>
      </Conversation>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className="mt-4 flex gap-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="Ask a question"
          rows={1}
          className="flex-1 resize-none rounded-lg border p-3 text-sm"
        />
        <button
          type="submit"
          disabled={status === "streaming"}
          className="rounded-lg border px-4 text-sm disabled:opacity-50"
        >
          {status === "streaming" ? "..." : "Send"}
        </button>
      </form>
    </div>
  )
}
