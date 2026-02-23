import { NavHeader } from "@/components/layout/nav-header";

export default function DashboardPage() {
  const metrics = [
    { label: "Annual Return", value: "61.4%", period: "YTD" },
    { label: "Sharpe Ratio", value: "3.12", period: "12M" },
    { label: "Max Drawdown", value: "11.4%", period: "Peak" },
    { label: "Active Pairs", value: "3", period: "Current" },
  ];

  const positions = [
    { pair: "XLM/XRP", pnl: "+2.25%", status: "ACTIVE" },
    { pair: "ETH/SOL", pnl: "+0.78%", status: "ACTIVE" },
    { pair: "BCH/TRX", pnl: "+1.75%", status: "ACTIVE" },
  ];

  return (
    <>
      <NavHeader />
      <main className="mx-auto max-w-7xl px-6 py-12">
        <div className="mb-12">
          <h1 className="text-2xl font-medium text-neutral-900 mb-2">
            Statistical Arbitrage
          </h1>
          <p className="text-neutral-600">
            Institutional-grade pairs trading platform
          </p>
        </div>

        <div className="grid grid-cols-4 gap-8 mb-16">
          {metrics.map((metric, index) => (
            <div key={index} className="text-center">
              <div className="text-3xl font-light text-neutral-900 mb-1">
                {metric.value}
              </div>
              <div className="text-sm text-neutral-600 mb-1">
                {metric.label}
              </div>
              <div className="text-xs text-neutral-400">
                {metric.period}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-16">
          <div>
            <h2 className="text-lg font-medium text-neutral-900 mb-6">
              Performance
            </h2>
            <div className="h-64 bg-neutral-50 border border-neutral-200 flex items-center justify-center">
              <div className="text-center text-neutral-400">
                <div className="mb-2">Chart Placeholder</div>
                <div className="text-xs">Real-time data when connected</div>
              </div>
            </div>
          </div>

          <div>
            <h2 className="text-lg font-medium text-neutral-900 mb-6">
              Active Positions
            </h2>
            <div className="space-y-4">
              {positions.map((position, index) => (
                <div key={index} className="flex justify-between items-center py-3 border-b border-neutral-100 last:border-b-0">
                  <div>
                    <div className="font-medium text-neutral-900">
                      {position.pair}
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      {position.status}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-neutral-900">
                      {position.pnl}
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      SIMULATED
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}