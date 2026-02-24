'use client';

import React, { useState } from 'react';
import { X, Server, Cloud, Package, Check, AlertCircle, Cpu, HardDrive, Globe, Shield } from 'lucide-react';

interface DeploymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  strategyConfig: any;
  onDeploy: (deploymentConfig: any) => void;
}

const DeploymentModal: React.FC<DeploymentModalProps> = ({ isOpen, onClose, strategyConfig, onDeploy }) => {
  const [selectedProvider, setSelectedProvider] = useState<'vps' | 'aws' | 'docker' | 'local'>('vps');
  const [deploymentConfig, setDeploymentConfig] = useState({
    serverHost: '',
    serverPort: 22,
    serverUser: 'root',
    serverPassword: '',
    useSSHKey: false,
    sshKeyPath: '',
    deploymentPath: '/opt/trading-strategy',
    usePM2: true,
    useDocker: false,
    autoRestart: true,
    monitoringEnabled: true,
    alertEmail: '',
    maxMemory: '2G',
    cpuLimit: 2,
  });

  const providers = [
    {
      id: 'vps',
      name: 'VPS (Recommended)',
      icon: Server,
      description: 'Deploy to DigitalOcean, Linode, or Vultr',
      specs: '2GB RAM, 2 vCPU, $10-20/mo',
      pros: ['Full control', 'Cost-effective', 'Easy setup'],
      recommended: true
    },
    {
      id: 'aws',
      name: 'AWS EC2',
      icon: Cloud,
      description: 'Deploy to Amazon Web Services',
      specs: 't3.small instance, $15-20/mo',
      pros: ['Highly scalable', 'Enterprise-grade', 'Auto-scaling']
    },
    {
      id: 'docker',
      name: 'Docker Container',
      icon: Package,
      description: 'Containerized deployment',
      specs: 'Any Docker host',
      pros: ['Portable', 'Isolated', 'Easy updates']
    },
    {
      id: 'local',
      name: 'Local Server',
      icon: Cpu,
      description: 'Run on your own hardware',
      specs: 'Your machine or Raspberry Pi',
      pros: ['No monthly cost', 'Full control', 'Private']
    }
  ];

  const handleDeploy = () => {
    const config = {
      ...deploymentConfig,
      provider: selectedProvider,
      strategy: strategyConfig
    };
    onDeploy(config);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Deploy Strategy to Server</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-white">
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Provider Selection */}
          <div>
            <h3 className="text-lg font-semibold mb-4">1. Choose Deployment Platform</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {providers.map((provider) => {
                const Icon = provider.icon;
                return (
                  <button
                    key={provider.id}
                    onClick={() => setSelectedProvider(provider.id as any)}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      selectedProvider === provider.id
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-start space-x-3">
                      <Icon className="w-6 h-6 text-blue-400 mt-1" />
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <h4 className="font-semibold">{provider.name}</h4>
                          {provider.recommended && (
                            <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded">
                              Recommended
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{provider.description}</p>
                        <p className="text-xs text-gray-500 mt-2">{provider.specs}</p>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {provider.pros.map((pro, i) => (
                            <span key={i} className="text-xs bg-gray-800 px-2 py-1 rounded">
                              {pro}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Server Configuration */}
          {selectedProvider === 'vps' && (
            <div>
              <h3 className="text-lg font-semibold mb-4">2. Server Configuration</h3>
              <div className="bg-gray-800 p-4 rounded-lg space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Server Host/IP</label>
                    <input
                      type="text"
                      value={deploymentConfig.serverHost}
                      onChange={(e) => setDeploymentConfig({...deploymentConfig, serverHost: e.target.value})}
                      className="w-full px-3 py-2 bg-gray-700 rounded-md"
                      placeholder="192.168.1.1 or server.domain.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">SSH Port</label>
                    <input
                      type="number"
                      value={deploymentConfig.serverPort}
                      onChange={(e) => setDeploymentConfig({...deploymentConfig, serverPort: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 bg-gray-700 rounded-md"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">SSH User</label>
                    <input
                      type="text"
                      value={deploymentConfig.serverUser}
                      onChange={(e) => setDeploymentConfig({...deploymentConfig, serverUser: e.target.value})}
                      className="w-full px-3 py-2 bg-gray-700 rounded-md"
                      placeholder="root"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      {deploymentConfig.useSSHKey ? 'SSH Key Path' : 'Password'}
                    </label>
                    <input
                      type={deploymentConfig.useSSHKey ? 'text' : 'password'}
                      value={deploymentConfig.useSSHKey ? deploymentConfig.sshKeyPath : deploymentConfig.serverPassword}
                      onChange={(e) => setDeploymentConfig({
                        ...deploymentConfig,
                        [deploymentConfig.useSSHKey ? 'sshKeyPath' : 'serverPassword']: e.target.value
                      })}
                      className="w-full px-3 py-2 bg-gray-700 rounded-md"
                      placeholder={deploymentConfig.useSSHKey ? '~/.ssh/id_rsa' : '••••••••'}
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={deploymentConfig.useSSHKey}
                    onChange={(e) => setDeploymentConfig({...deploymentConfig, useSSHKey: e.target.checked})}
                    className="rounded"
                  />
                  <label className="text-sm">Use SSH Key Authentication</label>
                </div>
              </div>
            </div>
          )}

          {/* Recommended VPS Providers */}
          {selectedProvider === 'vps' && (
            <div>
              <h3 className="text-lg font-semibold mb-4">Recommended VPS Providers</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-800 p-4 rounded-lg">
                  <h4 className="font-semibold text-blue-400">DigitalOcean</h4>
                  <p className="text-sm text-gray-400 mt-1">$12/mo - 2GB RAM, 2 vCPU</p>
                  <ul className="text-xs text-gray-500 mt-2 space-y-1">
                    <li>✓ $200 free credit</li>
                    <li>✓ Easy to use</li>
                    <li>✓ Great documentation</li>
                  </ul>
                  <a href="https://www.digitalocean.com" target="_blank" rel="noopener noreferrer"
                     className="text-blue-400 text-xs hover:underline mt-2 inline-block">
                    Sign up →
                  </a>
                </div>

                <div className="bg-gray-800 p-4 rounded-lg">
                  <h4 className="font-semibold text-green-400">Linode</h4>
                  <p className="text-sm text-gray-400 mt-1">$10/mo - 2GB RAM, 1 vCPU</p>
                  <ul className="text-xs text-gray-500 mt-2 space-y-1">
                    <li>✓ $100 free credit</li>
                    <li>✓ Reliable uptime</li>
                    <li>✓ Good support</li>
                  </ul>
                  <a href="https://www.linode.com" target="_blank" rel="noopener noreferrer"
                     className="text-green-400 text-xs hover:underline mt-2 inline-block">
                    Sign up →
                  </a>
                </div>

                <div className="bg-gray-800 p-4 rounded-lg">
                  <h4 className="font-semibold text-purple-400">Vultr</h4>
                  <p className="text-sm text-gray-400 mt-1">$12/mo - 2GB RAM, 2 vCPU</p>
                  <ul className="text-xs text-gray-500 mt-2 space-y-1">
                    <li>✓ $100 free credit</li>
                    <li>✓ Global locations</li>
                    <li>✓ Fast deployment</li>
                  </ul>
                  <a href="https://www.vultr.com" target="_blank" rel="noopener noreferrer"
                     className="text-purple-400 text-xs hover:underline mt-2 inline-block">
                    Sign up →
                  </a>
                </div>
              </div>
            </div>
          )}

          {/* Deployment Options */}
          <div>
            <h3 className="text-lg font-semibold mb-4">3. Deployment Options</h3>
            <div className="bg-gray-800 p-4 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Shield className="w-4 h-4 text-blue-400" />
                  <span className="text-sm">Use PM2 Process Manager</span>
                </div>
                <input
                  type="checkbox"
                  checked={deploymentConfig.usePM2}
                  onChange={(e) => setDeploymentConfig({...deploymentConfig, usePM2: e.target.checked})}
                  className="rounded"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Package className="w-4 h-4 text-blue-400" />
                  <span className="text-sm">Deploy with Docker</span>
                </div>
                <input
                  type="checkbox"
                  checked={deploymentConfig.useDocker}
                  onChange={(e) => setDeploymentConfig({...deploymentConfig, useDocker: e.target.checked})}
                  className="rounded"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Check className="w-4 h-4 text-green-400" />
                  <span className="text-sm">Auto-restart on failure</span>
                </div>
                <input
                  type="checkbox"
                  checked={deploymentConfig.autoRestart}
                  onChange={(e) => setDeploymentConfig({...deploymentConfig, autoRestart: e.target.checked})}
                  className="rounded"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-yellow-400" />
                  <span className="text-sm">Enable monitoring alerts</span>
                </div>
                <input
                  type="checkbox"
                  checked={deploymentConfig.monitoringEnabled}
                  onChange={(e) => setDeploymentConfig({...deploymentConfig, monitoringEnabled: e.target.checked})}
                  className="rounded"
                />
              </div>

              {deploymentConfig.monitoringEnabled && (
                <div>
                  <label className="block text-sm font-medium mb-1">Alert Email</label>
                  <input
                    type="email"
                    value={deploymentConfig.alertEmail}
                    onChange={(e) => setDeploymentConfig({...deploymentConfig, alertEmail: e.target.value})}
                    className="w-full px-3 py-2 bg-gray-700 rounded-md"
                    placeholder="alerts@example.com"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Max Memory</label>
                  <input
                    type="text"
                    value={deploymentConfig.maxMemory}
                    onChange={(e) => setDeploymentConfig({...deploymentConfig, maxMemory: e.target.value})}
                    className="w-full px-3 py-2 bg-gray-700 rounded-md"
                    placeholder="2G"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">CPU Limit</label>
                  <input
                    type="number"
                    value={deploymentConfig.cpuLimit}
                    onChange={(e) => setDeploymentConfig({...deploymentConfig, cpuLimit: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 bg-gray-700 rounded-md"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Quick Setup Guide */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
            <h4 className="font-semibold text-blue-400 mb-2">Quick Setup Guide</h4>
            <ol className="text-sm text-gray-300 space-y-1">
              <li>1. Sign up for a VPS provider (DigitalOcean recommended)</li>
              <li>2. Create a Ubuntu 22.04 droplet with 2GB RAM</li>
              <li>3. Copy the server IP address</li>
              <li>4. Enter server details above and click Deploy</li>
              <li>5. Strategy will be automatically installed and started</li>
            </ol>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-4">
            <button
              onClick={onClose}
              className="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDeploy}
              className="px-6 py-2 bg-blue-500 hover:bg-blue-600 rounded-md transition-colors flex items-center space-x-2"
            >
              <Globe className="w-4 h-4" />
              <span>Deploy Strategy</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeploymentModal;