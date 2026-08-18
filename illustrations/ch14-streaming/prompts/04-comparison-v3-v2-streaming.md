---
illustration_id: 04
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
Primary request: Draw a clean technical comparison between Deep Agents v3 Typed Projection and LangGraph v2 StreamPart protocol, ending in a shared application adapter.

TITLE — render exactly once at the top:
“v3 与 v2：两个观察层级”

LAYOUT — two equal columns with a center divider, both flowing down into one bottom adapter:

LEFT COLUMN — pale mint/blue header labeled exactly “v3 · Typed Projection”
- Subtitle exactly “面向产品角色”
- Show three stacked rounded cards with exact text:
  1. “message.text” with a chat icon
  2. “subagent.name / path / status” with a small branching robot icon
  3. “tool_call.input / output / error” with a wrench icon
- A small outlined tag says exactly “新页面优先”
- A short callout says exactly “直接表达谁在工作”

RIGHT COLUMN — pale lavender/peach header labeled exactly “v2 · StreamPart”
- Subtitle exactly “面向图执行协议”
- Show one large protocol envelope containing three large exact field names:
  “type”  “ns”  “data”
- Under “data”, branch into three small chips with exact labels:
  “updates”  “messages”  “custom”
- A small outlined tag says exactly “迁移与调试”
- A short callout says exactly “必须按 type 解读 data”

BOTTOM SHARED ADAPTER:
- Arrows from both columns enter one wide cream rounded box labeled exactly “应用事件 Adapter”
- Inside show four output chips with exact labels:
  “source”  “path”  “kind”  “sequence”
- One arrow continues to a small UI card labeled exactly “页面只读统一事件”

BOTTOM TAKEAWAY — render exactly once:
“不要在同一个循环里混用两套字段。”

STYLE:
- Match the supplied course reference only for visual style: warm cream paper, subtle paper grain, black hand-drawn lines with slight wobble, softly painted pastel fills, rounded boxes, simple technical icons, clean arrows, generous white space.
- Diagram only. No realistic humans, no screenshots, no glossy UI, no gradients, no 3D.
- All visible text must be exactly from the quoted strings above. Do not invent any other labels. Preserve the capitalization, dots, slashes, underscores, and API identifiers exactly.
- Make all identifiers large and sharply legible; keep Chinese annotations short.

COLORS:
- Warm cream background (#F5F0E8); black ink (#1A1A1A); light blue (#A8D8EA) and mint (#B5E5CF) for v3; lavender (#D5C6E0) and peach (#FFD5C2) for v2; coral (#E8655A) only for the final warning takeaway.
- Color values and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text.

Clean composition with generous white space. Simple background. Main elements centered by content needs.
ASPECT: 16:9 landscape, designed to remain readable at 1600×900, balanced technical detail.
