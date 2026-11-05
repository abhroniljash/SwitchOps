// SwitchOps Interactive Frontend Logic
let currentIncidentId = null;
let currentWorkflowState = "RECEIVED";
let cachedIncidents = [];

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    loadIncidentHistory();
    refreshState();
    // Real-time status update loop (every 3.5s)
    setInterval(refreshState, 3500);
});

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
        loadIncidentHistory();
    } catch (err) {
        console.error("Error triggering incident:", err);
    } finally {
        btn.disabled = false;
        btn.innerText = "🚨 Trigger Demo 500";
    }
}

async function loadIncidentHistory() {
    try {
        const resp = await fetch("/api/incidents/history");
        const data = await resp.json();
        cachedIncidents = data.history || [];
        
        // Populate quick dropdown
        const select = document.getElementById("historySelect");
        if (select) {
            select.innerHTML = '<option value="">📁 Past Incidents...</option>';
            cachedIncidents.forEach(inc => {
                const opt = document.createElement("option");
                opt.value = inc.id;
                opt.innerText = `${inc.id} (${inc.severity} - ${inc.status})`;
                if (inc.id === currentIncidentId) opt.selected = true;
                select.appendChild(opt);
            });
        }

        // Render modal table
        renderHistoryTable(cachedIncidents);
    } catch (e) {
        console.error("Error loading history:", e);
    }
}

function renderHistoryTable(incidents) {
    const tbody = document.getElementById("historyTableBody");
    if (!tbody) return;

    if (!incidents || incidents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 20px;">No incidents matching filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = incidents.map(inc => {
        const sevColor = inc.severity === "Critical" ? "#f85149" : (inc.severity === "High" ? "#d29922" : "#58a6ff");
        const statColor = getStatusColor(inc.status);
        const isCurrent = inc.id === currentIncidentId;

        return `
            <tr style="${isCurrent ? 'background: rgba(88, 166, 255, 0.1);' : ''}">
                <td class="mono" style="font-weight: 600; color: #58a6ff;">${escapeHtml(inc.id)}</td>
                <td><span style="color: ${sevColor}; font-weight: 600;">${escapeHtml(inc.severity)}</span></td>
                <td>${escapeHtml(inc.service_name || 'payments-service')}</td>
                <td><span class="badge" style="background-color: ${statColor}; color: #fff; font-size: 11px;">${escapeHtml(inc.status)}</span></td>
                <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(inc.summary || '')}">${escapeHtml(inc.summary || 'Incident')}</td>
                <td>
                    <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="selectIncidentFromModal('${inc.id}')">
                        ${isCurrent ? 'Active' : 'Load'}
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

function filterIncidentHistoryTable() {
    const search = (document.getElementById("historySearchInput").value || "").toLowerCase().trim();
    const severity = document.getElementById("historySeverityFilter").value;
    const status = document.getElementById("historyStatusFilter").value;

    const filtered = cachedIncidents.filter(inc => {
        const matchSearch = !search || 
            (inc.id && inc.id.toLowerCase().includes(search)) ||
            (inc.service_name && inc.service_name.toLowerCase().includes(search)) ||
            (inc.summary && inc.summary.toLowerCase().includes(search));
        
        const matchSev = !severity || inc.severity === severity;
        const matchStat = !status || inc.status === status;

        return matchSearch && matchSev && matchStat;
    });

    renderHistoryTable(filtered);
}

function openHistoryModal() {
    loadIncidentHistory();
    document.getElementById("historyModal").style.display = "flex";
}

function closeHistoryModal() {
    document.getElementById("historyModal").style.display = "none";
}

async function selectIncidentFromModal(incidentId) {
    closeHistoryModal();
    try {
        const resp = await fetch(`/incidents/${incidentId}`);
        const data = await resp.json();
        currentIncidentId = incidentId;
        updateRoomView(data);
        const select = document.getElementById("historySelect");
        if (select) select.value = incidentId;
    } catch (e) {
        console.error("Error loading selected incident:", e);
    }
}

async function switchIncidentFromHistory() {
    const select = document.getElementById("historySelect");
    const selectedId = select.value;
    if (!selectedId) return;

    try {
        const resp = await fetch(`/incidents/${selectedId}`);
        const data = await resp.json();
        currentIncidentId = selectedId;
        updateRoomView(data);
    } catch (e) {
        console.error("Error loading incident detail:", e);
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
    const btnRetry = document.getElementById("btnRetryAction");
    const btnReject = document.getElementById("btnRejectAction");

    if (currentWorkflowState === "AWAITING_FIX_APPROVAL") {
        banner.style.display = "flex";
        bannerTitle.innerText = "Human-in-the-Loop Approval Required (Step 1 of 2):";
        bannerSubtitle.innerText = "Review proposed patch diff. Authorize applying patch to disk and running isolated tests?";
        btnApprove.style.display = "inline-block";
        btnApprove.innerText = "✅ Authorize Tests";
        if (btnRetry) btnRetry.style.display = "none";
        if (btnReject) btnReject.style.display = "inline-block";
    } else if (currentWorkflowState === "AWAITING_PR_APPROVAL") {
        banner.style.display = "flex";
        bannerTitle.innerText = "Human-in-the-Loop Approval Required (Step 2 of 2):";
        bannerSubtitle.innerText = "Validation tests PASSED. Authorize creating Git branch and GitHub Pull Request?";
        btnApprove.style.display = "inline-block";
        btnApprove.innerText = "🚀 Create GitHub PR";
        if (btnRetry) btnRetry.style.display = "none";
        if (btnReject) btnReject.style.display = "inline-block";
    } else if (currentWorkflowState === "TEST_FAILED") {
        banner.style.display = "flex";
        bannerTitle.innerText = "❌ Validation Tests Failed: Review error logs.";
        bannerSubtitle.innerText = "Would you like to synthesize an alternative remediation patch or reject the workflow?";
        btnApprove.style.display = "none";
        if (btnRetry) btnRetry.style.display = "inline-block";
        if (btnReject) btnReject.style.display = "inline-block";
    } else {
        banner.style.display = "none";
    }

    // Agent Tasks Stream
    if (data.tasks) {
        renderTasks(data.tasks);
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

function renderTasks(tasks) {
    const list = document.getElementById("agentTaskList");
    if (!list) return;

    if (!tasks || tasks.length === 0) {
        list.innerHTML = `<div class="task-row"><span class="task-agent">[System]</span> Awaiting incident detection...</div>`;
        return;
    }

    list.innerHTML = tasks.map(t => `
        <div class="task-row">
            <span class="task-agent">[${escapeHtml(t.agent_type)}]</span>
            <span class="task-status ${t.status.toLowerCase()}">${t.status}</span>: 
            ${escapeHtml(t.output_summary || t.input_summary)}
            ${t.duration_seconds ? `<span class="task-dur">(${t.duration_seconds}s)</span>` : ''}
        </div>
    `).join("");
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

async function handleRetryClick() {
    if (!currentIncidentId) return;
    const btn = document.getElementById("btnRetryAction");
    if (btn) {
        btn.disabled = true;
        btn.innerText = "⏳ Synthesizing fix...";
    }
    try {
        const resp = await fetch(`/incidents/${currentIncidentId}/retry`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewer: "OnCallEngineer" })
        });
        const data = await resp.json();
        refreshState();
    } catch (e) {
        console.error("Retry error:", e);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "🔄 Suggest Alternative Fix";
        }
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
        loadIncidentHistory();
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
