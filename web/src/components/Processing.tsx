import { useEffect, useState } from "react";
import { ROTULO_ETAPA, type JobInfo } from "../lib/api";

const CORES_EQ = ["bg-vocal", "bg-drums", "bg-bass", "bg-other", "bg-brand"];

/** Visual de processamento: EQ animado em cores de stem + checklist de etapas. */
export function Processing({ job }: { job: JobInfo }) {
  const [segundos, setSegundos] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const idxAtual = job.etapas.indexOf(job.etapa);

  return (
    <div className="reveal rounded-xl border border-line bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <span className="microlabel !text-brand">gerando mashup</span>
        <span className="font-mono text-[12px] tabular-nums text-ink-soft">
          {String(Math.floor(segundos / 60)).padStart(2, "0")}:
          {String(segundos % 60).padStart(2, "0")}
        </span>
      </div>

      {/* EQ — barras nas cores dos stems */}
      <div className="mt-5 flex h-16 items-end justify-center gap-[5px]">
        {Array.from({ length: 24 }).map((_, i) => (
          <div
            key={i}
            className={`eq-bar w-[7px] rounded-t-sm ${CORES_EQ[i % CORES_EQ.length]}`}
            style={{
              height: `${30 + ((i * 37) % 65)}%`,
              animationDelay: `${(i % 8) * 0.09}s`,
              opacity: 0.85,
            }}
          />
        ))}
      </div>

      <ol className="mt-6 space-y-2">
        {job.etapas.map((etapa, i) => {
          const feita = idxAtual > i || job.status === "concluido";
          const ativa = idxAtual === i && job.status === "processando";
          return (
            <li key={etapa} className="flex items-center gap-3">
              <span
                className={`flex h-4 w-4 items-center justify-center rounded-full border text-[9px] ${
                  feita
                    ? "border-ok bg-ok text-white"
                    : ativa
                      ? "border-brand bg-brand-soft text-brand"
                      : "border-line bg-surface text-transparent"
                }`}
              >
                ✓
              </span>
              <span
                className={`relative overflow-hidden rounded px-1 text-[13px] ${
                  ativa ? "sweep font-medium text-ink" : feita ? "text-ink-soft" : "text-ink-faint"
                }`}
              >
                {ROTULO_ETAPA[etapa] ?? etapa}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="microlabel mt-5 text-center">
        ~1–2 min na GPU · {job.nome_a.slice(0, 32)} × {job.nome_b.slice(0, 32)}
      </p>
    </div>
  );
}
