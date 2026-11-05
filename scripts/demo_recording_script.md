# 🎬 SwitchOps: Hackathon Demo Recording Script (3–5 Minutes)
**WeMakeDevs Flip the Switch 2026 Hackathon**  
*Based on Section 18 of the Technical Implementation Guide*

---

## ⏱️ Video Outline (3–5 Minutes)

- **0:00 – 0:30 (Step 1)**: Problem Statement (Fragmented incident response & on-call fatigue)
- **0:30 – 1:00 (Step 2)**: Switch Architecture (Bridging team chat to autonomous agent workers)
- **1:00 – 1:30 (Steps 3 & 4)**: Trigger Controlled HTTP 500 & Ingestion
- **1:30 – 2:15 (Step 5)**: Triage Agent Evidence-Based Investigation (Real logs & repo files)
- **2:15 – 3:00 (Step 6 & 7)**: Remediation Diff & Isolated Test Execution (First Approval)
- **3:00 – 3:45 (Steps 8 & 9)**: GitOps Pull Request Creation (Second Approval) & Chat Confirmation
- **3:45 – 4:30 (Step 10)**: Safety Controls & Transparent Operational Analytics

---

## 🎙️ Spoken Narration Script

### Step 1: The Problem (0:00 – 0:30)
> *"Hello judges! When an application breaks in production, developers waste critical time jumping between monitoring alerts, terminal logs, git history, and Slack channels.*
>
> *Today, solo AI coding assistants sit isolated inside private IDEs. What engineering teams actually need is an active teammate directly inside their collaboration channels.*
>
> *Introducing **SwitchOps**—an autonomous incident commander and SRE teammate powered by **Switch** from SandboxAQ."*

### Step 2: Show Switch & Chat Integration (0:30 – 1:00)
*(Screen: Show Slack / Discord channel alongside the SwitchOps cockpit)*

> *"Switch is the central nervous system of SwitchOps. It connects our team messaging channel directly to specialized AI agents in a shared room `#incident-inc-7189`.*
>
> *All incident context, evidence, and approvals are preserved in this shared thread—so the whole team stays informed without context fragmentation."*

### Step 3 & 4: Trigger Controlled HTTP 500 (1:00 – 1:30)
*(Screen: Click the **🚨 Trigger Demo 500** button or call `/demo/error-500`)*

> *"Let's simulate a live incident. Our checkout microservice throws an unhandled HTTP 500 exception.*
>
> *Notice that SwitchOps immediately captures the alert, normalizes the event, deduplicates incoming signals, and enters the `RECEIVED` workflow state.*
>
> *Our team receives an instant acknowledgment in the room."*

### Step 5: Triage Agent Evidence-Based RCA (1:30 – 2:15)
*(Screen: Highlight the Triage findings, affected file, and evidence box)*

> *"Next, our **Triage Agent** doesn't guess or give generic advice. It searches the repository and extracts concrete evidence:*
> - *It isolates line 37 in `payments_service/app.py`.*
> - *It diagnoses the exact root cause with **High Confidence**: an unhandled `KeyError` caused by lowercase currency strings missing dictionary keys.*
> - *Notice how the uncertainty and evidence references are explicitly stated."*

### Step 6 & 7: Scoped Patch & Real Isolated Tests (2:15 – 3:00)
*(Screen: Show the unified diff viewer, then click **✅ Authorize Tests**)*

> *"Our **Remediation Agent** synthesizes a minimal surgical patch. It doesn't perform broad refactoring and strictly rejects modifying sensitive configuration or secrets.*
>
> *Crucially, SwitchOps enforces **Human-in-the-Loop safety**.*
>
> *As the on-call engineer, I review the diff and approve running validation tests.*
>
> *(Click **✅ Authorize Tests**)*
>
> *Our isolated Test Runner executes the allowlisted test suite in the background and streams the real process output: **Exit Code 0, 5 Passed in 0.12s**.*
> *We never show a green checkmark for a test that didn't run."*

### Step 8 & 9: GitOps Pull Request Dispatch (3:00 – 3:45)
*(Screen: Click **🚀 Create GitHub PR** and open the PR link)*

> *"With tests verified, SwitchOps requests final authorization to open a Pull Request.*
>
> *(Click **🚀 Create GitHub PR**)*
>
> *The **GitOps Agent** creates an isolated branch `fix/incident-7189`, commits the approved patch, and generates a Pull Request with complete root cause documentation, evidence excerpts, and limitations.*
>
> *The PR link is posted right back into our Switch room for the team."*

### Step 10: Safety Controls & Operational Analytics (3:45 – 4:30)
*(Screen: Point to the Operational Analytics grid with the 'Simulated demo data' label)*

> *"Finally, let's review our safety controls:*
> - *Zero automated merges to main.*
> - *Zero automated deployments.*
> - *Strict command allowlists and path restrictions.*
>
> *On our analytics panel—transparently labeled as simulated demo data—we track real event timestamps: time to triage under 1 second, time to PR under 3 seconds, with 2 required human review gates.*
>
> *SwitchOps proves how Switch can turn AI into a trusted, safe on-call partner.*
>
> *Thank you to WeMakeDevs and DevTools Academy for hosting Flip the Switch!"*

---

## 🛠️ Recording Tips
1. Keep the recording between **3 and 5 minutes**.
2. Run `python -m switchops.web.app` and open `http://localhost:5000` in your browser.
3. Keep Loom or OBS video resolution at **1080p** with crisp audio.
