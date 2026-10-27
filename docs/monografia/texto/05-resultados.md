# RESULTADOS

Este capítulo apresenta os resultados na ordem em que foram obtidos: o teste da simulação de referência, a análise por tipo de anomalia, a comparação com as regras, a sensibilidade e a robustez, o custo, a correção dos atributos relativos, a validação confirmatória, a ablação e o cenário com mudanças de rotina. Salvo indicação contrária, os valores estão em porcentagem, e os do *Isolation Forest* são a média das dez sementes do modelo.

## TESTE NA SIMULAÇÃO DE REFERÊNCIA

A @tab:teste e a @fig:comparacao mostram o desempenho dos quatro detectores na semana de teste da simulação de referência (semente 42), na versão corrigida da avaliação (v2).

Tabela: Desempenho no teste da simulação de referência {#tab:teste}

| Detector | Precisão | Recall | F1 | Falsos positivos | Cenários detectados | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| IF ajustado | 76,5 ± 3,7 | 61,7 ± 4,3 | 68,1 ± 2,0 | 65 | 75,5 ± 4,7 | 0,953 | 0,700 |
| IF sem rótulos | 69,2 ± 2,3 | 27,5 ± 2,1 | 39,3 ± 2,3 | 41 | 36,3 ± 3,6 | 0,918 | 0,507 |
| Regras | 96,7 | 68,5 | 80,2 | 8 | 73,1 | — | — |
| IF ∪ regras | 80,2 ± 3,8 | 79,3 ± 1,1 | 79,7 ± 1,3 | 67 | 86,2 ± 1,3 | — | — |

Fonte: elaborada pelo autor (2026).

Nota: média ± desvio-padrão nas dez sementes do modelo; as regras são determinísticas. Falsos positivos em número de janelas (média). A prevalência de janelas anômalas no teste é 7,2%, que é o PR-AUC de um detector aleatório.

![Desempenho dos detectores no teste da simulação de referência](figuras/comparacao_detectores.png){#fig:comparacao width=15}

Fonte: elaborada pelo autor (2026).

Nota: média ± desvio nas dez sementes do modelo; o rótulo sobre as barras é o F1.

O *Isolation Forest* ajustado na validação obteve F1 de 68,1%, com ROC-AUC de 0,953 e PR-AUC de 0,700, quase dez vezes a prevalência. As regras de especialista, escritas conhecendo os seis tipos de anomalia, tiveram F1 maior (80,2%), sustentado por uma precisão de 96,7%: geraram apenas oito falsos positivos em toda a semana de teste. A combinação IF ∪ regras teve F1 equivalente ao das regras (79,7%), com perfil diferente: precisão menor (80,2%) e recall bem maior (79,3% contra 68,5%), detectando 86,2% dos cenários, a maior cobertura entre os detectores.

O *Isolation Forest* sem rótulos, com os parâmetros padrão e o limiar no quantil de 99% do treino, ficou bem abaixo (F1 de 39,3%). A diferença não está na capacidade de ordenar as janelas, já que o ROC-AUC é alto (0,918), mas no limiar: sem rótulos, o modelo sinaliza poucas janelas e perde recall. A @fig:pr-roc mostra as curvas e o ponto de operação de cada detector.

![Curvas precisão–recall e ROC no teste](figuras/curvas_pr_roc.png){#fig:pr-roc width=15.5}

Fonte: elaborada pelo autor (2026).

Nota: semente 0 do modelo. Os pontos marcam o limiar usado por cada detector; as regras são um único ponto.

## RESULTADOS POR TIPO E INTENSIDADE

A @tab:tipos e a @fig:tipo-intensidade detalham a fração de cenários detectados por tipo e intensidade.

Tabela: Cenários detectados no teste, por tipo e intensidade {#tab:tipos}

| Tipo | Intensidade | Cenários | IF ajustado | Regras | IF ∪ regras |
|---|---|---:|---:|---:|---:|
| DML incomum | baixa | 8 | 61,3 | 37,5 | 62,5 |
| | média | 8 | 36,2 | 75,0 | 75,0 |
| | alta | 8 | 92,5 | 100,0 | 100,0 |
| falha de autenticação | baixa | 8 | 83,8 | 100,0 | 100,0 |
| | média | 8 | 65,0 | 100,0 | 100,0 |
| | alta | 8 | 83,8 | 100,0 | 100,0 |
| fora do horário | baixa | 8 | 91,2 | 87,5 | 98,8 |
| | média | 8 | 98,8 | 62,5 | 100,0 |
| | alta | 8 | 100,0 | 100,0 | 100,0 |
| rajada | baixa | 8 | 5,0 | 0,0 | 5,0 |
| | média | 8 | 82,5 | 25,0 | 87,5 |
| | alta | 8 | 87,5 | 62,5 | 87,5 |
| sem permissão | baixa | 8 | 53,8 | 100,0 | 100,0 |
| | média | 8 | 100,0 | 100,0 | 100,0 |
| | alta | 8 | 100,0 | 100,0 | 100,0 |
| volume alto | baixa | 8 | 55,0 | 50,0 | 71,2 |
| | média | 8 | 93,8 | 75,0 | 96,2 |
| | alta | 8 | 100,0 | 100,0 | 100,0 |
| leitura atípica (inédito) | baixa | 4 | 37,5 | 25,0 | 50,0 |
| | média | 4 | 40,0 | 25,0 | 50,0 |
| | alta | 4 | 87,5 | 50,0 | 92,5 |

Fonte: elaborada pelo autor (2026).

Nota: um cenário é detectado se ao menos uma das suas janelas gera alerta; média nas dez sementes do modelo.

![Cenários detectados no teste, por tipo e intensidade](figuras/deteccao_tipo_intensidade.png){#fig:tipo-intensidade width=15.5}

Fonte: elaborada pelo autor (2026).

O *Isolation Forest* detecta bem o que é volumoso ou foge da rotina: acessos fora do horário (91% a 100% dos cenários), rajadas médias e altas (82,5% a 87,5%), volume alto médio e alto (94% a 100%) e tentativas sem permissão médias e altas (100%). As intensidades baixas, desenhadas para ficar na faixa do ruído normal, são as mais difíceis; a rajada baixa, de três vezes a taxa normal, quase não é detectada por nenhum detector. As regras são imbatíveis nos tipos em que um único evento já é sinal forte, como falhas de autenticação e erros de permissão, que elas capturam com um limiar fixo sem custo.

No tipo inédito, o *Isolation Forest* detectou 37,5%, 40% e 87,5% dos cenários de intensidade baixa, média e alta, e a combinação chegou a 50% a 92,5%. A @fig:escores-tipo mostra a distribuição dos escores por tipo de cenário em relação ao limiar.

![Escores de anomalia das janelas de teste por tipo de cenário](figuras/scores_por_tipo.png){#fig:escores-tipo width=15}

Fonte: elaborada pelo autor (2026).

Nota: semente 0 do modelo. Caixas: quartis; bigodes: percentis 1 e 99; pontos: janelas anômalas; linha: limiar.

## ISOLATION FOREST E REGRAS

A @fig:if-regras classifica cada cenário de teste conforme quem o detectou: só o *Isolation Forest* (na maioria das sementes), só as regras, ambos ou nenhum.

![Cenários de teste detectados pelo Isolation Forest, pelas regras, por ambos ou por nenhum](figuras/cenarios_if_regras.png){#fig:if-regras width=15}

Fonte: elaborada pelo autor (2026).

Os cenários que só o *Isolation Forest* detecta concentram-se em rajadas (8), acessos fora do horário (4), volume alto (4) e no tipo inédito (4). Os que só as regras detectam concentram-se em falhas de autenticação (6), DML incomum (4) e erros de permissão (4). Os dois detectores erram e acertam em lugares diferentes, o que explica por que a combinação eleva o recall de 68,5% para 79,3% e os cenários detectados de 73,1% para 86,2%.

Parte da vantagem das regras vem de uma limitação do *Isolation Forest* discutida na Seção 2.4: os cortes das árvores ficam dentro da faixa de valores do treino. Uma janela com 300 comandos, quando o máximo do treino era 8, percorre as árvores como uma janela de 8 comandos, e o escore satura. As regras comparam diretamente com o máximo do usuário e não têm esse limite.

## SENSIBILIDADE E ROBUSTEZ

Na validação, o resultado se mostrou estável quanto ao número de árvores (100, 200 e 500 empatam dentro do desvio) e à fração de atributos por árvore (@fig:sensibilidade). Dois parâmetros importam: subamostras de 256 janelas reduzem o F1 de validação de 61,0% para 47,6%, e não aplicar a transformação logarítmica o reduz para 56,7%.

![F1 na validação variando um hiperparâmetro por vez](figuras/sensibilidade_hiperparametros.png){#fig:sensibilidade width=15.5}

Fonte: elaborada pelo autor (2026).

Nota: os demais hiperparâmetros ficam na configuração escolhida, em azul; média ± desvio nas cinco sementes de ajuste.

O tamanho da janela muda o perfil do detector (@fig:janela). Com janelas de 1 minuto, mais cenários são detectados na validação (82,0%, contra 70,2% com 5 minutos), com mais que o dobro de alertas (422 contra 191). Com 15 minutos, o F1 por janela é maior (68,8%), mas menos cenários são detectados (67,8%), com 106 alertas. O F1 não é comparável entre tamanhos, porque a unidade muda; os cenários detectados e o número de alertas mostram a troca entre cobertura e carga de trabalho. A janela de 5 minutos foi mantida como equilíbrio entre as duas.

![Efeito do tamanho da janela na validação](figuras/sensibilidade_janela.png){#fig:janela width=15.5}

Fonte: elaborada pelo autor (2026).

Nota: cada tamanho com a sua melhor configuração.

A robustez à semente da simulação foi medida reavaliando a configuração congelada em duas simulações novas (@fig:robustez). Nas três simulações, o F1 do *Isolation Forest* foi de 67,2 ± 1,6, e o das regras, de 78,8 ± 4,2; a combinação detectou 85,9 ± 4,3% dos cenários. O resultado do *Isolation Forest* depende pouco da simulação; o das regras varia mais.

![Robustez à semente da simulação](figuras/robustez_simulacoes.png){#fig:robustez width=15}

Fonte: elaborada pelo autor (2026).

Nota: cada ponto cinza é uma simulação (média das sementes do modelo); o ponto colorido e a barra são a média ± desvio entre elas.

## CUSTO COMPUTACIONAL

Quatro semanas de log, com 207.769 linhas de cliente, são processadas em cerca de 10 segundos (@tab:tempos e @fig:tempos).

Tabela: Tempo de cada etapa do SACLA sobre as quatro semanas da simulação de referência {#tab:tempos}

| Etapa | Tempo |
|---|---:|
| Leitura e eventos | 5,7 s |
| Agregação em janelas, com o histórico "deixando um dia de fora" | 3,5 s |
| Treino do modelo | 0,17 s |
| Escore da semana de teste | 0,04 s |
| Relatório com explicações | 0,6 s |

Fonte: elaborada pelo autor (2026).

![Tempo de cada etapa do SACLA](figuras/tempos_etapas.png){#fig:tempos width=14}

Fonte: elaborada pelo autor (2026).

O custo do SACLA é pequeno; o custo relevante é o do registro de log no servidor, discutido na Seção 4.2.

## CORREÇÃO DOS ATRIBUTOS RELATIVOS

Na primeira versão da avaliação (v1), os atributos relativos das janelas de treino eram calculados contra o histórico inteiro, que incluía a própria janela. As três frações de novidade valiam sempre zero no treino, e o *Isolation Forest* as ignorava: forçá-las a 1 em todas as janelas de teste não mudava nenhum escore (D41). O defeito foi encontrado por essa análise, sem olhar desempenho, e corrigido com o histórico "deixando um dia de fora" (Seção 4.4). Depois da correção, 83 janelas de treino passaram a ter IP inédito, 13 formato de consulta inédito e 2 tabela inédita, e forçar cada fração de novidade a 1 muda o escore em até 0,076. A @tab:v1v2 compara as duas versões.

Tabela: Primeira avaliação (v1) e avaliação corrigida (v2) no teste {#tab:v1v2}

| Detector | F1 v1 | F1 v2 | Cenários v1 | Cenários v2 | PR-AUC v1 → v2 |
|---|---:|---:|---:|---:|---:|
| IF ajustado | 63,8 ± 1,1 | 68,1 ± 2,0 | 69,8 ± 2,3 | 75,5 ± 4,7 | 0,644 → 0,700 |
| IF sem rótulos | 35,8 ± 2,7 | 39,3 ± 2,3 | 33,8 ± 3,3 | 36,3 ± 3,6 | 0,456 → 0,507 |
| Regras | 80,2 | 80,2 | 73,1 | 73,1 | — |
| IF ∪ regras | 79,2 ± 0,9 | 79,7 ± 1,3 | 84,7 ± 1,1 | 86,2 ± 1,3 | — |

Fonte: elaborada pelo autor (2026).

A correção elevou o F1 do *Isolation Forest* em 4,3 pontos, e a melhora apareceu também na robustez: nas três simulações, o F1 passou de 62,4 ± 1,2 para 67,2 ± 1,6. O maior ganho foi no tipo inédito: na intensidade alta, de 55% para 87,5% dos cenários. As regras não mudaram, porque usam só atributos absolutos e horas. Como a v2 usou o teste da simulação de referência pela segunda vez, ela foi tratada como uma versão corrigida, e a validação confirmatória a seguir verifica se os resultados se sustentam em dados novos.

## VALIDAÇÃO CONFIRMATÓRIA

As cinco simulações confirmatórias passaram em todas as verificações, com 266 cenários cada e contaminação do teste entre 6,7% e 7,2%. Antes de testar as hipóteses, as simulações de desenvolvimento foram reavaliadas pelo mesmo código e reproduziram exatamente os números publicados (diferença máxima de 5,6 × 10⁻¹⁷). A @tab:confirmatorio-detectores e a @fig:confirmatorio-detectores mostram o desempenho no agregado das cinco semanas de teste.

Tabela: Desempenho no agregado das simulações confirmatórias {#tab:confirmatorio-detectores}

| Detector | Precisão | Recall | F1 | Cenários detectados | Tipo inédito |
|---|---:|---:|---:|---:|---:|
| IF ajustado | 74,6 [71,4; 78,0] | 59,6 [56,2; 62,8] | 66,3 [63,4; 68,9] | 69,0 [65,9; 71,9] | 50,7 [39,3; 62,0] |
| IF sem rótulos | 71,7 [66,8; 76,7] | 30,9 [28,0; 34,1] | 43,2 [39,9; 46,6] | 37,5 [34,6; 40,6] | 19,3 [12,3; 26,7] |
| Regras | 94,7 [93,0; 96,2] | 67,9 [63,9; 71,6] | 79,1 [76,3; 81,7] | 73,5 [70,4; 76,5] | 41,7 [30,0; 53,3] |
| IF ∪ regras | 78,8 [75,9; 81,6] | 79,3 [76,5; 82,1] | 79,0 [76,9; 81,2] | 84,4 [81,9; 86,7] | 76,7 [68,0; 85,3] |

Fonte: elaborada pelo autor (2026).

Nota: entre colchetes, intervalo de confiança de 95% por *bootstrap* estratificado por simulação; 780 cenários de teste, 60 do tipo inédito.

![Detectores nas simulações confirmatórias](figuras/confirmatorio_detectores.png){#fig:confirmatorio-detectores width=15}

Fonte: elaborada pelo autor (2026).

Nota: cada ponto cinza é uma simulação; o ponto colorido e a barra são o agregado e o seu intervalo de 95%.

Os resultados de desenvolvimento se repetiram em dados novos. O F1 do *Isolation Forest* foi de 66,3%, contra 67,3% no agregado das simulações de desenvolvimento, e a combinação detectou 84,4% dos cenários, contra 85,9%. A @tab:hipoteses-resultado e a @fig:confirmatorio-diferencas apresentam os testes das hipóteses pré-registradas.

Tabela: Resultado das hipóteses pré-registradas {#tab:hipoteses-resultado}

| | Medida | A | B | A − B [IC 95%] | Discordantes (só A / só B) | p (Holm) | Resultado |
|---|---|---:|---:|---:|---:|---:|---|
| H1 | cenários detectados, IF ∪ regras × regras | 84,4 | 73,5 | +10,9 [8,9; 13,0] | 87 / 0 | < 0,0001 | confirmada |
| H2 | F1 por janela, IF ∪ regras × regras | 79,0 | 79,1 | −0,1 [−2,3; 2,5] | — | 1,00 | sem diferença |
| H3 | tipo inédito detectado, IF × regras | 50,7 | 41,7 | +9,0 [−9,5; 27,0] | 20 / 15 | 1,00 | não confirmada |

Fonte: elaborada pelo autor (2026).

![Diferenças entre detectores no agregado confirmatório](figuras/confirmatorio_diferencas.png){#fig:confirmatorio-diferencas width=15.5}

Fonte: elaborada pelo autor (2026).

Nota: em pontos percentuais, com intervalo de 95% por *bootstrap* pareado. Pontos cheios: hipóteses pré-registradas, com o p ajustado por Holm; vazios: diferenças só descritivas.

**H1 foi confirmada.** Em 87 dos 780 cenários, só a combinação detectou; em nenhum, só as regras. A combinação nunca perde um cenário das regras, por construção; o teste mostra que o ganho não é acaso, e o intervalo dá o seu tamanho, cerca de 11 pontos.

**H2 não mostrou diferença**, como esperado. O ganho de cobertura tem custo: a precisão cai 15,9 pontos [13,6; 18,1], o recall sobe 11,4 [9,0; 14,4], e o F1 por janela fica igual. Para quem faz a triagem, a escolha é entre cerca de um alerta falso a cada cinco, com 84,4% dos cenários cobertos, e um a cada dezenove, com 73,5%.

**H3 não foi confirmada.** No tipo inédito, o *Isolation Forest* detectou 50,7% dos cenários e as regras 41,7%, mas os acertos se dividem: 20 cenários só o modelo detectou e 15 só as regras. Embora não haja regra própria para esse tipo, a regra de linhas retornadas acima do máximo do usuário detectou 25 dos 60 cenários inéditos, porque a leitura paginada às vezes ultrapassa esse máximo. A vantagem do modelo vista na simulação de referência (quatro cenários só do modelo e nenhum só das regras) era variação daquela simulação. O que se sustenta é a complementaridade: a combinação detectou 76,7% dos cenários inéditos.

Entre as diferenças só descritivas, o *Isolation Forest* sozinho fica abaixo das regras em F1 (−12,8 pontos [−16,2; −9,3]) e em cenários detectados (−4,5 [−7,9; −1,3]).

## ABLAÇÃO DE ATRIBUTOS

A @tab:ablacao e a @fig:ablacao mostram a variação de desempenho, na validação das oito simulações, ao retirar cada grupo de atributos do *Isolation Forest*. Com todos os atributos, o F1 de validação é de 64,9%, a PR-AUC de 0,592 e a fração de cenários detectados de 73,0%.

Tabela: Variação ao retirar cada grupo de atributos do Isolation Forest (validação) {#tab:ablacao}

| Grupo retirado | Δ F1 | Δ PR-AUC | Δ cenários | Simulações em que o F1 piorou |
|---|---:|---:|---:|---:|
| relativos ao histórico | −17,0 [−19,4; −14,7] | −0,201 | −4,8 [−8,5; −1,2] | 8 de 8 |
| horário | −10,9 [−12,7; −9,1] | −0,129 | −1,6 [−5,4; +2,3] | 8 de 8 |
| novidade | −2,6 [−4,2; −1,0] | −0,029 | −4,0 [−5,2; −2,9] | 8 de 8 |
| origem | −0,9 [−2,6; +0,9] | −0,012 | −2,2 [−4,8; +0,4] | 6 de 8 |
| dependentes do auto_explain | +0,1 [−1,3; +1,5] | +0,017 | −9,6 [−12,7; −6,6] | 5 de 8 |

Fonte: elaborada pelo autor (2026).

Nota: Δ = variante − completo, em pontos percentuais (PR-AUC em unidades); entre colchetes, intervalo *t* de 95% entre as oito simulações.

![Ablação de atributos na validação](figuras/ablacao_grupos.png){#fig:ablacao width=15.5}

Fonte: elaborada pelo autor (2026).

Nota: pontos cinza: cada uma das oito simulações (média de cinco sementes); ponto colorido e barra: média e intervalo *t* de 95%. Melhor limiar da validação em cada caso.

Os atributos relativos ao histórico do usuário são o núcleo do modelo: sem eles, o F1 cai 17 pontos, em todas as simulações. Isso sustenta a decisão de comparar cada usuário consigo mesmo, e não com uma média geral. O horário vem em seguida. A novidade contribui pouco, mas sempre (pior nas oito simulações), e a origem não tem efeito mensurável, o que se explica pela pouca variação de origem que três redes simuladas produzem.

Sem os atributos que dependem do `auto_explain`, o F1 do *Isolation Forest* não muda, mas a cobertura cai: o modelo compensa no F1 sinalizando outras janelas e deixa de detectar cenários de dois tipos. Considerando o sistema inteiro, em que as regras também perdem as duas regras de linhas, a combinação passa de 85,3% para 70,2% dos cenários detectados. A perda está concentrada em volume alto (de 89,0% para 35,5%) e DML incomum (de 69,5% para 32,5%); os demais tipos ficam praticamente iguais. Os cerca de 10% de latência do `auto_explain` compram, portanto, cerca de 15 pontos de cobertura, justamente nos casos de extração de dados e de alteração em massa.

## TRÁFEGO NÃO ESTACIONÁRIO

As quinze simulações novas do cenário com mudanças de rotina passaram em todas as verificações. Uma delas, sem mudanças, parou por uma falha momentânea de resolução de nomes do Docker e foi refeita com a mesma semente, como determinava o pré-registro. As cinco simulações sem mudanças já avaliadas na validação confirmatória reproduziram os números publicados (diferença máxima de 1,1 × 10⁻¹⁶). A @tab:deriva e a @fig:deriva-perdas mostram a perda de cada detector.

Tabela: Desempenho sem e com mudanças legítimas de rotina {#tab:deriva}

| Detector | F1 sem → com | Perda de F1 [IC 95%] | Precisão sem → com | Cenários sem → com |
|---|---:|---:|---:|---:|
| IF ajustado | 66,2 → 64,5 | −1,7 [−4,1; +0,7] | 75,6 → 72,1 | 70,0 → 71,0 |
| IF sem rótulos | 41,2 → 37,8 | −3,4 [−6,8; −0,0] | 70,0 → 64,6 | 36,8 → 36,1 |
| Regras | 80,0 → 64,1 | −15,9 [−23,7; −8,1] | 94,0 → 61,7 | 74,7 → 74,4 |
| IF ∪ regras | 79,6 → 65,3 | −14,2 [−21,5; −7,0] | 79,2 → 56,7 | 85,4 → 86,1 |

Fonte: elaborada pelo autor (2026).

Nota: média nas dez sementes de simulação; intervalo *t* de 95%.

![Perda de cada detector com as mudanças de rotina](figuras/deriva_perdas.png){#fig:deriva-perdas width=15}

Fonte: elaborada pelo autor (2026).

Nota: com − sem mudanças, em pontos percentuais. Pontos cinza: cada uma das dez sementes; ponto colorido e barra: média e intervalo *t* de 95%.

**H4 foi confirmada.** O *Isolation Forest* perdeu 1,7 ponto de F1, com intervalo que inclui zero, e as regras perderam 15,9. A diferença das diferenças foi de +14,2 pontos [5,8; 22,5], com p ajustado de 0,0039 no teste *t* pareado nas dez sementes. Com as mudanças, o F1 das regras (64,1%) cai ao nível do *Isolation Forest* (64,5%). **H5 também foi confirmada:** a combinação continua detectando mais cenários que as regras, +11,8 pontos [10,3; 13,3]. Nenhum detector perdeu cobertura; as mudanças de rotina geram alarmes falsos, e não perda de detecção.

A @tab:alarmes e a @fig:deriva-alarmes mostram onde estão os alarmes falsos.

Tabela: Alarmes falsos nas janelas normais de teste afetadas por cada mudança {#tab:alarmes}

| Mudança | Janelas | IF ajustado | Regras | IF ∪ regras |
|---|---:|---:|---:|---:|
| troca de turno | 5.026 | 3,8 (24%) | 32,5 (91%) | 33,7 (72%) |
| pico de movimento | 1.405 | 11,0 (19%) | 10,0 (8%) | 14,9 (9%) |
| plantão | 340 | 4,3 (2%) | 0,0 | 4,3 (1%) |
| nova rotina | 1.791 | 2,9 (6%) | 0,2 | 2,9 (2%) |
| home office | 4.217 | 2,5 (13%) | 0,5 (1%) | 2,7 (5%) |
| crescimento | 15.703 | 0,8 (16%) | 0,1 (0,5%) | 0,9 (6%) |
| janelas não afetadas | 14.015 | 1,9 | 0,7 | 2,1 |

Fonte: elaborada pelo autor (2026).

Nota: fração das janelas sinalizadas, em porcentagem; entre parênteses, a parte de todos os alarmes falsos do detector com mudanças que cai nessas janelas. Nas férias o usuário não acessa o banco, então não há janelas afetadas.

![Alarmes falsos por mudança de rotina](figuras/deriva_alarmes.png){#fig:deriva-alarmes width=15.5}

Fonte: elaborada pelo autor (2026).

A perda das regras vem quase toda de uma única mudança. Na troca de turno, a regra de hora nunca vista dispara em toda janela de um horário que o usuário não tinha no treino: 32,5% das janelas afetadas viram alarmes falsos, e elas respondem por 91% dos alarmes falsos das regras. Nas outras mudanças, as regras são tão ou mais robustas que o *Isolation Forest*: ficam abaixo de 0,5% em crescimento, home office, nova rotina e plantão, já que a regra de hora não olha o dia da semana. O *Isolation Forest* sofre um pouco mais nas mudanças que só ele enxerga, como previsto no pré-registro, mas com taxas de 0,8% a 4,3%, próximas da sua taxa de base de 1,9%.

## RELATÓRIO EXPLICADO E FERRAMENTA DE APOIO

No teste da simulação de referência (semente 0), o relatório reuniu 295 janelas sinalizadas em 195 episódios: 125 contêm ao menos uma janela de cenário anômalo, e 70 não contêm nenhuma. Gerar o relatório com as explicações levou 0,6 segundo. Os comandos `sacla fit` e `sacla score`, aplicados aos logs da simulação, reproduziram exatamente os escores do modelo avaliado, o que garante que o caminho de uso real é o mesmo que foi medido (D39).

Os seis episódios de maior escore são a rotina noturna legítima do serviço batch, um por noite do teste. A explicação mostra o motivo: o lote passou a ler entre 4.290 e 4.619 linhas, acima do máximo do histórico (4.014), porque as tabelas de locações e pagamentos crescem ao longo da simulação. É uma deriva lenta dos dados, não uma anomalia de acesso, e a explicação permite que o analista a descarte rapidamente. A @fig:relatorio mostra um trecho do relatório.

![Trecho do relatório de anomalias em HTML](figuras/relatorio.png){#fig:relatorio width=15}

Fonte: elaborada pelo autor (2026).

Fora da avaliação, foi construída uma ferramenta de apoio: um monitor que aplica o mesmo detector às janelas de cinco minutos assim que elas fecham, em lotes, e um painel local, acessível só na própria máquina, que mostra os servidores e bancos supervisionados, os alertas explicados e a triagem de cada um (em análise, suspeito confirmado ou falso positivo). Nenhum número deste trabalho vem dessa ferramenta, e ela não altera o modelo avaliado. Na semana de teste reproduzida, o monitor gerou exatamente os mesmos alertas que o `sacla score` em lote: 296 janelas, uma a mais que o relatório da avaliação, porque no uso real o limiar é definido sem rótulos (Seção 4.4). A @fig:painel mostra a tela de alertas.

![Tela de alertas do painel local](figuras/painel.png){#fig:painel width=15.5}

Fonte: elaborada pelo autor (2026).
