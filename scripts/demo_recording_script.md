# 🎬 SwitchOps: Winning Demo Video Recording Script (2 Minutes)

Use this script to record your **2-minute demo video** for the **Flip the Switch** Hackathon submission on Loom or YouTube.

---

## ⏱️ Video Outline & Timestamps

- **0:00 - 0:25**: The Problem & The Solution (Why SwitchOps?)
- **0:25 - 1:00**: Live Incident Trigger & Automated RCA in the Switch Room
- **1:00 - 1:30**: Human-in-the-Loop Collaboration (Wispr Voice Approval)
- **1:30 - 1:50**: Automated GitHub PR & SandboxAQ Switch ROI Telemetry
- **1:50 - 2:00**: Conclusion & Open-Source Impact

---

## 🎙️ Step-by-Step Narration Script

### 1. Introduction (0:00 - 0:25)
> *"Hi everyone! When production breaks at 2 AM, the mean time to resolution for on-call engineers is over 45 minutes. Engineers are forced to jump across disparate monitoring dashboards, inspect logs, manually locate buggy code, and write patches.*
>
> *Today, I'm thrilled to introduce **SwitchOps**—an autonomous SRE teammate that embeds directly into your team's Slack and Discord channels using the open-source **Switch** bridge by SandboxAQ. Let's see it in action."*

### 2. Live Incident & Autonomous Diagnosis (0:25 - 1:00)
*(Screen: Show the SwitchOps Web UI on localhost:5000 or your Slack channel)*

> *"Here in our incident dashboard, an alert fires: our payments microservice is throwing a 500 error on checkout.*
>
> *(Click the **🚨 Trigger Production 500** button)*
>
> *Immediately, Switch connects our multi-agent team into a shared incident room `#incident-inc-7842`:*
> - *Our **Triage Agent** parses the stack trace and pinpoints the exact file and line number in `payments_service/app.py`.*
> - *The diagnosis? An unhandled KeyError from lowercase currency inputs.*
> - *Next, our **Remediation Agent** synthesizes a non-breaking surgical patch and generates an automated regression test, verifying that all 5 tests pass in 0.12 seconds."*

### 3. Human-in-the-Loop Collaboration with Wispr Flow (1:00 - 1:30)
*(Screen: Highlight the interactive approval card and click the Voice button)*

> *"Crucially, SwitchOps believes in **Human-in-the-Loop engineering**. It doesn't deploy blindly without human oversight. It posts a unified diff and regression test results directly into the chat thread.*
>
> *As the on-call engineer, I don't even need to touch my keyboard. Using our **Wispr Flow voice integration**, I can simply speak:*
>
> *(Speak or click: **"Looks good SwitchOps, approve the hotfix and deploy to production"**)*
>
> *Wispr Flow transcribes the intent with 98% confidence and dispatches the approval."*

### 4. Git Automation & Switch ROI (1:30 - 1:50)
*(Screen: Point to the Git PR link and the ROI grid on the right)*

> *"Instantly, our **GitOps Agent** cuts a new git branch, commits the fix using Conventional Commits, opens a Pull Request on GitHub, and links the post-mortem report right back into our chat.*
>
> *And by implementing the **SandboxAQ Switch ROI** framework, we observe:*
> - *Our MTTR dropped from 45 minutes to just 3.6 seconds—a **97%+ reduction**.*
> - *Over **$3,600** in downtime and engineering time saved.*
> - *All for less than 1 cent in LLM tokens—delivering a **400x+ ROI**."*

### 5. Closing (1:50 - 2:00)
> *"SwitchOps proves that when you bridge AI agents into human collaboration channels with Switch, you don't just get a chatbot—you get an autonomous, reliable engineering partner.*
>
> *Thank you to WeMakeDevs, DevTools Academy, and SandboxAQ for hosting Flip the Switch!"*

---

## 🛠️ Quick Checklist Before Recording
1. Start the web cockpit: `python -m switchops.web.app`
2. Open `http://localhost:5000` in full screen (or split half-screen with Slack/Discord).
3. Test the trigger button once to ensure smooth transitions.
4. Keep Loom recording set to 1080p with mic enabled.
