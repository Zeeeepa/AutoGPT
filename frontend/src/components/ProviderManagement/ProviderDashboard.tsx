import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { AlertCircle, CheckCircle, Clock, Monitor, Settings, Activity } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { providerApi } from '@/services/providerApi';

interface Provider {
  service_type: string;
  enabled: boolean;
  status: 'active' | 'inactive';
  browser_instance_id?: number;
  is_busy: boolean;
  active_requests: number;
  total_requests: number;
  error_count: number;
  last_request_time?: string;
}

interface BrowserInstance {
  instance_id: number;
  is_active: boolean;
  startup_time?: string;
  last_activity?: string;
  active_sessions: number;
  provider_sessions: string[];
  fingerprint: {
    user_agent: string;
    viewport: string;
    timezone: string;
    language: string;
    platform: string;
  };
  health?: {
    healthy: boolean;
    uptime_minutes: number;
    provider_health: Record<string, boolean>;
  };
}

interface SystemMetrics {
  total_active_instances: number;
  total_active_providers: number;
  total_concurrent_requests: number;
  pending_requests: number;
  last_scaling_event?: string;
  last_scaling_time?: string;
}

export const ProviderDashboard: React.FC = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [instances, setInstances] = useState<Record<string, BrowserInstance>>({});
  const [metrics, setMetrics] = useState<SystemMetrics>({
    total_active_instances: 0,
    total_active_providers: 0,
    total_concurrent_requests: 0,
    pending_requests: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket connection for real-time updates
  const { lastMessage, connectionStatus } = useWebSocket('/api/provider-management/ws');

  // Load initial data
  useEffect(() => {
    loadProviders();
    loadInstances();
    loadSystemStatus();
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const message = JSON.parse(lastMessage.data);
        
        switch (message.type) {
          case 'initial_status':
          case 'status_update':
            if (message.data) {
              setMetrics(message.data.metrics);
              // Update providers and instances from status
              if (message.data.providers) {
                const providerList = Object.entries(message.data.providers).map(([key, value]: [string, any]) => ({
                  service_type: key,
                  enabled: true,
                  status: 'active' as const,
                  browser_instance_id: value.browser_instance_id,
                  is_busy: value.is_busy,
                  active_requests: value.active_requests,
                  total_requests: value.total_requests,
                  error_count: value.error_count,
                  last_request_time: value.last_request_time,
                }));
                setProviders(providerList);
              }
              if (message.data.instances) {
                setInstances(message.data.instances);
              }
            }
            break;
          case 'instance_update':
            // Reload instances when they change
            loadInstances();
            break;
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    }
  }, [lastMessage]);

  const loadProviders = async () => {
    try {
      const response = await providerApi.listProviders();
      setProviders(response.providers);
      setMetrics(response.metrics);
    } catch (err) {
      setError('Failed to load providers');
      console.error(err);
    }
  };

  const loadInstances = async () => {
    try {
      const response = await providerApi.listInstances();
      setInstances(response.instances);
    } catch (err) {
      setError('Failed to load instances');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadSystemStatus = async () => {
    try {
      const response = await providerApi.getSystemStatus();
      // Update metrics from system status
      setMetrics(prev => ({
        ...prev,
        total_active_instances: response.total_active_instances || 0,
        total_active_providers: response.total_active_providers || 0,
        total_concurrent_requests: response.total_concurrent_requests || 0,
        pending_requests: response.pending_requests || 0,
      }));
    } catch (err) {
      console.error('Failed to load system status:', err);
    }
  };

  const toggleProvider = async (serviceType: string, enabled: boolean) => {
    try {
      if (enabled) {
        await providerApi.enableProvider(serviceType);
      } else {
        await providerApi.disableProvider(serviceType);
      }
      await loadProviders();
    } catch (err) {
      setError(`Failed to ${enabled ? 'enable' : 'disable'} provider`);
      console.error(err);
    }
  };

  const startInstance = async (instanceId: number) => {
    try {
      await providerApi.startInstance(instanceId);
      await loadInstances();
    } catch (err) {
      setError(`Failed to start instance ${instanceId}`);
      console.error(err);
    }
  };

  const stopInstance = async (instanceId: number) => {
    try {
      await providerApi.stopInstance(instanceId);
      await loadInstances();
    } catch (err) {
      setError(`Failed to stop instance ${instanceId}`);
      console.error(err);
    }
  };

  const getStatusIcon = (status: string, isHealthy?: boolean) => {
    if (status === 'active' && isHealthy !== false) {
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    } else if (status === 'active' && isHealthy === false) {
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    } else {
      return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const formatUptime = (minutes: number) => {
    if (minutes < 60) {
      return `${Math.round(minutes)}m`;
    } else if (minutes < 1440) {
      return `${Math.round(minutes / 60)}h`;
    } else {
      return `${Math.round(minutes / 1440)}d`;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Provider Management</h1>
          <p className="text-gray-600">Manage chat service providers and browser instances</p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant={connectionStatus === 'Connected' ? 'default' : 'destructive'}>
            {connectionStatus}
          </Badge>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
            <span className="text-red-700">{error}</span>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={() => setError(null)}
            >
              ×
            </Button>
          </div>
        </div>
      )}

      {/* System Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Active Instances</p>
                <p className="text-2xl font-bold">{metrics.total_active_instances}</p>
              </div>
              <Monitor className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Active Providers</p>
                <p className="text-2xl font-bold">{metrics.total_active_providers}</p>
              </div>
              <Settings className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Concurrent Requests</p>
                <p className="text-2xl font-bold">{metrics.total_concurrent_requests}</p>
              </div>
              <Activity className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Pending Requests</p>
                <p className="text-2xl font-bold">{metrics.pending_requests}</p>
              </div>
              <Clock className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="providers" className="space-y-4">
        <TabsList>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="instances">Browser Instances</TabsTrigger>
          <TabsTrigger value="scaling">Scaling Rules</TabsTrigger>
        </TabsList>

        {/* Providers Tab */}
        <TabsContent value="providers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Service Providers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providers.map((provider) => (
                  <Card key={provider.service_type} className="border">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-2">
                          {getStatusIcon(provider.status)}
                          <h3 className="font-semibold capitalize">
                            {provider.service_type.replace('_', ' ')}
                          </h3>
                        </div>
                        <Switch
                          checked={provider.enabled}
                          onCheckedChange={(checked) => 
                            toggleProvider(provider.service_type, checked)
                          }
                        />
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Instance:</span>
                          <Badge variant="outline">
                            {provider.browser_instance_id || 'N/A'}
                          </Badge>
                        </div>
                        
                        <div className="flex justify-between">
                          <span className="text-gray-600">Status:</span>
                          <Badge variant={provider.is_busy ? 'destructive' : 'default'}>
                            {provider.is_busy ? 'Busy' : 'Available'}
                          </Badge>
                        </div>
                        
                        <div className="flex justify-between">
                          <span className="text-gray-600">Requests:</span>
                          <span>{provider.total_requests}</span>
                        </div>
                        
                        <div className="flex justify-between">
                          <span className="text-gray-600">Errors:</span>
                          <span className={provider.error_count > 0 ? 'text-red-500' : ''}>
                            {provider.error_count}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Browser Instances Tab */}
        <TabsContent value="instances" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Browser Instances</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[1, 2, 3].map((instanceId) => {
                  const instance = instances[instanceId.toString()];
                  const isActive = instance?.is_active || false;
                  const isHealthy = instance?.health?.healthy;
                  
                  return (
                    <Card key={instanceId} className="border">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center space-x-3">
                            {getStatusIcon(isActive ? 'active' : 'inactive', isHealthy)}
                            <div>
                              <h3 className="font-semibold">Browser Instance {instanceId}</h3>
                              <p className="text-sm text-gray-600">
                                {instance?.fingerprint?.platform || 'Not configured'}
                              </p>
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-2">
                            {instanceId !== 1 && (
                              <>
                                {isActive ? (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => stopInstance(instanceId)}
                                  >
                                    Stop
                                  </Button>
                                ) : (
                                  <Button
                                    variant="default"
                                    size="sm"
                                    onClick={() => startInstance(instanceId)}
                                  >
                                    Start
                                  </Button>
                                )}
                              </>
                            )}
                            {instanceId === 1 && (
                              <Badge variant="secondary">Always Active</Badge>
                            )}
                          </div>
                        </div>
                        
                        {instance && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-gray-600">Sessions</p>
                              <p className="font-medium">{instance.active_sessions}</p>
                            </div>
                            
                            <div>
                              <p className="text-gray-600">Uptime</p>
                              <p className="font-medium">
                                {instance.health?.uptime_minutes 
                                  ? formatUptime(instance.health.uptime_minutes)
                                  : 'N/A'
                                }
                              </p>
                            </div>
                            
                            <div>
                              <p className="text-gray-600">Viewport</p>
                              <p className="font-medium">{instance.fingerprint?.viewport || 'N/A'}</p>
                            </div>
                            
                            <div>
                              <p className="text-gray-600">Timezone</p>
                              <p className="font-medium">{instance.fingerprint?.timezone || 'N/A'}</p>
                            </div>
                          </div>
                        )}
                        
                        {instance?.provider_sessions && instance.provider_sessions.length > 0 && (
                          <div className="mt-4">
                            <p className="text-sm text-gray-600 mb-2">Active Providers:</p>
                            <div className="flex flex-wrap gap-2">
                              {instance.provider_sessions.map((provider) => (
                                <Badge key={provider} variant="outline" className="text-xs">
                                  {provider.replace('_', ' ')}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scaling Rules Tab */}
        <TabsContent value="scaling" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Smart Scaling Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h4 className="font-medium">Scaling Rules</h4>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                      <span>✅ Instance 1: Always running (5 providers)</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                      <span>📈 Instance 2: Start when all 5 providers busy</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                      <span>🚀 Instance 3: Start when all 10 providers busy</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                      <span>⏰ Auto-shutdown: After 30 minutes idle</span>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <h4 className="font-medium">Current Status</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Max Instances:</span>
                      <Badge>3</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Providers per Instance:</span>
                      <Badge>5</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Idle Timeout:</span>
                      <Badge>30 minutes</Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Last Scaling Event:</span>
                      <Badge variant="outline">
                        {metrics.last_scaling_event || 'None'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Scaling Progress Visualization */}
              <div className="space-y-3">
                <h4 className="font-medium">Capacity Utilization</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Active Providers</span>
                    <span>{metrics.total_active_providers} / 15</span>
                  </div>
                  <Progress 
                    value={(metrics.total_active_providers / 15) * 100} 
                    className="h-2"
                  />
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Concurrent Requests</span>
                    <span>{metrics.total_concurrent_requests}</span>
                  </div>
                  <Progress 
                    value={Math.min((metrics.total_concurrent_requests / metrics.total_active_providers) * 100, 100)} 
                    className="h-2"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};
