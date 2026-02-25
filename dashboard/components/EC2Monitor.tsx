import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, Terminal, Cloud, AlertCircle, CheckCircle, XCircle, Upload } from 'lucide-react';

interface EC2Log {
    timestamp: string;
    message: string;
    type: 'info' | 'error' | 'warning' | 'buy' | 'sell' | 'profit' | 'loss';
}

interface EC2MonitorProps {
    onConnectionChange?: (connected: boolean) => void;
}

export default function EC2Monitor({ onConnectionChange }: EC2MonitorProps) {
    const [connected, setConnected] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [logs, setLogs] = useState<EC2Log[]>([]);
    const [instanceId, setInstanceId] = useState('');
    const [host, setHost] = useState('');
    const [username, setUsername] = useState('ubuntu');
    const [keyFile, setKeyFile] = useState<File | null>(null);
    const [error, setError] = useState('');
    const [isRunning, setIsRunning] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const scrollAreaRef = useRef<HTMLDivElement>(null);

    // Poll for logs when connected
    useEffect(() => {
        if (!connected || !instanceId) return;

        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/ec2/logs?instanceId=${instanceId}`);
                const data = await response.json();

                if (data.logs) {
                    setLogs(data.logs);
                    // Auto-scroll to bottom
                    if (scrollAreaRef.current) {
                        scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
                    }
                }
            } catch (error) {
                console.error('Error fetching logs:', error);
            }
        }, 2000); // Poll every 2 seconds

        return () => clearInterval(interval);
    }, [connected, instanceId]);

    // Check bot status
    useEffect(() => {
        if (!connected || !instanceId) return;

        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/ec2/status?instanceId=${instanceId}`);
                const data = await response.json();
                setIsRunning(data.isRunning);
            } catch (error) {
                console.error('Error checking status:', error);
            }
        }, 5000); // Check every 5 seconds

        return () => clearInterval(interval);
    }, [connected, instanceId]);

    const handleConnect = async () => {
        if (!host || !keyFile) {
            setError('Please provide EC2 host and private key file');
            return;
        }

        setConnecting(true);
        setError('');

        const formData = new FormData();
        formData.append('host', host);
        formData.append('username', username);
        formData.append('instanceId', instanceId || host);
        formData.append('keyFile', keyFile);

        try {
            const response = await fetch('/api/ec2/connect', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (response.ok) {
                setConnected(true);
                setInstanceId(data.instanceId);
                onConnectionChange?.(true);
            } else {
                setError(data.error || 'Failed to connect');
            }
        } catch (error) {
            setError('Connection failed: ' + (error as Error).message);
        } finally {
            setConnecting(false);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setKeyFile(file);
        }
    };

    const getLogColor = (type: string) => {
        switch (type) {
            case 'error': return 'text-red-500';
            case 'warning': return 'text-yellow-500';
            case 'buy': return 'text-green-500';
            case 'sell': return 'text-red-400';
            case 'profit': return 'text-green-600 font-bold';
            case 'loss': return 'text-red-600 font-bold';
            default: return 'text-gray-300';
        }
    };

    const getLogIcon = (type: string) => {
        switch (type) {
            case 'error': return '❌';
            case 'warning': return '⚠️';
            case 'buy': return '🟢';
            case 'sell': return '🔴';
            case 'profit': return '💰';
            case 'loss': return '⛔';
            default: return '📝';
        }
    };

    return (
        <Card className="w-full">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Cloud className="w-5 h-5" />
                        <CardTitle>EC2 Instance Monitor</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        {connected && (
                            <Badge variant={isRunning ? "default" : "secondary"}>
                                {isRunning ? 'Bot Running' : 'Bot Stopped'}
                            </Badge>
                        )}
                        <Badge variant={connected ? "default" : "outline"}>
                            {connected ? 'Connected' : 'Disconnected'}
                        </Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {!connected ? (
                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium">EC2 Public IP or DNS</label>
                            <Input
                                placeholder="e.g., 54.169.123.456 or ec2-54-169-123-456.ap-southeast-1.compute.amazonaws.com"
                                value={host}
                                onChange={(e) => setHost(e.target.value)}
                                className="mt-1"
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium">Username</label>
                            <Input
                                placeholder="ubuntu"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="mt-1"
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium">Private Key File (.pem)</label>
                            <div className="flex gap-2 mt-1">
                                <Button
                                    variant="outline"
                                    onClick={() => fileInputRef.current?.click()}
                                    className="w-full"
                                >
                                    <Upload className="w-4 h-4 mr-2" />
                                    {keyFile ? keyFile.name : 'Select Key File'}
                                </Button>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pem"
                                    onChange={handleFileSelect}
                                    className="hidden"
                                />
                            </div>
                        </div>

                        {error && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        <Button
                            onClick={handleConnect}
                            disabled={connecting}
                            className="w-full"
                        >
                            {connecting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Connecting...
                                </>
                            ) : (
                                <>
                                    <Terminal className="mr-2 h-4 w-4" />
                                    Connect to EC2
                                </>
                            )}
                        </Button>

                        <div className="text-sm text-muted-foreground">
                            <p>📍 Your EC2 details from AWS:</p>
                            <ul className="list-disc list-inside mt-2 space-y-1">
                                <li>Host: <code>ip-172-31-30-186</code></li>
                                <li>Public IP: Check AWS Console</li>
                                <li>Key: Your downloaded .pem file</li>
                            </ul>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <CheckCircle className="w-4 h-4 text-green-500" />
                                <span className="text-sm">Connected to {host}</span>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    setConnected(false);
                                    setLogs([]);
                                    onConnectionChange?.(false);
                                }}
                            >
                                Disconnect
                            </Button>
                        </div>

                        <div className="border rounded-lg bg-black/90 p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-gray-400">Live Logs from EC2</span>
                                <span className="text-xs text-gray-400">{logs.length} messages</span>
                            </div>
                            <ScrollArea className="h-[400px] w-full" ref={scrollAreaRef}>
                                <div className="space-y-1 font-mono text-xs">
                                    {logs.map((log, i) => (
                                        <div
                                            key={i}
                                            className={`flex items-start gap-2 ${getLogColor(log.type)}`}
                                        >
                                            <span className="flex-shrink-0">{getLogIcon(log.type)}</span>
                                            <span className="text-gray-500 flex-shrink-0">
                                                {new Date(log.timestamp).toLocaleTimeString()}
                                            </span>
                                            <span className="break-all">{log.message}</span>
                                        </div>
                                    ))}
                                    {logs.length === 0 && (
                                        <div className="text-gray-500 text-center py-8">
                                            Waiting for logs...
                                        </div>
                                    )}
                                </div>
                            </ScrollArea>
                        </div>

                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span className="text-muted-foreground">Status:</span>
                                <span className="ml-2 font-medium">
                                    {isRunning ? '🟢 Running' : '🔴 Stopped'}
                                </span>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Instance:</span>
                                <span className="ml-2 font-medium">{instanceId}</span>
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}