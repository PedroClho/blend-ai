import { useMemo } from "react";
import type { JobInfo, Resultado } from "../lib/api";
import { buildRegions, corSecao } from "../lib/wavesurfer";
import { Waveform } from "./Waveform";

function Leitura({
  rotulo,
  valor,
  unidade,
  destaque,
}: {
  rotulo: string;
  valor: string;
  unidade?: string;
  destaque?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3.5 py-3">
      <div className="microlabel">{rotulo}</div>
      <div
        className={`mt-1 font-mono text-xl font-semibold tabular-nums ${
          destaque ? "text-brand" : "text-ink"
        }`}
      >
        {valor}
        {unidade && (
          <span className="ml-1 text-[11px] font-normal text-ink-faint">{unidade}</span>
        )}
      </div>
    </div>
  );
}

export function Result({ job, onNovo }: { job: JobInfo; onNovo: () => void }) {
  const r = job.resultado as Resultado;
  const { score, plan } = r;
  const a = r.analise_vocal;
  const b = r.analise_base;

  // janela do vocal sobre a onda + seções na tira. Com BPM alvo a base foi
  // esticada: converte os tempos da análise (relógio original de B) p/ o mashup
  const regioes = useMemo(() => buildRegions(r), [r]);
  const baseRatio = plan.base_ratio || 1;
  const secoesMashup = useMemo(
    () =>
      (b?.segments ?? []).map((s) => ({
        ...s,
        start: s.start / baseRatio,
        end: s.end / baseRatio,
      })),
    [b, baseRatio],
  );
  const rotulos = useMemo(
    () => [...new Set((b?.segments ?? []).map((s) => s.label))],
    [b],
  );

  return (
    <div className="reveal space-y-5">
      {/* deck do mashup: waveform inteiro + estrutura por cima (a assinatura H1) */}
      <div className="rounded-xl border border-line bg-white p-6 shadow-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <span className="microlabel !text-brand">mashup pronto</span>
            <h2 className="mt-1 font-display text-base font-bold leading-snug">
              {job.nome_a.replace(/\.[^.]+$/, "")}
              <span className="mx-2 text-brand">×</span>
              {job.nome_b.replace(/\.[^.]+$/, "")}
            </h2>
          </div>
          <span className="microlabel rounded-full border border-line bg-surface px-2.5 py-1">
            modo {plan.mode}
          </span>
        </div>

        <div className="mt-4 mb-2 flex items-baseline justify-between">
          <span className="microlabel">estrutura da base × entrada do vocal</span>
          <span className="font-mono text-[11px] text-ink-faint">
            {plan.mode === "manual"
              ? `ancoragem manual · seção ${plan.secao.label}`
              : plan.nivel_fallback === 0
                ? `seção real: ${plan.secao.label}`
                : `fallback nível ${plan.nivel_fallback}`}
          </span>
        </div>

        <Waveform
          src={r.audio_url}
          regions={regioes}
          secoes={secoesMashup}
          waveColor="#b9bfca"
          progressColor="#6d5ef6"
          accent="#6d5ef6"
          height={80}
        />

        {/* legenda das seções */}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {rotulos.map((rot) => (
            <span key={rot} className="flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-[3px]"
                style={{ background: corSecao(rot), opacity: 0.55 }}
              />
              <span className="microlabel !text-[0.58rem]">{rot}</span>
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-[3px] border-2 border-vocal" />
            <span className="microlabel !text-[0.58rem]">vocal A</span>
          </span>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <a
            href={r.audio_url}
            download
            className="rounded-lg bg-brand px-4 py-2 text-[13px] font-semibold text-white shadow-card transition-colors hover:bg-brand-deep"
          >
            ⬇ Baixar .wav
          </a>
          <button
            type="button"
            onClick={onNovo}
            className="cursor-pointer rounded-lg border border-line bg-white px-4 py-2 text-[13px] font-medium text-ink-soft transition-colors hover:bg-surface"
          >
            Novo mashup
          </button>
        </div>
      </div>

      {/* leituras: compatibilidade + plano */}
      <div className="rounded-xl border border-line bg-white p-6 shadow-card">
        <div className="rule mb-4">
          <span className="microlabel">leituras do motor</span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Leitura rotulo="compatibilidade" valor={score.total.toFixed(2)} destaque />
          <Leitura rotulo="harmônico" valor={score.harmonico.toFixed(2)} />
          <Leitura rotulo="tempo" valor={score.tempo.toFixed(2)} />
          <Leitura rotulo="camelot dist" valor={String(score.camelot_dist)} unidade="passos" />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Leitura rotulo="stretch vocal" valor={`×${plan.bpm_ratio.toFixed(3)}`} />
          <Leitura
            rotulo="transposição"
            valor={`${plan.pitch_shift_semitones >= 0 ? "+" : ""}${plan.pitch_shift_semitones.toFixed(0)}`}
            unidade="st"
          />
          <Leitura
            rotulo="vocal entra em"
            valor={`${Math.floor(plan.vocal_offset / 60)}:${String(Math.round(plan.vocal_offset % 60)).padStart(2, "0")}`}
          />
          <Leitura
            rotulo="deck A · deck B"
            valor={`${a?.bpm.toFixed(0) ?? "—"}·${b?.bpm.toFixed(0) ?? "—"}`}
            unidade="bpm"
          />
        </div>

        {plan.bpm_alvo != null && (
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Leitura rotulo="bpm final" valor={plan.bpm_alvo.toFixed(0)} unidade="bpm" destaque />
            <Leitura rotulo="stretch base" valor={`×${plan.base_ratio.toFixed(3)}`} />
          </div>
        )}

        {(a?.key_camelot || b?.key_camelot) && (
          <p className="mt-3 font-mono text-[11px] text-ink-soft">
            tom A: <span className="text-ink">{a?.key_camelot ?? "?"}</span> · tom B:{" "}
            <span className="text-ink">{b?.key_camelot ?? "?"}</span>
            {plan.pitch_shift_semitones !== 0 &&
              ` → vocal transposto ${plan.pitch_shift_semitones > 0 ? "+" : ""}${plan.pitch_shift_semitones.toFixed(0)} st para compatibilizar`}
          </p>
        )}
      </div>
    </div>
  );
}
