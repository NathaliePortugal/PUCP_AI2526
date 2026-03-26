export async function sendMessage(message, sessionId) {
  const res = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });

  return res.json();
}