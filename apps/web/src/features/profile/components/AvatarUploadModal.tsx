"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";

import { updateMyAvatar } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function centerSquareCrop(width: number, height: number): Crop {
  return centerCrop(
    makeAspectCrop({ unit: "%", width: 88 }, 1, width, height),
    width,
    height,
  );
}

async function getCroppedJpegBase64(
  image: HTMLImageElement,
  crop: Crop,
  outputSize = 200,
): Promise<string> {
  const canvas = document.createElement("canvas");
  canvas.width = outputSize;
  canvas.height = outputSize;
  const ctx = canvas.getContext("2d")!;
  const scaleX = image.naturalWidth / image.width;
  const scaleY = image.naturalHeight / image.height;
  ctx.drawImage(
    image,
    (crop.x ?? 0) * scaleX, (crop.y ?? 0) * scaleY,
    (crop.width ?? 0) * scaleX, (crop.height ?? 0) * scaleY,
    0, 0, outputSize, outputSize,
  );
  return new Promise((resolve) => {
    canvas.toBlob(
      (blob) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve((reader.result as string).split(",")[1]);
        reader.readAsDataURL(blob!);
      },
      "image/jpeg",
      0.85,
    );
  });
}

/** Gera blob URL de preview circular para o crop selecionado */
async function getPreviewBlobUrl(
  image: HTMLImageElement,
  crop: Crop,
): Promise<string> {
  const size = 120;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const scaleX = image.naturalWidth / image.width;
  const scaleY = image.naturalHeight / image.height;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(
    image,
    (crop.x ?? 0) * scaleX, (crop.y ?? 0) * scaleY,
    (crop.width ?? 0) * scaleX, (crop.height ?? 0) * scaleY,
    0, 0, size, size,
  );
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(URL.createObjectURL(blob!)), "image/jpeg", 0.8);
  });
}

export function AvatarUploadModal({ open, onClose, onSaved }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const prevPreviewUrl = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  // ESC para fechar
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Resetar estado ao fechar
  function handleClose() {
    setSrc(null);
    setCrop(undefined);
    setCompletedCrop(undefined);
    if (prevPreviewUrl.current) URL.revokeObjectURL(prevPreviewUrl.current);
    prevPreviewUrl.current = null;
    setPreviewUrl(null);
    onClose();
  }

  function loadFile(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Imagem muito grande (máx 5MB)");
      return;
    }
    if (!file.type.startsWith("image/")) {
      toast.error("Selecione um arquivo de imagem");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setSrc(reader.result as string);
    reader.readAsDataURL(file);
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) loadFile(file);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) loadFile(file);
  }

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { width, height } = e.currentTarget;
    const initial = centerSquareCrop(width, height);
    setCrop(initial);
    setCompletedCrop(initial);
  }

  // Atualiza preview ao mover o crop
  const updatePreview = useCallback(async (c: Crop) => {
    if (!imgRef.current || !c.width || !c.height) return;
    const url = await getPreviewBlobUrl(imgRef.current, c);
    if (prevPreviewUrl.current) URL.revokeObjectURL(prevPreviewUrl.current);
    prevPreviewUrl.current = url;
    setPreviewUrl(url);
  }, []);

  async function onSave() {
    if (!imgRef.current || !completedCrop) return;
    setSaving(true);
    try {
      const base64 = await getCroppedJpegBase64(imgRef.current, completedCrop);
      await updateMyAvatar(base64);
      toast.success("Foto atualizada com sucesso");
      onSaved();
      handleClose();
    } catch {
      toast.error("Falha ao salvar a foto");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      {/* Card */}
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-outline-variant bg-white dark:bg-surface-container shadow-2xl"
        style={{ animation: "avatarModalIn 0.22s cubic-bezier(.22,1,.36,1) both" }}
      >
        <style>{`
          @keyframes avatarModalIn {
            from { opacity: 0; transform: scale(0.94) translateY(8px); }
            to   { opacity: 1; transform: scale(1) translateY(0); }
          }
        `}</style>

        {/* Header */}
        <div className="flex items-center justify-between border-b border-outline-variant/60 bg-surface-container-low px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-container">
              <span
                className="material-symbols-outlined text-on-primary-container"
                style={{ fontSize: "18px", fontVariationSettings: "'FILL' 1" }}
              >
                photo_camera
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-on-surface">Foto de perfil</p>
              <p className="text-xs text-on-surface-variant">
                {src ? "Ajuste o enquadramento circular" : "Selecione uma imagem"}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant transition hover:bg-surface-container hover:text-on-surface"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>close</span>
          </button>
        </div>

        {/* Body */}
        {!src ? (
          /* Drop zone */
          <div className="px-6 py-8">
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`flex cursor-pointer flex-col items-center gap-4 rounded-2xl border-2 border-dashed px-8 py-10 transition-all ${
                dragging
                  ? "border-primary bg-primary/5 scale-[1.01]"
                  : "border-outline-variant bg-surface-container-low hover:border-primary/50 hover:bg-primary/3"
              }`}
            >
              <div
                className={`flex h-16 w-16 items-center justify-center rounded-full transition-all ${
                  dragging ? "bg-primary text-on-primary scale-110" : "bg-primary-container text-on-primary-container"
                }`}
              >
                <span
                  className="material-symbols-outlined"
                  style={{ fontSize: "28px", fontVariationSettings: "'FILL' 1" }}
                >
                  {dragging ? "download" : "add_photo_alternate"}
                </span>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-on-surface">
                  {dragging ? "Solte aqui" : "Clique ou arraste uma imagem"}
                </p>
                <p className="mt-1 text-xs text-on-surface-variant">
                  PNG, JPG, WebP — até 5 MB
                </p>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={onFile}
            />
          </div>
        ) : (
          /* Crop + preview */
          <div className="flex flex-col gap-0">
            {/* Crop area */}
            <div className="flex items-center justify-center bg-black/90 px-4 py-4">
              <ReactCrop
                crop={crop}
                onChange={setCrop}
                onComplete={(c) => { setCompletedCrop(c); updatePreview(c); }}
                aspect={1}
                circularCrop
                keepSelection
                className="max-h-72 overflow-hidden rounded-xl"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={imgRef}
                  src={src}
                  alt=""
                  onLoad={onImageLoad}
                  className="max-h-72 w-auto"
                />
              </ReactCrop>
            </div>

            {/* Preview bar */}
            <div className="flex items-center gap-4 border-t border-outline-variant/60 bg-surface-container-low px-6 py-3">
              <span className="text-xs font-medium text-on-surface-variant">Preview:</span>
              {/* 48px */}
              <div className="h-12 w-12 overflow-hidden rounded-full border-2 border-outline-variant">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="h-full w-full bg-surface-container" />
                )}
              </div>
              {/* 32px */}
              <div className="h-8 w-8 overflow-hidden rounded-full border-2 border-outline-variant">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="h-full w-full bg-surface-container" />
                )}
              </div>
              {/* 24px */}
              <div className="h-6 w-6 overflow-hidden rounded-full border-2 border-outline-variant">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="h-full w-full bg-surface-container" />
                )}
              </div>
              <span className="ml-auto text-xs text-on-surface-variant">
                Como aparecerá no sistema
              </span>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-outline-variant/60 bg-surface-container-low/50 px-6 py-4">
          <button
            onClick={src ? () => { setSrc(null); setCrop(undefined); setCompletedCrop(undefined); } : handleClose}
            className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium text-on-surface-variant transition hover:bg-surface-container hover:text-on-surface"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
              {src ? "arrow_back" : "close"}
            </span>
            {src ? "Trocar imagem" : "Cancelar"}
          </button>

          {src && (
            <button
              onClick={onSave}
              disabled={saving || !completedCrop}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-on-primary shadow-sm transition hover:opacity-90 disabled:opacity-40"
            >
              {saving ? (
                <>
                  <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                    progress_activity
                  </span>
                  Salvando...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
                    check_circle
                  </span>
                  Aplicar foto
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
