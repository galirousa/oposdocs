/* Consent layer. No non-essential cookies and no ad scripts fire before
 * consent. Rejecting is one click, same prominence as accepting. Consent
 * state lives client-side; each decision is logged server-side for audit.
 *
 * Production note: swap this for a TCF v2.2 certified CMP (Google's free CMP)
 * before enabling AdSense in the EEA. The load gate below stays identical.
 */
(function () {
  "use strict";
  var KEY = "opos-consent";
  var script = document.currentScript;
  var adsEnabled = script && script.dataset.adsEnabled === "1";
  var adsenseClient = script ? script.dataset.adsenseClient : "";
  var banner = document.getElementById("consent-banner");

  function getConsent() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function logConsent(decision) {
    try {
      fetch("/consentimiento/registrar/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ decision: decision })
      });
    } catch (e) { /* audit log is best-effort */ }
  }
  function csrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }
  function loadAds() {
    if (!adsEnabled || !adsenseClient) return;
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + encodeURIComponent(adsenseClient);
    s.crossOrigin = "anonymous";
    document.head.appendChild(s);
  }
  function decide(decision) {
    try { localStorage.setItem(KEY, decision); } catch (e) { /* private mode */ }
    if (banner) banner.hidden = true;
    logConsent(decision);
    if (decision === "accepted") loadAds();
  }

  var stored = getConsent();
  if (stored === "accepted") {
    loadAds();
  } else if (stored !== "rejected" && banner) {
    banner.hidden = false;
    document.getElementById("consent-accept").addEventListener("click", function () { decide("accepted"); });
    document.getElementById("consent-reject").addEventListener("click", function () { decide("rejected"); });
  }
})();
