// Kopiera till web/config.js om sidan ligger som ren statisk fil utan servern.
// Ligger sidan bakom FastAPI-servern serveras /config.js automatiskt från .env.
window.AIREPA_CONFIG = {
  publicKey: "din-vapi-public-key",
  assistantId: "ditt-assistant-id"
};
