# Blend AI — conteúdo dos slides (fonte editável)
#
# Edite os TEXTOS aqui e rode:   python scripts/gera_slides.py
# Isso reescreve docs/apresentacao-blend-ai.html mantendo o visual do deck.
#
# Marcação simples dentro dos textos:
#   **negrito**          -> negrito
#   [palavra](brand)     -> destaque colorido (brand, bad, ok, brand-deep, drums, other, vocal, ink-soft...)
#   //                   -> quebra de linha
# Listas: um campo terminado em ":" seguido de linhas "- ...".
# Colunas dentro de um item de lista são separadas por "|" (a ordem importa — ver comentário de cada lista).
# Linhas começando com "#" são comentários e são ignoradas.


## slide 1
kicker: PAV · Processamento de Áudio e Voz · UFG · Trabalho final
lead: Mashups automáticos guiados por **compatibilidade** e **estrutura musical** — o vocal de uma faixa sobre o instrumental de outra, casando tempo, tom e o encaixe da música.


## slide 2
kicker: Motivação
titulo: Todo mundo já ouviu // um [mashup](brand)
lead: Pegar o **vocal** de uma música e tocá-lo sobre o **instrumental** de outra. DJs fazem isso na mão — e, pra soar bem, três coisas precisam casar:
# itens:  cor-do-ponto | rótulo | resto da frase
itens:
- drums | Tempo | — as batidas (BPM) andando juntas
- other | Tom | — a harmonia combinando
- brand | Estrutura | — o break batendo junto, o drop caindo junto
labelA: faixa A · vocal
labelB: faixa B · base
fechamento: **E se o computador pudesse propor esse encaixe — sozinho?**


## slide 3
kicker: A pergunta científica
titulo: Não basta casar // BPM e tom
lead: O jeito **ingênuo** — só alinhar tempo, tom e o primeiro tempo — costuma jogar o vocal numa parte vazia da música, e as frases não batem com o ponto alto.
hipotese_label: Nossa hipótese central · H1
hipotese: Alinhar pela **[estrutura musical](brand)** — casar as seções das duas faixas — produz mashups percebidos como **[mais musicais](brand)** do que o alinhamento ingênuo.
fechamento: É uma **pergunta testável** — não só "fazer um app". É o que dá rigor ao trabalho.


## slide 4
kicker: O motor de áudio
titulo: Da faixa crua ao mashup, em etapas
grupo_analise: Análise — blocos consolidados na literatura
# nodes_analise:  título | sublinha | ferramenta   (use // para quebrar o título)
nodes_analise:
- Separação | vocal · base | Demucs
- Beat & // downbeat | | allin1
- Tom → // Camelot | | Essentia
- Seções | intro·refrão·drop | allin1
grupo_contrib: ★ Nossa contribuição
# nodes_contrib:  título (use // para quebrar)
nodes_contrib:
- Score de // compatibilidade
- Alinhamento // estrutura-aware
grupo_sintese: Síntese
# node_sintese:  título | sublinha | ferramenta
node_sintese: Mix | stretch · pitch | Rubber Band
fechamento: Reaproveitamos os blocos já resolvidos pela literatura. **O método novo está no ★** — prever compatibilidade e casar as estruturas.


## slide 5
kicker: Três ideias de áudio
titulo: Três conceitos que sustentam tudo
# conceitos:  título | texto    (os ícones são fixos: barras de stem, grade de beats, roda Camelot)
conceitos:
- Separação de fontes | Isolar vocal, bateria, baixo e harmonia de uma música **já mixada**. Sem isso, não dá pra pegar só o vocal.
- Downbeat & compasso | O **["1"](brand)** de cada compasso — onde uma frase começa. Casar downbeats é casar o **esqueleto rítmico**.
- Roda Camelot | Tons num relógio: [vizinhos combinam](brand). Ferramenta clássica de DJ — vira um número de "distância harmônica".


## slide 6
kicker: ★ Contribuição central
titulo: Break com break, drop com drop
lead: O alinhamento ingênuo só casa o primeiro tempo. A gente casa as **seções das duas faixas**: [break com break](brand), [drop com drop](brand) — o vocal cai onde a base também explode.
trackA: A · vocal
trackB: B · base
baseline_tag: Baseline · ingênuo
baseline_caption: Só o downbeat 0 coincide. Cada faixa tem seu próprio comprimento, então o [drop do vocal cai no vazio da base](bad) — a energia fura.
proposto_tag: Proposto · estrutura-aware
proposto_caption: Deslocamos a base para as seções se encaixarem: [break com break, drop com drop](brand-deep). As duas faixas explodem juntas.
guide_break: break ↔ break
guide_drop: drop ↔ drop


## slide 7
kicker: O que vamos testar
titulo: Três hipóteses, três testes
# hipoteses:  rótulo | destaque (negrito) | resto | chip | cor-do-ponto
hipoteses:
- H1 | Estrutura-aware soa mais musical | que o alinhamento ingênuo. | painel às cegas · **Wilcoxon** | brand
- H2 | O score de compatibilidade prevê a qualidade percebida | (Camelot + razão de BPM + energia). | correlação · **Spearman** | other
- H3 | Vocais falados toleram mais distância de tom | — às vezes dispensam transposição (estilo do funk). | casos de salto alto | drums
fechamento: Avaliação **às cegas**, escala Likert 1–5. É o que separa **ciência** de "achismo".


## slide 8
kicker: Prova de conceito
titulo: O motor já roda ponta-a-ponta
# itens:  título | texto    (símbolos fixos por ordem: ✓ ◧ ♪)
itens:
- Pipeline completo na GPU | mashups reais gerados e aprovados de ouvido.
- Matriz de compatibilidade · dados reais | 12 faixas, 66 pares (Rekordbox). O score separa pares bons dos ruins — base da H2.
- Exemplo gerado | vocal Tatsch · Tension sobre a base Broken Hill · Zero Tolerance.
callout: tocar Tatsch · Tension sobre a base Broken Hill · Zero Tolerance.
barras_label: Score de compatibilidade · amostra
# barras:  rótulo | valor (0 a 1)
barras_top:
- Swag × Get Naughty | 1.00
- All We Got × Hands Up | 1.00
- Stop Talking × Swag | 0.96
barras_low:
- Trust Me × Swag | 0.37
- Zero Tol. × Bad Wolf | 0.22
barras_nota: Mesmo tom + mesmo BPM → topo; salto harmônico + BPM distante → fundo.


## slide 9
kicker: O que aprendemos
titulo: Dois achados que mudaram o rumo
card1_tag: H3 na prática
card1_titulo: O vocal falado caiu bem [sem transposição](brand)
card1_texto: Vocal **falado** (declamado) é mais fala ritmada que melodia — carrega pouca informação de altura. Mesmo com tom distante, forçar o pitch-shift só [adicionava artefato](bad). Deixar no tom natural soou melhor.
card2_tag: Limite do 100% automático
card2_titulo: O caminho não é tirar o humano — é ["IA sugere, DJ ancora"](brand)
card2_texto: Em vocal esparso, a máquina erra o recorte. Próximo passo: **"Ver + ancorar na mão"** — ver a forma de onda e a estrutura das duas faixas e ajustar o encaixe na tela.


## slide 10
kicker: Fechamento
titulo: Para onde vai
lead: **Blend AI** = mashup automático cujo diferencial é alinhar pela **estrutura musical**, com um **score** que prevê compatibilidade.
# cards:  rótulo | título | sublinha
cards:
- Próximo passo | Interface "Ver + ancorar na mão" | waveform + estrutura das 2 faixas na tela
- Avaliação | Coletar o experimento subjetivo | Wilcoxon / Spearman · infra congelada
- Visão | Motor de análise reaproveitável | biblioteca · stems · samples
assinatura: Obrigado.
assinatura_sub: Perguntas?
