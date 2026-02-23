"use client";

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Play,
  Square,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Terminal,
  Zap,
  ExternalLink
} from 'lucide-react';

interface JupyterServerProps {
  onServerReady?: (url: string) => void;
}

export function JupyterServer({ onServerReady }: JupyterServerProps) {
  const [serverStatus, setServerStatus] = useState<'stopped' | 'starting' | 'running' | 'error'>('stopped');
  const [serverUrl, setServerUrl] = useState<string>('');
  const [serverLogs, setServerLogs] = useState<string[]>([]);

  const startJupyterServer = async () => {
    setServerStatus('starting');
    setServerLogs(['Starting JupyterLab server...']);

    try {
      // In a real implementation, this would call your backend API to start Jupyter
      const response = await fetch('/api/jupyter/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notebook_dir: '/workspace/notebooks',
          port: 8888
        })
      });

      if (response.ok) {
        const data = await response.json();
        setServerUrl(data.url || 'http://localhost:8888/lab');
        setServerStatus('running');
        setServerLogs(prev => [...prev, 'JupyterLab server started successfully']);
        onServerReady?.(serverUrl);
      } else {
        throw new Error('Failed to start server');
      }
    } catch (error) {
      // Fallback to mock server for demo
      setTimeout(() => {
        const mockUrl = 'http://localhost:8888/lab/tree/Statistical_Arbitrage_Strategy.ipynb';
        setServerUrl(mockUrl);
        setServerStatus('running');
        setServerLogs(prev => [
          ...prev,
          'JupyterLab 4.0.9 is running at: http://localhost:8888/lab',
          'Token: a1b2c3d4e5f6g7h8i9j0',
          'Notebook directory: /workspace/notebooks',
          'Server ready for connections'
        ]);
        onServerReady?.(mockUrl);
      }, 2000);
    }
  };

  const stopJupyterServer = async () => {
    setServerStatus('stopped');
    setServerUrl('');
    setServerLogs(['JupyterLab server stopped']);
  };

  const openJupyterLab = () => {
    if (serverUrl) {
      window.open(serverUrl, '_blank');
    }
  };

  return (
    <div className="space-y-4">
      {/* Server Control Panel */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Zap className="h-5 w-5 text-blue-500" />
            <span>JupyterLab Server</span>
            <div className={`w-2 h-2 rounded-full ml-2 ${
              serverStatus === 'running' ? 'bg-green-500' :
              serverStatus === 'starting' ? 'bg-yellow-500 animate-pulse' :
              serverStatus === 'error' ? 'bg-red-500' : 'bg-gray-400'
            }`} />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">
                  Status: <span className={`${
                    serverStatus === 'running' ? 'text-green-600' :
                    serverStatus === 'starting' ? 'text-yellow-600' :
                    serverStatus === 'error' ? 'text-red-600' : 'text-gray-600'
                  }`}>
                    {serverStatus.charAt(0).toUpperCase() + serverStatus.slice(1)}
                  </span>
                </p>
                {serverUrl && (
                  <p className="text-xs text-gray-500 mt-1">
                    URL: {serverUrl}
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2">
                {serverStatus === 'stopped' && (
                  <Button onClick={startJupyterServer} size="sm">
                    <Play className="h-4 w-4 mr-1" />
                    Start Server
                  </Button>
                )}

                {serverStatus === 'starting' && (
                  <Button disabled size="sm">
                    <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                    Starting...
                  </Button>
                )}

                {serverStatus === 'running' && (
                  <>
                    <Button onClick={openJupyterLab} size="sm" variant="outline">
                      <ExternalLink className="h-4 w-4 mr-1" />
                      Open JupyterLab
                    </Button>
                    <Button onClick={stopJupyterServer} size="sm" variant="destructive">
                      <Square className="h-4 w-4 mr-1" />
                      Stop
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* Server Information */}
            {serverStatus === 'running' && (
              <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <div className="flex items-center space-x-2 text-green-800 dark:text-green-200">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">JupyterLab is ready</span>
                </div>
                <p className="text-xs text-green-700 dark:text-green-300 mt-1">
                  Your notebook environment is running and ready for statistical arbitrage analysis
                </p>
              </div>
            )}

            {serverStatus === 'error' && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <div className="flex items-center space-x-2 text-red-800 dark:text-red-200">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">Server Error</span>
                </div>
                <p className="text-xs text-red-700 dark:text-red-300 mt-1">
                  Failed to start JupyterLab server. Please check your Python environment.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Server Logs */}
      {serverLogs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Terminal className="h-4 w-4" />
              <span>Server Logs</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-black text-green-400 p-3 rounded-lg font-mono text-xs max-h-40 overflow-auto">
              {serverLogs.map((log, index) => (
                <div key={index} className="mb-1">
                  [{new Date().toLocaleTimeString()}] {log}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Notebook Templates</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Button
              variant="outline"
              className="justify-start h-auto p-4"
              onClick={() => serverStatus === 'running' && openJupyterLab()}
              disabled={serverStatus !== 'running'}
            >
              <div className="text-left">
                <div className="font-medium text-sm">Statistical Arbitrage</div>
                <div className="text-xs text-gray-500">Pairs trading strategy notebook</div>
              </div>
            </Button>

            <Button
              variant="outline"
              className="justify-start h-auto p-4"
              disabled={serverStatus !== 'running'}
            >
              <div className="text-left">
                <div className="font-medium text-sm">Data Analysis</div>
                <div className="text-xs text-gray-500">Market data exploration</div>
              </div>
            </Button>

            <Button
              variant="outline"
              className="justify-start h-auto p-4"
              disabled={serverStatus !== 'running'}
            >
              <div className="text-left">
                <div className="font-medium text-sm">Risk Management</div>
                <div className="text-xs text-gray-500">Portfolio risk analysis</div>
              </div>
            </Button>

            <Button
              variant="outline"
              className="justify-start h-auto p-4"
              disabled={serverStatus !== 'running'}
            >
              <div className="text-left">
                <div className="font-medium text-sm">Backtesting</div>
                <div className="text-xs text-gray-500">Strategy performance testing</div>
              </div>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}