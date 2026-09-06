import { auth } from "@/auth"
import { mintServiceToken } from "@/lib/service-token"

export const runtime = "nodejs"

/**
 * Relays a human approval decision to the backend, which resumes the paused
 * run from its checkpoint. Same BFF pattern as the chat route: verify the
 * session, mint a service token, forward to FastAPI.
 */
export async function POST(req: Request) {
  const session = await auth()
  if (!session?.user?.email) {
    return new Response("Unauthorized", { status: 401 })
  }

  const token = await mintServiceToken(session.user.email, "user")
  const { approval_id, decision } = await req.json()

  const res = await fetch(`${process.env.FASTAPI_URL}/approve`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ approval_id, decision }),
  })

  const body = await res.text()
  console.log("APPROVE RESPONSE:", res.status, body)
  return new Response(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  })
}
