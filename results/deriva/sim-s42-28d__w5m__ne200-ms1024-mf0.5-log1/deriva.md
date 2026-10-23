# Tráfego não estacionário (configuração congelada `ne200-ms1024-mf0.5-log1`)

Pré-registro: `docs/decisoes.md`, D55. 10 sementes, cada uma simulada sem e com as mudanças de rotina de `config/drift.yaml`. Valores em %; perdas = com − sem deriva, em pontos percentuais.

## Hipóteses

| | Teste | Medida | A | B | Resultado A | Resultado B | A − B [IC] | p | p (Holm) | Decisão |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| H4 | did_t | F1 | Isolation Forest (ajustado) | Regras | -1.7 (perda) | -15.9 (perda) | +14.2 [+5.8; +22.5] | 0.0039 | 0.0039 | rejeita H0 |
| H5 | mcnemar | cenários detectados | Isolation Forest ∪ regras | Regras | 86.1 | 74.4 | +11.8 [+10.3; +13.3] | < 0.0001 | < 0.0001 | rejeita H0 |

H4: diferença das diferenças por semente e teste t pareado (10 sementes; a simulação é a unidade). H5: McNemar exato no agregado com deriva, com a detecção em ao menos metade das sementes do modelo. Holm sobre as hipóteses.

## Perda de cada detector com a deriva (média nas sementes, intervalo t de 95%)

| Detector | F1 sem → com | Δ F1 | Precisão sem → com | Δ precisão | Cenários sem → com | Δ cenários |
|---|---:|---:|---:|---:|---:|---:|
| Isolation Forest (ajustado) | 66.2 → 64.5 | -1.7 [-4.1; +0.7] | 75.6 → 72.1 | -3.5 [-7.6; +0.6] | 70.0 → 71.0 | +0.9 [-4.1; +5.9] |
| Isolation Forest (sem rótulos) | 41.2 → 37.8 | -3.4 [-6.8; -0.0] | 70.0 → 64.6 | -5.4 [-10.7; -0.1] | 36.8 → 36.1 | -0.7 [-4.8; +3.5] |
| Regras | 80.0 → 64.1 | -15.9 [-23.7; -8.1] | 94.0 → 61.7 | -32.3 [-47.1; -17.4] | 74.7 → 74.4 | -0.3 [-2.5; +1.9] |
| Isolation Forest ∪ regras | 79.6 → 65.3 | -14.2 [-21.5; -7.0] | 79.2 → 56.7 | -22.5 [-34.2; -10.9] | 85.4 → 86.1 | +0.7 [-2.1; +3.5] |

## Agregado das simulações (intervalo de 95% por bootstrap estratificado)

| Detector | F1 sem deriva | F1 com deriva | Cenários sem deriva | Cenários com deriva |
|---|---:|---:|---:|---:|
| Isolation Forest (ajustado) | 66.3 [64.2; 68.4] | 64.5 [62.1; 66.9] | 70.0 [68.0; 72.1] | 71.0 [68.9; 73.1] |
| Isolation Forest (sem rótulos) | 41.3 [38.7; 43.8] | 38.0 [35.3; 40.7] | 36.8 [34.7; 39.1] | 36.1 [34.0; 38.3] |
| Regras | 80.1 [78.2; 81.9] | 62.5 [58.3; 67.0] | 74.7 [72.4; 76.8] | 74.4 [72.0; 76.5] |
| Isolation Forest ∪ regras | 79.5 [77.9; 81.2] | 64.0 [60.0; 68.0] | 85.4 [83.6; 87.1] | 86.1 [84.4; 87.8] |

## Alarmes falsos nas janelas normais de teste afetadas por cada mudança (%)

| Mudança | Janelas | Isolation Forest (ajustado) | Isolation Forest (sem rótulos) | Regras | Isolation Forest ∪ regras |
|---|---:|---:|---:|---:|---:|
| crescimento | 15703 | 0.8 | 1.0 | 0.1 | 0.9 |
| ferias | 0 | — | — | — | — |
| home_office | 4217 | 2.5 | 1.3 | 0.5 | 2.7 |
| nova_rotina | 1791 | 2.9 | 3.8 | 0.2 | 2.9 |
| pico_movimento | 1405 | 11.0 | 9.4 | 10.0 | 14.9 |
| plantao | 340 | 4.3 | 0.5 | 0.0 | 4.3 |
| troca_turno | 5026 | 3.8 | 1.8 | 32.5 | 33.7 |
| (não afetadas) | 14015 | 1.9 | 1.2 | 0.7 | 2.1 |

### Parte de todos os alarmes falsos com deriva que cai nas janelas de cada mudança (%)

| Mudança | Isolation Forest (ajustado) | Isolation Forest (sem rótulos) | Regras | Isolation Forest ∪ regras |
|---|---:|---:|---:|---:|
| crescimento | 15.9 | 26.7 | 0.5 | 5.8 |
| ferias | 0.0 | 0.0 | 0.0 | 0.0 |
| home_office | 12.9 | 9.2 | 1.1 | 4.8 |
| nova_rotina | 6.3 | 11.8 | 0.2 | 2.2 |
| pico_movimento | 19.2 | 22.9 | 7.8 | 8.8 |
| plantao | 1.8 | 0.3 | 0.0 | 0.6 |
| troca_turno | 23.7 | 16.0 | 90.9 | 71.6 |
| (não afetadas) | 32.9 | 29.6 | 5.5 | 12.2 |

Mudanças sorteadas: 110 nas 10 simulações com deriva (`drift_plans.csv`); por tipo: crescimento 10, ferias 20, home_office 20, nova_rotina 10, pico_movimento 20, plantao 10, troca_turno 20. Nas férias o usuário não acessa o banco: não há janelas afetadas.

## Conferência

- As simulações sem deriva já avaliadas na Fase 7 (sim-s101-28d, sim-s202-28d, sim-s303-28d, sim-s404-28d, sim-s505-28d) reproduzem os números publicados (diferença máxima: 1.1e-16).
