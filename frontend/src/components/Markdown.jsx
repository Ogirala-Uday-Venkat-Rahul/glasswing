// A small, dependency-free Markdown renderer.
//
// The agent answers in Markdown -- bold, bullet lists, headings, inline code,
// the occasional link. Rendered as plain text those markers show up as literal
// "**" and "*" on screen, which reads as broken. Rather than pull in a library
// we parse the subset the model actually produces and render it through React
// elements. Everything is real DOM (no dangerouslySetInnerHTML), so there is no
// HTML-injection surface: the worst a stray character can do is render as text.

// --- Inline: bold, italic, inline code, links --------------------------------
// One regex matches the four inline forms; we walk the matches, emitting the
// plain text between them untouched. Order in the alternation matters -- ** must
// be tried before * so bold isn't misread as two italics.
const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\n]+\*)|(\[[^\]]+\]\([^)\s]+\))/g;

function renderInline(text, keyBase) {
  const nodes = [];
  let last = 0;
  let m;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const token = m[0];
    const key = `${keyBase}-${i++}`;
    if (token.startsWith("`")) {
      nodes.push(<code key={key} className="md-code">{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("*")) {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else {
      // [label](url)
      const split = token.indexOf("](");
      const label = token.slice(1, split);
      const url = token.slice(split + 2, -1);
      nodes.push(
        <a key={key} href={url} target="_blank" rel="noopener noreferrer">{label}</a>
      );
    }
    last = m.index + token.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// --- Blocks: headings, lists, paragraphs -------------------------------------
// Group the lines into blocks, then render each. A blank line ends the current
// list or paragraph; a run of list items becomes one list; everything else is a
// paragraph whose internal line breaks we keep.
const HEADING = /^(#{1,3})\s+(.*)$/;
const BULLET = /^\s*[-*]\s+(.*)$/;
const NUMBERED = /^\s*\d+\.\s+(.*)$/;

function parseBlocks(src) {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let para = null; // accumulating paragraph lines
  let list = null; // { ordered, items: [] }

  const flush = () => {
    if (para) { blocks.push({ type: "p", lines: para }); para = null; }
    if (list) { blocks.push({ type: "list", ...list }); list = null; }
  };

  for (const line of lines) {
    if (!line.trim()) { flush(); continue; }

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({ type: "h", level: heading[1].length, text: heading[2] });
      continue;
    }

    const bullet = BULLET.exec(line);
    const numbered = !bullet && NUMBERED.exec(line);
    if (bullet || numbered) {
      if (para) { blocks.push({ type: "p", lines: para }); para = null; }
      const ordered = Boolean(numbered);
      if (!list || list.ordered !== ordered) {
        if (list) blocks.push({ type: "list", ...list });
        list = { ordered, items: [] };
      }
      list.items.push((bullet || numbered)[1]);
      continue;
    }

    // A plain line: part of a paragraph. Ends any open list.
    if (list) { blocks.push({ type: "list", ...list }); list = null; }
    (para ||= []).push(line);
  }
  flush();
  return blocks;
}

export default function Markdown({ text }) {
  const blocks = parseBlocks(text || "");
  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.type === "h") {
          const Tag = `h${Math.min(b.level + 2, 6)}`; // # -> h3, keeps it in-flow
          return <Tag key={i} className="md-h">{renderInline(b.text, `h${i}`)}</Tag>;
        }
        if (b.type === "list") {
          const Tag = b.ordered ? "ol" : "ul";
          return (
            <Tag key={i} className="md-list">
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it, `l${i}-${j}`)}</li>
              ))}
            </Tag>
          );
        }
        // paragraph: keep internal line breaks
        return (
          <p key={i} className="md-p">
            {b.lines.map((ln, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {renderInline(ln, `p${i}-${j}`)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}
