# Stat Arb Platform Dashboard

A modern web dashboard for the Statistical Arbitrage Trading Platform, built with Next.js 14, TypeScript, and Tailwind CSS.

## Features

- **Research**: Interactive Jupyter-like notebook for strategy development
- **Backtest**: Visualize and analyze backtest results
- **Execution**: Monitor and control live trading
- **Real-time Updates**: WebSocket integration for live data
- **Modern UI**: Clean, responsive interface matching infrastructure-sigmatic style

## Getting Started

### 1. Install Dependencies

```bash
cd dashboard
npm install
```

### 2. Start the Python API Server

In the parent directory:

```bash
python3 api_server.py
```

This will start the FastAPI server on http://localhost:8000

### 3. Run the Dashboard

```bash
npm run dev
```

Open http://localhost:3000 in your browser.

## Pages

### Overview (`/`)
- Dashboard with key metrics
- Recent performance chart
- Active strategies overview

### Research (`/research`)
- Python notebook interface
- Strategy code editor
- Analysis visualizations

### Backtest (`/backtest`)
- View historical backtest results
- Performance metrics and validation
- Trading pairs analysis
- Equity curve visualization

### Execution (`/execution`)
- Live trading control (Start/Pause/Stop)
- Open positions monitoring
- Trade history
- Risk management dashboard

## Architecture

```
dashboard/
├── app/                    # Next.js app directory
│   ├── api/               # API routes
│   ├── research/          # Research page
│   ├── backtest/          # Backtest page
│   ├── execution/         # Execution page
│   └── layout.tsx         # Root layout
├── components/
│   ├── ui/                # Reusable UI components
│   └── layout/            # Layout components
└── lib/                   # Utilities
```

## API Integration

The dashboard connects to the Python backend via:
- REST API endpoints for data fetching
- WebSocket for real-time updates (planned)

## Development

### Add New Components

UI components are in `components/ui/` and follow the shadcn/ui pattern.

### API Routes

API routes in `app/api/` proxy requests to the Python backend.

## Production

Build for production:

```bash
npm run build
npm start
```

## Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```