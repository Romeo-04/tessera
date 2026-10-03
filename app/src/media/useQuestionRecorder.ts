import {
  RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder,
} from "expo-audio";
import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";
import { transcribe } from "../lib/api";

export type MicState =
  | { kind: "idle" }
  | { kind: "recording" }
  | { kind: "transcribing" }
  | { kind: "error"; message: string };

// A spoken question, not a dictation session: stop on its own after this long.
const MAX_MS = 45_000;

/**
 * Tap to start, tap to stop, and the words come back for the caller to show in
 * the text box. Nothing is asked automatically: the caregiver reads what was
 * heard, fixes it if needed, and then asks - so a mis-heard drug name is caught
 * by a person, not acted on.
 */
export function useQuestionRecorder(onText: (text: string) => void) {
  const recorder = useAudioRecorder(RecordingPresets.LOW_QUALITY);
  const [state, setState] = useState<MicState>({ kind: "idle" });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setState({ kind: "transcribing" });
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("no recording");
      const web = Platform.OS === "web";
      const r = await transcribe({ uri, name: web ? "question.webm" : "question.m4a", type: web ? "audio/webm" : "audio/mp4" });
      if (!r.ok) return setState({ kind: "error", message: `${r.reason} You can type the question instead.` });
      if (!r.value.text) return setState({ kind: "error", message: "Nothing clear was heard. Try again closer to the phone, or type it." });
      onText(r.value.text);
      setState({ kind: "idle" });
    } catch {
      setState({ kind: "error", message: "The recording did not work. You can type the question instead." });
    }
  }, [recorder, onText]);

  const start = useCallback(async () => {
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) {
      setState({ kind: "error", message: "Microphone access is off for Tessera. You can type the question instead." });
      return;
    }
    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setState({ kind: "recording" });
      timer.current = setTimeout(() => { void stop(); }, MAX_MS);
    } catch {
      setState({ kind: "error", message: "The microphone could not start. You can type the question instead." });
    }
  }, [recorder, stop]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const toggle = useCallback(() => {
    if (state.kind === "recording") void stop();
    else if (state.kind !== "transcribing") void start();
  }, [state.kind, start, stop]);

  return { state, toggle };
}
