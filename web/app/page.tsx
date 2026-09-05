import {signIn, signOut, auth} from "@/auth";

export default async function Home() {
  const session = await auth();

  if (session?.user){
    return (
      <main style = {{ padding: 40}}>
        <p> Signed in as {session.user.email}</p>
        <form action = {async () => {"use server"; await signOut()}}>
          <button type = "submit"> Sign out</button>
        </form>
      </main>
    )
  }

  return (
    <main style = {{ padding: 40}}>
      <form action = { async() => { "use server"; await signIn("google")}}>
        <button type = "submit"> Sign in with google

        </button>
      </form>
    </main>
  )
}