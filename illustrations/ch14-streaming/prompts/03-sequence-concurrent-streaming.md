---
illustration_id: 03
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
Primary request: Draw a hand-drawn sequence and routing diagram showing why coordinator and researcher streams must be consumed concurrently for a realtime UI.

TITLE — render exactly once at the top:
“事件交错到达，消费也要并发”

LAYOUT — three vertical zones from left to right:

LEFT ZONE — two parallel swimlanes, clearly separated:
- Upper lane header exactly “coordinator” in a pale blue capsule
- Lower lane header exactly “researcher” in a pale lavender capsule
- Time flows downward using a thin hand-drawn vertical line in each lane
- Put these event cards in chronological vertical order, interleaved across the two lanes:
  1. coordinator card: “开始委派”
  2. researcher card: “消息：开始研究”
  3. researcher peach tool card: “search · running”
  4. researcher mint tool card: “search · completed”
  5. researcher card: “消息：整理资料”
  6. coordinator card: “最终总结”
- Use short dotted horizontal timing guides to show the interleaving.

CENTER ZONE — a forked comparison:
- Top coral-outline funnel titled exactly “串行消费”
- Under it show a wrongly reordered list:
  “coordinator 全部”
  “researcher 全部”
- Add a coral warning label exactly “顺序失真”
- Bottom mint-outline merge titled exactly “并发消费”
- Put the exact code label “asyncio.gather / interleave” inside
- Merge arrows from both swimlanes into it without blocking one another.

RIGHT ZONE — one clean UI event feed titled exactly “页面事件流”
- Show four compact cards in correct arrival order:
  “委派已启动”
  “正在搜索”
  “正在整理”
  “最终总结”
- Use a small sequence-number badge 1, 2, 3, 4 on these cards.

BOTTOM TAKEAWAY — render exactly once:
“并发消费保留实时感；精确审计再读取 raw events。”

STYLE:
- Match the supplied course flow reference only for visual style: warm cream paper, subtle paper grain, black hand-drawn lines with slight wobble, softly painted pastel cards, rounded boxes, unambiguous arrows, restrained doodles, generous white space.
- Diagram only. No realistic people, no screenshots, no glossy UI, no gradients, no 3D.
- All visible text must be exactly from the quoted strings above. Do not invent extra text. Preserve “asyncio.gather / interleave” and English identifiers exactly.
- Text should be large, legible, handwritten-style, with clear lane and flow hierarchy.

COLORS:
- Warm cream background (#F5F0E8); black ink (#1A1A1A); light blue (#A8D8EA) coordinator; lavender (#D5C6E0) researcher; peach (#FFD5C2) running tool; mint (#B5E5CF) completed or correct flow; coral (#E8655A) wrong serial flow.
- Color values and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text.

Clean composition with generous white space. Simple background. Main elements centered by content needs.
ASPECT: 16:9 landscape, designed to remain readable at 1600×900, balanced detail level.
