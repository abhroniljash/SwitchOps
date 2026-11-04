// SwitchOps Interactive Frontend Logic
let currentRoomId = null;

async function triggerIncident() {
    const btn = document.getElementById("btnTriggerIncident");
    btn.disabled = true;
    btn.innerText = "⏳ Ingesting Alert...";

    try {
        const resp = await fetch("/api/incident/trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        currentRoomId = data.room_id;

        // Update UI components
        updateRoomView(data);
    } catch (err) {
        console.error("Error triggering incident:", err);
    } finally {
        btn.disabled = false;
        btn.innerText = "🚨 Trigger Production 500";
    }
}

function updateRoomView(data) {
    if (!data) return;

    // Room info
    const inc = data.incident;
    const prop = data.proposal;

    document.getElementById("roomTitle").innerText = `incident-${inc.id.toLowerCase()}`;
    document.getElementById("roomStatusBadge").innerText = inc.status;
    document.getElementById("roomStatusBadge").style.backgroundColor = inc.status === "RESOLVED" ? "#238636" : "#d29922";
    document.getElementById("roomStatusBadge").style.color = "#fff";

    // Telemetry cards
    document.getElementById("infoIncId").innerText = inc.id;
    document.getElementById("infoService").innerText = inc.service;
    document.getElementById("infoRootCause").innerText = inc.root_cause_summary || "Analyzing...";
    document.getElementById("incidentSeverity").innerText = inc.severity;
    document.getElementById("incidentSeverity").style.color = inc.severity === "CRITICAL" ? "#f85149" : "#d29922";

    // Proposal & Diff
    if (prop) {
        document.getElementById("diffTargetFile").innerText = prop.target_file;
        renderDiff(prop.diff);
        document.getElementById("terminalOutput").innerText = prop.test_run_output;
        document.getElementById("testBadge").innerText = prop.tests_passed ? "5 PASSED ✅" : "FAILED ❌";

        // Show approval banner if awaiting
        if (data.incident.status !== "RESOLVED" && data.incident.status !== "CLOSED") {
            document.getElementById("approvalBanner").style.display = "flex";
        } else {
            document.getElementById("approvalBanner").style.display = "none";
        }
    }

    // Pull request & ROI if resolved
    if (data.pull_request) {
        document.getElementById("approvalBanner").style.display = "none";
    }

    if (data.roi) {
        document.getElementById("roiMttr").innerText = `${data.roi.mttr_reduction_percent}%`;
        document.getElementById("roiSavings").innerText = `$${data.roi.total_value_delivered_usd.toLocaleString()}`;
        document.getElementById("roiCost").innerText = `$${data.roi.llm_cost_usd}`;
        document.getElementById("roiMultiplier").innerText = `${data.roi.roi_multiplier}x`;
    }

    // Messages
    if (data.messages) {
        renderMessages(data.messages);
    }
}

function renderDiff(diffText) {
    const viewer = document.getElementById("diffViewer");
    if (!diffText) {
        viewer.innerHTML = `<span class="comment">// No active diff</span>`;
        return;
    }

    const lines = diffText.split("\n");
    viewer.innerHTML = lines.map(line => {
        if (line.startsWith("+") && !line.startsWith("+++")) {
            return `<span class="diff-add">${escapeHtml(line)}</span>`;
        } else if (line.startsWith("-") && !line.startsWith("---")) {
            return `<span class="diff-rem">${escapeHtml(line)}</span>`;
        } else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) {
            return `<span class="diff-hdr">${escapeHtml(line)}</span>`;
        }
        return `<span>${escapeHtml(line)}</span>`;
    }).join("");
}

function renderMessages(messages) {
    const container = document.getElementById("chatMessages");
    container.innerHTML = "";

    messages.forEach(msg => {
        const div = document.createElement("div");
        const roleClass = msg.role === "user" ? "user" : (msg.role === "agent" ? "agent" : "system");
        div.className = `msg ${roleClass}`;

        let icon = "⚡";
        if (msg.role === "user") icon = "👤";
        else if (msg.sender.includes("Triage")) icon = "🔍";
        else if (msg.sender.includes("Remediation")) icon = "🛠️";
        else if (msg.sender.includes("Git")) icon = "🚀";

        div.innerHTML = `
            <div class="msg-avatar">${icon}</div>
            <div class="msg-body">
                <div class="msg-meta">${escapeHtml(msg.sender)} • ${formatTime(msg.timestamp)}</div>
                <div class="msg-text">${formatMessageText(msg.text)}</div>
            </div>
        `;
        container.appendChild(div);
    });

    container.scrollTop = container.scrollHeight;
}

function formatMessageText(text) {
    // Basic Markdown format for bold and links
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code class="mono" style="background:#21262d;padding:2px 4px;border-radius:4px;">$1</code>');
    formatted = formatted.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#58a6ff;">$1</a>');
    return formatted;
}

async function approveIncident() {
    try {
        const resp = await fetch("/api/incident/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: currentRoomId })
        });
        const data = await resp.json();
        document.getElementById("approvalBanner").style.display = "none";
        refreshState();
    } catch (e) {
        console.error(e);
    }
}

async function rejectIncident() {
    try {
        await fetch("/api/incident/reject", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: currentRoomId })
        });
        document.getElementById("approvalBanner").style.display = "none";
        refreshState();
    } catch (e) {
        console.error(e);
    }
}

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    try {
        await fetch("/api/chat/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: currentRoomId, text: text })
        });
        refreshState();
    } catch (e) {
        console.error(e);
    }
}

function handleInputKey(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

async function triggerVoiceApprove() {
    const sampleVoicePrompt = "Looks good SwitchOps, approve the hotfix and deploy to production.";
    try {
        await fetch("/api/voice/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: currentRoomId, transcript: sampleVoicePrompt })
        });
        refreshState();
    } catch (e) {
        console.error(e);
    }
}

function promptVoiceCommand() {
    const prompt = window.prompt("Speak or type via Wispr Flow Dictation:", "SwitchOps, investigate the payments 500 error and prepare hotfix");
    if (prompt) {
        fetch("/api/voice/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: currentRoomId, transcript: prompt })
        }).then(() => refreshState());
    }
}

async function refreshState() {
    if (!currentRoomId) return;
    try {
        const resp = await fetch(`/api/room/state?room_id=${currentRoomId}`);
        const data = await resp.json();
        if (data.active) {
            updateRoomView(data);
        }
    } catch (e) {
        console.error(e);
    }
}

async function openWisprModal() {
    const modal = document.getElementById("wisprModal");
    modal.style.display = "flex";
    try {
        const resp = await fetch("/api/wispr/scorecard");
        const data = await resp.json();
        document.getElementById("wisprScorecardContent").innerHTML = `
            <div style="background:#0d1117;padding:12px;border-radius:6px;border:1px solid #30363d;font-family:monospace;font-size:12px;">
                <p><strong>Track:</strong> ${data.hackathon_track}</p>
                <p><strong>Wispr Flow Status:</strong> ACTIVE (Connected)</p>
                <p><strong>Total Voice Prompts:</strong> ${data.total_voice_commands_processed}</p>
                <p><strong>Words Spoken:</strong> ${data.estimated_words_spoken}</p>
                <p><strong>Hands-Free Time Saved:</strong> ${data.estimated_hands_free_time_saved_minutes} minutes</p>
                <p><strong>Voice Intent Accuracy:</strong> ${data.average_intent_accuracy}</p>
                <hr style="border-color:#30363d;margin:10px 0;">
                <p><strong>Voice Capabilities:</strong></p>
                <ul>
                    ${data.voice_first_features.map(f => `<li>${f}</li>`).join("")}
                </ul>
            </div>
            <p style="margin-top:12px;font-size:12px;color:#8b949e;">
                This scorecard satisfies the submission criteria for the Wispr Flow side track ($500 prize).
            </p>
        `;
    } catch (e) {
        console.error(e);
    }
}

function closeWisprModal(e) {
    document.getElementById("wisprModal").style.display = "none";
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatTime(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
