import { useRef, useState, type ReactNode } from "react";
import { ROTULO_ETAPA_CURTO, type EstadoAnalise, type Segmento } from "../lib/api";
import type { RegionSpec } from "../lib/wavesurfer";
import { Waveform } from "./Waveform";

interface DeckProps {
  letra: "A" | "B";
  papel: string; // "vocal" | "base"
  descricao: string;
  cor: string; // classe tailwind da cor de assinatura do deck
  arquivo: File | null;
  onArquivo: (f: File | null) => void;
  desabilitado?: boolean;
  /** análise prévia (modo manual): chips de bpm/tom/seções + progresso. */
  analise?: EstadoAnalise;
  /** âncora/janela do vocal desenhada sobre a onda. */
  regioes?: RegionSpec[];
  /** estrutura musical — tira sólida de seções abaixo da onda. */
  secoes?: Segmento[];
  /** posição atual do player deste deck (p/ "marcar no cursor" da App). */
  onPosicao?: (t: number) => void;
  alturaOnda?: number;
  /** readout da âncora deste deck (injetado pela App no modo manual). */
  children?: ReactNode;
}

const ACEITOS = [".mp3", ".wav", ".flac"];

// cores do waveform por deck (onda clara + progresso na cor do stem)
const CORES_WAVE: Record<string, { onda: string; progresso: string }> = {
  "bg-vocal": { onda: "#a9c2f6", progresso: "#3b82f6" },
  "bg-other": { onda: "#8fd9bd", progresso: "#10b981" },
};

function ChipsAnalise({ analise }: { analise: EstadoAnalise }) {
  if (analise.status === "rodando") {
    return (
      <p className="microlabel mt-2 flex items-center gap-1.5 !text-brand">
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
        analisando · {ROTULO_ETAPA_CURTO[analise.etapa ?? ""] ?? analise.etapa}
      </p>
    );
  }
  if (analise.status === "erro") {
    return (
      <p className="microlabel mt-2 !normal-case !text-bad" title={analise.erro}>
        análise falhou — {analise.erro?.slice(0, 60)}
      </p>
    );
  }
  if (analise.status === "pronta" && analise.dados) {
    const d = analise.dados;
    return (
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {[
          `${d.bpm.toFixed(1)} bpm`,
          d.key_camelot ?? "tom ?",
          `${d.segments.length} seções`,
          ...(d.cache ? ["cache"] : []),
        ].map((chip) => (
          <span
            key={chip}
            className="microlabel rounded-full border border-line bg-surface px-2 py-0.5 !text-ink-soft"
          >
            {chip}
          </span>
        ))}
      </div>
    );
  }
  return null;
}

export function Deck({
  letra,
  papel,
  descricao,
  cor,
  arquivo,
  onArquivo,
  desabilitado,
  analise,
  regioes,
  secoes,
  onPosicao,
  alturaOnda = 56,
  children,
}: DeckProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);
  const wave = CORES_WAVE[cor] ?? { onda: "#c3c9d4", progresso: "#6d5ef6" };

  function aceitar(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    const ext = `.${f.name.split(".").pop()?.toLowerCase()}`;
    if (ACEITOS.includes(ext)) onArquivo(f);
  }

  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-white shadow-card transition-all ${
        arrastando ? "border-brand shadow-lift" : "border-line"
      } ${desabilitado ? "pointer-events-none opacity-60" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setArrastando(true);
      }}
      onDragLeave={() => setArrastando(false)}
      onDrop={(e) => {
        e.preventDefault();
        setArrastando(false);
        aceitar(e.dataTransfer.files);
      }}
    >
      {/* hairline de assinatura do deck */}
      <div className={`h-[3px] w-full ${cor}`} />

      <div className="p-5">
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-2.5">
            <span className="font-display text-lg font-bold">{letra}</span>
            <span className="microlabel !text-ink-soft">deck {papel}</span>
          </div>
          {arquivo && (
            <button
              type="button"
              onClick={() => onArquivo(null)}
              className="microlabel cursor-pointer !text-ink-faint transition-colors hover:!text-bad"
            >
              remover ✕
            </button>
          )}
        </div>

        <p className="mt-1 text-[13px] leading-snug text-ink-soft">{descricao}</p>

        {arquivo ? (
          <div className="mt-4">
            {/* a faixa inteira, na hora — sem ida ao backend */}
            <Waveform
              key={`${arquivo.name}-${arquivo.size}-${arquivo.lastModified}`}
              src={arquivo}
              waveColor={wave.onda}
              progressColor={wave.progresso}
              accent={wave.progresso}
              height={alturaOnda}
              regions={regioes}
              secoes={secoes}
              onPosicao={onPosicao}
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink">
                {arquivo.name}
              </span>
              <span className="microlabel shrink-0">
                {(arquivo.size / 1024 / 1024).toFixed(1)} MB
              </span>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="microlabel shrink-0 cursor-pointer border-l border-line pl-2 transition-colors hover:!text-brand"
              >
                trocar
              </button>
            </div>
            {analise && <ChipsAnalise analise={analise} />}
            {children}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mt-4 flex w-full cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-ink-faint/40 bg-surface/60 px-4 py-7 transition-colors hover:border-brand hover:bg-brand-soft/40"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5 text-ink-faint"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5" strokeLinecap="round" />
            </svg>
            <span className="text-[13px] font-medium text-ink-soft">
              solte o arquivo ou clique
            </span>
            <span className="microlabel">mp3 · wav · flac</span>
          </button>
        )}

        <input
          ref={inputRef}
          type="file"
          data-deck={letra}
          accept={ACEITOS.join(",")}
          className="hidden"
          onChange={(e) => aceitar(e.target.files)}
        />
      </div>
    </div>
  );
}
