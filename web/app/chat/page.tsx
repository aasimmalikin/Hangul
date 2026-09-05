"use client"

import { useChat } from "@ai-sdk/react"
import { useState } from "react"

export default function Chat() {
  const { messages, sendMessage } = useChat()
  const [input, setInput] = useState("")

  return (
    <main style={{ padding: 40, maxWidth: 600 }}>
      {messages.map((m) => (
        <div key={m.id} style={{ margin: "12px 0" }}>
          <strong>{m.role}: </strong>
          {m.parts.map((p, i) =>
            p.type === "text" ? <span key={i}>{p.text}</span> : null
          )}
        </div>
      ))}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (input.trim()) {
            sendMessage({ text: input })
            setInput("")
          }
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          style={{ width: "100%", padding: 8 }}
        />
      </form>
    </main>
  )
}
