# F1 Overall — Sistema de Avaliação de Pilotos da Fórmula 1 (1950–2026)

Plataforma Full-Stack que calcula o **Overall (0–99)** de todos os pilotos da história da Fórmula 1 (`1950–2026`), isolando a habilidade individual da performance do carro (~75–85% do resultado bruto em pista).

## Metodologia Estatística Implementada

### 1. Isolamento Piloto vs. Carro
- **Delta de Companheiro**: Comparação em diferença percentual simétrica (`%`) de tempo de volta entre companheiros de equipe na mesma corrida e na mesma fase da classificação, neutralizando o comprimento de cada circuito.
- **Calibração em Rede (LMM / Ridge IRLS)**: Resolução esparsa (`scipy.sparse.linalg.lsqr` + pesos robustos de Huber) conectando todo o histórico de duelos entre equipes e temporadas:
  $$\text{Desempenho}_{i,r} = \alpha_{\text{piloto}} + \gamma_{\text{equipe},\text{temporada}} + \beta_1(\text{Idade} - 27) + \beta_2(\text{Idade} - 27)^2 + \varepsilon$$

### 2. Pilares e Pesos do Overall
1. **Ritmo de Corrida (35%)**: Mediana do delta percentual em **ar limpo** (gap $\ge 1.8\text{s}$ para o carro à frente reconstruído via relógio acumulado de pista), corrigido por queima de combustível, composto de pneu (`SOFT`/`MEDIUM`/`HARD`/`INTERMEDIATE`/`WET`), idade do pneu e bônus de conservação de degradação por stint (com integração ponderada de corridas Sprint `SR`).
2. **Classificação (25%)**: Mediana do delta percentual na última sessão válida disputada em igualdade pelos dois carros da equipe (`Q3` → `Q2` → `Q1` ou `QB`/`QA`), mais integração ponderada do Sprint Shootout (`SQ1`–`SQ3`).
3. **Consistência / Consciência (20%)**: Taxa de corridas sem erros próprios (penalizando apenas abandonos por erro/colisão e punições de condução da FIA, ajustados à média da época) + baixa variância intrastint medida via MAD detrendado.
4. **Combate / Racecraft (15%)**: Saldo de posições na Volta 1 ajustado pela curva empírica da posição do grid + eficiência de ultrapassagens e defesas em bandeira verde.
5. **Experiência (5%)**: Curva logarítmica acumulada de GPs largados ($\ln(1 + \min(N_{\text{starts}}, 350))$).

### 3. Regras de Higiene de Dados (Data Hygiene)
- Uso sistemático de **mediana**, **MAD** e **média aparada**.
- **Separação estrita de abandonos**: DNFs mecânicos ou de equipe (`Engine`, `Gearbox`, `Hydraulics`, `Electrical`, `Suspension`, desclassificações técnicas) são excluídos da amostra de erro e nunca penalizam o piloto.
- **Filtragem de voltas anômalas**: Remoção automática de Volta 1, voltas deletadas, `in-laps`, `out-laps`, Safety Car / VSC / Bandeira Vermelha e outliers $> 1.07\times$ a mediana da volta.

### 4. Pipeline Matemático Final & Sub-Índices
- **Ponderação Temporal**: Decaimento exponencial ($w_r = 2^{-\Delta r / H}$) para Overall Atual ($H=16$ GPs) e por Temporada ($H=14$ GPs); combinação **75% Janela de Auge (melhor triênio)** + **25% Longevidade** para o Ranking Histórico All-Time.
- **Bayesian Shrinkage**: $\text{ScoreAjustado} = \frac{n \cdot \text{Observado} + m \cdot \text{MédiaBase}}{n + m}$ ($m = 10$ GPs por padrão).
- **Intervalo de Confiança (`overall_ci`)**: Margem de incerteza estatística ($\pm \sigma$) calculada a partir do tamanho efetivo da amostra.
- **Especialidades & Badges**: Sub-índices para **Chuva** (`wet_ovr`), **Circuitos de Rua** (`street_ovr`), **Alta Velocidade** (`high_speed_ovr`) e **Gestão de Pneus** (`tyre_mgmt_ovr`), além da nota corrida a corrida (`weekend_score`).
- **Padronização Z-Score & Escala (60–99)**:
  $$\text{Overall} = \text{clip}\big(82 + 6 \cdot Z_{\text{final}},\, 60,\, 99\big)$$

---

## Recursos da Interface Web (`frontend/`)
- **Grid & Temporadas (`/`)**: Power Ranking atual e seletor de todas as 77 temporadas (`1950–2026`), com fotos, bandeiras, badges, intervalo de confiança e força isolada dos carros.
- **Histórico All-Time (`/all-time`)**: Todos os `820` pilotos avaliados com filtros por década, nacionalidade, mínimo de GPs e campeões.
- **Raio-X de GPs (`/races`)**: Nota por fim de semana (`Nota FDS`), clima/tipo de circuito, neutralizações SC/VSC, estratégia de stints de pneus e consistência de voltas limpas.
- **Equipes & Linhagens (`/teams`)**: Evolução histórica de chassi por franquia (ex.: Tyrrell → Brawn → Mercedes; Stewart → Red Bull) e Hall da Fama dos pilotos.
- **Simulador "E se...?" (`/what-if`)**: Campeonato em **Carros Iguais** (neutralizando diferenças de equipamento e DNFs mecânicos) + simulador **Monte Carlo de Troca de Assento**.
- **Comparador H2H (`/compare`)**, **Rede de Companheiros (`/network`)**, **Sandbox & Metodologia (`/sandbox`)**, **Busca Global (`Ctrl+K`)**, **Exportação de Cards PNG** e **Sincronização 1-clique**.

---

## Fontes de Dados (Ingestão Multi-Camada)
- **Jolpica-F1 (CSV Dump Oficial + REST API Incremental)**: Histórico completo de 1950 a 2026 (`drivers`, `teams`, `sessions`, `laps` volta a volta desde 1996, `pit_stops` e motivos detalhados de DNF).
- **OpenF1 API (`2023–2026`)**: Compostos de pneu por stint, idade inicial do pneu, neutralizações `SC`/`VSC` e punições dos comissários da FIA no controle de prova.
- **FastF1 SDK (`2018–2026`)**: Conector oficial com cache em disco e suporte opcional a autenticação F1 TV (`FASTF1_TOKEN` ou login interativo via `python -m app.cli sync-fastf1`).
- **Wikipedia REST API**: Retratos oficiais dos pilotos com cache persistido em SQLite (`driver_portraits`).

---

## Arquitetura do Projeto

- `backend/` — **Python 3.12 + FastAPI + SQLite + NumPy/SciPy/Pandas/FastF1**
- `frontend/` — **React 19 + TypeScript + Vite + Tailwind CSS + Recharts**

### Como Executar Localmente

```bash
# 1. Configurar ambiente Python e dependências do Frontend
make setup

# 2. Baixar dados reais (1950–2026) e calcular todo o modelo estatístico
make bootstrap

# 3. Auditar métricas no terminal
make audit

# 4. Rodar backend (porta 8000) e frontend (porta 5173) em desenvolvimento
make dev
```

### Comandos Úteis da CLI
- `cd backend && .venv/bin/python -m app.cli sync` — Sincroniza novas corridas recentes via Jolpica REST + OpenF1 e recalcula as notas.
- `cd backend && .venv/bin/python -m app.cli recompute` — Recalcula o modelo matemático localmente a partir do SQLite.
- `cd backend && .venv/bin/python -m app.cli sync-fastf1` — Enriquece sessões de 2018–2026 com FastF1 (requer cache local ou assinatura F1 TV).
- `make test` — Executa a suíte de testes unitários/integração (`pytest`) e o build de produção do frontend (`tsc -b && vite build`).

---

## Execução com Docker & Docker Compose

O projeto conta com dockerização multi-serviço (`docker-compose.yml` com Nginx + FastAPI) e também com um `Dockerfile` all-in-one na raiz para deploy em nuvem (Cloud Run / Railway / Render / Fly.io).

### Subir localmente com Docker Compose

```bash
# Opcional: copie e personalize portas/variáveis (.env)
cp .env.example .env

# Build e inicialização em segundo plano (use sudo se o usuário ainda não estiver no grupo docker)
docker compose up -d --build
```

- **Interface Web (Frontend Nginx + proxy `/api`)**: `http://localhost:8080` (ajustável via `FRONTEND_PORT`)
- **API FastAPI & Swagger (`/docs`)**: `http://localhost:8010/docs` (ajustável via `BACKEND_PORT`)
- **Persistência & Bootstrap Automático**: O diretório local `./backend/data` é montado em `/data` dentro do container `backend`. Se o arquivo `f1_overall.sqlite` já existir populado, a API sobe imediatamente; caso esteja vazio, o script `backend/entrypoint.sh` executa `python -m app.cli bootstrap --skip-fastf1` automaticamente na primeira inicialização (`AUTO_BOOTSTRAP=true`).

### Comandos Make para Docker
- `make docker-build` — Constrói as imagens `backend` e `frontend`
- `make docker-up` — Sobe toda a stack com `docker compose up -d --build`
- `make docker-down` — Encerra os containers preservando `./backend/data`
- `make docker-logs` — Acompanha logs de ambos os containers
- `make docker-sync` — Executa sincronização incremental + OpenF1 + recomputação dentro do container
- `make docker-recompute` — Recalcula o modelo estatístico dentro do container
- `make docker-audit` — Imprime relatório de cobertura e rankings do container

### Imagem Única (All-in-One para PaaS)
Para ambientes que esperam um único container servindo API e SPA:

```bash
docker build -t f1-overall:all-in-one .
docker run -d -p 8000:8000 -v $(pwd)/backend/data:/data f1-overall:all-in-one
```

---

## Deploy em Produção (Railway + Vercel)

- **Backend API (Railway)**: Serviço `f1-overall` configurado no diretório `/backend` (branch `develop`), com volume persistente `/data` e URL pública `https://f1-overall-production.up.railway.app`.
- **Frontend SPA + Proxy `/api` (Vercel)**: Os arquivos `vercel.json` (raiz) e `frontend/vercel.json` já redirecionam `/api/:path*` para `https://f1-overall-production.up.railway.app/api/:path*` e encaminham rotas do React Router para `/index.html`.
  1. Faça push da branch `develop` (ou merge em `main`): `git push origin develop`
  2. No painel da **Vercel**, importe o repositório `rodrigop07/f1-overall` selecionando a branch `develop` (funciona tanto deixando **Root Directory** na raiz `./` quanto escolhendo `frontend`) e clique em **Deploy**.
