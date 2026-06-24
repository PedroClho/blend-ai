import { useCallback, useEffect, useRef, useState } from "react";
import { Deck } from "./components/Deck";
import { Header } from "./components/Header";
import { Processing } from "./components/Processing";
import { Result } from "./components/Result";
import { consultarJob, criarMashup, type JobInfo, type Modo } from "./lib/api";

export default function App() {
  const [faixaA, setFaixaA] = useState<File | null>(null);
  const [faixaB, setFaixaB] = useState<File | null>(null);
  const [modo, setModo] = useState<Modo>("proposto");
  const [job, setJob] = useState<JobInfo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const pararPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);
  useEffect(() => pararPolling, [pararPolling]);

  async function gerar() {
    if (!faixaA || !faixaB) return;
    setErro(null);
    try {
      const id = await criarMashup(faixaA, faixaB, modo);
      const info = await consultarJob(id);
      setJob(info);
      pollRef.current = window.setInterval(async () => {
        try {
          const atual = await consultarJob(id);
          setJob(atual);
          if (atual.status === "concluido" || atual.status === "erro") pararPolling();
        } catch {
          /* transitório de rede: tenta no próximo tick */
        }
      }, 1500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    }
  }

  function novo() {
    pararPolling();
    setJob(null);
    setErro(null);
  }

  const ocupado = job !== null && (job.status === "na_fila" || job.status === "processando");
  const pronto = job?.status === "concluido" && job.resultado;
  // hero encolhe assim que há faixa/decisão na tela — abre espaço pros waveforms
  const heroCompacto = !!(faixaA || faixaB || job);

  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-5xl px-6 pb-20">
        {/* hero — compacto assim que entra faixa/job */}
        <section className={`text-center ${heroCompacto ? "pb-5 pt-6" : "pb-8 pt-10 sm:pt-14"}`}>
          <p className="microlabel reveal !text-brand">
            pav · ufg — alinhamento estrutura-aware
          </p>
          <h1
            className={`reveal mx-auto mt-3 max-w-2xl font-display font-bold leading-[1.25] tracking-tight ${
              heroCompacto ? "text-[1.4rem] sm:text-2xl" : "text-[1.65rem] sm:text-4xl"
            }`}
            style={{ animationDelay: "0.06s" }}
          >
            O vocal de uma faixa.
            <br />
            <span className="text-brand">A estrutura</span> de outra.
          </h1>

          {!heroCompacto && (
            <>
              <p
                className="reveal mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-ink-soft"
                style={{ animationDelay: "0.12s" }}
              >
                O Blend AI separa os stems, detecta BPM, tom e as seções musicais — e
                encaixa o vocal na seção certa do instrumental, em fase com o groove.
              </p>

              {/* régua de beats — assinatura visual (4 compassos, downbeats marcados) */}
              <div
                className="reveal mx-auto mt-8 flex max-w-md items-end justify-between"
                style={{ animationDelay: "0.18s" }}
                aria-hidden
              >
                {Array.from({ length: 17 }).map((_, i) => (
                  <span
                    key={i}
                    className={
                      i % 4 === 0
                        ? "h-4 w-[2px] rounded-full bg-brand"
                        : "h-2 w-px rounded-full bg-ink-faint/50"
                    }
                  />
                ))}
              </div>
            </>
          )}
        </section>

        {pronto ? (
          <Result job={job} onNovo={novo} />
        ) : ocupado ? (
          <Processing job={job} />
        ) : (
          <>
            {/* decks */}
            <section
              className="reveal grid items-stretch gap-4 sm:grid-cols-[1fr_auto_1fr]"
              style={{ animationDelay: "0.18s" }}
            >
              <Deck
                letra="A"
                papel="vocal"
                descricao="De onde vem o vocal. O motor isola a voz e recorta a janela mais cantada."
                cor="bg-vocal"
                arquivo={faixaA}
                onArquivo={setFaixaA}
              />
              <div className="hidden flex-col items-center justify-center gap-1.5 sm:flex">
                <span className="flex h-11 w-11 items-center justify-center rounded-full border border-line bg-white font-display text-lg font-bold text-brand shadow-card">
                  ×
                </span>
                <span className="microlabel !text-[0.55rem]">blend</span>
              </div>
              <Deck
                letra="B"
                papel="base"
                descricao="De onde vem o instrumental. A estrutura dela guia onde o vocal entra."
                cor="bg-other"
                arquivo={faixaB}
                onArquivo={setFaixaB}
              />
            </section>

            {/* modo + gerar */}
            <section
              className="reveal mx-auto mt-6 max-w-xl"
              style={{ animationDelay: "0.24s" }}
            >
              <div className="flex items-center justify-center gap-1 rounded-lg border border-line bg-surface p-1">
                {(["proposto", "baseline"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setModo(m)}
                    className={`flex-1 cursor-pointer rounded-md px-4 py-2 text-[13px] font-medium transition-all ${
                      modo === m
                        ? "bg-white text-ink shadow-card"
                        : "text-ink-faint hover:text-ink-soft"
                    }`}
                  >
                    {m === "proposto" ? "Estrutura-aware" : "Baseline ingênuo"}
                    <span className="microlabel mt-0.5 block !text-[0.55rem]">
                      {m === "proposto" ? "seção + downbeat + frase" : "só bpm + tom + 1º downbeat"}
                    </span>
                  </button>
                ))}
              </div>

              <button
                type="button"
                disabled={!faixaA || !faixaB}
                onClick={gerar}
                className={`mt-4 w-full rounded-xl px-6 py-4 font-display text-[15px] font-bold tracking-tight text-white transition-all ${
                  faixaA && faixaB
                    ? "beat-pulse cursor-pointer bg-brand hover:bg-brand-deep"
                    : "cursor-not-allowed bg-ink-faint/50"
                }`}
              >
                {faixaA && faixaB ? "Gerar mashup" : "Carregue os dois decks"}
              </button>

              {erro && (
                <p className="mt-3 rounded-lg border border-bad/30 bg-bad/5 px-4 py-2.5 text-center text-[13px] text-bad">
                  {erro}
                </p>
              )}
            </section>
          </>
        )}

        {job?.status === "erro" && (
          <div className="reveal mt-6 rounded-xl border border-bad/30 bg-bad/5 p-5 text-center">
            <p className="text-[14px] font-medium text-bad">A geração falhou.</p>
            <p className="mt-1 font-mono text-[12px] text-ink-soft">{job.erro}</p>
            <button
              type="button"
              onClick={novo}
              className="mt-3 cursor-pointer rounded-lg border border-line bg-white px-4 py-2 text-[13px] font-medium"
            >
              Tentar de novo
            </button>
          </div>
        )}
      </main>

      <footer className="border-t border-line py-6">
        <p className="microlabel text-center">
          blend ai — trabalho final de processamento de áudio e voz · ufg ·{" "}
          demucs + allin1 + essentia + rubber band
        </p>
      </footer>
    </div>
  );
}
