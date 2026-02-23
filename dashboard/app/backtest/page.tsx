"use client";

import { useState } from "react";
import { NavHeader } from "@/components/layout/nav-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Play, Download, Settings, TrendingUp, TrendingDown, Activity, Clock } from "lucide-react";
import { format } from "date-fns";
import { EquityCurve } from "@/components/charts/equity-curve";
import { generateEquityCurveData, generateDrawdownData } from "@/lib/equity-data";

export default function BacktestPage() {
  const [selectedBacktest, setSelectedBacktest] = useState(0);

  const backtests = [
    {
      id: "backtest_results_20260213_092907.pkl",
      date: new Date("2026-02-13T09:29:07"),
      status: "completed",
      annualReturn: 61.4,
      sharpe: 3.12,
      maxDrawdown: -11.4,
      totalReturn: 93.1,
      viablePairs: 30,
      validation: "passed",
    },
    {
      id: "backtest_results_20260212_115554.pkl",
      date: new Date("2026-02-12T11:55:54"),
      status: "completed",
      annualReturn: 62.2,
      sharpe: 3.31,
      maxDrawdown: -10.1,
      totalReturn: 95.4,
      viablePairs: 30,
      validation: "passed",
    },
    {
      id: "backtest_results_20260212_114803.pkl",
      date: new Date("2026-02-12T11:48:03"),
      status: "completed",
      annualReturn: 171.5,
      sharpe: 5.56,
      maxDrawdown: -10.5,
      totalReturn: 106.6,
      viablePairs: 30,
      validation: "failed",
    },
  ];

  const currentBacktest = backtests[selectedBacktest];

  return (
    <>
      <NavHeader />
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold tracking-tight">Backtest</h2>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm">
              <Settings className="mr-2 h-4 w-4" />
              Configure
            </Button>
            <Button size="sm">
              <Play className="mr-2 h-4 w-4" />
              Run New Backtest
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {backtests.map((bt, index) => (
            <Card
              key={bt.id}
              className={`cursor-pointer ${selectedBacktest === index ? "border-primary" : ""}`}
              onClick={() => setSelectedBacktest(index)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {format(bt.date, "MMM dd, yyyy HH:mm")}
                  </CardTitle>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      bt.validation === "passed"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {bt.validation === "passed" ? "✓ Valid" : "✗ Invalid"}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Annual Return</span>
                    <span className="font-medium">{bt.annualReturn}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Sharpe Ratio</span>
                    <span className="font-medium">{bt.sharpe}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Max Drawdown</span>
                    <span className="font-medium text-red-600">{bt.maxDrawdown}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs defaultValue="performance" className="space-y-4">
          <TabsList>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="pairs">Trading Pairs</TabsTrigger>
            <TabsTrigger value="trades">Trade History</TabsTrigger>
            <TabsTrigger value="validation">Validation</TabsTrigger>
          </TabsList>

          <TabsContent value="performance" className="space-y-4">
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Annual Return</CardTitle>
                  <TrendingUp className="h-4 w-4 text-green-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{currentBacktest.annualReturn}%</div>
                  <p className="text-xs text-muted-foreground">Target: {'>'}25%</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Sharpe Ratio</CardTitle>
                  <Activity className="h-4 w-4 text-blue-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{currentBacktest.sharpe}</div>
                  <p className="text-xs text-muted-foreground">Target: {'>'}1.0</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Max Drawdown</CardTitle>
                  <TrendingDown className="h-4 w-4 text-red-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{currentBacktest.maxDrawdown}%</div>
                  <p className="text-xs text-muted-foreground">Target: &lt;15%</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Return</CardTitle>
                  <TrendingUp className="h-4 w-4 text-green-600" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{currentBacktest.totalReturn}%</div>
                  <p className="text-xs text-muted-foreground">Full period</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Equity Curve vs BTC</CardTitle>
                  <CardDescription>Portfolio performance vs Bitcoin benchmark</CardDescription>
                </CardHeader>
                <CardContent>
                  <EquityCurve strategyData={generateEquityCurveData(currentBacktest.id)} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Drawdown Analysis</CardTitle>
                  <CardDescription>Maximum drawdown periods</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center p-3 bg-red-50 dark:bg-red-900/20 rounded">
                      <div>
                        <p className="font-medium text-red-900 dark:text-red-100">Strategy Max Drawdown</p>
                        <p className="text-sm text-red-700 dark:text-red-300">Worst peak-to-trough decline</p>
                      </div>
                      <span className="text-lg font-bold text-red-600">{currentBacktest.maxDrawdown}%</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded">
                      <div>
                        <p className="font-medium text-orange-900 dark:text-orange-100">BTC Max Drawdown</p>
                        <p className="text-sm text-orange-700 dark:text-orange-300">Benchmark comparison</p>
                      </div>
                      <span className="text-lg font-bold text-orange-600">-18.2%</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-green-50 dark:bg-green-900/20 rounded">
                      <div>
                        <p className="font-medium text-green-900 dark:text-green-100">Recovery Time</p>
                        <p className="text-sm text-green-700 dark:text-green-300">Average time to recover</p>
                      </div>
                      <span className="text-lg font-bold text-green-600">8.3 days</span>
                    </div>
                    <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                      <p className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-1">Risk-Adjusted Performance</p>
                      <p className="text-xs text-blue-700 dark:text-blue-300">Strategy achieves {currentBacktest.annualReturn}% returns with {Math.abs(currentBacktest.maxDrawdown)}% max drawdown, significantly outperforming BTC's risk-return profile.</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="pairs" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Selected Trading Pairs</CardTitle>
                <CardDescription>{currentBacktest.viablePairs} pairs selected from universe</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-4 gap-4 text-sm font-medium text-muted-foreground">
                    <div>Pair</div>
                    <div>Tier</div>
                    <div>Score</div>
                    <div>ADF p-value</div>
                  </div>
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div className="font-medium">XLM-XRP</div>
                    <div>Tier 1</div>
                    <div>95.2</div>
                    <div>0.0001</div>
                  </div>
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div className="font-medium">ETH-SOL</div>
                    <div>Tier 1</div>
                    <div>86.3</div>
                    <div>0.0012</div>
                  </div>
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div className="font-medium">BCH-TRX</div>
                    <div>Tier 1</div>
                    <div>85.9</div>
                    <div>0.0015</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="trades" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Trade History</CardTitle>
                <CardDescription>Recent trades from backtest</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-muted-foreground">
                  Trade history will be displayed here
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="validation" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Strategy Validation</CardTitle>
                <CardDescription>Validation checks against strategy requirements</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <p className="font-medium">Annual Return &gt; 25%</p>
                      <p className="text-sm text-muted-foreground">Target minimum return</p>
                    </div>
                    <span className={currentBacktest.annualReturn > 25 ? "text-green-600" : "text-red-600"}>
                      {currentBacktest.annualReturn > 25 ? "✓ PASS" : "✗ FAIL"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <p className="font-medium">Sharpe Ratio &gt; 1.0</p>
                      <p className="text-sm text-muted-foreground">Risk-adjusted performance</p>
                    </div>
                    <span className={currentBacktest.sharpe > 1.0 ? "text-green-600" : "text-red-600"}>
                      {currentBacktest.sharpe > 1.0 ? "✓ PASS" : "✗ FAIL"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <p className="font-medium">Max Drawdown &lt; 15%</p>
                      <p className="text-sm text-muted-foreground">Maximum acceptable loss</p>
                    </div>
                    <span className={Math.abs(currentBacktest.maxDrawdown) < 15 ? "text-green-600" : "text-red-600"}>
                      {Math.abs(currentBacktest.maxDrawdown) < 15 ? "✓ PASS" : "✗ FAIL"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <p className="font-medium">Sharpe Ratio &lt; 3.5</p>
                      <p className="text-sm text-muted-foreground">Realistic performance check</p>
                    </div>
                    <span className={currentBacktest.sharpe < 3.5 ? "text-green-600" : "text-red-600"}>
                      {currentBacktest.sharpe < 3.5 ? "✓ PASS" : "✗ FAIL"}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </>
  );
}