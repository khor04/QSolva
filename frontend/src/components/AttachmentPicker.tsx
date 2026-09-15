import { useEffect, useRef, useState } from "react";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
}

export function AttachmentPicker({ files, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviewUrls(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  useEffect(() => {
    function handlePaste(e: ClipboardEvent) {
      const images = Array.from(e.clipboardData?.items ?? [])
        .filter((item) => item.type.startsWith("image/"))
        .map((item) => item.getAsFile())
        .filter((f): f is File => f !== null);

      if (images.length > 0) {
        e.preventDefault();
        onChange([...files, ...images]);
      }
    }

    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, [files, onChange]);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length > 0) onChange([...files, ...selected]);
    e.target.value = "";
  }

  function removeFile(index: number) {
    onChange(files.filter((_, i) => i !== index));
  }

  return (
    <div>
      <div className="rounded-md border border-dashed border-border-warm bg-cream p-4 text-center text-sm text-neutral-500">
        <p>
          Paste a screenshot (<kbd className="rounded border border-border-warm bg-white px-1">Ctrl</kbd>+
          <kbd className="rounded border border-border-warm bg-white px-1">V</kbd>) anywhere on this page, or{" "}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="font-medium text-primary-dark underline"
          >
            upload a file
          </button>
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {files.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3">
          {files.map((file, i) => (
            <div key={i} className="relative">
              <img
                src={previewUrls[i]}
                alt={file.name}
                className="h-20 w-20 rounded-md border border-border-warm object-cover"
              />
              <button
                type="button"
                onClick={() => removeFile(i)}
                aria-label="Remove attachment"
                className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-xs text-white"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
