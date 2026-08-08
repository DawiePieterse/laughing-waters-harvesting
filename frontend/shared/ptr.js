// Shared pull-to-refresh for the installed PWAs. Standalone mode has no
// browser reload UI, so each screen attaches its own data-refresh callback:
//   LWPTR.attach(async () => { ...reload lists, re-render... });
// Touch-only by design - desktop/mouse users have visible refresh buttons.
const LWPTR = (() => {
  const THRESHOLD = 70;   // px of (damped) pull that triggers a refresh
  const MAX_PULL = 110;
  let onRefresh = null;
  let startY = null;
  let pullDistance = 0;
  let refreshing = false;
  let indicator = null;

  function ensureIndicator() {
    if (indicator) return indicator;
    indicator = document.createElement("div");
    indicator.className = "ptr-indicator";
    indicator.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i>`;
    document.body.appendChild(indicator);
    return indicator;
  }

  function setPull(px) {
    const el = ensureIndicator();
    // Slides down from above the header; the icon turns as you pull.
    el.style.transform = `translate(-50%, ${px - 56}px) rotate(${px * 3}deg)`;
    el.style.opacity = px > 4 ? "1" : "0";
    el.classList.toggle("ready", px >= THRESHOLD);
  }

  async function trigger() {
    const el = ensureIndicator();
    refreshing = true;
    el.classList.add("spinning");
    setPull(THRESHOLD);
    try {
      if (onRefresh) await onRefresh();
    } catch (e) { /* refresh errors surface via each screen's own UI */ }
    el.classList.remove("spinning", "ready");
    setPull(0);
    refreshing = false;
  }

  function onTouchStart(e) {
    if (refreshing || window.scrollY > 0) { startY = null; return; }
    startY = e.touches[0].clientY;
    pullDistance = 0;
  }

  function onTouchMove(e) {
    if (startY === null || refreshing) return;
    const dy = e.touches[0].clientY - startY;
    if (dy <= 0 || window.scrollY > 0) { pullDistance = 0; setPull(0); return; }
    pullDistance = Math.min(dy * 0.5, MAX_PULL); // damped so it feels elastic
    setPull(pullDistance);
    if (pullDistance > 8 && e.cancelable) e.preventDefault();
  }

  function onTouchEnd() {
    if (startY === null || refreshing) return;
    startY = null;
    if (pullDistance >= THRESHOLD) trigger();
    else setPull(0);
    pullDistance = 0;
  }

  return {
    attach(callback) {
      onRefresh = callback;
      ensureIndicator();
      document.addEventListener("touchstart", onTouchStart, { passive: true });
      document.addEventListener("touchmove", onTouchMove, { passive: false });
      document.addEventListener("touchend", onTouchEnd, { passive: true });
      document.addEventListener("touchcancel", onTouchEnd, { passive: true });
    },
  };
})();
