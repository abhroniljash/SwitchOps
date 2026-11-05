// SwitchOps Interactive Frontend Logic
let currentIncidentId = null;
let currentWorkflowState = "RECEIVED";

async function triggerIncident() {
    const btn = document.getElementById("btnTriggerIncident");
    btn.disabled = true;
    btn.innerText = "⏳ Ingesting & Triaging...";

    try {
        const resp = await fetch("/incidents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ demo: true })
        });
        const data = await resp.json();
        currentIncidentId = data.incident_id;
        updateRoomView(data);
    } catch (err) {
        console.error("Error triggering incident:", err);
    } finally {
        btn.disabled = false;
        btn.innerText = "🚨 Trigger Demo 500";
    }
}

function updateRoomView(data) {
    if (!data) return;

    const inc = data.incident;
    const patch = data.patch;
    const testRun = data.test_run;
    const pr = data.pull_request;

    if (inc) {
        currentIncidentId = inc.incident_id || inc.id;
        currentWorkflowState = inc.status;

        document.getElementById("roomTitle").innerText = `incident-${currentIncidentId.toLowerCase()}`;
        
        // Status Badge
        const statusBadge = document.getElementById("roomStatusBadge");
        statusBadge.innerText = inc.status;
        statusBadge.style.backgroundColor = getStatusColor(inc.status);
        statusBadge.style.color = "#fff";

        document.getElementById("infoIncId").innerText = currentIncidentId;
        document.getElementById("infoService").innerText = inc.service_name;
        document.getElementById("infoWorkflowState").innerText = inc.status;
        document.getElementById("infoRootCause").innerText = inc.likely_root_cause || inc.summary || "Analyzing...";
        
        const sevBadge = document.getElementById("incidentSeverity");
        sevBadge.innerText = inc.severity;
        sevBadge.style.color = inc.severity === "Critical" ? "#f85149" : "#d29922";

        if (inc.confidence && inc.confidence.level) {
            document.getElementById("confidenceRow").style.display = "flex";
            document.getElementById("infoConfidence").innerText = `${inc.confidence.level} (${inc.confidence.explanation})`;
        }
    }

    // Patch Diff Inspector
    if (patch) {
        if (patch.files_changed && patch.files_changed.length > 0) {
            document.getElementById("diffTargetFile").innerText = patch.files_changed[0];
        }
        renderDiff(patch.diff);
    }

    // Test Runner Output
    if (testRun) {
        const testBadge = document.getElementById("testBadge");
        testBadge.innerText = testRun.status === "PASSED" ? "PASSED ✅" : "FAILED ❌";
        testBadge.className = testRun.status === "PASSED" ? "badge badge-success" : "badge badge-danger";
        
        const term = document.getElementById("terminalOutput");
        term.innerText = `Command: ${testRun.command_profile}\nExit Code: ${testRun.exit_code} | Duration: ${testRun.duration_ms}ms\n\n${testRun.stdout_reference || testRun.stderr_reference}`;
    }

    // Step-by-Step Approval Banner
    const banner = document.getElementById("approvalBanner");
    const bannerTitle = document.getElementById("bannerTitle");
    const bannerSubtitle = document.getElementById("bannerSubtitle");
    const btnApprove = document.getElementById("btnApproveAction");

    if (currentWorkflowState === "AWAITING_FIX_APPROVAL") {
        banner.style.display = "flex";
        bannerTitle.innerText = "Human-in-the-Loop Approval Required (Step 1 of 2):";
        bannerSubtitle.innerText = "Review proposed patch diff. Authorize running isolated validation tests?";
        btnApprove.innerText = "✅ Authorize Tests";
    } else if (currentWorkflowState === "AWAITING_PR_APPROVAL") {
        banner.style.display = "flex";
        bannerTitle.innerText = "Human-in-the-Loop Approval Required (Step 2 of 2):";
        bannerSubtitle.innerText = "Validation tests PASSED. Authorize creating Git branch and GitHub Pull Request?";
        btnApprove.innerText = "🚀 Create GitHub PR";
    } else {
        banner.style.display = "none";
    }

    // Telemetry stats
    if (data.analytics) {
        document.getElementById("statTriageTime").innerText = `${data.analytics.average_time_to_triage_seconds}s`;
        document.getElementById("statPrTime").innerText = `${data.analytics.average_time_to_pr_seconds}s`;
        document.getElementById("statPassRate").innerText = data.analytics.test_pass_rate;
    }

    // Messages
    if (data.messages) {
        renderMessages(data.messages);
    }
}

function getStatusColor(status) {
    switch (status) {
        case "PR_CREATED": return "#238636";
        case "TEST_PASSED": return "#1f6feb";
        case "AWAITING_FIX_APPROVAL":
        case "AWAITING_PR_APPROVAL": return "#d29922";
        case "TEST_FAILED":
        case "FAILED":
        case "REJECTED": return "#da3633";
        default: return "#30363d";
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
        else if (msg.sender.includes("Test")) icon = "🧪";
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
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code class="mono" style="background:#21262d;padding:2px 4px;border-radius:4px;">$1</code>');
    formatted = formatted.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#58a6ff;text-decoration:underline;">$1</a>');
    return formatted;
}

async function handleApproveClick() {
    if (!currentIncidentId) return;

    const action = (currentWorkflowState === "AWAITING_PR_APPROVAL") ? "pr" : "patch";
    try {
        const resp = await fetch(`/incidents/${currentIncidentId}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: action, reviewer: "OnCallEngineer" })
        });
        const data = await resp.json();
        refreshState();
    } catch (e) {
        console.error("Approval error:", e);
    }
}

async function rejectIncident() {
    if (!currentIncidentId) return;
    try {
        await fetch(`/incidents/${currentIncidentId}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewer: "OnCallEngineer", reason: "Rejected by operator." })
        });
        refreshState();
    } catch (e) {
        console.error("Rejection error:", e);
    }
}

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    try {
        await fetch("/integrations/switch/events", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, sender: "OnCallEngineer" })
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

async function refreshState() {
    try {
        const resp = await fetch("/api/room/state");
        const data = await resp.json();
        if (data.active) {
            updateRoomView(data);
        }
    } catch (e) {
        console.error(e);
    }
}

function openManualIncidentModal() {
    document.getElementById("manualModal").style.display = "flex";
}

function closeManualModal() {
    document.getElementById("manualModal").style.display = "none";
}

async function submitManualIncident(event) {
    event.preventDefault();
    const service = document.getElementById("manualService").value;
    const severity = document.getElementById("manualSeverity").value;
    const summary = document.getElementById("manualSummary").value;
    const stack = document.getElementById("manualStackTrace").value;

    closeManualModal();

    const payload = {
        source: "manual",
        service_name: service,
        severity: severity,
        summary: summary,
        stack_trace: stack,
    };

    try {
        const resp = await fetch("/incidents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        updateRoomView(data);
    } catch (e) {
        console.error("Manual intake error:", e);
    }
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
