# Live2D example / Live2D 範例

`zh-lipsync` only outputs a timeline, so it works with any Live2D runtime. Each frame:

1. Look up the shape at the audio's current time.
2. Turn it into the two standard Cubism parameters:
   - `ParamMouthOpenY`: how far the mouth is open, 0 to 1.
   - `ParamMouthForm`: the mouth's form, from -1 (round) to 1 (wide).

`zh-lipsync` 只輸出時間軸，所以任何 Live2D 播放器都能用。每一幀：

1. 依音檔目前的秒數查出當下的嘴型。
2. 把嘴型換成 Cubism 的兩個標準參數：
   - `ParamMouthOpenY`：嘴巴張開的程度，0～1。
   - `ParamMouthForm`：嘴型，-1（圓）到 1（扁）。

```js
import { CuePlayer, live2dTarget, Smoother } from '../js/zh-lipsync-player.js';

const timeline = await (await fetch('voice.lipsync.json')).json();
const player = new CuePlayer(timeline.cues);
const open = new Smoother(), form = new Smoother({ attack: 0.05, release: 0.05 });

// pixi-live2d-display (MIT) example; with the official Cubism Web SDK, call
// model.setParameterValueById(...) at the same place in your update loop.
app.ticker.add(() => {
  const dt = app.ticker.deltaMS / 1000;
  const target = live2dTarget(player.at(audio.currentTime));
  const core = model.internalModel.coreModel;
  core.setParameterValueById('ParamMouthOpenY', open.step(target.open, dt));
  core.setParameterValueById('ParamMouthForm', form.step(target.form, dt));
});
```

**Shape table.** These values are in `LIVE2D_SHAPES` in `../js/zh-lipsync-player.js`. Tune them to your model.

**嘴型對照表。** 數值寫在 `../js/zh-lipsync-player.js` 的 `LIVE2D_SHAPES`，請依自己的模型調整。

| shape | Zhuyin / 注音 | ParamMouthOpenY | ParamMouthForm |
|---|---|---|---|
| `a` | ㄚ ㄢ ㄤ … | 1.0 | 0 |
| `e` | ㄜ ㄝ ㄟ ㄣ ㄥ ㄧㄢ … | 0.5 | 0.3 |
| `i` | ㄧ ㄧㄣ ㄧㄥ, 是/字/知 | 0.25 | 1 |
| `o` | ㄛ ㄨㄛ ㄡ ㄧㄡ | 0.65 | -0.7 |
| `u` | ㄨ ㄩ ㄨㄥ … | 0.3 | -1 |
| `n` | closed / 閉嘴 | 0 | 0 |

**Not included.** No Live2D model or SDK is shipped here. The Cubism SDK and the sample models have their own licenses.

**沒附的東西。** 這裡不附任何 Live2D 模型或 SDK。Cubism SDK 和範例模型各有自己的授權。

**Not tested yet.** This example has not been run against a real Live2D model. The table values are untuned defaults.

**還沒測過。** 這個範例沒有接真的 Live2D 模型跑過，對照表的數值也還沒調。
