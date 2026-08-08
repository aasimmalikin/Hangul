"""agentic-qa demo frontend. Consumes the harness API:
  POST /upload   — index a document into this session
  POST /ask      — ask a question (returns answer + tools used + cost + budget + safety)
  GET  /quality  — latest eval scores + CI-gate verdict
  GET  /metrics  — rolling observability metrics
  GET  /traces   — recent per-run traces
"""

import uuid
import requests
import streamlit as st

API_URL = "http://localhost:8000"

st.set_page_config(page_title="agentic-qa", page_icon="🧭", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = "sess-" + uuid.uuid4().hex[:16]
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded" not in st.session_state:
    st.session_state.uploaded = []

HEADERS = {"X-Session-ID": st.session_state.session_id}

TOOL_LABELS = {
    "web_search": "🌐 web search",
    "search_docs": "📄 your documents",
    "calculator": "🧮 calculator",
}
def tool_label(name: str) -> str:
    if name.startswith("filesystem__"):
        return "📁 filesystem (MCP)"
    return TOOL_LABELS.get(name, f"🔧 {name}")


with st.sidebar:
    st.markdown("### agentic-qa")
    st.caption("an agent that picks the right tool")

    st.markdown("**Capabilities**")
    st.markdown(
        "- 🌐 Web search\n- 📄 Your documents (RAG)\n- 📁 Filesystem (MCP)\n"
        "- 🧮 Calculator\n- 💬 Direct GPT-4 chat"
    )

    st.divider()
    st.markdown("**Your document**")
    up = st.file_uploader("Upload txt, md, or pdf", type=["txt", "md", "pdf"],
                          label_visibility="collapsed")
    if up is not None and up.name not in st.session_state.uploaded:
        with st.spinner(f"Indexing {up.name}…"):
            try:
                r = requests.post(f"{API_URL}/upload", headers=HEADERS,
                                  files={"file": (up.name, up.getvalue())}, timeout=120)
                if r.ok:
                    n = r.json().get("chunks_indexed", 0)
                    st.session_state.uploaded.append(up.name)
                    st.success(f"{up.name} · {n} chunks")
                else:
                    st.error(f"Upload failed: {r.text[:200]}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not reach API: {e}")

    for name in st.session_state.uploaded:
        st.caption(f"✅ {name}")

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:14]}…`")


st.title("Ask anything")
st.caption("General questions use web search. Upload a document to ground answers in it. "
           "Destructive actions are blocked by the policy layer.")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("badges"):
            st.caption(" · ".join(m["badges"]))

prompt = st.chat_input("Ask a question…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agent working…"):
            try:
                r = requests.post(f"{API_URL}/ask", headers=HEADERS,
                                  json={"question": prompt}, timeout=180)
                data = r.json()
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not reach API: {e}")
                st.stop()

        answer = data.get("answer", "(no answer)")
        st.markdown(answer)

        badges = []
        for t in data.get("tools_used", []):
            badges.append(tool_label(t))
        if not data.get("tools_used"):
            badges.append("💬 direct model")
        if data.get("safety_blocked"):
            blocked = ", ".join(data["safety_blocked"])
            st.warning(f"🛡️ Safety gate: blocked {blocked} (destructive, not executed)")
        cost = data.get("cost_usd", 0)
        steps = data.get("steps", 0)
        meta = f"{steps} steps · ${cost:.4f}"
        if data.get("cached"):
            meta += " · cached"
        badges.append(meta)

        st.caption(" · ".join(badges))

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "badges": badges,
    })


st.divider()
tab_q, tab_obs = st.tabs(["Quality (evals + CI gate)", "Under the hood"])

with tab_q:
    try:
        q = requests.get(f"{API_URL}/quality", headers=HEADERS, timeout=10).json()
        if q.get("available"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Correctness", f"{q['avg_correctness']:.2f}")
            c2.metric("Faithfulness", f"{q['avg_faithfulness']:.2f}")
            c3.metric("Pass rate", f"{q['pass_rate']*100:.0f}%")
            if q.get("gate_passed"):
                st.success(f"✅ CI gate: PASS · {q.get('cases')} cases · {q.get('model')}")
            else:
                st.error(f"❌ CI gate: FAIL · {q.get('blocking_failures')}")
            st.caption(f"prompt {q.get('prompt_version')} · index {q.get('index_version')} "
                       f"· {q.get('run_file')}")
        else:
            st.info("No eval runs found yet.")
    except Exception:  # noqa: BLE001
        st.info("Quality endpoint not reachable.")

with tab_obs:
    try:
        m = requests.get(f"{API_URL}/metrics", headers=HEADERS, timeout=10).json()
        if m.get("runs"):
            a, b, c, d = st.columns(4)
            a.metric("Runs", m["runs"])
            b.metric("Avg latency", f"{m['avg_latency_ms']:.0f} ms")
            c.metric("Total cost", f"${m['total_cost_usd']:.4f}")
            d.metric("Error rate", f"{m['error_rate']*100:.0f}%")
        else:
            st.info("No runs recorded yet — ask a question above.")

        tr = requests.get(f"{API_URL}/traces", headers=HEADERS, timeout=10).json()
        traces = tr.get("traces", [])
        if traces:
            st.markdown("**Recent runs**")
            for t in traces[:8]:
                st.caption(
                    f"`{t['trace_id'][:12]}` · {t['total_ms']:.0f} ms · "
                    f"{t['model_calls']} model / {t['tool_calls']} tool calls · "
                    f"{t['input_tokens']}+{t['output_tokens']} tok · ${t['cost_usd']:.4f}"
                    + (" · ⚠️ error" if t.get("errors") else "")
                )
    except Exception:  # noqa: BLE001
        st.info("Observability endpoints not reachable.")
