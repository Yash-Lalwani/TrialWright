// Renders the small Markdown subset the draft endpoint produces (headings, bullet and numbered
// lists, paragraphs, bold) as React elements. No HTML is injected; unknown syntax stays as text.
// NCT ids in the text become links to ClinicalTrials.gov.

import type { ReactNode } from "react";

const NCT = /\bNCT\d{8}\b/g;

export function nctUrl(id: string) {
  return `https://clinicaltrials.gov/study/${encodeURIComponent(id)}`;
}

function inline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  // Bold first, then NCT ids inside each piece.
  text.split(/(\*\*[^*]+\*\*)/g).forEach((part, i) => {
    const bold = /^\*\*([^*]+)\*\*$/.exec(part);
    const nodes = linkNct(bold ? bold[1] : part, `${keyBase}-${i}`);
    if (bold) out.push(<strong key={`${keyBase}-${i}`}>{nodes}</strong>);
    else out.push(...nodes);
  });
  return out;
}

function linkNct(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(NCT)) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(
      <a
        key={`${keyBase}-${m.index}`}
        href={nctUrl(m[0])}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-primary underline-offset-2 hover:underline"
      >
        {m[0]}
      </a>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ source }: { source: string }) {
  const blocks: ReactNode[] = [];
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const cls = level <= 2 ? "mt-4 text-base font-semibold" : "mt-4 text-sm font-semibold";
      blocks.push(
        level <= 2 ? (
          <h4 key={key++} className={cls}>{inline(heading[2], `h${key}`)}</h4>
        ) : (
          <h5 key={key++} className={cls}>{inline(heading[2], `h${key}`)}</h5>
        ),
      );
      i += 1;
      continue;
    }
    const bullet = /^\s*(?:[-*]|\d+[.)])\s+/;
    if (bullet.test(line)) {
      const ordered = /^\s*\d/.test(line);
      const items: string[] = [];
      while (i < lines.length && bullet.test(lines[i])) {
        items.push(lines[i].replace(bullet, ""));
        i += 1;
      }
      const Tag = ordered ? "ol" : "ul";
      blocks.push(
        <Tag key={key++} className={ordered ? "mt-2 list-decimal space-y-1 pl-5" : "mt-2 list-disc space-y-1 pl-5"}>
          {items.map((t, n) => (
            <li key={n}>{inline(t, `l${key}-${n}`)}</li>
          ))}
        </Tag>,
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6})\s/.test(lines[i]) && !bullet.test(lines[i])) {
      para.push(lines[i].trim());
      i += 1;
    }
    blocks.push(
      <p key={key++} className="mt-2 leading-relaxed">
        {inline(para.join(" "), `p${key}`)}
      </p>,
    );
  }
  return <div className="text-sm [&>:first-child]:mt-0">{blocks}</div>;
}
