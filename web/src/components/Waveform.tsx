import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/plugins/regions";
import type { Segmento } from "../lib/api";
import {
  corSecao,
  fmtTime,
  fundirSecoes,
  textoContraste,
  type RegionSpec,
} from "../lib/wavesurfer";

interface WaveformProps {
  /** File (deck, decodifica no navegador) ou URL (resultado). */
  src: File | string;
  waveColor?: string;
  progressColor?: string;
  /** cor do cursor e do botão tocar. */
  accent?: string;
  height?: number;
  /** janela/entrada do vocal desenhada sobre a onda. */
  regions?: RegionSpec[];
  /** estrutura musical (allin1) — tira sólida de seções abaixo da onda. */
  secoes?: Segmento[];
  interact?: boolean;
  /** posição atual do player (a cada timeupdate) — App usa no "marcar no cursor". */
  onPosicao?: (t: number) => void;
}

/** Tira de seções estilo "phrase bar" do Rekordbox: blocos sólidos + rótulo.
 * Mesma escala de tempo da onda (0..dur → 0..100% da mesma largura).
 * Clicar num ponto/seção NAVEGA o player até lá (audição, não âncora). */
function TiraSecoes({
  secoes,
  dur,
  onSeek,
}: {
  secoes: Segmento[];
  dur: number;
  onSeek: (t: number) => void;
}) {
  const blocos = fundirSecoes(secoes);
  return (
    <div
      className="relative mt-1 h-[18px] w-full cursor-pointer select-none overflow-hidden rounded-[4px] bg-surface"
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        onSeek(((e.clientX - r.left) / r.width) * dur);
      }}
    >
      {blocos.map((s, i) => {
        const larg = ((s.end - s.start) / dur) * 100;
        const cor = corSecao(s.label);
        return (
          <span
            key={`${s.label}-${i}`}
            className="absolute top-0 flex h-full items-center justify-center overflow-hidden"
            style={{
              left: `${(s.start / dur) * 100}%`,
              width: `${Math.max(larg, 0.4)}%`,
              background: cor,
              opacity: 0.92,
              borderRight: "1px solid rgba(255,255,255,0.85)",
            }}
            title={`${s.label} · ${fmtTime(s.start)}–${fmtTime(s.end)}`}
          >
            {larg > 7 && (
              <span
                className="truncate px-1 font-mono text-[8px] font-semibold uppercase tracking-wide"
                style={{ color: textoContraste(cor) }}
              >
                {s.label}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

function desenharRegions(plugin: RegionsPlugin, regions: RegionSpec[] | undefined) {
  plugin.clearRegions();
  if (!regions) return;
  for (const r of regions) {
    const reg = plugin.addRegion({
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

/**
 * Waveform da faixa inteira (estilo Rekordbox) sobre wavesurfer v7. Decodifica o
 * File no cliente — sem backend. Clique (onda ou tira de seções) NAVEGA e TOCA
 * (audição); âncoras são definidas fora, por campo/cursor. Regions e altura
 * sincronizam SEM recriar a instância (não re-decodifica a cada mudança).
 */
export function Waveform({
  src,
  waveColor = "#c3c9d4",
  progressColor = "#6d5ef6",
  accent = "#6d5ef6",
  height = 56,
  regions,
  secoes,
  interact = true,
  onPosicao,
}: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsPluginRef = useRef<RegionsPlugin | null>(null);
  const [pronto, setPronto] = useState(false);
  const [tocando, setTocando] = useState(false);
  const [dur, setDur] = useState(0);
  const [pos, setPos] = useState(0);
  const [falhou, setFalhou] = useState(false);

  // refs de valores mutáveis lidos pelos handlers — mantêm o efeito de criação
  // estável (regions/âncoras mudam com frequência; recriar = re-decodificar tudo)
  const regionsRef = useRef(regions);
  regionsRef.current = regions;
  const onPosicaoRef = useRef(onPosicao);
  onPosicaoRef.current = onPosicao;
  const heightRef = useRef(height);
  heightRef.current = height;

  function ouvirEm(t: number) {
    const ws = wsRef.current;
    if (!ws) return;
    ws.setTime(t);
    if (!ws.isPlaying()) ws.play();
  }

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setPronto(false);
    setTocando(false);
    setPos(0);
    setDur(0);
    setFalhou(false);

    const regionsPlugin = RegionsPlugin.create();
    regionsPluginRef.current = regionsPlugin;
    const ws = WaveSurfer.create({
      container: el,
      height: heightRef.current,
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
      plugins: [regionsPlugin],
    });
    wsRef.current = ws;

    if (typeof src === "string") ws.load(src);
    else ws.loadBlob(src);

    const offs = [
      ws.on("ready", (d) => {
        setDur(d);
        setPronto(true);
        desenharRegions(regionsPlugin, regionsRef.current);
      }),
      // clicar na onda busca (nativo) E começa a tocar — audição imediata
      ws.on("click", () => {
        if (!ws.isPlaying()) ws.play();
      }),
      ws.on("play", () => setTocando(true)),
      ws.on("pause", () => setTocando(false)),
      ws.on("finish", () => setTocando(false)),
      ws.on("timeupdate", (t) => {
        setPos(t);
        onPosicaoRef.current?.(t);
      }),
      ws.on("error", () => setFalhou(true)),
    ];

    return () => {
      offs.forEach((off) => off());
      ws.destroy();
      wsRef.current = null;
      regionsPluginRef.current = null;
    };
  }, [src, waveColor, progressColor, accent, interact]);

  // regions mudaram (ex.: âncora nova) → redesenha sobre a instância viva
  useEffect(() => {
    const plugin = regionsPluginRef.current;
    if (plugin && pronto) desenharRegions(plugin, regions);
  }, [regions, pronto]);

  // altura muda entre modos (manual usa onda mais alta) sem recriar
  useEffect(() => {
    wsRef.current?.setOptions({ height });
  }, [height]);

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

      {secoes && secoes.length > 0 && dur > 0 && (
        <TiraSecoes secoes={secoes} dur={dur} onSeek={ouvirEm} />
      )}

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
