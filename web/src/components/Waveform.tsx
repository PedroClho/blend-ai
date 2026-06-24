import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/plugins/regions";
import { fmtTime, type RegionSpec } from "../lib/wavesurfer";

interface WaveformProps {
  /** File (deck, decodifica no navegador) ou URL (resultado). */
  src: File | string;
  waveColor?: string;
  progressColor?: string;
  /** cor do cursor e do botão tocar. */
  accent?: string;
  height?: number;
  /** seções/janela do vocal desenhadas sobre o waveform (só no resultado). */
  regions?: RegionSpec[];
  interact?: boolean;
}

/**
 * Waveform da faixa inteira (estilo Rekordbox) sobre wavesurfer v7: tocar/pausar,
 * clique-pra-buscar e regions opcionais. Decodifica o File no cliente — sem backend.
 */
export function Waveform({
  src,
  waveColor = "#c3c9d4",
  progressColor = "#6d5ef6",
  accent = "#6d5ef6",
  height = 56,
  regions,
  interact = true,
}: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const [pronto, setPronto] = useState(false);
  const [tocando, setTocando] = useState(false);
  const [dur, setDur] = useState(0);
  const [pos, setPos] = useState(0);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setPronto(false);
    setTocando(false);
    setPos(0);
    setDur(0);
    setFalhou(false);

    const temRegions = regions != null && regions.length > 0;
    const regionsPlugin = temRegions ? RegionsPlugin.create() : null;
    const ws = WaveSurfer.create({
      container: el,
      height,
      waveColor,
      progressColor,
      cursorColor: accent,
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      interact,
      dragToSeek: true,
      plugins: regionsPlugin ? [regionsPlugin] : [],
    });
    wsRef.current = ws;

    if (typeof src === "string") ws.load(src);
    else ws.loadBlob(src);

    const offs = [
      ws.on("ready", (d) => {
        setDur(d);
        setPronto(true);
        if (regionsPlugin && regions) {
          for (const r of regions) {
            const reg = regionsPlugin.addRegion({
              id: r.id,
              start: r.start,
              end: r.end,
              color: r.color,
              content: r.content,
              drag: false,
              resize: false,
            });
            if (r.outline && reg.element) {
              reg.element.style.outline = `2px solid ${r.outline}`;
              reg.element.style.outlineOffset = "-2px";
              reg.element.style.borderRadius = "3px";
            }
          }
        }
      }),
      ws.on("play", () => setTocando(true)),
      ws.on("pause", () => setTocando(false)),
      ws.on("finish", () => setTocando(false)),
      ws.on("timeupdate", (t) => setPos(t)),
      ws.on("error", () => setFalhou(true)),
    ];

    return () => {
      offs.forEach((off) => off());
      ws.destroy();
      wsRef.current = null;
    };
  }, [src, regions, waveColor, progressColor, accent, height, interact]);

  return (
    <div>
      <div className="relative" style={{ minHeight: height }}>
        <div ref={containerRef} />
        {!pronto && !falhou && (
          <div
            className="ws-skeleton absolute inset-0 rounded-md"
            style={{ height }}
            aria-hidden
          />
        )}
        {falhou && (
          <div
            className="absolute inset-0 flex items-center justify-center rounded-md border border-line bg-surface text-[12px] text-ink-faint"
            style={{ height }}
          >
            não foi possível ler o áudio
          </div>
        )}
      </div>

      <div className="mt-2 flex items-center gap-2.5">
        <button
          type="button"
          disabled={!pronto}
          onClick={() => wsRef.current?.playPause()}
          className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-opacity disabled:cursor-default disabled:opacity-40"
          style={{ background: accent }}
          aria-label={tocando ? "pausar" : "tocar"}
        >
          {tocando ? (
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="currentColor">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="currentColor">
              <path d="M8 5.5v13l11-6.5z" />
            </svg>
          )}
        </button>
        <span className="font-mono text-[11px] tabular-nums text-ink-faint">
          {fmtTime(pos)} <span className="opacity-50">/ {fmtTime(dur)}</span>
        </span>
      </div>
    </div>
  );
}
