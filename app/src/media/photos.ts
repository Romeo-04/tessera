import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import type { PhotoInput } from "../lib/api";
import { fitLongEdge } from "../lib/photoSize";

export const MAX_PHOTOS = 8;

/**
 * Downscale and re-encode one photo on the device before it is uploaded.
 * Re-encoding also drops EXIF - including GPS location - which a photo of a
 * medicine cabinet has no reason to carry off the phone.
 */
export async function prepare(uri: string, width: number, height: number, i: number): Promise<PhotoInput> {
  const ctx = ImageManipulator.manipulate(uri);
  const fit = fitLongEdge(width, height);
  if (fit) ctx.resize(fit);
  const ref = await ctx.renderAsync();
  const out = await ref.saveAsync({ compress: 0.7, format: SaveFormat.JPEG });
  // The size is shown on the "what crossed the network" panel; best effort only.
  let bytes: number | undefined;
  try {
    bytes = (await (await fetch(out.uri)).blob()).size;
  } catch {
    bytes = undefined;
  }
  return { uri: out.uri, name: `label-${i + 1}.jpg`, type: "image/jpeg", bytes };
}

/** The library picker: the fallback when there is no camera or it is not allowed. */
export async function pickPhotos(): Promise<PhotoInput[] | null> {
  const r = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"], allowsMultipleSelection: true, selectionLimit: MAX_PHOTOS, quality: 1,
  });
  if (r.canceled || !r.assets?.length) return null;
  return Promise.all(r.assets.slice(0, MAX_PHOTOS).map((a, i) => prepare(a.uri, a.width, a.height, i)));
}
