// Base URL of the running Karabakh Atlas backend API.
//
// Auto-detects localhost (local dev) vs. the deployed Render API — so
// the same file works unmodified in both places. If the API service
// ever gets renamed/redeployed elsewhere, update PROD_API_BASE below.
const PROD_API_BASE = "https://karabakh-atlas-api.onrender.com/api/v1";
const isLocalDev = ["localhost", "127.0.0.1"].includes(window.location.hostname);
window.KBA_API_BASE = isLocalDev
  ? "http://localhost:5000/api/v1"
  : PROD_API_BASE;
