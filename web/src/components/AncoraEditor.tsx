import { useEffect, useState } from "react";
import { fmtTime } from "../lib/wavesurfer";

/** "m:ss(.d)", "mm:ss" ou segundos puros ("128", "128.5") → segundos; null se inválido. */
export function parseTempo(txt: string): number | null {
  const s = txt.trim().replace(",", ".");
  if (s === "") return null;
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  const m = /^(\d+):(\d{1,2}(\.\d+)?)$/.exec(s);
  if (m) return parseInt(m[1], 10) * 60 + parseFloat(m[2]);
  return null;
}

interface AncoraEditorProps {
  /** ex.: "vocal começa em" (deck A) / "vocal entra em" (deck B). */
  rotulo: string;
  /** âncora atual em segundos (já snapada); null = ainda não marcada. */
  valor: number | null;
  /** linha de leitura sob o campo (compasso/seção/duração). */
  info?: string | null;
  /** recebe o tempo digitado/capturado — a App aplica o snap no downbeat. */
  onDefinir: (t: number) => void;
  /** captura a posição atual do player do deck. */
  onCursor: () => void;
  /** desloca a âncora ±1 compasso (downbeat vizinho). */
  onNudge: (delta: 1 | -1) => void;
}

/**
 * Editor de âncora do modo manual: digite o tempo (ex.: "2:08" ou "128"),
 * ou toque a faixa e capture com "no cursor". A onda é só audição — clicar
 * nela navega e toca, nunca marca.
 */
export function AncoraEditor({
  rotulo,
  valor,
  info,
  onDefinir,
  onCursor,
  onNudge,
}: AncoraEditorProps) {
  const [draft, setDraft] = useState(valor != null ? fmtTime(valor) : "");
  useEffect(() => {
    setDraft(valor != null ? fmtTime(valor) : "");
  }, [valor]);

  function confirmar() {
    const t = parseTempo(draft);
    if (t != null) onDefinir(Math.max(0, t));
    else setDraft(valor != null ? fmtTime(valor) : ""); // inválido: volta ao atual
  }

  return (
    <div className="mt-2 rounded-md border border-line bg-surface/70 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="microlabel shrink-0">{rotulo}</span>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={confirmar}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          placeholder="2:08"
          className="w-[4.5rem] rounded border border-line bg-white px-1.5 py-0.5 text-center font-mono text-[12px] tabular-nums outline-none transition-colors focus:border-brand"
          aria-label={rotulo}
        />
        <button
          type="button"
          onClick={onCursor}
          title="usar a posição atual do player (snap no downbeat)"
          className="cursor-pointer rounded border border-line bg-white px-2 py-0.5 font-mono text-[11px] text-ink-soft transition-colors hover:border-brand hover:text-brand"
        >
          ⌖ no cursor
        </button>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => onNudge(-1)}
            disabled={valor == null}
            title="1 compasso antes"
            className="cursor-pointer rounded border border-line bg-white px-1.5 py-0.5 font-mono text-[11px] text-ink-soft transition-colors hover:border-brand hover:text-brand disabled:cursor-default disabled:opacity-40"
          >
            −1c
          </button>
          <button
            type="button"
            onClick={() => onNudge(1)}
            disabled={valor == null}
            title="1 compasso depois"
            className="cursor-pointer rounded border border-line bg-white px-1.5 py-0.5 font-mono text-[11px] text-ink-soft transition-colors hover:border-brand hover:text-brand disabled:cursor-default disabled:opacity-40"
          >
            +1c
          </button>
        </div>
      </div>
      {info && (
        <p className="mt-1.5 font-mono text-[11px] leading-relaxed text-ink-soft">{info}</p>
      )}
    </div>
  );
}
