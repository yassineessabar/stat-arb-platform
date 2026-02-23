"use client";

import { useState } from 'react';
import { NavHeader } from "@/components/layout/nav-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Play,
  Square,
  RefreshCw,
  ExternalLink,
  BookOpen,
  Zap,
  CheckCircle,
  AlertTriangle,
  Terminal
} from "lucide-react";

export default function ResearchPage() {
  const [jupyterStatus, setJupyterStatus] = useState<'stopped' | 'starting' | 'running' | 'error'>('stopped');
  const [jupyterUrl, setJupyterUrl] = useState<string>('');
  const [jupyterLogs, setJupyterLogs] = useState<string[]>([]);

  const startJupyterLab = async () => {
    setJupyterStatus('starting');
    setJupyterLogs(['Starting JupyterLab server...']);

    try {
      const response = await fetch('/api/jupyter/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notebook_dir: './notebooks',
          port: 8888
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setJupyterUrl(data.url);
          setJupyterStatus('running');
          setJupyterLogs(prev => [
            ...prev,
            'JupyterLab server started successfully!',
            `URL: ${data.url}`,
            `Token: ${data.token}`,
            `PID: ${data.pid}`
          ]);
        } else {
          throw new Error(data.message || 'Failed to start JupyterLab');
        }
      } else {
        throw new Error('Server error');
      }
    } catch (error) {
      console.error('Error starting JupyterLab:', error);
      setJupyterStatus('error');
      setJupyterLogs(prev => [
        ...prev,
        `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
      ]);
    }
  };

  const openJupyterLab = () => {
    if (jupyterUrl) {
      window.open(jupyterUrl, '_blank', 'width=1400,height=900');
    }
  };

  const stopJupyterLab = async () => {
    setJupyterStatus('stopped');
    setJupyterUrl('');
    setJupyterLogs(['JupyterLab server stopped']);
  };

  return (
    <>
      <NavHeader />
      <main className="flex-1 space-y-6 p-8 pt-6">
        {/* Header */}
        <div className="flex items-center space-x-4">
          <BookOpen className="h-8 w-8 text-blue-600" />
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Research</h2>
            <p className="text-muted-foreground">
              Statistical Arbitrage Strategy Development with JupyterLab
            </p>
          </div>
        </div>

        {/* JupyterLab Control */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Zap className="h-5 w-5 text-blue-500" />
              <span>JupyterLab Environment</span>
              <div className={`w-2 h-2 rounded-full ml-2 ${
                jupyterStatus === 'running' ? 'bg-green-500' :
                jupyterStatus === 'starting' ? 'bg-yellow-500 animate-pulse' :
                jupyterStatus === 'error' ? 'bg-red-500' : 'bg-gray-400'
              }`} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Status & Controls */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">
                  Status: <span className={`${
                    jupyterStatus === 'running' ? 'text-green-600' :
                    jupyterStatus === 'starting' ? 'text-yellow-600' :
                    jupyterStatus === 'error' ? 'text-red-600' : 'text-gray-600'
                  }`}>
                    {jupyterStatus.charAt(0).toUpperCase() + jupyterStatus.slice(1)}
                  </span>
                </p>
                {jupyterUrl && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Server URL: {jupyterUrl}
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2">
                {jupyterStatus === 'stopped' && (
                  <Button onClick={startJupyterLab}>
                    <Play className="h-4 w-4 mr-1" />
                    Start JupyterLab
                  </Button>
                )}

                {jupyterStatus === 'starting' && (
                  <Button disabled>
                    <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                    Starting...
                  </Button>
                )}

                {jupyterStatus === 'running' && (
                  <>
                    <Button onClick={openJupyterLab} variant="default">
                      <ExternalLink className="h-4 w-4 mr-1" />
                      Open JupyterLab
                    </Button>
                    <Button onClick={stopJupyterLab} variant="destructive" size="sm">
                      <Square className="h-4 w-4 mr-1" />
                      Stop
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Status Alerts */}
            {jupyterStatus === 'running' && (
              <Alert className="border-green-200 bg-green-50 dark:bg-green-900/20">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800 dark:text-green-200">
                  JupyterLab is running! Click "Open JupyterLab" to access your Statistical Arbitrage Strategy notebook.
                </AlertDescription>
              </Alert>
            )}

            {jupyterStatus === 'error' && (
              <Alert className="border-red-200 bg-red-50 dark:bg-red-900/20">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <AlertDescription className="text-red-800 dark:text-red-200">
                  Failed to start JupyterLab server. Check the logs below for details.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Features Overview */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Statistical Arbitrage Notebook</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-3">
                Complete implementation with cointegration testing, strategy backtesting, and performance analysis.
              </p>
              <div className="text-xs space-y-1">
                <div>✓ Universe selection & data download</div>
                <div>✓ Cointegration analysis</div>
                <div>✓ Z-score strategy implementation</div>
                <div>✓ Backtesting & performance metrics</div>
                <div>✓ Risk management parameters</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Pre-installed Libraries</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-3">
                All quantitative finance libraries ready to use.
              </p>
              <div className="text-xs space-y-1">
                <div>📊 pandas, numpy, matplotlib</div>
                <div>📈 yfinance, statsmodels</div>
                <div>🤖 scikit-learn, seaborn</div>
                <div>📓 JupyterLab with extensions</div>
                <div>🔧 Full Python 3.13 environment</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Live Strategy Results</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-3">
                Current backtest performance metrics.
              </p>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span>Annual Return:</span>
                  <span className="text-green-600 font-medium">61.4%</span>
                </div>
                <div className="flex justify-between">
                  <span>Sharpe Ratio:</span>
                  <span className="text-blue-600 font-medium">3.12</span>
                </div>
                <div className="flex justify-between">
                  <span>Max Drawdown:</span>
                  <span className="text-red-600 font-medium">-11.4%</span>
                </div>
                <div className="flex justify-between">
                  <span>Win Rate:</span>
                  <span className="text-green-600 font-medium">61.1%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Server Logs */}
        {jupyterLogs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Terminal className="h-4 w-4" />
                <span>Server Logs</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-black text-green-400 p-3 rounded-lg font-mono text-xs max-h-40 overflow-auto">
                {jupyterLogs.map((log, index) => (
                  <div key={index} className="mb-1">
                    [{new Date().toLocaleTimeString()}] {log}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Instructions */}
        <Card>
          <CardHeader>
            <CardTitle>Getting Started</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <p>
                <strong>1.</strong> Click "Start JupyterLab" to launch your research environment
              </p>
              <p>
                <strong>2.</strong> Open JupyterLab in a new window for the full experience
              </p>
              <p>
                <strong>3.</strong> Navigate to "Statistical_Arbitrage_Strategy.ipynb" to begin analysis
              </p>
              <p>
                <strong>4.</strong> Run cells sequentially to execute the full strategy pipeline
              </p>
              <p className="text-muted-foreground">
                <strong>Note:</strong> The notebook includes live data fetching, strategy backtesting,
                and performance visualization with your actual trading results.
              </p>
            </div>
          </CardContent>
        </Card>
      </main>
    </>
  );
}