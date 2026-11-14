const $ = (id) => document.getElementById(id);

function addBubble(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  const p = document.createElement("p");
  p.textContent = text;
  if (role === "assistant") {
    const title = document.createElement("strong");
    title.textContent = "LearnYah";
    bubble.appendChild(title);
  }
  bubble.appendChild(p);
  $("chat-messages").appendChild(bubble);
  $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.error || `Request failed (${response.status})`);
  return body;
}

async function refreshDocuments() {
  const list = $("documents");
  try {
    const docs = await api("/api/documents");
    list.replaceChildren();
    if (!docs.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "No notes uploaded yet.";
      list.appendChild(li);
      return;
    }
    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.textContent = `${doc.filename} · ${doc.chunk_count} chunks`;
      list.appendChild(li);
    });
  } catch (err) {
    list.textContent = "Could not load documents.";
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $("chat-panel").classList.toggle("hidden", tab.dataset.tab !== "chat");
    $("quiz-panel").classList.toggle("hidden", tab.dataset.tab !== "quiz");
  });
});

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("file").files[0];
  if (!file) return;
  const status = $("upload-status");
  status.textContent = "Uploading and extracting text…";
  const data = new FormData();
  data.append("file", file);
  try {
    const result = await api("/api/documents", { method: "POST", body: data });
    status.textContent = `Added ${result.filename} (${result.chunk_count} text chunks).`;
    $("file").value = "";
    refreshDocuments();
  } catch (err) {
    status.textContent = err.message;
  }
});

$("refresh-docs").addEventListener("click", refreshDocuments);

$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("message").value.trim();
  if (!message) return;
  addBubble("user", message);
  $("message").value = "";
  const button = $("send-button");
  button.disabled = true;
  button.textContent = "Thinking…";
  const loading = document.createElement("div");
  loading.className = "bubble assistant";
  loading.textContent = "Thinking through your question…";
  $("chat-messages").appendChild(loading);
  try {
    const result = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, use_documents: $("use-docs").checked }),
    });
    loading.remove();
    let answer = result.answer;
    if (result.sources?.length) {
      answer += "\n\nSources used:\n" + result.sources.map(s => `• ${s.filename}, chunk ${s.chunk}`).join("\n");
    }
    addBubble("assistant", answer);
  } catch (err) {
    loading.remove();
    addBubble("assistant", `I couldn't complete that request: ${err.message}`);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Ask LearnYah <span>↗</span>';
    $("message").focus();
  }
});

$("quiz-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("quiz-button");
  const resultEl = $("quiz-result");
  button.disabled = true;
  button.textContent = "Creating quiz…";
  resultEl.textContent = "Generating questions…";
  try {
    const result = await api("/api/quiz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: $("topic").value.trim(),
        question_count: Number($("count").value),
        use_documents: $("quiz-use-docs").checked,
      }),
    });
    resultEl.textContent = result.quiz + (result.sources.length ? "\n\nBased on: " + result.sources.join(", ") : "");
  } catch (err) {
    resultEl.textContent = `Could not generate quiz: ${err.message}`;
  } finally {
    button.disabled = false;
    button.textContent = "Generate practice quiz";
  }
});

refreshDocuments();
