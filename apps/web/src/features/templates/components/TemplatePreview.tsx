"use client";

interface TemplateButton {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER";
  text: string;
}

interface Props {
  body: string;
  header?: string;
  headerType?: "TEXT" | "IMAGE" | "VIDEO" | "DOCUMENT";
  footer?: string;
  buttons?: TemplateButton[];
  bodyExamples?: string[];
  headerExample?: string;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderWithVars(text: string, examples: string[]): string {
  return escapeHtml(text)
    .replace(/\{\{(\d+)\}\}/g, (_, n: string) => {
      const idx = parseInt(n, 10) - 1;
      const ex = examples[idx];
      if (ex && ex.trim()) {
        return `<span class="font-medium text-teal-700 dark:text-teal-300">${escapeHtml(ex)}</span>`;
      }
      return `<span class="font-medium text-teal-700 dark:text-teal-300">{{${n}}}</span>`;
    })
    .replace(/\n/g, "<br />");
}

export function TemplatePreview({
  body,
  header,
  headerType = "TEXT",
  footer,
  buttons = [],
  bodyExamples = [],
  headerExample,
}: Props) {
  const hasHeader = header && headerType === "TEXT";
  const isMediaHeader = headerType === "IMAGE" || headerType === "VIDEO" || headerType === "DOCUMENT";

  return (
    <div className="flex flex-col items-center">
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
        Preview ao vivo
      </p>

      {/* Phone frame */}
      <div
        className="relative mx-auto"
        style={{
          width: 260,
          height: 520,
          background: "linear-gradient(145deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
          borderRadius: 36,
          padding: "3px",
          boxShadow: "0 0 0 2px #2d2d4e, 0 20px 60px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1)",
        }}
      >
        {/* Screen */}
        <div
          style={{
            background: "#e5ddd5",
            borderRadius: 33,
            height: "100%",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Notch */}
          <div
            style={{
              position: "absolute",
              top: 12,
              left: "50%",
              transform: "translateX(-50%)",
              width: 80,
              height: 20,
              background: "linear-gradient(145deg, #1a1a2e, #16213e)",
              borderRadius: 10,
              zIndex: 10,
            }}
          />

          {/* WhatsApp header bar */}
          <div
            style={{
              background: "#075e54",
              paddingTop: 32,
              paddingBottom: 10,
              paddingLeft: 12,
              paddingRight: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexShrink: 0,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "#128c7e",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                color: "white",
                flexShrink: 0,
              }}
            >
              C
            </div>
            <div>
              <p style={{ color: "white", fontSize: 13, fontWeight: 600, lineHeight: 1.2 }}>Contato</p>
              <p style={{ color: "rgba(255,255,255,0.7)", fontSize: 10, lineHeight: 1.2 }}>online</p>
            </div>
          </div>

          {/* Chat area */}
          <div
            className="wa-chat-scroll"
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "10px 8px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-start",
            }}
          >
            {/* Message bubble */}
            <div style={{ alignSelf: "flex-end", maxWidth: "88%" }}>
              <div
                style={{
                  background: "#dcf8c6",
                  borderRadius: "12px 12px 2px 12px",
                  overflow: "hidden",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
                  minWidth: 120,
                }}
              >
                {/* Media header placeholder */}
                {isMediaHeader && (
                  <div
                    style={{
                      background: headerType === "IMAGE"
                        ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
                        : headerType === "VIDEO"
                        ? "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
                        : "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
                      height: 80,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    <span style={{ fontSize: 24 }}>
                      {headerType === "IMAGE" ? "🖼️" : headerType === "VIDEO" ? "🎬" : "📄"}
                    </span>
                    <span style={{ color: "white", fontSize: 9, opacity: 0.9 }}>
                      {headerType === "IMAGE" ? "Imagem" : headerType === "VIDEO" ? "Vídeo" : "Documento"}
                    </span>
                  </div>
                )}

                <div style={{ padding: "8px 10px 4px" }}>
                  {/* Text header */}
                  {hasHeader && (
                    <p
                      style={{ fontWeight: 700, fontSize: 12, color: "#1a1a1a", marginBottom: 4, lineHeight: 1.4 }}
                      dangerouslySetInnerHTML={{
                        __html: renderWithVars(header || "", headerExample ? [headerExample] : []),
                      }}
                    />
                  )}

                  {/* Body */}
                  <p
                    style={{ fontSize: 12, color: "#303030", lineHeight: 1.5, wordBreak: "break-word" }}
                    dangerouslySetInnerHTML={{ __html: renderWithVars(body, bodyExamples) }}
                  />

                  {/* Footer */}
                  {footer && (
                    <p style={{ fontSize: 10, color: "#8696a0", marginTop: 4, lineHeight: 1.3 }}>{footer}</p>
                  )}

                  <p style={{ fontSize: 9, color: "#8696a0", textAlign: "right", marginTop: 4 }}>
                    agora ✓✓
                  </p>
                </div>

                {/* Buttons */}
                {buttons.length > 0 && (
                  <div style={{ borderTop: "1px solid rgba(0,0,0,0.08)" }}>
                    {buttons.map((btn, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "7px 10px",
                          textAlign: "center",
                          borderTop: i > 0 ? "1px solid rgba(0,0,0,0.06)" : undefined,
                          color: "#0a7cff",
                          fontSize: 12,
                          fontWeight: 500,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 4,
                        }}
                      >
                        {btn.type === "URL" && <span style={{ fontSize: 10 }}>🔗</span>}
                        {btn.type === "PHONE_NUMBER" && <span style={{ fontSize: 10 }}>📞</span>}
                        {btn.text || `Botão ${i + 1}`}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Input bar */}
          <div
            style={{
              background: "#f0f0f0",
              padding: "8px 10px",
              display: "flex",
              alignItems: "center",
              gap: 6,
              flexShrink: 0,
            }}
          >
            <div
              style={{
                flex: 1,
                background: "white",
                borderRadius: 20,
                padding: "6px 12px",
                fontSize: 11,
                color: "#aaa",
              }}
            >
              Mensagem
            </div>
            <div
              style={{
                width: 32,
                height: 32,
                background: "#075e54",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <span style={{ color: "white", fontSize: 14 }}>➤</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
