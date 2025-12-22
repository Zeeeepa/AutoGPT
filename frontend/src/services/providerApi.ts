/**
 * API client for provider management endpoints
 */

const API_BASE = '/api/provider-management';

interface ApiResponse<T = any> {
  success?: boolean;
  message?: string;
  data?: T;
  error?: string;
}

class ProviderApiClient {
  private async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // Provider Management
  async listProviders() {
    return this.request('/providers');
  }

  async enableProvider(serviceType: string) {
    return this.request(`/providers/${serviceType}/enable`, {
      method: 'POST',
    });
  }

  async disableProvider(serviceType: string) {
    return this.request(`/providers/${serviceType}/disable`, {
      method: 'POST',
    });
  }

  // Browser Instance Management
  async listInstances() {
    return this.request('/instances');
  }

  async startInstance(instanceId: number) {
    return this.request(`/instances/${instanceId}/start`, {
      method: 'POST',
    });
  }

  async stopInstance(instanceId: number) {
    return this.request(`/instances/${instanceId}/stop`, {
      method: 'POST',
    });
  }

  async checkInstanceHealth(instanceId: number) {
    return this.request(`/instances/${instanceId}/health`);
  }

  // Scaling Management
  async getScalingStatus() {
    return this.request('/scaling/status');
  }

  async getScalingRules() {
    return this.request('/scaling/rules');
  }

  async updateScalingRules(rules: {
    auto_scale_enabled: boolean;
    idle_timeout_minutes: number;
    max_instances: number;
    providers_per_instance: number;
    scaling_cooldown_seconds: number;
  }) {
    return this.request('/scaling/rules', {
      method: 'POST',
      body: JSON.stringify(rules),
    });
  }

  // System Status
  async getSystemStatus() {
    return this.request('/status');
  }
}

export const providerApi = new ProviderApiClient();
