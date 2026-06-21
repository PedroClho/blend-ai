Métodos adotados

O Blend AI gera mashups automáticos encaixando o vocal de uma faixa sobre o
instrumental de outra. A solução é um pipeline de processamento de áudio, não um
modelo único fim-a-fim:

1. Separação de fontes com Demucs v4, isolando vocal e instrumental.
2. Análise rítmica e estrutural com allin1: beat, downbeat e segmentação
   rotulada (intro, verso, refrão, drop).
3. Detecção de tom convertido para a notação Camelot, via Essentia (tom do
   Rekordbox usado como referência de validação).
4. Score de compatibilidade combinando distância harmônica (Camelot), razão de
   BPM e similaridade de energia/estrutura.
5. Alinhamento estrutura-aware: escolha da seção certa do instrumental e
   sincronização das frases vocais aos downbeats.
6. Síntese com time-stretch e pitch-shift (Rubber Band) e mixagem final.


Datasets

Para a demonstração e o experimento usamos tech house sobre tech house, com as 11
faixas já coletadas e BPM próximo (1 a 3 de diferença), o que isola o efeito da
estrutura e permite testar a hipótese principal de forma controlada.

Para validar objetivamente a etapa de análise usamos datasets de referência:
MUSDB18 (separação), GiantSteps (tom e tempo), Harmonix Set (downbeats e estrutura)
e GTZAN (gênero e tempo).

Treinamento e fine-tuning

Não haverá treinamento nem fine-tuning. Todos os modelos (Demucs, allin1, Essentia)
são usados pré-treinados, apenas em inferência.
