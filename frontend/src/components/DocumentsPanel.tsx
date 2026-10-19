import { ChangeEvent, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { DocumentInfo } from "../types";

interface Props {
  sectionId: string;
  docs: DocumentInfo[];
  onDocsChange: (docs: DocumentInfo[]) => void;
  onClose: () => void;
}

const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function DocumentsPanel({ sectionId, docs, onDocsChange, onClose }: Props) {
  const [library, setLibrary] = useState<DocumentInfo[]>([]);
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listDocuments().then(setLibrary).catch(() => {});
  }, [docs.length]);

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    setError(null);
    setUploading((n) => n + files.length);
    const added: DocumentInfo[] = [];
    for (const file of files) {
      try {
        added.push(await api.uploadDocument(file, sectionId));
      } catch (err) {
        setError(`${file.name}: ${err instanceof ApiError ? err.message : "upload failed"}`);
      } finally {
        setUploading((n) => n - 1);
      }
    }
    if (added.length) onDocsChange([...docs, ...added]);
  }

  async function attach(documentId: string) {
    const doc = await api.attachDocument(sectionId, documentId);
    onDocsChange([...docs, doc]);
  }

  async function detach(documentId: string) {
    await api.detachDocument(sectionId, documentId);
    onDocsChange(docs.filter((d) => d.id !== documentId));
  }

  const attachedIds = new Set(docs.map((d) => d.id));
  const available = library.filter((d) => !attachedIds.has(d.id) && d.status === "ready");

  return (
    <aside className="docs-panel">
      <div className="panel-header">
        <h3>Documents in this chat</h3>
        <button className="icon" onClick={onClose} aria-label="Close documents">
          ×
        </button>
      </div>
      <p className="small muted">Answers and quizzes use only these files.</p>

      <input ref={inputRef} type="file" accept={ACCEPT} multiple hidden onChange={upload} />
      <button className="primary full" onClick={() => inputRef.current?.click()} disabled={uploading > 0}>
        {uploading > 0 ? `Uploading ${uploading}…` : "Upload files"}
      </button>
      <div className="small muted">PDF, DOCX, TXT, MD, PNG, JPG · up to 25 MB</div>
      {error && <div className="error">{error}</div>}

      <ul className="doc-list">
        {docs.length === 0 && <li className="muted small">No documents yet.</li>}
        {docs.map((d) => (
          <li key={d.id}>
            <div className="doc-name ellipsis" title={d.filename}>
              {d.filename}
            </div>
            <div className="doc-meta">
              <span className={`status ${d.status}`}>{d.status}</span>
              <span className="small muted">
                {formatSize(d.size_bytes)}
                {d.status === "ready" ? ` · ${d.chunk_count} chunks` : ""}
              </span>
              <button className="link small" onClick={() => detach(d.id)}>
                Remove
              </button>
            </div>
            {d.error && <div className="error small">{d.error}</div>}
          </li>
        ))}
      </ul>

      {available.length > 0 && (
        <>
          <h4>From your other chats</h4>
          <ul className="doc-list">
            {available.map((d) => (
              <li key={d.id}>
                <div className="doc-name ellipsis" title={d.filename}>
                  {d.filename}
                </div>
                <button className="secondary small" onClick={() => attach(d.id)}>
                  Add to chat
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
