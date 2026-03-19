"use client";

import { Fragment, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationPopover } from "./CitationPopover";

interface Reference {
  content: string;
  score: number;
  source_id: string | null;
  source_title: string;
}

interface MarkdownWithCitationsProps {
  content: string;
  references?: Reference[];
  className?: string;
}

function processChildren(
  children: ReactNode,
  references: Reference[]
): ReactNode {
  if (typeof children === "string") {
    return injectCitations(children, references);
  }
  if (Array.isArray(children)) {
    return children.map((child, i) => (
      <Fragment key={i}>{processChildren(child, references)}</Fragment>
    ));
  }
  return children;
}

function injectCitations(text: string, references: Reference[]): ReactNode {
  // Inline citation injection:
  // We search for patterns like `[1]` in text nodes and replace them with
  // `<CitationPopover />` buttons so they stay within the same paragraph/line.
  const pattern = /\[(\d+)\]/g;
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    const citIndex = parseInt(match[1], 10);
    if (citIndex >= 1 && citIndex <= references.length) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      parts.push(
        <CitationPopover
          key={`c${key++}`}
          index={citIndex}
          reference={references[citIndex - 1]}
        />
      );
      lastIndex = match.index + match[0].length;
    }
  }

  if (lastIndex === 0) return text;
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return <>{parts}</>;
}

function makeWrappedComponent(
  Tag: string,
  baseClass: string,
  references: Reference[]
) {
  return function WrappedComponent({ children, ...props }: any) {
    return (
      <Tag className={baseClass} {...props}>
        {processChildren(children, references)}
      </Tag>
    );
  };
}

export function MarkdownWithCitations({
  content,
  references,
  className = "",
}: MarkdownWithCitationsProps) {
  const hasRefs = !!references && references.length > 0;

  const components: Record<string, any> = {
    h1: ({ children }: any) => (
      <h1 className="text-xl font-bold mt-4 mb-2 border-b border-[var(--border)] pb-2">
        {hasRefs ? processChildren(children, references!) : children}
      </h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="text-lg font-semibold mt-3 mb-1.5">
        {hasRefs ? processChildren(children, references!) : children}
      </h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="text-base font-semibold mt-2.5 mb-1">
        {hasRefs ? processChildren(children, references!) : children}
      </h3>
    ),
    p: ({ children }: any) => (
      <p className="my-1.5 leading-relaxed">
        {hasRefs ? processChildren(children, references!) : children}
      </p>
    ),
    ul: ({ children }: any) => (
      <ul className="my-1.5 ml-4 list-disc space-y-0.5">{children}</ul>
    ),
    ol: ({ children }: any) => (
      <ol className="my-1.5 ml-4 list-decimal space-y-0.5">{children}</ol>
    ),
    li: ({ children }: any) => (
      <li className="leading-relaxed">
        {hasRefs ? processChildren(children, references!) : children}
      </li>
    ),
    code: ({ className: cn, children, ...props }: any) => {
      const isInline = !cn;
      if (isInline) {
        return (
          <code className="rounded bg-[var(--secondary)] px-1.5 py-0.5 text-xs font-mono">
            {children}
          </code>
        );
      }
      return (
        <code
          className={`block overflow-x-auto rounded-lg bg-[var(--secondary)] p-3 text-xs font-mono leading-relaxed ${cn || ""}`}
          {...props}
        >
          {children}
        </code>
      );
    },
    pre: ({ children }: any) => <pre className="my-2 overflow-x-auto">{children}</pre>,
    blockquote: ({ children }: any) => (
      <blockquote className="my-2 border-l-3 border-[var(--primary)] pl-3 italic text-[var(--muted-foreground)]">
        {hasRefs ? processChildren(children, references!) : children}
      </blockquote>
    ),
    table: ({ children }: any) => (
      <div className="my-2 overflow-x-auto">
        <table className="w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    th: ({ children }: any) => (
      <th className="border border-[var(--border)] bg-[var(--secondary)] px-3 py-1.5 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border border-[var(--border)] px-3 py-1.5">
        {hasRefs ? processChildren(children, references!) : children}
      </td>
    ),
    a: ({ children, href }: any) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--primary)] underline hover:opacity-80"
      >
        {children}
      </a>
    ),
    strong: ({ children }: any) => (
      <strong className="font-semibold">
        {hasRefs ? processChildren(children, references!) : children}
      </strong>
    ),
  };

  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
