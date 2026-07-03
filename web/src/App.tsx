import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AncoraEditor } from "./components/AncoraEditor";
import { Deck } from "./components/Deck";
import { Header } from "./components/Header";
import { Processing } from "./components/Processing";
import { Result } from "./components/Result";
import {
  consultarAnalise,
  consultarJob,
  criarAnalise,
  criarMashup,
  type EstadoAnalise,
  type JobInfo,
  type Modo,
} from "./lib/api";
import {
  bpmRatio,
  downbeatMaisProximo,
  downbeatVizinho,
  numeroDoCompasso,
  secaoEm,
  segundosDeCompassos,
} from "./lib/mashup";
import { corSecao, hexParaRgba, type RegionSpec } from "./lib/wavesurfer";

/** Estratégia de colocação do vocal: os dois braços do experimento + a mão do DJ. */
type Estrategia = Modo | "manual";

const ESTRATEGIAS: { id: Estrategia; titulo: string; sub: string }[] = [
  { id: "proposto", titulo: "Estrutura-aware", sub: "seção + downbeat + frase" },
  { id: "baseline", titulo: "Baseline ingênuo", sub: "bpm + tom + 1º downbeat" },
  { id: "manual", titulo: "Manual (DJ)", sub: "você ancora na waveform" },
];

const COR_VOCAL = "#3b82f6";

export default function App() {
  const [faixaA, setFaixaA] = useState<File | null>(null);
  const [faixaB, setFaixaB] = useState<File | null>(null);
  const [estrategia, setEstrategia] = useState<Estrategia>("proposto");
  const [transpor, setTranspor] = useState(true);
  const [job, setJob] = useState<JobInfo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  // modo manual: análise prévia por deck + âncoras (segundos, snap em downbeat)
  const [analises, setAnalises] = useState<{ A: EstadoAnalise; B: EstadoAnalise }>({
    A: { status: "nenhuma" },
    B: { status: "nenhuma" },
  });
  const [vocalIn, setVocalIn] = useState<number | null>(null);
  const [vocalOffset, setVocalOffset] = useState<number | null>(null);
  const [compassos, setCompassos] = useState(16);
  /** BPM final desejado (campo texto; vazio = manter o BPM da base). */
  const [bpmAlvo, setBpmAlvo] = useState("");
  /** posição atual do player de cada deck (p/ "marcar no cursor") — ref: sem re-render. */
  const posDecks = useRef<{ A: number; B: number }>({ A: 0, B: 0 });
  const pollAnalises = useRef<{ A: number | null; B: number | null }>({ A: null, B: null });
  // geração invalida polls/respostas de um arquivo que já foi trocado no deck
  const geracaoAnalise = useRef<{ A: number; B: number }>({ A: 0, B: 0 });

  const pararPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pararPollAnalise = useCallback((letra: "A" | "B") => {
    const t = pollAnalises.current[letra];
    if (t !== null) {
      clearInterval(t);
      pollAnalises.current[letra] = null;
    }
  }, []);

  useEffect(
    () => () => {
      pararPolling();
      pararPollAnalise("A");
      pararPollAnalise("B");
    },
    [pararPolling, pararPollAnalise],
  );

  const iniciarAnalise = useCallback(
    async (letra: "A" | "B", f: File) => {
      const g = ++geracaoAnalise.current[letra];
      const setEstado = (e: EstadoAnalise) => {
        if (geracaoAnalise.current[letra] !== g) return; // deck já trocou de faixa
        setAnalises((prev) => ({ ...prev, [letra]: e }));
      };
      setEstado({ status: "rodando", etapa: "na_fila" });
      try {
        const id = await criarAnalise(f);
        const tick = async () => {
          if (geracaoAnalise.current[letra] !== g) return;
          try {
            const info = await consultarAnalise(id);
            if (geracaoAnalise.current[letra] !== g) return;
            if (info.status === "concluido" && info.resultado) {
              pararPollAnalise(letra);
              setEstado({ status: "pronta", dados: info.resultado });
            } else if (info.status === "erro") {
              pararPollAnalise(letra);
              setEstado({ status: "erro", erro: info.erro ?? "falha na análise" });
            } else {
              setEstado({ status: "rodando", etapa: info.etapa || "na_fila" });
            }
          } catch {
            /* transitório de rede: tenta no próximo tick */
          }
        };
        pararPollAnalise(letra);
        pollAnalises.current[letra] = window.setInterval(tick, 1500);
        void tick();
      } catch (e) {
        setEstado({ status: "erro", erro: e instanceof Error ? e.message : String(e) });
      }
    },
    [pararPollAnalise],
  );

  // entrar no modo manual (ou trocar de faixa nele) dispara a análise que faltar
  useEffect(() => {
    if (estrategia !== "manual") return;
    if (faixaA && analises.A.status === "nenhuma") void iniciarAnalise("A", faixaA);
    if (faixaB && analises.B.status === "nenhuma") void iniciarAnalise("B", faixaB);
  }, [estrategia, faixaA, faixaB, analises.A.status, analises.B.status, iniciarAnalise]);

  function trocarFaixa(letra: "A" | "B", f: File | null) {
    geracaoAnalise.current[letra]++;
    pararPollAnalise(letra);
    setAnalises((prev) => ({ ...prev, [letra]: { status: "nenhuma" } }));
    if (letra === "A") {
      setFaixaA(f);
      setVocalIn(null);
    } else {
      setFaixaB(f);
      setVocalOffset(null);
    }
  }

  // ------- derivados do modo manual -------
  const manual = estrategia === "manual";
  const dadosA = analises.A.dados;
  const dadosB = analises.B.dados;
  const durJanelaA = dadosA ? segundosDeCompassos(dadosA.bpm, compassos) : null;
  const ratio = dadosA && dadosB ? bpmRatio(dadosB.bpm, dadosA.bpm) : 1;
  const durNaBase = durJanelaA != null ? durJanelaA / ratio : null;

  // sobre a onda só a janela/entrada do vocal — a estrutura vive na tira de
  // seções sólida (prop `secoes`), onde as cores não brigam com a cor da onda
  const regioesA = useMemo<RegionSpec[]>(() => {
    if (!(manual && dadosA && vocalIn != null && durJanelaA != null)) return [];
    return [
      {
        id: "janela-vocal",
        start: vocalIn,
        end: vocalIn + durJanelaA,
        color: hexParaRgba(COR_VOCAL, 0.18),
        content: "vocal",
        outline: COR_VOCAL,
      },
    ];
  }, [dadosA, manual, vocalIn, durJanelaA]);

  const regioesB = useMemo<RegionSpec[]>(() => {
    if (!(manual && dadosB && vocalOffset != null && durNaBase != null)) return [];
    return [
      {
        id: "entrada-vocal",
        start: vocalOffset,
        end: vocalOffset + durNaBase,
        color: hexParaRgba(COR_VOCAL, 0.18),
        content: "vocal A",
        outline: COR_VOCAL,
      },
    ];
  }, [dadosB, manual, vocalOffset, durNaBase]);

  // âncoras entram por campo de tempo / botão "no cursor" — sempre com snap
  // no downbeat. Clicar na onda/tira só navega e toca (audição).
  const definirVocalIn = (t: number) => {
    if (dadosA) setVocalIn(downbeatMaisProximo(dadosA.downbeats, t));
  };
  const definirVocalOffset = (t: number) => {
    if (dadosB) setVocalOffset(downbeatMaisProximo(dadosB.downbeats, t));
  };

  const rotulosSecoes = useMemo(
    () => [
      ...new Set(
        [...(dadosA?.segments ?? []), ...(dadosB?.segments ?? [])].map((s) => s.label),
      ),
    ],
    [dadosA, dadosB],
  );

  const analisesProntas = analises.A.status === "pronta" && analises.B.status === "pronta";
  const analiseFalhou = analises.A.status === "erro" || analises.B.status === "erro";
  const ancorasProntas = vocalIn != null && vocalOffset != null && durJanelaA != null;
  const podeGerar = !!faixaA && !!faixaB && (!manual || (analisesProntas && ancorasProntas));

  async function gerar() {
    if (!faixaA || !faixaB || !podeGerar) return;
    setErro(null);
    let bpmFinal: number | null = null;
    if (bpmAlvo.trim() !== "") {
      bpmFinal = Number(bpmAlvo.replace(",", "."));
      if (!isFinite(bpmFinal) || bpmFinal < 40 || bpmFinal > 220) {
        setErro("BPM final deve ser um número entre 40 e 220 (ou vazio p/ manter o da base).");
        return;
      }
    }
    try {
      const modoEnvio: Modo = manual ? "proposto" : (estrategia as Modo);
      const id = await criarMashup(faixaA, faixaB, modoEnvio, {
        transpor,
        bpmAlvo: bpmFinal,
        ancoras:
          manual && vocalIn != null && vocalOffset != null && durJanelaA != null
            ? { vocal_in: vocalIn, vocal_dur: durJanelaA, vocal_offset: vocalOffset }
            : null,
      });
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

  const rotuloGerar = !faixaA || !faixaB
    ? "Carregue os dois decks"
    : manual && analiseFalhou
      ? "Análise falhou — reanalise abaixo"
      : manual && !analisesProntas
        ? "Analisando as faixas…"
        : manual && !ancorasProntas
          ? "Marque as âncoras em A e B"
          : "Gerar mashup";

  const instrucaoManual = !faixaA || !faixaB
    ? "Carregue os dois decks para analisar a grade (downbeats + seções)."
    : !analisesProntas
      ? "Analisando as faixas na GPU (~1 min por faixa nova; instantâneo se já analisada)…"
      : vocalIn == null
        ? "1 de 2 — em A: toque a faixa (clique na onda/tira navega e toca), ache onde o vocal começa e use “no cursor”, ou digite o tempo."
        : vocalOffset == null
          ? "2 de 2 — em B: ache o ponto de entrada ouvindo e marque com “no cursor”, ou digite o tempo (ex.: 2:08)."
          : "Âncoras marcadas — ajuste pelo campo, “no cursor” ou ±1c, e gere o mashup. Tudo snapa no downbeat.";

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
                onArquivo={(f) => trocarFaixa("A", f)}
                analise={analises.A}
                regioes={regioesA}
                secoes={dadosA?.segments}
                onPosicao={(t) => {
                  posDecks.current.A = t;
                }}
                alturaOnda={manual ? 72 : 56}
              >
                {manual && dadosA && (
                  <AncoraEditor
                    rotulo="vocal começa em"
                    valor={vocalIn}
                    info={
                      vocalIn != null && durJanelaA != null
                        ? `compasso ${numeroDoCompasso(dadosA.downbeats, vocalIn)} · janela de ${compassos} compassos (~${durJanelaA.toFixed(0)}s)`
                        : "toque a faixa, ache o ponto e use “no cursor” — ou digite o tempo"
                    }
                    onDefinir={definirVocalIn}
                    onCursor={() => definirVocalIn(posDecks.current.A)}
                    onNudge={(d) => {
                      if (vocalIn != null && dadosA)
                        setVocalIn(downbeatVizinho(dadosA.downbeats, vocalIn, d));
                    }}
                  />
                )}
              </Deck>
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
                onArquivo={(f) => trocarFaixa("B", f)}
                analise={analises.B}
                regioes={regioesB}
                secoes={dadosB?.segments}
                onPosicao={(t) => {
                  posDecks.current.B = t;
                }}
                alturaOnda={manual ? 72 : 56}
              >
                {manual && dadosB && (
                  <AncoraEditor
                    rotulo="vocal entra em"
                    valor={vocalOffset}
                    info={
                      vocalOffset != null
                        ? `seção ${secaoEm(dadosB.segments, vocalOffset) ?? "?"}` +
                          (durNaBase != null
                            ? ` · ocupa ~${durNaBase.toFixed(0)}s (stretch ×${ratio.toFixed(3)})`
                            : "")
                        : "toque a faixa, ache o ponto e use “no cursor” — ou digite o tempo"
                    }
                    onDefinir={definirVocalOffset}
                    onCursor={() => definirVocalOffset(posDecks.current.B)}
                    onNudge={(d) => {
                      if (vocalOffset != null && dadosB)
                        setVocalOffset(downbeatVizinho(dadosB.downbeats, vocalOffset, d));
                    }}
                  />
                )}
              </Deck>
            </section>

            {/* estratégia + ancoragem + gerar */}
            <section
              className="reveal mx-auto mt-6 max-w-xl"
              style={{ animationDelay: "0.24s" }}
            >
              <div className="flex items-center justify-center gap-1 rounded-lg border border-line bg-surface p-1">
                {ESTRATEGIAS.map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    onClick={() => setEstrategia(e.id)}
                    className={`flex-1 cursor-pointer rounded-md px-2 py-2 text-[13px] font-medium transition-all ${
                      estrategia === e.id
                        ? "bg-white text-ink shadow-card"
                        : "text-ink-faint hover:text-ink-soft"
                    }`}
                  >
                    {e.titulo}
                    <span className="microlabel mt-0.5 block !text-[0.55rem]">{e.sub}</span>
                  </button>
                ))}
              </div>

              {/* painel do modo manual: instrução, tamanho da janela, legenda */}
              {manual && (
                <div className="mt-3 rounded-xl border border-line bg-white p-4 shadow-card">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="microlabel">ancoragem manual</span>
                    <span className="microlabel !text-[0.55rem] !text-ink-faint">
                      snap por compasso (downbeats do allin1)
                    </span>
                  </div>
                  <p className="mt-2 text-[13px] leading-snug text-ink-soft">{instrucaoManual}</p>

                  <div className="mt-3 flex items-center justify-between rounded-lg border border-line bg-surface px-3 py-2">
                    <span className="text-[13px] text-ink-soft">Janela do vocal (em A)</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setCompassos((c) => Math.max(4, c - 4))}
                        className="h-6 w-6 cursor-pointer rounded-md border border-line bg-white font-mono text-[13px] leading-none text-ink-soft hover:text-brand"
                        aria-label="menos compassos"
                      >
                        −
                      </button>
                      <span className="font-mono text-[12px] tabular-nums">
                        {compassos} compassos
                        {durJanelaA != null && (
                          <span className="text-ink-faint"> · ~{durJanelaA.toFixed(0)}s</span>
                        )}
                      </span>
                      <button
                        type="button"
                        onClick={() => setCompassos((c) => Math.min(64, c + 4))}
                        className="h-6 w-6 cursor-pointer rounded-md border border-line bg-white font-mono text-[13px] leading-none text-ink-soft hover:text-brand"
                        aria-label="mais compassos"
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {rotulosSecoes.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
                      {rotulosSecoes.map((rot) => (
                        <span key={rot} className="flex items-center gap-1.5">
                          <span
                            className="h-2 w-2 rounded-[3px]"
                            style={{ background: corSecao(rot), opacity: 0.55 }}
                          />
                          <span className="microlabel !text-[0.58rem]">{rot}</span>
                        </span>
                      ))}
                    </div>
                  )}

                  {analiseFalhou && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(["A", "B"] as const).map((l) => {
                        const f = l === "A" ? faixaA : faixaB;
                        return (
                          analises[l].status === "erro" &&
                          f && (
                            <button
                              key={l}
                              type="button"
                              onClick={() => void iniciarAnalise(l, f)}
                              className="cursor-pointer rounded-lg border border-bad/40 bg-bad/5 px-3 py-1.5 text-[12px] font-medium text-bad hover:bg-bad/10"
                            >
                              reanalisar deck {l}
                            </button>
                          )
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5">
                <span className="text-[13px] text-ink-soft">
                  BPM final
                  <span className="microlabel mt-0.5 block !text-[0.55rem]">
                    as duas faixas vão pro bpm escolhido antes do merge · vazio = bpm da base
                  </span>
                </span>
                <input
                  value={bpmAlvo}
                  onChange={(e) => setBpmAlvo(e.target.value)}
                  placeholder={dadosB ? dadosB.bpm.toFixed(0) : "auto"}
                  inputMode="decimal"
                  aria-label="BPM final do mashup"
                  className="w-20 shrink-0 rounded border border-line bg-white px-2 py-1 text-center font-mono text-[13px] tabular-nums outline-none transition-colors focus:border-brand"
                />
              </div>

              <label className="mt-3 flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5">
                <span className="text-[13px] text-ink-soft">
                  Transpor tom automaticamente
                  <span className="microlabel mt-0.5 block !text-[0.55rem]">
                    desligue p/ vocal declamado (funk) — tolera distância harmônica
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={transpor}
                  onChange={(e) => setTranspor(e.target.checked)}
                  className="h-4 w-4 shrink-0 cursor-pointer accent-brand"
                />
              </label>

              <button
                type="button"
                disabled={!podeGerar}
                onClick={gerar}
                className={`mt-4 w-full rounded-xl px-6 py-4 font-display text-[15px] font-bold tracking-tight text-white transition-all ${
                  podeGerar
                    ? "beat-pulse cursor-pointer bg-brand hover:bg-brand-deep"
                    : "cursor-not-allowed bg-ink-faint/50"
                }`}
              >
                {rotuloGerar}
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
