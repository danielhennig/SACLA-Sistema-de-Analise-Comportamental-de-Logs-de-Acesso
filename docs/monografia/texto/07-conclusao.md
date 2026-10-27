# CONCLUSÃO

Este trabalho apresentou o SACLA, um sistema que lê o log nativo do PostgreSQL e aponta, com explicação, janelas de cinco minutos em que um usuário se comporta de forma atípica em relação ao próprio histórico, usando um único algoritmo de aprendizado não supervisionado, o *Isolation Forest*. O problema de pesquisa perguntava se isso é possível com desempenho comparável ao de regras de especialista e com alertas interpretáveis. A resposta é sim, com uma ressalva importante: o modelo não supera as regras sozinho, mas as complementa.

Em um laboratório reprodutível, com usuários simulados executando acessos reais sobre a base Pagila e anomalias com rótulos mantidos fora do log, o *Isolation Forest* obteve F1 de 68,1% na simulação de referência e de 66,3% em cinco simulações confirmatórias nunca vistas. As regras, escritas conhecendo os tipos de anomalia, tiveram F1 de cerca de 80%. A combinação dos dois detectou 84% a 86% dos cenários, cerca de 11 pontos a mais que as regras sozinhas, resultado confirmado com teste estatístico em hipóteses registradas antes dos dados. Quando a rotina dos usuários muda de forma legítima, as regras perdem 15,9 pontos de F1, quase todos por causa de trocas de turno, e o *Isolation Forest* perde 1,7.

## CONTRIBUIÇÕES

- **Um detector que usa só o log nativo.** O SACLA não exige extensões de auditoria, alterações no SGBD nem acesso às aplicações; a instrumentação se resume a parâmetros de configuração e a um módulo distribuído com o PostgreSQL, cujo custo foi medido.
- **Atributos relativos ao histórico de cada usuário**, com um cuidado metodológico que se mostrou decisivo: calcular os atributos das janelas de treino "deixando um dia de fora", sem o que as frações de novidade não têm efeito no modelo.
- **Alertas explicados** pelos atributos mais raros para o usuário e agrupados em episódios, o que tornou rápido descartar alarmes falsos como o da rotina batch.
- **Um laboratório reprodutível** com simulação de usuários, ruído legítimo, anomalias em três intensidades, um tipo inédito, mudanças de rotina e verificações automáticas de coerência entre o que foi executado e o que foi registrado.
- **Uma avaliação rigorosa**, com linha de base explícita, teste usado uma vez, réplicas com várias sementes, validação confirmatória e cenário de mudanças de rotina pré-registrados, testes estatísticos com correção para comparações múltiplas e relato dos resultados que não se confirmaram.

## LIMITAÇÕES

As principais limitações são o uso de dados sintéticos, desenhados pelo mesmo autor que escreveu as regras e o catálogo de mudanças; uma base pequena e um único SGBD; o custo de cerca de 10% de latência do registro de linhas; e a saturação do escore do *Isolation Forest* para valores muito acima do observado no treino. O Capítulo 6 discute essas limitações em detalhe.

## TRABALHOS FUTUROS

- **Avaliação com dados reais.** Aplicar o SACLA ao log de um servidor em produção, mesmo sem rótulos, e analisar qualitativamente os alertas com quem conhece o sistema é o passo mais importante para a validade externa.
- **Combinação em produção.** Levar as regras para dentro do SACLA e emitir alertas pela combinação dos dois detectores, que teve a melhor cobertura em todas as análises, com as regras de horário reaprendidas após mudanças confirmadas na triagem.
- **Atualização do histórico.** Reajustar o modelo periodicamente com uma janela móvel de histórico, o que trataria a deriva lenta dos dados, como o crescimento das tabelas, e as mudanças permanentes de rotina.
- **Custo do registro de linhas.** Avaliar o `auto_explain` com amostragem de comandos (`auto_explain.sample_rate`) ou com registro só acima de uma duração mínima, medindo quanto de cobertura se preserva com menos custo.
- **Saturação do escore.** Acrescentar atributos que expressem a distância de cada valor ao máximo do histórico do usuário, para que valores extremos não se confundam com valores de borda, e avaliar variantes do algoritmo com cortes de inclinação aleatória, que reduzem os artefatos do escore em regiões sem dados (Hariri; Carrasco Kind; Brunner, 2021).
