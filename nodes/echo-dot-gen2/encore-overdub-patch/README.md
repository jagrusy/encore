# Encore Overdub Integration & Bluetooth Relay Hooks

This folder extends the vendored [`overdub`](../overdub/README.md) daemon on your rooted **Echo Dot 2nd Gen (`biscuit`)**:

1. **Action Button -> Surface Pro 3 AI Agent:**
   When Overdub captures an action-button press/hold and publishes it via ESPHome (or via the `encore_hook.sh` webhook helper), `encore-brain` receives `/api/v1/ai/wake` and routes responses to your Echo Show 5 screens and TTS pipeline.
2. **Sendspin -> Bluetooth Satellite Relay:**
   Once your 2nd-Gen Dot is paired to a nearby 3rd-Gen Echo Dot (`donut`) over FireOS/Android Bluetooth settings, Overdub automatically streams synchronized Sendspin audio out to that paired Bluetooth speaker (disable the Dot's internal speaker in favor of the BT A2DP sink).
