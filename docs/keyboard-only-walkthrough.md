# Keyboard-only demo walkthrough

This walkthrough covers the local demo without a mouse. The mock API, mock microphone, and tool approval preview do not connect to paid services, access a microphone, or execute tools.

## Start the recoverable API-error demo

In PowerShell, start Vite with a one-time API error scenario:

```powershell
$env:VITE_API_MOCK_SCENARIO = 'transient-error'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`. The first session API request fails; retrying it succeeds.

## Walkthrough

1. Press `Tab` to focus **Skip to main content**, then press `Enter`.
2. Press `Tab` to **New session**, then press `Enter`. Wait for creation to finish; focus returns to the button.
3. Tab to **Start** and press `Space` or `Enter`. Capture starts and the API panel reports **Request failed**. Focus moves to **Retry**. The live mock segment appears as **Listening · interim**.
4. From **Retry**, press `Shift+Tab` to reach **Enable mock microphone**. Press `Enter`; the status reports simulated readiness, and focus moves to the microphone status. Press `Tab` to return to **Retry**, then press `Enter`. The mock API recovers and displays **Success**.
5. Tab to the **Conversation transcript** region. The interim segment updates in place to final text, then shows its revision; fixture-supplied values display labels such as **Mock demo confidence: 94%**. Segments without a supplied value have no confidence label.
6. Tab to **Trigger mock tool call**, then press `Enter`. Tab to **Approve** or **Deny** and press `Space` or `Enter`. The result is announced, focus returns to the trigger, and the result explicitly says no tool was executed. Trigger it again to try the other decision.
7. Tab to the **Screen context** switch. It starts off. Press `Space` to turn it on, then `Space` again to turn it off. Confirm the visible “Not shared” status when off.

All controls are native links, buttons, or checkbox switches; no custom keyboard trap or modal is used. Focus rings remain visible, and the API retry and tool decision return focus to stable controls after completion.

## Verified behavior

- `npm test -- --run` covers skip navigation, session controls, context switch keyboard behavior, transient API retry recovery, and both mock tool decisions.
- The mock tool approval panel is intentionally a local interaction preview. Backend tool execution and approval routes remain pending validation.
