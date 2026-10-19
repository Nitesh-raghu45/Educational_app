import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";

interface Props {
  message: Message;
  onRetry?: () => void;
}

export default function MessageBubble({ message, onRetry }: Props) {
  if (message.role === "user") {
    return (
      <div className="message user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  const waiting = (message.status === "pending" || message.status === "streaming") && !message.content;
  return (
    <div className="message assistant">
      <div className="answer">
        {waiting ? (
          <div className="typing">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        )}
        {message.status === "streaming" && message.content && <span className="cursor" />}
        {message.citations && message.citations.length > 0 && (
          <div className="citations">
            {message.citations.map((c) => (
              <details key={c.chunk_id} className="citation">
                <summary>
                  [{c.index}] {c.filename}
                  {c.page ? ` · p.${c.page}` : ""}
                </summary>
                <p>{c.snippet}</p>
              </details>
            ))}
          </div>
        )}
        {message.status === "failed" && (
          <div className="failed">
            The answer couldn't be generated.
            {onRetry && (
              <button className="secondary small" onClick={onRetry}>
                Retry (won't use a question)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
