"use client";

import { useRef, useState } from "react";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";

import { Modal } from "@/shared/components/Modal";
import { updateMyAvatar } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function centerSquareCrop(width: number, height: number): Crop {
  return centerCrop(
    makeAspectCrop({ unit: "%", width: 90 }, 1, width, height),
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
    (crop.x ?? 0) * scaleX,
    (crop.y ?? 0) * scaleY,
    (crop.width ?? 0) * scaleX,
    (crop.height ?? 0) * scaleY,
    0,
    0,
    outputSize,
    outputSize,
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

export function AvatarUploadModal({ open, onClose, onSaved }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const imgRef = useRef<HTMLImageElement>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Imagem muito grande (máx 5MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setSrc(reader.result as string);
    reader.readAsDataURL(file);
  }

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { width, height } = e.currentTarget;
    setCrop(centerSquareCrop(width, height));
  }

  async function onSave() {
    if (!imgRef.current || !completedCrop) return;
    setSaving(true);
    try {
      const base64 = await getCroppedJpegBase64(imgRef.current, completedCrop);
      await updateMyAvatar(base64);
      toast.success("Foto atualizada");
      onSaved();
      setSrc(null);
      onClose();
    } catch {
      toast.error("Falha ao salvar foto");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Atualizar foto de perfil" size="sm">
      {!src && (
        <div className="flex flex-col gap-3 p-2">
          <input type="file" accept="image/*" onChange={onFile} />
          <p className="text-sm text-on-surface-variant">
            Escolha uma imagem (até 5MB). Você poderá recortar antes de salvar.
          </p>
        </div>
      )}
      {src && (
        <div className="flex flex-col gap-3 p-2">
          <ReactCrop
            crop={crop}
            onChange={setCrop}
            onComplete={setCompletedCrop}
            aspect={1}
            circularCrop
            keepSelection
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img ref={imgRef} src={src} alt="" onLoad={onImageLoad} />
          </ReactCrop>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setSrc(null)}
              className="rounded bg-surface-container px-3 py-2 text-on-surface"
            >
              Cancelar
            </button>
            <button
              onClick={onSave}
              disabled={saving || !completedCrop}
              className="rounded bg-primary px-3 py-2 text-on-primary disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
