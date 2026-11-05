# Week 2 demo script

## One-time setup

In PowerShell, start the app with its recoverable mock API error enabled:

```powershell
$env:VITE_API_MOCK_SCENARIO = 'transient-error'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`. To repeat the demo, reload the page first; the one-time mock failure resets with the page.

## Demo

1. **Open and start capture.** Select **New session**, then **Start**.
   - **Expected:** Session is active, capture status reads **Capturing**, and the capture-start announcement fires. The first session API request also fails in this mock scenario; **Request failed** and **Retry** appear. Leave Retry for step 4.
2. **Show interim and final transcript.** Watch the live transcript for about five seconds; updates arrive roughly every 1.4 seconds.
   - **Expected:** One segment updates in place through **Listening · interim**, then displays its final text with a **Revised** marker. Fixture-provided confidence appears as **Mock demo confidence: 94%**.
3. **Show pause and resume.** Select **Pause**, then **Resume**.
   - **Expected:** Status changes to **Paused** then **Capturing**; polite announcements say “Capture paused” and “Capture resumed.” The transcript segment retains its **Revised** marker and confidence.
4. **Recover the API request.** Select **Retry**.
   - **Expected:** The mock request succeeds and the API panel shows **Success**. Capture remains active and the transcript stays visible. The failure was triggered during Start because that action makes the first session request; this script intentionally delays retry until after the transcript and capture controls are demonstrated.
5. **Explicitly toggle screen context.** In **Context & Sources**, turn **Screen context** on, then off.
   - **Expected:** It starts off. On enable, the switch reads **On** and the panel says it is enabled for this session. On disable, it reads **Off**, displays **Not shared**, and states “Screen context is off — nothing from your screen is shared.” No screen data is included in the mock transcript/context output while off.

All transcript, API, capture, and context behavior in this demo is local mock behavior; the mock microphone does not record audio.
