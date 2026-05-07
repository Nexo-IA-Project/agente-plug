interface Props {
  body: string;
  header?: string;
  footer?: string;
}

export function TemplatePreview({ body, header, footer }: Props) {
  const highlighted = body.replace(/\{\{(\d+)\}\}/g, (_: string, n: string) => `[variável ${n}]`);

  return (
    <div className="rounded-2xl bg-[#075e54] p-3">
      <div className="rounded-xl bg-white px-3 py-2 shadow-sm">
        {header && (
          <p className="mb-1 text-xs font-semibold text-gray-900">{header}</p>
        )}
        <p className="whitespace-pre-wrap text-sm text-gray-800">{highlighted}</p>
        {footer && (
          <p className="mt-1 text-xs text-gray-400">{footer}</p>
        )}
        <p className="mt-1 text-right text-xs text-gray-400">agora ✓✓</p>
      </div>
    </div>
  );
}
