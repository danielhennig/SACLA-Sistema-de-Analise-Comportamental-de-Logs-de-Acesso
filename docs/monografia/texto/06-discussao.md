# DISCUSSÃO

Este capítulo retoma as questões de pesquisa da introdução à luz dos resultados, discute as implicações práticas e apresenta as ameaças à validade do trabalho.

## RESPOSTAS ÀS QUESTÕES DE PESQUISA

**1. Com que precisão e cobertura o *Isolation Forest* sinaliza acessos anômalos?** Na simulação de referência, com F1 de 68,1%, precisão de 76,5% e recall de 61,7%, detectando 75,5% dos cenários. Nas cinco simulações confirmatórias, o F1 foi de 66,3% [63,4; 68,9]. O modelo é forte no que é volumoso ou foge da rotina (horário, volume alto, rajadas médias e altas) e fraco nas intensidades baixas, desenhadas para se confundir com o ruído normal.

**2. O modelo detecta um tipo de anomalia que não aparece antes do teste?** Em parte. O *Isolation Forest* detectou cerca de metade dos cenários do tipo inédito, mais que as regras, mas a diferença não se confirmou estatisticamente (H3). O resultado mais sólido é outro: modelo e regras detectam cenários inéditos diferentes, e juntos chegam a 76,7%.

**3. O que o modelo acrescenta às regras de especialista?** Cobertura. Sozinho, o *Isolation Forest* fica abaixo das regras, que foram escritas conhecendo os tipos de anomalia e têm precisão altíssima. Combinado com elas, acrescenta cerca de 11 pontos de cenários detectados, sem perder nenhum cenário das regras (H1), ao custo de mais alarmes falsos; o F1 por janela fica igual (H2).

**4. Quanto os resultados dependem dos parâmetros e das sementes?** Pouco do número de árvores e da fração de atributos; bastante do tamanho da subamostra e da transformação logarítmica. O tamanho da janela troca cobertura por número de alertas. Entre simulações, o F1 do *Isolation Forest* variou cerca de dois pontos de desvio, menos que o das regras.

**5. As conclusões se repetem em dados novos? O que pesa no modelo?** Sim: em cinco simulações nunca vistas, com hipóteses registradas antes dos dados, os números ficaram a um ou dois pontos dos de desenvolvimento. A comparação do usuário com o próprio histórico é o que mais pesa; sem ela, o F1 cai 17 pontos. O registro de linhas pelo `auto_explain` não altera o F1 do modelo, mas sustenta cerca de 15 pontos de cobertura nos casos de volume e alteração em massa.

**6. Como os detectores se comportam quando a rotina muda?** O *Isolation Forest* perde 1,7 ponto de F1; as regras perdem 15,9 (H4), quase tudo por causa das trocas de turno. A cobertura não muda para nenhum dos detectores.

## IMPLICAÇÕES PRÁTICAS

Os resultados não sustentam trocar regras simples por aprendizado de máquina. Sustentam combinar as duas coisas, cada uma no que faz melhor. Regras de limiar fixo são imbatíveis para sinais inequívocos, como falhas de autenticação em série e tentativas sem permissão: custam pouco, quase não erram e qualquer administrador entende. O *Isolation Forest* acrescenta o que as regras não foram escritas para ver, como rajadas moderadas, leituras que fogem do padrão e combinações incomuns de atributos, e degrada de forma mais suave quando a rotina dos usuários muda.

A troca de turno ilustra o segundo ponto. Uma regra de "hora nunca vista" é razoável enquanto os horários são estáveis e se torna uma fonte de alarmes falsos assim que a escala muda. Na prática, regras desse tipo precisam de manutenção, por exemplo reaprender os horários de um usuário depois que a mudança é confirmada na triagem. O modelo, que compara cada janela com um histórico que já pode conter parte da mudança, absorve melhor esse tipo de evento.

Há também uma decisão de custo. O `auto_explain` com contagem de linhas custa cerca de 10% de latência e cerca de 10 KB de log por comando. Sem ele, o SACLA continua cobrindo autenticação, permissão, horário e rajadas no mesmo nível, mas perde mais da metade da detecção de leituras volumosas e de alterações em massa, que são justamente os casos de extração de dados e de dano maior. A escolha depende do que a organização mais teme e de quanto desempenho pode ceder.

Por fim, as explicações mostraram valor mesmo nos alarmes falsos. Os episódios de maior escore no teste foram a rotina noturna do serviço batch, que passou a ler mais linhas porque as tabelas cresceram. Sem explicação, seriam seis alertas graves; com ela, o analista vê em segundos que o volume subiu pouco acima do máximo de um processo conhecido e descarta o alerta.

## AMEAÇAS À VALIDADE

### Validade interna e de construto

- **Dados sintéticos.** O tráfego é simulado. Usuários reais variam mais, o que tende a reduzir a precisão de qualquer detector. O cenário com mudanças de rotina confirmou isso para as regras (precisão de 94% para 62%), mas o catálogo de mudanças também foi escrito pelo autor, e a frequência de cada mudança, como duas de quatro atendentes trocando de turno no mês, é uma escolha de desenho.
- **Mesmo autor nos dois lados.** O autor desenhou as anomalias, os atributos e as regras. As regras foram escritas conhecendo os seis tipos de anomalia, o que favorece a linha de base. O tipo inédito, a análise por tipo e as tabelas de "quem afeta quem" escritas antes dos dados mitigam, mas não eliminam, esse viés.
- **Horários simulados e execução sequencial.** Não há concorrência real entre sessões. As durações dos comandos são reais, mas medidas sem contenção.
- **Correção depois de ver o teste.** A versão corrigida dos atributos relativos usou o teste da simulação de referência pela segunda vez. O defeito foi encontrado sem olhar desempenho e o protocolo não mudou; a validação confirmatória, em simulações novas e com hipóteses registradas antes, mostrou que os resultados se sustentam.
- **Saturação do escore.** O *Isolation Forest* não distingue um valor um pouco acima do máximo do treino de um valor cem vezes acima, o que explica parte da vantagem das regras em casos extremos.
- **Contaminação e deriva.** Anomalias no treino elevam o "máximo do usuário" e podem mascarar cenários parecidos no teste. O crescimento das tabelas faz a rotina batch legítima parecer atípica.

### Validade externa

- Uma base pequena, um único SGBD e dez usuários. Organizações reais têm centenas de usuários, aplicações compartilhando credenciais e padrões sazonais mais longos que quatro semanas.
- Três redes simulam a origem das conexões; endereços reais são mais diversos, o que pode dar aos atributos de origem um peso que eles não mostraram aqui.
- O custo do `auto_explain` limita o uso direto da configuração completa em servidores com carga alta.

### Validade de conclusão

- **Teste usado uma vez.** Hiperparâmetros e limiares vêm só da validação; nas simulações confirmatórias e de mudança de rotina, o teste foi usado uma única vez, depois do pré-registro.
- **O que os intervalos medem.** Na validação confirmatória, os intervalos por *bootstrap* tratam as simulações como estratos fixos e medem a incerteza de amostragem das janelas e dos cenários. A variação entre simulações aparece à parte, nas figuras, e entra diretamente no teste *t* pareado da hipótese H4.
- **Poder estatístico no tipo inédito.** São 60 cenários inéditos, e só 35 discordantes entre o modelo e as regras. Uma diferença de nove pontos não pode ser distinguida do acaso com esse tamanho; a ausência de significância não prova que os dois sejam iguais.
- **Ablação exploratória.** A ablação usa o melhor limiar da própria validação, o que é otimista. Ela serve para comparar variantes entre si, não para estimar desempenho.
- **Gerador comum.** Todas as simulações vêm do mesmo gerador. Os intervalos e testes medem a variação entre sementes, não entre ambientes reais.
