"use client";

import React, { useState, useEffect } from 'react';
import {
  Play,
  Square,
  Plus,
  Save,
  Download,
  Upload,
  Settings,
  Folder,
  FileText,
  Code,
  Terminal,
  Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { JupyterViewer } from '@/components/notebook/jupyter-viewer';

interface JupyterLabProps {
  notebook: any;
  onNotebookChange?: (notebook: any) => void;
}

export function JupyterLab({ notebook, onNotebookChange }: JupyterLabProps) {
  const [selectedCell, setSelectedCell] = useState(0);
  const [isKernelReady, setIsKernelReady] = useState(true);
  const [executionCount, setExecutionCount] = useState(1);

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Top Menu Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 text-sm font-medium">
            <Zap className="h-4 w-4 text-blue-500" />
            <span>JupyterLab</span>
          </div>
          <div className="h-4 border-l border-gray-300 dark:border-gray-600 mx-2"></div>
          <Button variant="ghost" size="sm">
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <Save className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <Download className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <Upload className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${isKernelReady ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-gray-600 dark:text-gray-300">
              {isKernelReady ? 'Python 3 (ipykernel)' : 'Kernel Disconnected'}
            </span>
          </div>
          <Button variant="ghost" size="sm">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <div className="w-64 bg-white dark:bg-gray-800 border-r flex flex-col">
          {/* Sidebar Tabs */}
          <div className="flex border-b">
            <button className="flex-1 p-2 text-center bg-blue-50 dark:bg-blue-900/20 border-b-2 border-blue-500">
              <Folder className="h-4 w-4 mx-auto mb-1" />
              <span className="text-xs">Files</span>
            </button>
            <button className="flex-1 p-2 text-center hover:bg-gray-50 dark:hover:bg-gray-700">
              <Terminal className="h-4 w-4 mx-auto mb-1" />
              <span className="text-xs">Running</span>
            </button>
          </div>

          {/* File Browser */}
          <div className="flex-1 p-3 overflow-auto">
            <div className="space-y-1">
              <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
                <FileText className="h-4 w-4 text-blue-500" />
                <span className="text-sm">Statistical_Arbitrage_Strategy.ipynb</span>
              </div>
              <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer text-gray-500">
                <Code className="h-4 w-4" />
                <span className="text-sm">data_processing.py</span>
              </div>
              <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer text-gray-500">
                <FileText className="h-4 w-4" />
                <span className="text-sm">requirements.txt</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Notebook Tabs */}
          <div className="flex items-center bg-white dark:bg-gray-800 border-b px-4">
            <div className="flex items-center space-x-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border-t-2 border-blue-500 rounded-t">
              <Code className="h-4 w-4" />
              <span className="text-sm font-medium">Statistical_Arbitrage_Strategy.ipynb</span>
              <button className="ml-2 hover:bg-gray-200 dark:hover:bg-gray-600 p-1 rounded">
                ×
              </button>
            </div>
          </div>

          {/* Notebook Toolbar */}
          <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b">
            <div className="flex items-center space-x-2">
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-1" />
                Cell
              </Button>
              <div className="h-4 border-l border-gray-300 mx-1"></div>
              <Button size="sm" variant="outline">
                <Play className="h-4 w-4 mr-1" />
                Run
              </Button>
              <Button size="sm" variant="outline">
                <Square className="h-4 w-4 mr-1" />
                Stop
              </Button>
              <div className="h-4 border-l border-gray-300 mx-1"></div>
              <select className="px-2 py-1 border rounded text-sm">
                <option>Code</option>
                <option>Markdown</option>
                <option>Raw</option>
              </select>
            </div>

            <div className="text-sm text-gray-600 dark:text-gray-300">
              Last saved: Feb 13, 2024 14:32:15
            </div>
          </div>

          {/* Notebook Content */}
          <div className="flex-1 overflow-auto bg-white dark:bg-gray-900 p-4">
            <div className="max-w-4xl mx-auto">
              <JupyterViewer notebook={notebook} />
            </div>
          </div>
        </div>

        {/* Right Sidebar - Inspector/Property Panel */}
        <div className="w-80 bg-white dark:bg-gray-800 border-l">
          <div className="p-3 border-b">
            <h3 className="font-medium text-sm">Inspector</h3>
          </div>
          <div className="p-3 space-y-4">
            <div>
              <h4 className="text-sm font-medium mb-2">Kernel Info</h4>
              <div className="text-xs space-y-1 text-gray-600 dark:text-gray-300">
                <div>Status: {isKernelReady ? 'Ready' : 'Busy'}</div>
                <div>Language: Python 3.9.0</div>
                <div>Environment: stat-arb-env</div>
                <div>Memory: 1.2 GB / 8.0 GB</div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium mb-2">Cell Metadata</h4>
              <div className="text-xs space-y-1 text-gray-600 dark:text-gray-300">
                <div>Type: Code</div>
                <div>Execution Count: {executionCount}</div>
                <div>Last Run: 14:32:15</div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium mb-2">Variables</h4>
              <div className="text-xs space-y-1 text-gray-600 dark:text-gray-300 max-h-40 overflow-auto">
                <div className="flex justify-between">
                  <span>universe</span>
                  <span className="text-blue-600">list[15]</span>
                </div>
                <div className="flex justify-between">
                  <span>data</span>
                  <span className="text-green-600">DataFrame</span>
                </div>
                <div className="flex justify-between">
                  <span>results</span>
                  <span className="text-purple-600">dict</span>
                </div>
                <div className="flex justify-between">
                  <span>strategy</span>
                  <span className="text-orange-600">PairTradingStrategy</span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium mb-2">Performance</h4>
              <div className="text-xs space-y-1 text-gray-600 dark:text-gray-300">
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
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}