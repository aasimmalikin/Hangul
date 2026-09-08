import { signIn, signOut, auth } from "@/auth"
import { HangulSigil } from "@/components/HangulSigil"
import { Wordmark } from "@/components/Wordmark"

export default async function Home() {
  const session = await auth()

  if (session?.user) {
    return (
      <main className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4">
        <Wordmark href={null} className="absolute left-6 top-6" />
        <HangulSigil size={56} className="text-primary mb-5" />
        <p className="text-foreground text-sm mb-6">
          Signed in as {session.user.email}
        </p>
        <div className="flex gap-3">
          <a href="/chat" className="rounded-lg bg-primary px-5 py-2 text-sm text-primary-foreground">
            Open chat
          </a>
          <form action={async () => { "use server"; await signOut() }}>
            <button
              type="submit"
              className="rounded-lg border border-border px-5 py-2 text-sm text-foreground"
            >
              Sign out
            </button>
          </form>
        </div>
      </main>
    )
  }

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <Wordmark href={null} className="absolute left-6 top-6" />
      <HangulSigil size={80} className="text-primary mb-6" />
      <h1 className="font-[family-name:var(--font-fraunces)] text-4xl text-foreground mb-1">
        Hangul
      </h1>
      <p className="text-muted-foreground text-sm mb-10">An agentic assistant</p>
      <form action={async () => { "use server"; await signIn("google") }}>
        <button
          type="submit"
          className="rounded-lg bg-primary px-6 py-2.5 text-sm text-primary-foreground"
        >
          Sign in with Google
        </button>
      </form>
    </main>
  )
}
