"use client";

import { useEffect, useRef } from "react";

interface WaveformProps {
  /** 0–1 audio level */
  level: number;
  /** Whether audio is active */
  active: boolean;
  /** Color for the bars */
  color?: string;
}

/**
 * Animated waveform visualizer.
 * Renders a bar-based waveform that responds to mic audio level.
 */
export function Waveform({ level, active, color = "#22d3ee" }: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const barsRef = useRef<number[]>([]);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const NUM_BARS = 32;
    const BAR_WIDTH = 3;
    const GAP = 2;

    // Initialize bars
    if (barsRef.current.length === 0) {
      barsRef.current = Array.from({ length: NUM_BARS }, () => 0.05);
    }

    const draw = () => {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const bars = barsRef.current;
      const totalWidth = NUM_BARS * (BAR_WIDTH + GAP) - GAP;
      const startX = (W - totalWidth) / 2;

      bars.forEach((h, i) => {
        const barH = Math.max(4, h * H * 0.85);
        const x = startX + i * (BAR_WIDTH + GAP);
        const y = (H - barH) / 2;

        const alpha = active ? 0.9 : 0.3;
        ctx.fillStyle = color;
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.roundRect(x, y, BAR_WIDTH, barH, 1.5);
        ctx.fill();
      });

      ctx.globalAlpha = 1;
      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [active, color]);

  // Update bars based on audio level
  useEffect(() => {
    const NUM_BARS = 32;
    if (barsRef.current.length === 0) {
      barsRef.current = Array.from({ length: NUM_BARS }, () => 0.05);
    }

    // Shift bars left and add new value on the right
    const noise = active ? (Math.random() * 0.15 * level) : 0;
    const newVal = active ? Math.max(0.05, level + noise) : 0.05 + Math.random() * 0.03;
    barsRef.current = [...barsRef.current.slice(1), newVal];
  }, [level, active]);

  return (
    <canvas
      ref={canvasRef}
      width={240}
      height={60}
      className="w-full max-w-xs"
      aria-hidden="true"
    />
  );
}
