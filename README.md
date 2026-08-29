# <p align="center">BOOSTBANDITOS</p>

<p align="center">
  <strong>Engine Management de alta performance para Suzuki Bandit 1200 Turbo com ITBs.</strong><br>
  Full Sequential · Alpha-N + MAP Vector · Smart Fuel Pump PWM · Total Telemetry
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/spacevipgames/speeduino/refs/heads/master/logo.png" alt="BoostBanditOS" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ECU-ATmega2560-cc0000?style=for-the-badge" alt="ATmega2560">
  <img src="https://img.shields.io/badge/INJECTION-FULL_SEQUENTIAL-111111?style=for-the-badge" alt="Full Sequential">
  <img src="https://img.shields.io/badge/FUEL-ALPHA--N_%2B_MAP_VECTOR-045da8?style=for-the-badge" alt="Alpha-N + MAP Vector">
  <a href="https://github.com/spacevipgames/speeduino"><img src="https://img.shields.io/badge/ENGINEERING-ARCHITECTURE-6617a8?style=for-the-badge&logo=github" alt="Architecture"></a>
</p>

---

## A proposta

**BoostBanditOS** é uma evolução profunda da Speeduino para uma Bandit 1200 Turbo com ITBs. A firmware foi desenhada para unir a resposta instantânea do TPS à leitura real de carga pelo MAP, coordenando combustível, ignição, pressão e transientes com precisão de arquitetura racing.

Não é um conjunto de mapas isolados: é um sistema em que cada camada conhece o seu papel, trabalha dentro de limites claros e aparece separadamente na telemetria.

## Full Sequential Architecture

Quatro injetores. Quatro canais. Quatro eventos de fase independentes.

```text
PW FINAL ─┬─ PW1 → Cilindro 1
          ├─ PW2 → Cilindro 2
          ├─ PW3 → Cilindro 3
          └─ PW4 → Cilindro 4
```

O BoostBanditOS preserva a duração de pulso integral em cada canal sequencial e executa a entrega de combustível no evento angular correto. A arquitetura de sincronismo foi construída para manter continuidade de operação e coerência de fase em todas as condições de rotação.

## Alpha-N + MAP Vector Fuel

ITB exige leitura de intenção. Turbo exige leitura de carga. A estratégia combina os dois:

```text
TPS × RPM  →  VE1 / Alpha-N        → intenção do piloto
MAP × RPM  →  VE2 / Fuel2          → carga real do plenum
TPSdot + MAPdot → Vetor VE2        → velocidade da demanda
                                           ↓
                                  PW Modelo Ar → PW Final
```

**VE1** dá a resposta imediata do acelerador.

**VE2** é uma tabela MAP/RPM multiplicativa, refinando a massa de combustível sobre a base Alpha-N.

**Vetor VE2** enxerga subida conjunta de TPS e MAP e adiciona autoridade transitória limitada, rápida e calibrável.

O resultado é uma entrega limpa em condição estável e agressiva quando o motor pede carga.

## Intelligent Transient Control

### Spool-Sync AE

O sistema de enriquecimento acelera junto com o motor. TPS, MAP, TPSdot, MAPdot, RPMdot e lambda formam uma leitura de intenção, spool e recuperação de troca.

* adder inteligente por intensidade de evento;
* hold calculado dinamicamente;
* decay progressivo e limpo;
* recuperação dedicada para queda de RPM sob carga;
* proteção de riqueza e assistência por lambda.

### DFCO Reentry

A reentrada de combustível é tratada como uma ponte de torque. A firmware acompanha MAP, micro-TPS, permanência e lambda para devolver combustível com suavidade e autoridade, eliminando o comportamento seco e brusco típico de ITBs.

### Ignition Layering

A arquitetura Spark2 adiciona uma camada estratégica sobre a ignição principal. Ela permite compor avanço por contexto de carga, preservando a tabela central como referência e abrindo espaço para curvas sofisticadas por MAP, pressão e regime.

## Smart Fuel Pump PWM

O canal de bomba é um sistema de gerenciamento de combustível, não um simples acionamento.

A infraestrutura IDLE1/timer foi convertida em um controlador PWM de bomba que combina pressão PS10, RPM, TPS, MAP, pós-partida e faixas de duty. O resultado é pressão entregue com inteligência: autoridade total quando o motor exige e modulação refinada nas regiões de baixa demanda, contribuindo para uma marcha lenta mais estável e um sistema mais eficiente.

## Total Telemetry

O BoostBanditOS registra o combustível como uma cadeia de decisões, não como um único número final.

| Camada         | Telemetria disponível                                       |
| -------------- | ----------------------------------------------------------- |
| Vetor de carga | VE2 Base, pedido, efetivo e estado ativo                    |
| Dinâmica       | TPS DOT Raw, MAP DOT Raw, RPMdot e carga                    |
| Enriquecimento | AE nativo, AE híbrido, Spool Add, hold, decay e recuperação |
| Reentrada      | DFCO Add e hold                                             |
| Combustível    | PW Modelo Ar, PW Final, duty final e PW por canal           |
| Plataforma     | Sync, loops/s, loops/rev, avanço e estados do sistema       |
| Bomba          | pressão, PWM ativo e duty                                   |

Essa visão permite criar **Moto Profiles** precisos: Rua, Pista, Agressivo e perfis dedicados por comportamento de carga. Cada perfil pode ter personalidade própria sem sacrificar rastreabilidade.

## Próxima fronteira: Sequential Fuel Trim Matrix

A próxima evolução expande o sequencial para o nível de acabamento fino por cilindro. A matriz de Fuel Trim 1–4 permitirá correções individuais organizadas por zonas de RPM, TPS, MAP e carga — incluindo vetores específicos para baixa carga, transiente, spool e alta demanda.

```text
Base de combustível
        ↓
Trim individual por cilindro
        ↓
Vetores por área de operação
        ↓
PW sequencial final de cada bico
```

É a base para uma calibração extremamente refinada: quatro cilindros tratados como quatro assinaturas de combustão, dentro de uma mesma estratégia coerente.

## Engenharia enxuta, resposta brutal

Construída sobre ATmega2560, a firmware prioriza:

* cálculos inteiros e determinísticos;
* baixo custo de CPU e RAM;
* loops dedicados ao que realmente move a moto;
* sincronismo, combustível e ignição como caminhos prioritários;
* limites e clamps explícitos em cada camada.

## Estrutura

| Caminho                                                           | Conteúdo                                  |
| ----------------------------------------------------------------- | ----------------------------------------- |
| [`speeduino/`](./speeduino)                                       | Fonte customizada da firmware             |
| [`reference/`](./reference)                                       | INI, cálculos e referências de integração |
| [Arquitetura técnica](https://github.com/spacevipgames/speeduino) | Documentação das camadas de controle      |

## Créditos

**Projeto e arquitetura custom:** Marcos Vinicius Estabio

**Base original:** [Speeduino](https://speeduino.com/) — Josh Stewart e comunidade

**Licença:** [GNU GPL v2](./LICENSE)

<p align="center"><em>Built for boost. Tuned by intent. Proven by data.</em></p>
