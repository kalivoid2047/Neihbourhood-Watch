/**
 * Emergency siren built on the Web Audio API (no audio asset to ship).
 *
 * Browsers keep an AudioContext suspended until the user has interacted with
 * the page, so `armSiren()` hooks the first gesture; `startSiren()` reports
 * whether sound is actually playing so the UI can ask for a tap when it is not.
 */

let ctx = null;
let nodes = null;
let sweepTimer = null;

function getContext() {
  if (!ctx) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    ctx = new AudioCtx();
  }
  return ctx;
}

/** Call once at startup: unlocks audio on the user's first click/tap/keypress. */
export function armSiren() {
  const unlock = () => {
    getContext()?.resume?.();
    window.removeEventListener('pointerdown', unlock);
    window.removeEventListener('keydown', unlock);
  };
  window.addEventListener('pointerdown', unlock);
  window.addEventListener('keydown', unlock);
  return () => {
    window.removeEventListener('pointerdown', unlock);
    window.removeEventListener('keydown', unlock);
  };
}

/** Start the two-tone wail. Returns true if the browser let it make sound. */
export async function startSiren() {
  const audio = getContext();
  if (!audio) return false;
  try {
    await audio.resume();
  } catch { /* handled by the state check below */ }
  if (audio.state !== 'running') return false;
  if (nodes) return true;

  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = 'square';
  osc.frequency.value = 660;
  gain.gain.value = 0.25;
  osc.connect(gain).connect(audio.destination);
  osc.start();
  nodes = { osc, gain };

  let high = false;
  const sweep = () => {
    high = !high;
    osc.frequency.cancelScheduledValues(audio.currentTime);
    osc.frequency.setValueAtTime(osc.frequency.value, audio.currentTime);
    osc.frequency.linearRampToValueAtTime(high ? 960 : 660, audio.currentTime + 0.45);
  };
  sweep();
  sweepTimer = setInterval(sweep, 500);
  return true;
}

export function stopSiren() {
  clearInterval(sweepTimer);
  sweepTimer = null;
  if (nodes) {
    try { nodes.osc.stop(); } catch { /* already stopped */ }
    nodes.osc.disconnect();
    nodes.gain.disconnect();
    nodes = null;
  }
}
