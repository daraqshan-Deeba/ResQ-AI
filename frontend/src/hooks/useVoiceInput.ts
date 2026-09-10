"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiUpload } from "@/lib/api";

type VoiceStatus = "idle" | "recording" | "transcribing" | "error";

interface TranscriptionResponse {
  text: string;
}

const MAX_RECORD_MS = 60_000;

export function useVoiceInput(
  onTranscript: (text: string) => void,
  language: string = "English",
) {
  const [supported, setSupported] = useState(false);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const stopTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        typeof MediaRecorder !== "undefined",
    );
  }, []);

  const cleanupStream = useCallback(() => {
    if (stopTimerRef.current) {
      window.clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const transcribeBlob = useCallback(
    async (blob: Blob) => {
      setStatus("transcribing");
      setError(null);

      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");
      formData.append("language", language);

      const res = await apiUpload<TranscriptionResponse>("/api/transcribe", formData);
      if (!res.ok) {
        setStatus("error");
        setError(res.error);
        return;
      }

      const text = res.data.text?.trim();
      if (text) onTranscript(text);
      setStatus("idle");
    },
    [language, onTranscript],
  );

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
  }, []);

  const startRecording = useCallback(async () => {
    if (!supported || status === "recording" || status === "transcribing") return;

    setError(null);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onerror = () => {
        setStatus("error");
        setError("Recording failed. Check microphone permissions.");
        cleanupStream();
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        cleanupStream();
        if (blob.size === 0) {
          setStatus("error");
          setError("No audio captured. Try again.");
          return;
        }
        await transcribeBlob(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setStatus("recording");

      stopTimerRef.current = window.setTimeout(() => {
        stopRecording();
      }, MAX_RECORD_MS);
    } catch {
      cleanupStream();
      setStatus("error");
      setError("Microphone access denied or unavailable.");
    }
  }, [cleanupStream, status, stopRecording, supported, transcribeBlob]);

  const toggle = useCallback(() => {
    if (status === "recording") {
      stopRecording();
      return;
    }
    if (status === "idle" || status === "error") {
      startRecording();
    }
  }, [startRecording, status, stopRecording]);

  useEffect(() => () => cleanupStream(), [cleanupStream]);

  return {
    supported,
    listening: status === "recording",
    transcribing: status === "transcribing",
    status,
    error,
    toggle,
  };
}
