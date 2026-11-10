// zh-lipsync timeline player (no dependencies). Works with any avatar runtime.
//
//   import { CuePlayer, live2dTarget, Smoother } from './zh-lipsync-player.js';
//   const player = new CuePlayer(timeline.cues, { lead: 1 / 30 });
//   each frame: const shape = player.at(audio.currentTime);   // 'a' | 'i' | 'u' | 'e' | 'o' | 'n'

export class CuePlayer {
  /** cues: [{t, shape}] from zh-lipsync (sorted). lead: show shapes slightly early (seconds) to hide render latency. */
  constructor(cues, { lead = 1 / 30 } = {}) {
    this.cues = cues; this.lead = lead; this.k = -1; this.lastT = -Infinity;
  }
  /** Shape at time t (seconds of the audio). Fast for increasing t; seeking backwards is fine too. */
  at(t) {
    t += this.lead;
    if (t < this.lastT) this.k = -1;          // seek back: restart the scan
    this.lastT = t;
    const c = this.cues;
    while (this.k + 1 < c.length && c[this.k + 1].t <= t) this.k++;
    return this.k >= 0 ? c[this.k].shape : 'n';
  }
}

/** Live2D standard parameters for each shape: ParamMouthOpenY 0..1, ParamMouthForm -1 (round) .. 1 (wide). */
export const LIVE2D_SHAPES = {
  a: { open: 1.0, form: 0.0 },
  i: { open: 0.25, form: 1.0 },
  u: { open: 0.3, form: -1.0 },
  e: { open: 0.5, form: 0.3 },
  o: { open: 0.65, form: -0.7 },
  n: { open: 0.0, form: 0.0 },
};
export const live2dTarget = shape => LIVE2D_SHAPES[shape] ?? LIVE2D_SHAPES.n;

/** Exponential smoothing so the mouth moves instead of snapping: ~30 ms to open, ~45 ms to close. */
export class Smoother {
  constructor({ attack = 0.03, release = 0.045 } = {}) { this.attack = attack; this.release = release; this.v = 0; }
  step(target, dt) {
    const tau = target > this.v ? this.attack : this.release;
    this.v += (target - this.v) * (1 - Math.exp(-dt / tau));
    return this.v;
  }
}
