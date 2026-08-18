---
illustration_id: 03-v2
type: flowchart
style: sketch-notes
palette: macaron
references:
  - ref_id: 02
    filename: 02-ref-course-flow.png
    usage: style
---

Use case: scientific-educational
Asset type: 16:9 course chapter illustration for a Chinese technical tutorial
Primary request: Redraw the realtime streaming sequence diagram as a clean Chinese course illustration. Keep the technical relationships, but remove all layout-instruction labels and reduce text clutter.

TITLE — render exactly once at the top:
“事件交错到达，消费也要并发”

COMPOSITION:
- Use three visual areas separated only by white space and thin hand-drawn dividers.
- IMPORTANT: never display any area or layout names. Do not render “LEFT ZONE”, “CENTER ZONE”, “RIGHT ZONE”, “ZONE”, “LANE”, “LAYOUT”, or other design-instruction words anywhere.

FIRST AREA — two parallel time lanes:
- Only two lane headers: “coordinator” and “researcher”.
- Time flows downward.
- Show these event cards in interleaved chronological order:
  “开始委派”
  “消息：开始研究”
  “search · running”
  “search · completed”
  “消息：整理资料”
  “最终总结”
- Dotted timing guides make the interleaving obvious.

SECOND AREA — compare two consumption paths:
- Coral funnel titled “串行消费”. Inside it show only “coordinator 全部” and “researcher 全部”. Add the warning “顺序失真”.
- Mint merge arrow titled “并发消费”. Inside it show exactly “asyncio.gather / interleave”.
- Both time lanes feed the concurrent path without blocking.

THIRD AREA — compact event feed:
- Header “页面事件流”.
- Four cards with numbered badges 1–4:
  “委派已启动”
  “正在搜索”
  “正在整理”
  “最终总结”

BOTTOM TAKEAWAY — render exactly once:
“并发消费保留实时感；精确审计再读取 raw events。”

TEXT RULES:
- Render only the title, lane headers, event labels, consumption labels, UI feed labels, and takeaway explicitly quoted above.
- Do not invent captions, translations, zone names, code comments, or decorative words.
- Preserve “coordinator”, “researcher”, “search · running”, “search · completed”, “asyncio.gather / interleave”, and “raw events” exactly.
- All text large, legible, and handwritten-style.

STYLE:
- Match the established course style: warm cream paper, subtle paper grain, black hand-drawn lines with slight wobble, low-saturation blue/mint/lavender/peach cards, rounded boxes, unambiguous arrows, generous white space.
- Diagram only. No realistic people, no screenshots, no glossy UI, no gradients, no 3D.
- Keep the image as airy and restrained as the existing Chapter 12–13 diagrams.

COLORS:
- Warm cream background (#F5F0E8); black ink (#1A1A1A); light blue (#A8D8EA); lavender (#D5C6E0); peach (#FFD5C2); mint (#B5E5CF); coral (#E8655A) only for the serial-flow warning.
- Color values and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text.

Clean composition with generous white space. Simple background. Main elements centered by content needs.
ASPECT: 16:9 landscape, designed to remain readable at 1600×900, balanced detail level.
