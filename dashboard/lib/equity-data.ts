// Mock equity curve data based on actual backtest results
export const generateEquityCurveData = (backtestId: string) => {
  // Base BTC performance (moderate growth with volatility)
  const btcData = [];
  let btcValue = 0; // Starting at 0% return
  const btcDrift = 0.0003; // ~28% annual return
  const btcVolatility = 0.045;

  // Strategy performance data based on backtest results
  const strategyParams = {
    "backtest_results_20260213_092907.pkl": {
      finalReturn: 0.931, // 93.1% total return
      sharpe: 3.12,
      volatility: 0.20, // Lower volatility than BTC
      maxDD: -0.114
    },
    "backtest_results_20260212_115554.pkl": {
      finalReturn: 0.954, // 95.4% total return
      sharpe: 3.31,
      volatility: 0.19,
      maxDD: -0.101
    },
    "backtest_results_20260212_114803.pkl": {
      finalReturn: 1.066, // 106.6% total return (but validation failed)
      sharpe: 5.56,
      volatility: 0.31, // Higher volatility explaining the validation failure
      maxDD: -0.105
    }
  };

  const params = strategyParams[backtestId as keyof typeof strategyParams] || strategyParams["backtest_results_20260213_092907.pkl"];

  const strategyData = [];
  let strategyValue = 0;
  const strategyDrift = params.finalReturn / 408; // Daily drift to reach final return
  const strategyVolatility = params.volatility / Math.sqrt(252); // Daily volatility

  // Generate 408 days of data (from backtest period: 2023-01-01 to 2024-02-13)
  const startDate = new Date('2023-01-01');
  const dates = [];

  for (let i = 0; i < 408; i++) {
    const currentDate = new Date(startDate);
    currentDate.setDate(startDate.getDate() + i);
    dates.push(currentDate.toISOString().split('T')[0]);

    // BTC random walk with drift
    const btcReturn = btcDrift + btcVolatility * (Math.random() - 0.5);
    btcValue += btcReturn;
    btcData.push(btcValue);

    // Strategy returns with mean reversion and lower correlation to BTC
    const strategyReturn = strategyDrift + strategyVolatility * (Math.random() - 0.5) * 0.7; // Lower correlation

    // Add some mean reversion characteristic of stat arb
    if (i > 20) {
      const recentPerf = strategyValue;
      const meanReversionFactor = -0.0001 * recentPerf; // Pull towards mean
      strategyValue += strategyReturn + meanReversionFactor;
    } else {
      strategyValue += strategyReturn;
    }

    strategyData.push(strategyValue);
  }

  // Create final data structure
  return dates.map((date, i) => ({
    date,
    strategy: strategyData[i],
    btc: btcData[i],
  }));
};

// Additional chart for drawdown visualization
export const generateDrawdownData = (backtestId: string) => {
  const equityData = generateEquityCurveData(backtestId);

  // Calculate running maximum and drawdown for strategy
  let strategyMax = 0;
  const strategyDrawdowns = [];

  // Calculate running maximum and drawdown for BTC
  let btcMax = 0;
  const btcDrawdowns = [];

  equityData.forEach((point) => {
    // Strategy drawdown
    if (point.strategy > strategyMax) {
      strategyMax = point.strategy;
    }
    const strategyDrawdown = (point.strategy - strategyMax) / (1 + strategyMax);
    strategyDrawdowns.push(strategyDrawdown);

    // BTC drawdown
    if (point.btc > btcMax) {
      btcMax = point.btc;
    }
    const btcDrawdown = (point.btc - btcMax) / (1 + btcMax);
    btcDrawdowns.push(btcDrawdown);
  });

  return equityData.map((point, i) => ({
    date: point.date,
    strategyDrawdown: strategyDrawdowns[i],
    btcDrawdown: btcDrawdowns[i],
  }));
};