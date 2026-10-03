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

// Speech, not music. The stock LOW_QUALITY preset records 3GP/AMR-NB on
// Android (8 kHz narrowband), which is poor input for transcription; this keeps
// AAC in an m4a container on every native platform, mono at 16 kHz.
const SPEECH = {
  ...RecordingPresets.HIGH_QUALITY,
  sampleRate: 16000,
  numberOfChannels: 1,
  bitRate: 32000,
};

/**
 * Tap to start, tap to stop, and the words come back for the caller to show in
 * the text box. Nothing is asked automatically: the caregiver reads what was
 * heard, fixes it if needed, and then asks - so a mis-heard drug name is caught
 * by a person, not acted on.
 */
export function useQuestionRecorder(onText: (text: string) => void, onSent?: () => void) {
  const recorder = useAudioRecorder(SPEECH);
  // Guards the permission prompt: a second tap while it is open must not start twice.
  const starting = useRef(false);
  const [state, setState] = useState<MicState>({ kind: "idle" });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setState({ kind: "transcribing" });
    try {
      await recorder.stop();
      // Release the recording session so playback and other apps behave normally.
      await setAudioModeAsync({ allowsRecording: false }).catch(() => undefined);
      const uri = recorder.uri;
      if (!uri) throw new Error("no recording");
      onSent?.();
      const web = Platform.OS === "web";
      const r = await transcribe({ uri, name: web ? "question.webm" : "question.m4a", type: web ? "audio/webm" : "audio/mp4" });
      if (!r.ok) return setState({ kind: "error", message: `${r.reason} You can type the question instead.` });
      if (!r.value.text) return setState({ kind: "error", message: "Nothing clear was heard. Try again closer to the phone, or type it." });
      onText(r.value.text);
      setState({ kind: "idle" });
    } catch {
      setState({ kind: "error", message: "The recording did not work. You can type the question instead." });
    }
  }, [recorder, onText, onSent]);

  const start = useCallback(async () => {
    if (starting.current) return;
    starting.current = true;
    const perm = await requestRecordingPermissionsAsync().finally(() => { starting.current = false; });
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
