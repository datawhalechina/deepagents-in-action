---
illustration_id: 01
type: comparison
style: sketch-notes
palette: macaron
references:
  - ref_id: 01
    filename: 01-ref-course-style.png
    usage: style
---

Use case: scientific-educational
Asset type: 16:9 course chapter illustration for a Chinese technical tutorial
Primary request: Draw a clean hand-drawn comparison explaining how the same agent request looks opaque with invoke() and observable with Streaming.

TITLE — render exactly once at the top:
“从黑盒等待到实时可见”

LAYOUT — balanced left/right split with a hand-drawn vertical divider:

LEFT SIDE — a pale peach zone titled exactly “invoke()：只等最终值”
- At the top, a small user request card labeled exactly “研究 Agent Streaming”
- One thick arrow enters a large closed rounded box labeled exactly “Agent 运行中”
- Inside or over the closed box show a spinner and the exact short text “正在生成……”
- Hide the internal work behind the closed box; use three faint question-mark doodles, not extra labels
- At the bottom, one result card labeled exactly “最终答案”
- A small coral warning tag says exactly “过程不可见”

RIGHT SIDE — a pale mint/blue zone titled exactly “Streaming：过程逐步展开”
- The same user request enters a vertical stack of four visible cards connected by arrows:
  1. blue card with robot icon, exact label “coordinator”
  2. lavender card with small assistant icon, exact label “researcher · running”
  3. peach tool card with magnifier icon, exact label “search · completed”
  4. mint message card, exact label “正在整理资料”
- Then connect to a result card labeled exactly “最终答案”
- A small green emphasis tag says exactly “状态 · 消息 · 工具”

BOTTOM TAKEAWAY — render exactly once:
“Streaming 不是更快完成，而是让运行过程可以被理解。”

STYLE:
- Match the supplied course reference only for visual style: warm cream paper, subtle paper grain, black hand-drawn lines with slight wobble, softly painted pastel fills, rounded boxes, simple line icons, generous white space.
- Diagram-style visuals only. No realistic people, no screenshots, no glossy UI, no gradients, no 3D.
- All visible text must be exactly from the quoted strings above. Do not invent any other text. Preserve English API spelling and punctuation exactly.
- Text should be large, legible, and handwritten. Keep visual hierarchy obvious at a glance.

COLORS:
- Warm cream background (#F5F0E8); black ink (#1A1A1A); light blue (#A8D8EA); mint (#B5E5CF); lavender (#D5C6E0); peach (#FFD5C2); coral (#E8655A) only for the warning.
- Color values and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text.

Clean composition with generous white space. Simple background. Main elements centered by content needs.
ASPECT: 16:9 landscape, designed to remain readable at 1600×900, balanced detail level.
