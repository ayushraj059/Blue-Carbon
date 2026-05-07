# Blue Carbon Registry & MRV System

Agentic AI + Blockchain system for measuring, reporting, and verifying blue carbon sequestration in Indian coastal ecosystems.

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │           NGINX (port 80)           │
                        │   /api → backend  /ws → backend     │
                        │         / → frontend                │
                        └────────────┬───────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                             │
    ┌─────────▼──────────┐                      ┌──────────▼──────────┐
    │  FastAPI Backend   │                      │   React Frontend    │
    │  (port 8000)       │                      │   (port 3000)       │
    │                    │                      │  - UploadPanel      │
    │  ┌──────────────┐  │                      │  - PipelineView     │
    │  │  LangGraph   │  │◄─── WebSocket ──────►│  - RegistryTable   │
    │  │  Pipeline    │  │                      │  - OpsPanel         │
    │  └──────┬───────┘  │                      └─────────────────────┘
    │         │          │
    │  ┌──────▼───────┐  │       ┌─────────────┐
    │  │ CrewAI Agents│  │       │  PostgreSQL  │
    │  │              │  │──────►│  (pipeline   │
    │  │ - Collector  │  │       │   runs +     │
    │  │ - Estimator  │  │       │   credits)   │
    │  │ - Verifier   │  │       └─────────────┘
    │  │ - Registry   │  │
    │  │ - OpsMonitor │  │       ┌─────────────┐
    │  └──────┬───────┘  │       │    Redis     │
    │         │          │──────►│  (pub/sub +  │
    │  ┌──────▼───────┐  │       │   metrics)   │
    │  │  Groq LLM    │  │       └─────────────┘
    │  │  (llama-3.3) │  │
    │  └──────┬───────┘  │       ┌─────────────┐
    │         │          │       │  Pinecone    │
    │  ┌──────▼───────┐  │──────►│  (RAG index │
    │  │ RAG Retriever│  │       │   coeffs)   │
    │  └──────────────┘  │       └─────────────┘
    │                    │
    │  ┌──────────────┐  │       ┌─────────────┐
    │  │  Web3.py     │  │──────►│  Polygon    │
    │  │  Blockchain  │  │       │  Mumbai     │
    │  └──────────────┘  │       │  Testnet    │
    └────────────────────┘       └─────────────┘
```

## Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for contract deployment)
- Python 3.11+ (optional, for local dev)
- Free API keys: Groq, Pinecone, Alchemy
- MetaMask wallet with Mumbai testnet MATIC

## Setup (Step by Step)

### 1. Clone the repo
```bash
git clone <your-repo-url>
cd blue-carbon-registry
```

### 2. Deploy Smart Contract
```bash
cd contracts
npm install
npx hardhat compile
# Fund your wallet with test MATIC first (see below)
npx hardhat run scripts/deploy.js --network mumbai
# Note the deployed address printed in terminal
```

### 3. Get Free Test MATIC
Visit: https://faucet.polygon.technology/
- Connect your MetaMask
- Select Mumbai testnet
- Request 0.5 MATIC (enough for many transactions)

### 4. Configure Environment
```bash
cp backend/.env.example .env
# Edit .env and fill in all values:
```

Required `.env` values:
| Variable | Where to get it |
|---|---|
| `GROQ_API_KEY` | console.groq.com |
| `PINECONE_API_KEY` | app.pinecone.io |
| `PINECONE_ENV` | Your Pinecone index region (e.g. `us-east-1`) |
| `ALCHEMY_RPC_URL` | dashboard.alchemy.com → Mumbai RPC |
| `DEPLOYER_PRIVATE_KEY` | MetaMask → Account Details → Export Key |
| `CONTRACT_ADDRESS` | Output from step 2 |
| `SECRET_KEY` | Any 32+ char random string |

### 5. Launch
```bash
docker compose up --build
```

Visit http://localhost and upload `data/sample_sites.csv`

## Sample CSV Format

| site_id | location | vegetation_density | soil_carbon_pct | water_salinity | area_hectares | measurement_date |
|---|---|---|---|---|---|---|
| SB-001 | Sundarbans | 0.82 | 8.4 | 28.5 | 120.0 | 2024-01-15 |

- `vegetation_density`: 0.0–1.0
- `soil_carbon_pct`: 0.5–15.0
- `water_salinity`: 10–45 PSU
- `area_hectares`: > 0

Row `GD-002` in the sample CSV has anomalous values to trigger the verifier.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/upload` | Upload CSV, start pipeline |
| GET | `/api/pipeline/{run_id}` | Get pipeline status |
| GET | `/api/credits` | List all registered credits |
| GET | `/api/credit/{project_id}` | Single credit details |
| GET | `/api/ops` | Agent metrics from Redis |
| GET | `/health` | Health check |
| WS | `/ws/pipeline/{run_id}` | Live pipeline progress stream |

## Carbon Formula

```
carbon_tons = area_hectares × vegetation_density × soil_carbon_pct × 3.67 × ecosystem_multiplier
```

Ecosystem multipliers (from Pinecone RAG):
- Mangrove: 1.8
- Seagrass: 1.4
- Salt marsh: 1.2
- Coastal wetland: 1.1
- Tidal flat: 0.9

## Screenshots

> Add screenshots of the Upload, Pipeline, Registry, and Ops tabs here after running the app.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (async), PostgreSQL, Redis
- **Agents**: CrewAI, LangGraph, Groq (llama-3.3-70b-versatile)
- **RAG**: Pinecone, sentence-transformers (all-MiniLM-L6-v2)
- **Blockchain**: Solidity, Hardhat, Web3.py, Polygon Mumbai
- **Frontend**: React 18, TailwindCSS, Recharts, Axios, WebSocket
- **DevOps**: Docker Compose, Nginx
