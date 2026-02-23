"use client";

import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface CellOutput {
  output_type: string;
  text?: string[];
  data?: {
    'text/plain'?: string[];
    'text/html'?: string[];
    'image/png'?: string;
    'application/json'?: any;
  };
  name?: string;
  traceback?: string[];
}

interface NotebookCell {
  cell_type: 'code' | 'markdown' | 'raw';
  source: string | string[];
  execution_count?: number | null;
  outputs?: CellOutput[];
  metadata?: any;
}

interface JupyterViewerProps {
  notebook: {
    cells: NotebookCell[];
    metadata?: any;
    nbformat?: number;
    nbformat_minor?: number;
  };
}

export function JupyterViewer({ notebook }: JupyterViewerProps) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);
  const renderOutput = (output: CellOutput) => {
    if (output.output_type === 'stream') {
      return (
        <pre className="bg-gray-900 text-gray-100 p-2 text-xs overflow-x-auto">
          {output.text?.join('')}
        </pre>
      );
    }

    if (output.output_type === 'execute_result' || output.output_type === 'display_data') {
      if (output.data?.['image/png']) {
        return (
          <img
            src={`data:image/png;base64,${output.data['image/png']}`}
            alt="Output"
            className="max-w-full"
          />
        );
      }
      if (output.data?.['text/html']) {
        return (
          <div
            className="overflow-x-auto"
            dangerouslySetInnerHTML={{ __html: output.data['text/html'].join('') }}
          />
        );
      }
      if (output.data?.['text/plain']) {
        return (
          <pre className="bg-gray-900 text-gray-100 p-2 text-xs overflow-x-auto">
            {output.data['text/plain'].join('\n')}
          </pre>
        );
      }
    }

    if (output.output_type === 'error') {
      return (
        <pre className="bg-red-900/20 text-red-400 p-2 text-xs overflow-x-auto border border-red-500/50">
          {output.traceback?.join('\n')}
        </pre>
      );
    }

    return null;
  };

  const getSourceString = (source: string | string[]) => {
    return Array.isArray(source) ? source.join('') : source;
  };

  return (
    <div className="space-y-1">
      {notebook.cells.map((cell, index) => (
        <div key={index} className="group relative">
          <div className="flex">
            {/* Cell number/type indicator */}
            <div className="w-20 flex-shrink-0 pr-4 text-right">
              {cell.cell_type === 'code' && (
                <span className="text-xs text-muted-foreground">
                  [{cell.execution_count ?? ' '}]:
                </span>
              )}
              {cell.cell_type === 'markdown' && (
                <span className="text-xs text-muted-foreground italic">
                  md:
                </span>
              )}
            </div>

            {/* Cell content */}
            <div className="flex-1 min-w-0">
              {cell.cell_type === 'markdown' ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={{
                      code: ({ inline, className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || '');
                        return !inline && match && isMounted ? (
                          <SyntaxHighlighter
                            style={vscDarkPlus}
                            language={match[1]}
                            PreTag="div"
                            className="text-xs"
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        ) : (
                          <code className="bg-gray-800 px-1 py-0.5 rounded text-xs" {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {getSourceString(cell.source)}
                  </ReactMarkdown>
                </div>
              ) : cell.cell_type === 'code' ? (
                <div>
                  <div className="bg-gray-900 rounded-md overflow-hidden">
                    {isMounted ? (
                      <SyntaxHighlighter
                        language="python"
                        style={vscDarkPlus}
                        customStyle={{
                          margin: 0,
                          padding: '0.5rem',
                          fontSize: '0.75rem',
                          lineHeight: '1.5',
                        }}
                      >
                        {getSourceString(cell.source)}
                      </SyntaxHighlighter>
                    ) : (
                      <pre className="bg-gray-900 text-gray-100 p-2 text-xs overflow-x-auto rounded-md">
                        {getSourceString(cell.source)}
                      </pre>
                    )}
                  </div>
                  {cell.outputs && cell.outputs.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {cell.outputs.map((output, outputIdx) => (
                        <div key={outputIdx}>
                          {renderOutput(output)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <pre className="bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto">
                  {getSourceString(cell.source)}
                </pre>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}